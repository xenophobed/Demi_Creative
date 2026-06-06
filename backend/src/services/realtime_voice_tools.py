"""
Realtime voice tool definitions + handlers (#646).

Exposes Claude's specialist-orchestration surface to the OpenAI Realtime
model as native function-calling tools. Tool results translate into the
SAME ``launch_flow`` payload shape the text-mode SSE pipeline emits, so
the frontend's ``useLaunchFlowNavigation`` consumes both without
branching on origin.

Public surface (the broker — #645 — only touches these):

    TOOL_VERSION              # the schema version we ship today
    get_tool_definitions()    # list[dict] to register with the OpenAI WS
    handle_tool_call(name, args, ctx) -> dict   # dispatch one tool call
    warn_on_version_drift(model_version)        # advisory log on drift
    ToolContext               # broker-controlled context object

Tool result envelope (what ``handle_tool_call`` returns):

    {"type": "launch_flow", "payload": {flow_type, route, prefill}}
    {"type": "tool_result", "payload": {...}}      # recall / safety / errors
    {"type": "end_call",    "payload": {ended_reason, reason}}

The broker then converts each envelope into either a WS event the
client consumes or a session-close signal.

Why this lives in ``services/`` instead of ``agents/``: the parent
agent (``my_agent_proxy``) is Claude-only. The voice surface plugs the
SAME launch helper into a NON-Claude model (the OpenAI Realtime API),
so the integration layer is a service, not an agent. ``services/`` is
the right home for cross-model glue.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from ..agents.my_agent_proxy import (
    build_launch_flow_payload,
    list_launch_flow_types,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

# Bumped on any semantic change to the tool schemas. Per PRD §3.16.8
# launch prerequisite #6, every tool def carries this field so a stale
# client and a forward-rolled server can detect drift without crashing.
TOOL_VERSION: str = "1.0.0"


def warn_on_version_drift(model_version: Optional[str]) -> None:
    """Log a warning when the model self-reports a different tool version.

    Drift is allowed (the upstream session may have been started against
    a previous schema), but it should be visible in operator logs so a
    long-lived prod regression doesn't hide silently. Same-version calls
    are silent — the contract test pins both branches.
    """
    if not model_version or model_version == TOOL_VERSION:
        return
    logger.warning(
        "Realtime voice tool version drift: server=%s model=%s",
        TOOL_VERSION,
        model_version,
    )


# ---------------------------------------------------------------------------
# Broker-controlled context
# ---------------------------------------------------------------------------


@dataclass
class ToolContext:
    """Per-turn context the broker hands to every tool call.

    Pre-binding ``user_id``, ``child_id``, ``age_group`` here means the
    model can never inject another child's ID by accident — the handler
    only ever touches the IDs the broker authenticated this session
    against. Same isolation pattern as #288 / #590 in vector_search.
    """

    user_id: str
    child_id: str
    age_group: str
    session_id: str


# ---------------------------------------------------------------------------
# Indirection hooks for tests
# ---------------------------------------------------------------------------
#
# The handlers below call into two MCP-style coroutines for memory recall
# and safety review. We expose them as module-level attributes so contract
# tests can monkeypatch one without dragging the full MCP server stack
# (and its ChromaDB/pgvector dependencies) into the test process. Lazy
# defaults defer the heavy imports until the first call.


_search_my_stories_handler: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None
_check_content_safety_handler: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None


async def _get_search_handler() -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    global _search_my_stories_handler
    if _search_my_stories_handler is None:
        from ..mcp_servers.vector_search_server import (
            search_my_stories as _raw_search,
        )
        _search_my_stories_handler = getattr(_raw_search, "handler", _raw_search)
    return _search_my_stories_handler


async def _get_safety_handler() -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    global _check_content_safety_handler
    if _check_content_safety_handler is None:
        from ..mcp_servers import check_content_safety
        _check_content_safety_handler = getattr(check_content_safety, "handler", check_content_safety)
    return _check_content_safety_handler


# ---------------------------------------------------------------------------
# Tool definitions — JSON-schema registered with the OpenAI Realtime WS
# ---------------------------------------------------------------------------


# Standard prefill shape exposed to the model. Keep it open-ended (no
# required keys) so the model can call a launch tool with no arguments
# — that's a valid "drop the child on the landing page" hand-off.
_PREFILL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "description": (
        "Optional prefill keys forwarded as URL query params on the "
        "landing page. Allowed keys: story_id, session_id, episode_id, "
        "child_id, age_group, session, theme, category."
    ),
    "additionalProperties": True,
}


def _launch_image_story_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "launch_image_story",
        "description": (
            "Hand off to the Image-to-Story flow. Use when the child says "
            "they want to turn a drawing or picture into a story. The "
            "child profile (child_id, age_group) is pre-bound by the "
            "server — you only choose optional prefill values like a theme."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prefill": _PREFILL_SCHEMA,
            },
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def _launch_interactive_story_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "launch_interactive_story",
        "description": (
            "Hand off to the branching Interactive Story flow. Use when "
            "the child asks for choices, an adventure, or a "
            "choose-your-own-adventure story."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prefill": _PREFILL_SCHEMA,
            },
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def _launch_kids_daily_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "launch_kids_daily",
        "description": (
            "Hand off to Kids Daily (kid-friendly news). Use when the "
            "child asks about today's news, headlines, or what's "
            "happening in the world."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prefill": _PREFILL_SCHEMA,
            },
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def _recall_memory_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "recall_memory",
        "description": (
            "Search this child's previous stories by topic, character, "
            "or keyword. Pure recall — does NOT launch a new generation. "
            "Use when the child asks 'find my Lightning Dog story' or "
            "'what was that one about the moon'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text query to search by.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max number of stories to return (default 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def _safety_review_reply_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "safety_review_reply",
        "description": (
            "Run a child-safety review on a candidate buddy reply. The "
            "broker enforces a global safety gate anyway, but exposing "
            "this tool lets the model self-check before committing to a "
            "delicate reply (e.g. when the child brings up grief or fear)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The candidate reply text to review.",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def _end_call_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "end_call",
        "description": (
            "Cleanly end the voice session. Use when the child says "
            "goodbye, gets quiet for a long time, or asks to stop. The "
            "broker closes the WS with ended_reason='voice_tool_end_call'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "Short, friendly reason — surfaces in telemetry "
                        "only, never shown to the child."
                    ),
                },
            },
            "additionalProperties": False,
        },
        "version": TOOL_VERSION,
    }


def get_tool_definitions() -> list[Dict[str, Any]]:
    """Return JSON-schema tool definitions for the OpenAI Realtime session.

    The broker (#645) calls this once when establishing the upstream WS
    and registers each entry as a function tool on the session. Order
    is stable so contract tests can pin the surface byte-for-byte.
    """
    return [
        _launch_image_story_tool(),
        _launch_interactive_story_tool(),
        _launch_kids_daily_tool(),
        _recall_memory_tool(),
        _safety_review_reply_tool(),
        _end_call_tool(),
    ]


# ---------------------------------------------------------------------------
# Launch-flow helper (voice path)
# ---------------------------------------------------------------------------


def _build_launch_flow_for_voice(
    flow_type: str,
    prefill: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Thin alias that proxies to ``build_launch_flow_payload``.

    Exposed as a separate symbol so the parity contract has a clean
    voice-side handle to assert against. Both helpers are the *same*
    function under the hood — this is the single source of truth the
    parity contract pins (#646).
    """
    return build_launch_flow_payload(flow_type, prefill)


def _merge_prefill(
    raw: Optional[Dict[str, Any]],
    ctx: ToolContext,
) -> Dict[str, Any]:
    """Stitch the broker-bound child profile onto the model's prefill.

    The model picks the optional fields (theme, category, episode_id...);
    the broker injects the pre-authenticated identifiers (child_id +
    age_group) so the model cannot pass another child's ID even by
    mistake. Same defense-in-depth pattern as the SDK tool in #496.
    """
    merged: Dict[str, Any] = {
        "child_id": ctx.child_id,
        "age_group": ctx.age_group,
    }
    if isinstance(raw, dict):
        for key, value in raw.items():
            if value is None:
                continue
            merged[key] = value
    # Broker-bound IDs always win on conflict — the model can't reroute.
    merged["child_id"] = ctx.child_id
    merged["age_group"] = ctx.age_group
    return merged


# ---------------------------------------------------------------------------
# Tool-call dispatch
# ---------------------------------------------------------------------------


async def _handle_launch(
    flow_type: str,
    args: Dict[str, Any],
    ctx: ToolContext,
) -> Dict[str, Any]:
    prefill = _merge_prefill(args.get("prefill"), ctx)
    payload = _build_launch_flow_for_voice(flow_type, prefill)
    if payload is None:
        # Defensive — flow_type must be in the registry because the
        # tool name is fixed by us, but log loudly if it ever isn't.
        logger.warning("launch tool for unknown flow_type=%r", flow_type)
        return {
            "type": "tool_result",
            "payload": {"error": f"unknown_flow_type:{flow_type}"},
        }
    return {"type": "launch_flow", "payload": payload}


async def _handle_recall_memory(
    args: Dict[str, Any],
    ctx: ToolContext,
) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    if not query:
        return {
            "type": "tool_result",
            "payload": {
                "error": "missing_query",
                "stories": [],
                "total_found": 0,
            },
        }

    handler = await _get_search_handler()
    try:
        raw = await handler({
            "query": query,
            # child_id is broker-bound — model never picks the scope.
            "child_id": ctx.child_id,
            "top_k": int(args.get("top_k") or 5),
        })
    except Exception as exc:  # noqa: BLE001 — degrade, don't kill the turn
        logger.warning(
            "[session=%s] recall_memory handler failed: %s",
            ctx.session_id, exc,
        )
        return {
            "type": "tool_result",
            "payload": {"error": f"recall_failed:{exc}", "stories": []},
        }

    # The MCP envelope is {"content": [{"type":"text","text": json}]}.
    # Unwrap to a plain dict so the model can directly quote results.
    try:
        text = raw["content"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning(
            "[session=%s] recall_memory returned malformed envelope",
            ctx.session_id,
        )
        return {
            "type": "tool_result",
            "payload": {"error": "malformed_recall", "stories": []},
        }
    return {"type": "tool_result", "payload": parsed}


async def _handle_safety_review(
    args: Dict[str, Any],
    ctx: ToolContext,
) -> Dict[str, Any]:
    text = (args.get("text") or "").strip()
    if not text:
        return {
            "type": "tool_result",
            "payload": {"error": "missing_text", "passed": False, "safety_score": 0.0},
        }

    handler = await _get_safety_handler()
    try:
        # The MCP server expects target_age — map age_group → midpoint.
        target_age = {"3-5": 4, "6-8": 7, "9-12": 10}.get(ctx.age_group, 7)
        raw = await handler({
            "content_text": text,
            "content_type": "story",
            "target_age": target_age,
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[session=%s] safety_review handler failed: %s",
            ctx.session_id, exc,
        )
        return {
            "type": "tool_result",
            "payload": {"error": f"safety_failed:{exc}", "passed": False},
        }

    try:
        parsed = json.loads(raw["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError):
        return {
            "type": "tool_result",
            "payload": {"error": "malformed_safety_envelope", "passed": False},
        }
    # Tolerate either {passed} or just {safety_score} — the MCP returns
    # both today but a contract-level normalisation keeps the model's
    # downstream logic stable across schema tweaks.
    score = float(parsed.get("safety_score") or 0.0)
    passed = bool(parsed.get("passed", score >= 0.85))
    return {
        "type": "tool_result",
        "payload": {"safety_score": score, "passed": passed},
    }


async def _handle_end_call(
    args: Dict[str, Any],
    ctx: ToolContext,
) -> Dict[str, Any]:
    # The broker maps this envelope to a clean WS close. The
    # ``ended_reason`` string is part of the contract — PRD §3.16.7
    # quota math distinguishes a model-initiated hangup from a user
    # disconnect so we can sample them differently in telemetry.
    reason = (args.get("reason") or "").strip() or "buddy_ended"
    return {
        "type": "end_call",
        "payload": {
            "ended_reason": "voice_tool_end_call",
            "reason": reason,
        },
    }


# Static dispatch table — clearer than a long if/elif chain and gives
# the contract test a stable target for "all six tools wired up".
_DISPATCH: Dict[str, Callable[[Dict[str, Any], ToolContext], Awaitable[Dict[str, Any]]]] = {
    "launch_image_story": lambda a, c: _handle_launch("image_story", a, c),
    "launch_interactive_story": lambda a, c: _handle_launch("interactive_story", a, c),
    "launch_kids_daily": lambda a, c: _handle_launch("kids_daily", a, c),
    "recall_memory": _handle_recall_memory,
    "safety_review_reply": _handle_safety_review,
    "end_call": _handle_end_call,
}


async def handle_tool_call(
    name: str,
    args: Dict[str, Any],
    context: ToolContext,
) -> Dict[str, Any]:
    """Dispatch one OpenAI Realtime tool call to its handler.

    Always returns a dict envelope — never raises — because a raised
    exception during a tool call would orphan the model's turn waiting
    for a result, and the WS broker has no way to send a synthetic
    result later. Unknown tool names degrade to a clean error envelope
    the model can recover from.
    """
    handler = _DISPATCH.get(name)
    if handler is None:
        logger.warning(
            "[session=%s] unknown tool call name=%r",
            context.session_id, name,
        )
        return {
            "type": "tool_result",
            "payload": {"error": f"unknown_tool:{name}"},
        }
    try:
        return await handler(args or {}, context)
    except Exception as exc:  # noqa: BLE001
        # Last-ditch envelope — a bug in a handler should not orphan
        # the turn. Logged loud so the operator can diagnose.
        logger.exception(
            "[session=%s] tool %s crashed: %s",
            context.session_id, name, exc,
        )
        return {
            "type": "tool_result",
            "payload": {"error": f"handler_crashed:{exc}"},
        }


# Re-export for convenience — the broker often wants the full set of
# registered flow names when wiring its routing table.
__all__ = [
    "TOOL_VERSION",
    "ToolContext",
    "get_tool_definitions",
    "handle_tool_call",
    "list_launch_flow_types",
    "warn_on_version_drift",
]
