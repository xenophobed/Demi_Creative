"""Shared programmatic post-generation safety enforcement (#421).

This module provides a single, code-controlled gate that EVERY user-facing
generation flow must pass through before returning content to a child.

Why this exists
---------------
The Claude Agent SDK prompts already *instruct* the model to call
``mcp__safety-check__check_content_safety`` after generating story or news
text. That instruction is advisory: a model that ignores the prompt (or a
code path that bypasses the SDK and calls the Anthropic API directly, like
``_direct_generate*`` in the three current agents) can return unchecked text.

CLAUDE.md treats the safety check as non-negotiable. To make it
non-negotiable in *code* — not just in *prompt* — every direct-generation
path now calls :func:`enforce_post_gen_safety`, which:

1. Runs ``check_content_safety`` on the assembled text in-process.
2. Logs the score.
3. If the score is below threshold, runs ``suggest_content_improvements``
   and rechecks (one retry, per acceptance criteria).
4. Raises :class:`RuntimeError` if both passes still fail. Callers either
   degrade to deterministic mock content or surface a structured error.

Thresholds (per CLAUDE.md):
- Default: ``0.85``
- Ages 3-5: tightened to ``0.90`` (children in this group are most
  sensitive to even mild conflict / scary imagery).

This trades a small amount of latency (one extra API call on failure) for
a guarantee that no story / episode / dialogue is ever shipped without a
programmatic safety pass.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..mcp_servers.safety_check_server import (
    check_content_safety,
    suggest_content_improvements,
)

logger = logging.getLogger(__name__)


# Map age-group strings used across the codebase to a representative
# integer age that the safety MCP tool expects.
_AGE_GROUP_TO_INT: Dict[str, int] = {
    "3-5": 4,
    "6-8": 7,
    "9-12": 10,
}


def safety_threshold(age_group: str) -> float:
    """Return the minimum acceptable safety score for an age group.

    The default threshold (``0.85``) comes from CLAUDE.md. We tighten to
    ``0.90`` for ages 3-5 because that band is most sensitive to even
    borderline content (mild conflict, scary imagery, complex emotions).
    """

    return 0.90 if age_group == "3-5" else 0.85


def _target_age(age_group: str) -> int:
    return _AGE_GROUP_TO_INT.get(age_group, 7)


def _unwrap_tool_payload(result: Any) -> Dict[str, Any]:
    """Unwrap an SDK MCP tool envelope into the inner JSON dict.

    The SDK tool always returns ``{"content": [{"type": "text", "text": "<json>"}]}``.
    Some upstream callers store the inner JSON directly; both shapes
    are tolerated.
    """

    if isinstance(result, dict) and "content" in result:
        try:
            text = result["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return {}
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def _call_check(content_text: str, content_type: str, target_age: int) -> Dict[str, Any]:
    """Invoke the safety MCP tool's handler and return the parsed payload.

    ``check_content_safety`` is decorated with the SDK's ``@tool``, which
    wraps it in an ``SdkMcpTool`` object that is NOT itself callable — the
    raw async function lives at ``.handler``. (Same pattern used in
    ``api/routes/agents.py::_run_safety_check``.)
    """

    raw = await check_content_safety.handler({
        "content_text": content_text,
        "content_type": content_type,
        "target_age": target_age,
    })
    return _unwrap_tool_payload(raw)


async def _call_suggest(
    *,
    original_content: str,
    safety_check_result: Dict[str, Any],
    target_age: int,
) -> Dict[str, Any]:
    raw = await suggest_content_improvements.handler({
        "original_content": original_content,
        "safety_check_result": safety_check_result,
        "target_age": target_age,
    })
    return _unwrap_tool_payload(raw)


async def enforce_post_gen_safety(
    content_text: str,
    *,
    content_type: str,
    age_group: str,
    allow_retry: bool = True,
) -> Tuple[str, float, bool]:
    """Run a programmatic safety check and a single repair attempt.

    Args:
        content_text: The generated story / dialogue / news text.
        content_type: One of ``image_story``, ``interactive_story``,
            ``kids_daily``, ``kids_daily_dialogue`` — used for telemetry
            and to give the model context inside the safety prompt.
        age_group: ``"3-5"`` | ``"6-8"`` | ``"9-12"``.
        allow_retry: If ``False``, skip the ``suggest_content_improvements``
            repair step and raise on the first failure. Useful for tests.

    Returns:
        A tuple ``(text, safety_score, was_retried)`` where:

        - ``text`` is the original text if it passed, otherwise the
          improved text that passed on retry.
        - ``safety_score`` is the final score (always ``>= threshold``).
        - ``was_retried`` is ``True`` if a repair pass happened.

    Raises:
        RuntimeError: If both the initial check and the repaired retry
            score below threshold (or if retry is disabled and the
            first check fails).
    """

    if not content_text or not content_text.strip():
        # Empty text is never safe to ship; treat as below-threshold.
        raise RuntimeError("safety_check_received_empty_content")

    threshold = safety_threshold(age_group)
    target_age = _target_age(age_group)

    first = await _call_check(content_text, content_type, target_age)
    first_score = _coerce_score(first.get("safety_score"))
    logger.info(
        "safety_check content_type=%s age_group=%s score=%.3f threshold=%.2f",
        content_type,
        age_group,
        first_score,
        threshold,
    )

    if first_score >= threshold:
        return content_text, first_score, False

    if not allow_retry:
        raise RuntimeError(
            f"safety_below_threshold: {first_score:.3f} < {threshold:.2f}"
        )

    suggestion = await _call_suggest(
        original_content=content_text,
        safety_check_result=first,
        target_age=target_age,
    )
    improved_text = (
        suggestion.get("improved_content")
        or suggestion.get("improved_text")
        or content_text
    )
    if not isinstance(improved_text, str) or not improved_text.strip():
        improved_text = content_text

    second = await _call_check(improved_text, content_type, target_age)
    second_score = _coerce_score(second.get("safety_score"))
    logger.info(
        "safety_recheck content_type=%s age_group=%s score=%.3f threshold=%.2f",
        content_type,
        age_group,
        second_score,
        threshold,
    )

    if second_score >= threshold:
        return improved_text, second_score, True

    raise RuntimeError(
        "safety_below_threshold_after_retry: "
        f"first={first_score:.3f} second={second_score:.3f} threshold={threshold:.2f}"
    )


def _coerce_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


__all__ = [
    "enforce_post_gen_safety",
    "safety_threshold",
]
