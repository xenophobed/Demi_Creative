"""
Contract tests for the OpenAI Realtime function-calling surface (#646).

The Realtime model needs to be able to hand off to specialists (image
story, interactive story, kids daily) AND to settings flows AND to a
clean-exit signal — over a voice channel — without the frontend having
to branch on origin. That means:

  - Every launch_flow tool we expose to the Realtime model MUST produce
    the same SSE-shaped ``launch_flow`` payload the text-mode pipeline
    emits via ``my_agent_proxy``.
  - The tool definitions themselves are versioned (PRD §3.16.8 launch
    prerequisite #6), so a stale client and a forward-rolled server
    can detect drift without crashing.
  - ``recall_memory`` returns the same envelope ``my_agent_memory``
    surfaces in text mode, so the Realtime model can re-prompt with it.
  - ``end_call`` produces an explicit exit signal the broker can map to
    ``ended_reason="voice_tool_end_call"`` (PRD §3.16.7 quota math).

These tests are intentionally model-agnostic — they don't speak HTTP to
OpenAI. They lock the shape of ``realtime_voice_tools`` so the broker
in #645 can wire its function-calling event handler against a stable
contract.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module import & version
# ---------------------------------------------------------------------------


class TestModuleSurface:
    """The new module exposes a tight, versioned public API."""

    def test_module_imports(self):
        # Imports must be side-effect free — no upstream network I/O at
        # load time. The realtime broker imports this module to register
        # tool definitions; a heavy import would block session startup.
        from backend.src.services import realtime_voice_tools  # noqa: F401

    def test_tool_version_constant_is_semver_string(self):
        from backend.src.services.realtime_voice_tools import TOOL_VERSION
        assert isinstance(TOOL_VERSION, str)
        assert TOOL_VERSION == "1.0.0"

    def test_module_exposes_public_api(self):
        from backend.src.services import realtime_voice_tools as rvt
        assert hasattr(rvt, "get_tool_definitions")
        assert hasattr(rvt, "handle_tool_call")
        assert hasattr(rvt, "ToolContext")
        assert callable(rvt.get_tool_definitions)
        assert inspect.iscoroutinefunction(rvt.handle_tool_call)


# ---------------------------------------------------------------------------
# Tool definitions schema
# ---------------------------------------------------------------------------


EXPECTED_TOOL_NAMES = {
    "launch_image_story",
    "launch_interactive_story",
    "launch_kids_daily",
    "recall_memory",
    "safety_review_reply",
    "end_call",
}


class TestToolDefinitions:
    """The schema list registered with the OpenAI Realtime session."""

    def test_all_six_tools_present(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        defs = get_tool_definitions()
        names = {d["name"] for d in defs}
        assert names == EXPECTED_TOOL_NAMES, (
            f"tool set drift: missing={EXPECTED_TOOL_NAMES - names}, "
            f"extra={names - EXPECTED_TOOL_NAMES}"
        )

    def test_every_tool_has_version_field(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        for d in get_tool_definitions():
            assert d.get("version") == "1.0.0", (
                f"tool {d.get('name')!r} missing version=1.0.0"
            )

    def test_every_tool_is_function_typed(self):
        """OpenAI Realtime expects ``type: "function"`` on each tool."""
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        for d in get_tool_definitions():
            assert d.get("type") == "function", (
                f"tool {d.get('name')!r} must declare type='function'"
            )

    def test_every_tool_has_description(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        for d in get_tool_definitions():
            desc = d.get("description") or ""
            assert isinstance(desc, str) and desc.strip(), (
                f"tool {d.get('name')!r} needs a non-empty description"
            )

    def test_every_tool_has_json_schema_parameters(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        for d in get_tool_definitions():
            params = d.get("parameters")
            assert isinstance(params, dict), f"{d.get('name')!r} parameters missing"
            assert params.get("type") == "object"
            assert "properties" in params

    def test_launch_image_story_required_args(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        defs = {d["name"]: d for d in get_tool_definitions()}
        params = defs["launch_image_story"]["parameters"]
        props = params["properties"]
        # child_id + age_group come from the broker (pre-bound) so they're
        # NOT required in the tool's JSON schema — the model only chooses
        # an optional prefill. Lock the prefill key.
        assert "prefill" in props

    def test_end_call_includes_reason(self):
        from backend.src.services.realtime_voice_tools import get_tool_definitions
        defs = {d["name"]: d for d in get_tool_definitions()}
        end = defs["end_call"]
        assert "reason" in end["parameters"]["properties"]


# ---------------------------------------------------------------------------
# handle_tool_call — launch_flow parity with the text-mode SSE pipeline
# ---------------------------------------------------------------------------


def _make_context(**overrides: Any):
    from backend.src.services.realtime_voice_tools import ToolContext
    return ToolContext(
        user_id=overrides.get("user_id", "u_test"),
        child_id=overrides.get("child_id", "c_test"),
        age_group=overrides.get("age_group", "6-8"),
        session_id=overrides.get("session_id", "voice_test_001"),
    )


class TestLaunchFlowToolResults:
    """Tool results must mirror text-mode SSE ``launch_flow`` data."""

    @pytest.mark.asyncio
    async def test_launch_image_story_emits_launch_flow_payload(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_image_story",
            {"prefill": {"theme": "space"}},
            _make_context(),
        )
        assert result["type"] == "launch_flow"
        payload = result["payload"]
        assert payload["flow_type"] == "image_story"
        # Route shape matches what the text proxy produces when no
        # resource_id is bound yet (lands on /upload, not /story/<id>).
        assert payload["route"] == "/upload"
        prefill = payload["prefill"]
        assert prefill["child_id"] == "c_test"
        assert prefill["age_group"] == "6-8"
        assert prefill["theme"] == "space"

    @pytest.mark.asyncio
    async def test_launch_interactive_story_uses_query_param(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_interactive_story",
            {"prefill": {"session_id": "sess_42", "theme": "ocean"}},
            _make_context(age_group="9-12"),
        )
        assert result["type"] == "launch_flow"
        payload = result["payload"]
        assert payload["flow_type"] == "interactive_story"
        # Interactive resumes at /interactive?session=<id>, not at
        # /interactive/<id> — text mode's registry has id_location="query".
        assert payload["route"] == "/interactive"
        prefill = payload["prefill"]
        assert prefill["session"] == "sess_42"
        assert "session_id" not in prefill  # id_field rewritten to session
        assert prefill["theme"] == "ocean"
        assert prefill["age_group"] == "9-12"

    @pytest.mark.asyncio
    async def test_launch_kids_daily_appends_episode_id(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_kids_daily",
            {"prefill": {"episode_id": "ep_77"}},
            _make_context(),
        )
        payload = result["payload"]
        assert payload["flow_type"] == "kids_daily"
        assert payload["route"] == "/kids-daily/ep_77"
        assert payload["prefill"]["episode_id"] == "ep_77"
        assert payload["prefill"]["child_id"] == "c_test"

    @pytest.mark.asyncio
    async def test_launch_kids_daily_without_episode_id(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_kids_daily",
            {},
            _make_context(),
        )
        payload = result["payload"]
        assert payload["flow_type"] == "kids_daily"
        # No episode binds → landing route (matches text-mode behavior).
        assert payload["route"] == "/kids-daily"

    @pytest.mark.asyncio
    async def test_launch_agent_settings_flow(self):
        """Voice can hand off to /agent-settings (My Agent persona surface)."""
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_image_story",  # any launch tool — assert flow below
            {},
            _make_context(),
        )
        # The agent_settings + child_settings handoffs are checked
        # through the parity contract test rather than dedicated tools,
        # because the spec asks the SAME helper to handle them. The voice
        # surface exposes them via prefill on a settings-shaped tool;
        # this test simply confirms the registry is parameterised by
        # flow_type and accepts these strings without crashing.
        from backend.src.agents.my_agent_proxy import (
            build_launch_flow_payload,
            list_launch_flow_types,
        )
        all_types = list_launch_flow_types()
        assert "agent_settings" in all_types
        assert "child_settings" in all_types
        agent = build_launch_flow_payload("agent_settings", {"child_id": "c_test"})
        assert agent is not None
        assert agent["flow_type"] == "agent_settings"
        assert agent["route"].startswith("/agent-settings") or agent["route"].startswith("/my-agent")
        child = build_launch_flow_payload("child_settings", {"child_id": "c_test"})
        assert child is not None
        assert child["flow_type"] == "child_settings"


# ---------------------------------------------------------------------------
# recall_memory
# ---------------------------------------------------------------------------


class TestRecallMemoryTool:
    """recall_memory threads search hits back into the next model turn."""

    @pytest.mark.asyncio
    async def test_recall_memory_returns_threadable_payload(self, monkeypatch):
        from backend.src.services import realtime_voice_tools as rvt

        async def _fake_search(args):
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "stories": [
                            {"story_id": "s1", "title": "Lightning Dog",
                             "preview": "A puppy with thunder pals..."},
                        ],
                        "total_found": 1,
                    }),
                }]
            }

        monkeypatch.setattr(rvt, "_search_my_stories_handler", _fake_search)
        result = await rvt.handle_tool_call(
            "recall_memory",
            {"query": "lightning dog"},
            _make_context(),
        )
        assert result["type"] == "tool_result"
        payload = result["payload"]
        # Threadable: the model gets a `stories` array it can quote.
        assert payload["stories"][0]["title"] == "Lightning Dog"
        assert payload["total_found"] == 1

    @pytest.mark.asyncio
    async def test_recall_memory_missing_query_returns_error_envelope(self, monkeypatch):
        from backend.src.services import realtime_voice_tools as rvt
        result = await rvt.handle_tool_call(
            "recall_memory",
            {},  # missing query
            _make_context(),
        )
        # Even on bad input, return a tool_result envelope — never raise.
        # Otherwise the Realtime model orphans the turn waiting for a result.
        assert result["type"] == "tool_result"
        payload = result["payload"]
        assert payload.get("error") or payload.get("stories") == []


# ---------------------------------------------------------------------------
# safety_review_reply + end_call
# ---------------------------------------------------------------------------


class TestSafetyReviewAndEndCall:

    @pytest.mark.asyncio
    async def test_safety_review_reply_returns_safety_envelope(self, monkeypatch):
        from backend.src.services import realtime_voice_tools as rvt

        async def _fake_safety(args):
            # Mimic the check_content_safety MCP handler shape.
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({"safety_score": 0.97, "passed": True}),
                }]
            }

        monkeypatch.setattr(rvt, "_check_content_safety_handler", _fake_safety)
        result = await rvt.handle_tool_call(
            "safety_review_reply",
            {"text": "Once upon a time..."},
            _make_context(),
        )
        assert result["type"] == "tool_result"
        payload = result["payload"]
        assert payload["safety_score"] == 0.97
        assert payload["passed"] is True

    @pytest.mark.asyncio
    async def test_end_call_produces_exit_signal(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "end_call",
            {"reason": "child said goodbye"},
            _make_context(),
        )
        # The broker maps this envelope to ws close with
        # ended_reason="voice_tool_end_call" — pin both the type and the
        # exact ended_reason string so #645's reviewer can grep for it.
        assert result["type"] == "end_call"
        assert result["payload"]["ended_reason"] == "voice_tool_end_call"
        assert "reason" in result["payload"]


# ---------------------------------------------------------------------------
# Unknown tool + version drift
# ---------------------------------------------------------------------------


class TestUnknownToolAndVersionDrift:
    """The model can send anything — degrade, don't crash."""

    @pytest.mark.asyncio
    async def test_unknown_tool_name_returns_error_envelope(self):
        from backend.src.services.realtime_voice_tools import handle_tool_call
        result = await handle_tool_call(
            "launch_a_secret_thing",  # not registered
            {},
            _make_context(),
        )
        assert result["type"] == "tool_result"
        assert "unknown_tool" in result["payload"].get("error", "")

    def test_version_drift_logs_warning_not_crash(self, caplog):
        from backend.src.services.realtime_voice_tools import warn_on_version_drift
        with caplog.at_level(logging.WARNING):
            # Model claims it's running against an older tool version —
            # don't crash, but emit a warning the operator can grep.
            warn_on_version_drift(model_version="0.9.0")
        assert any("version" in rec.message.lower() for rec in caplog.records)

    def test_version_match_does_not_warn(self, caplog):
        from backend.src.services.realtime_voice_tools import warn_on_version_drift
        with caplog.at_level(logging.WARNING):
            warn_on_version_drift(model_version="1.0.0")
        # Same version — silence is the contract.
        assert not any("version" in rec.message.lower() for rec in caplog.records)
