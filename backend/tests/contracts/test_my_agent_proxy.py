"""
My Agent Proxy Contract Tests (#495)

Locks down the runtime contract for the multi-agent proxy orchestrator that
powers POST /api/v1/me/agent/chat/stream:

  - The `my-agent-tools` MCP server registers exactly the six tools that
    the parent agent and subagents are allow-listed to call.
  - Each skill-gated tool returns a `{"error": "skill_disabled", ...}`
    envelope (NOT a raise) when the corresponding `enabled_skills` flag
    is missing — so the SSE stream stays alive and the orchestrator can
    explain the gap to the child.
  - `check_child_content_safety` intentionally bypasses skill gating —
    safety is non-negotiable per PRD §3.4 and this test snapshots that
    policy so a future "gate everything" refactor cannot silently
    disable child-safety review.
  - `create_image_story` returns `{"error": "image_required"}` when no
    image is attached, even if the image_story skill is enabled.
  - `_build_subagents` produces four AgentDefinitions whose allow-listed
    tool names stay in lock-step with `_make_tools` — preventing rename
    drift between the registration site and the subagent contract.
  - `stream_my_agent_chat` emits a structured SSE `error` event with
    code `SDK_UNAVAILABLE` when claude_agent_sdk cannot be imported
    (so the route can never crash on cold/test envs).
  - `stream_my_agent_chat` emits `AGENT_NOT_FOUND` when the user has
    not finished My Agent onboarding yet.

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #495
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.src.agents import my_agent_proxy
from backend.src.services.database import db_manager
from backend.src.services.database.agent_repository import AgentData
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_agent(enabled_skills: list[str] | None = None) -> AgentData:
    """Build a minimal AgentData stand-in for skill-gating tests."""
    return AgentData(
        agent_id="agt_test",
        user_id="u_test",
        child_id="c_test",
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦊",
        agent_title="Story Wizard",
        tone="warm_curious",
        interaction_style="guided_playful",
        enabled_skills=enabled_skills if enabled_skills is not None else [],
        favorite_topics=[],
        learning_goals=[],
        custom_instructions="",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


def _build_tools_for(agent: AgentData, *, image_path: str | None = None) -> dict[str, Any]:
    """
    Call `_make_tools` with create_sdk_mcp_server patched to passthrough,
    so the returned dict exposes the raw SdkMcpTool objects via the
    ``tools`` key for inspection.
    """
    def _passthrough(**kwargs):
        return kwargs

    with patch.object(my_agent_proxy, "create_sdk_mcp_server", _passthrough):
        return my_agent_proxy._make_tools(
            user_id="u_test",
            child_id="c_test",
            image_path=image_path,
            agent=agent,
        )


def _tool_by_name(tools_server: dict[str, Any], name: str):
    for t in tools_server["tools"]:
        if getattr(t, "name", None) == name:
            return t
    raise AssertionError(f"Tool not registered: {name}")


async def _invoke(tool_obj, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Invoke an SdkMcpTool. The decorator wraps the async function in a
    registration object whose actual callable is at ``.handler`` — calling
    the object directly raises ``TypeError: 'SdkMcpTool' object is not
    callable``. The same gotcha is documented in backend/src/api/routes/agents.py.
    """
    handler = getattr(tool_obj, "handler", tool_obj)
    return await handler(payload)


def _unwrap_envelope(result: dict[str, Any]) -> dict[str, Any]:
    """Tools return MCP-shaped {"content": [{"type":"text","text": JSON}]}."""
    text = result["content"][0]["text"]
    return json.loads(text)


def _parse_sse_events(blob: str) -> list[dict[str, Any]]:
    """Parse the raw SSE byte stream into a list of {event, data} dicts."""
    events: list[dict[str, Any]] = []
    for chunk in blob.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        event_name: str | None = None
        data_lines: list[str] = []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if event_name is None:
            continue
        try:
            data = json.loads("\n".join(data_lines)) if data_lines else {}
        except json.JSONDecodeError:
            data = {"_raw": "\n".join(data_lines)}
        events.append({"event": event_name, "data": data})
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_TEST_USER_ID = "proxy_test_user"
_TEST_CHILD_ID = "proxy_test_child"


@pytest_asyncio.fixture
async def test_db():
    """
    In-memory DB shared with the global db_manager so agent_chat_repo /
    agent_repo (which import db_manager at module level) see our test
    schema.
    """
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    # Seed user row (agent_chat_sessions has FK on users.user_id).
    from datetime import datetime as _dt
    now = _dt.now().isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (
            user_id, username, email, password_hash, display_name,
            is_active, is_verified, role,
            membership_tier, referral_code, referred_by,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _TEST_USER_ID,
            "proxy_test_user",
            "proxy@test.com",
            "h",
            "Proxy",
            1,
            1,
            "child",
            "free",
            "TESTPROXY",
            None,
            now,
            now,
        ),
    )
    await db_manager.commit()

    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


# ---------------------------------------------------------------------------
# MCP server shape
# ---------------------------------------------------------------------------


EXPECTED_TOOL_NAMES = {
    "create_image_story",
    "start_interactive_story",
    "continue_interactive_story",
    "create_kids_daily_episode",
    "check_child_content_safety",
    "generate_my_agent_audio",
}


class TestMcpServerShape:
    """The my-agent-tools server must expose a stable name/version/tool-set."""

    def test_server_name_and_version(self):
        """Server identity is part of the contract; subagents reference it."""
        server = _build_tools_for(_fake_agent())
        assert server["name"] == "my-agent-tools"
        assert server["version"] == "1.0.0"

    def test_exposes_exactly_six_tools(self):
        """Adding or removing tools must update both this test and the subagent allow-lists."""
        server = _build_tools_for(_fake_agent())
        names = {getattr(t, "name", None) for t in server["tools"]}
        assert names == EXPECTED_TOOL_NAMES, f"Unexpected tool set: {names}"


# ---------------------------------------------------------------------------
# Skill gating
# ---------------------------------------------------------------------------


class TestSkillGating:
    """Each gated tool must return a skill_disabled envelope, not raise."""

    @pytest.mark.asyncio
    async def test_create_image_story_gated_on_image_story(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]), image_path="/tmp/x.png")
        result = await _invoke(
            _tool_by_name(server, "create_image_story"),
            {"child_age": 7, "interests": [], "enable_audio": False, "voice": "", "art_theme": ""},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "skill_disabled", "skill": "image_story"}

    @pytest.mark.asyncio
    async def test_start_interactive_story_gated_on_interactive_story(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]))
        result = await _invoke(
            _tool_by_name(server, "start_interactive_story"),
            {"age_group": "6-8", "interests": [], "theme": "", "enable_audio": False},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "skill_disabled", "skill": "interactive_story"}

    @pytest.mark.asyncio
    async def test_continue_interactive_story_gated_on_interactive_story(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]))
        result = await _invoke(
            _tool_by_name(server, "continue_interactive_story"),
            {"session_id": "s1", "choice_id": "c1", "session_data": {}, "enable_audio": False},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "skill_disabled", "skill": "interactive_story"}

    @pytest.mark.asyncio
    async def test_create_kids_daily_episode_gated_on_kids_daily(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]))
        result = await _invoke(
            _tool_by_name(server, "create_kids_daily_episode"),
            {"news_text": "headline", "age_group": "6-8", "category": "general", "news_url": ""},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "skill_disabled", "skill": "kids_daily"}

    @pytest.mark.asyncio
    async def test_generate_my_agent_audio_gated_on_audio_narration(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]))
        result = await _invoke(
            _tool_by_name(server, "generate_my_agent_audio"),
            {"story_text": "hi", "voice": "nova", "speed": 1.0, "child_age": 7},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "skill_disabled", "skill": "audio_narration"}


class TestSafetyToolNeverGated:
    """check_child_content_safety must NOT be skill-gated — child safety
    is a non-negotiable per PRD §3.4. This test snapshots that policy so
    a future refactor that "gates everything for consistency" cannot
    silently disable safety review."""

    @pytest.mark.asyncio
    async def test_safety_tool_runs_with_empty_enabled_skills(self):
        server = _build_tools_for(_fake_agent(enabled_skills=[]))
        # Patch the upstream safety MCP so we don't exercise the model.
        with patch(
            "backend.src.agents.my_agent_proxy.check_content_safety.handler",
            new=AsyncMock(return_value={"content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]}),
        ):
            result = await _invoke(
                _tool_by_name(server, "check_child_content_safety"),
                {"content_text": "hello", "content_type": "agent_persona", "target_age": 7},
            )
        # Must NOT be a skill_disabled envelope.
        payload = _unwrap_envelope(result) if isinstance(result, dict) and "content" in result else result
        assert payload != {"error": "skill_disabled", "skill": "safety_review"}
        # Must surface the upstream safety_score envelope.
        assert payload.get("safety_score") == 0.99


# ---------------------------------------------------------------------------
# Image required guard
# ---------------------------------------------------------------------------


class TestImageRequiredGuard:
    """create_image_story must refuse to run without an attached image."""

    @pytest.mark.asyncio
    async def test_missing_image_returns_image_required(self):
        server = _build_tools_for(
            _fake_agent(enabled_skills=["image_story"]),
            image_path=None,
        )
        result = await _invoke(
            _tool_by_name(server, "create_image_story"),
            {"child_age": 7, "interests": [], "enable_audio": False, "voice": "", "art_theme": ""},
        )
        payload = _unwrap_envelope(result)
        assert payload == {"error": "image_required"}


# ---------------------------------------------------------------------------
# Subagent registration + tool-name sync
# ---------------------------------------------------------------------------


EXPECTED_SUBAGENTS = {
    "image-story-specialist": ["mcp__my-agent-tools__create_image_story"],
    "interactive-story-specialist": [
        "mcp__my-agent-tools__start_interactive_story",
        "mcp__my-agent-tools__continue_interactive_story",
    ],
    "kids-daily-specialist": ["mcp__my-agent-tools__create_kids_daily_episode"],
    "safety-review-specialist": ["mcp__my-agent-tools__check_child_content_safety"],
}


class TestSubagentRegistration:
    """All four AgentDefinitions register without error and carry the
    expected model + tool allow-list."""

    def test_all_four_subagents_registered(self):
        subagents = my_agent_proxy._build_subagents("ctx")
        assert set(subagents.keys()) == set(EXPECTED_SUBAGENTS.keys())

    def test_subagents_use_haiku_model(self):
        subagents = my_agent_proxy._build_subagents("ctx")
        for name, defn in subagents.items():
            assert getattr(defn, "model", None) == "haiku", f"{name} did not pin model=haiku"

    def test_subagent_tools_match_allow_list(self):
        """Snapshot the tools list per subagent — a tool rename in
        _make_tools must force this test to be updated alongside the
        subagent definition, preventing silent drift."""
        subagents = my_agent_proxy._build_subagents("ctx")
        for name, expected_tools in EXPECTED_SUBAGENTS.items():
            actual = list(getattr(subagents[name], "tools", []) or [])
            assert actual == expected_tools, (
                f"{name} tools drifted: expected={expected_tools} actual={actual}"
            )

    def test_subagent_tool_names_match_registered_mcp_tools(self):
        """Every subagent tool string must point at a real tool exposed
        by `_make_tools` — otherwise the parent agent would call an
        unknown tool at runtime."""
        registered = {f"mcp__my-agent-tools__{n}" for n in EXPECTED_TOOL_NAMES}
        subagents = my_agent_proxy._build_subagents("ctx")
        for name, defn in subagents.items():
            for tool_name in getattr(defn, "tools", []) or []:
                assert tool_name in registered, (
                    f"{name} references unknown tool {tool_name}"
                )

    def test_safety_review_specialist_carries_safety_prompt(self):
        """Defensive: the safety specialist must mention safety review
        in its prompt so it is steered toward the right behavior."""
        subagents = my_agent_proxy._build_subagents("ctx")
        prompt = getattr(subagents["safety-review-specialist"], "prompt", "")
        assert "safety" in prompt.lower()


# ---------------------------------------------------------------------------
# SDK fallback path
# ---------------------------------------------------------------------------


class TestSdkUnavailableFallback:
    """When claude_agent_sdk fails to import, stream_my_agent_chat must
    emit a structured SSE error event instead of raising. This is the
    only thing protecting the route from a hard crash in cold/test envs
    or when the SDK is intentionally disabled."""

    @pytest.mark.asyncio
    async def test_emits_sdk_unavailable_error_event(self, test_db):
        # Force both SDK entry points to None to simulate ImportError fallback.
        with patch.object(my_agent_proxy, "ClaudeSDKClient", None), \
             patch.object(my_agent_proxy, "ClaudeAgentOptions", None):
            chunks: list[str] = []
            async for chunk in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="hello buddy",
            ):
                chunks.append(chunk)

        events = _parse_sse_events("".join(chunks))
        error_events = [e for e in events if e["event"] == "error"]
        assert error_events, f"Expected an SSE error event, got: {[e['event'] for e in events]}"
        assert error_events[0]["data"]["error"] == "SDK_UNAVAILABLE"
        # And no 'result'/'complete' should be emitted after a hard fail.
        assert not any(e["event"] == "complete" for e in events)


# ---------------------------------------------------------------------------
# Agent not found path
# ---------------------------------------------------------------------------


class TestAgentNotFoundPath:
    """When the user has not finished My Agent onboarding yet (no row in
    user_agents), the stream must emit AGENT_NOT_FOUND instead of crashing
    in `_make_tools` (which assumes `agent.enabled_skills` exists)."""

    @pytest.mark.asyncio
    async def test_emits_agent_not_found_when_no_agent_row(self, test_db):
        # SDK is available in CI venv — patch agent_repo.get_agent to None
        # so we skip the persona lookup and exercise the not-found branch.
        with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=None)):
            chunks: list[str] = []
            async for chunk in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="hi",
            ):
                chunks.append(chunk)

        events = _parse_sse_events("".join(chunks))
        error_events = [e for e in events if e["event"] == "error"]
        assert error_events, f"Expected an SSE error event, got: {[e['event'] for e in events]}"
        assert error_events[0]["data"]["error"] == "AGENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# launch_flow SSE event (#496)
# ---------------------------------------------------------------------------


class _FakeSDKClient:
    """Async-context-manager stand-in for ClaudeSDKClient.

    Yields a caller-supplied list of SDK messages from receive_response()
    so we can drive ToolResultBlock paths without spinning a real agent.
    """

    def __init__(self, *, messages):
        self._messages = messages

    def __call__(self, *_args, **_kwargs):  # pragma: no cover - unused
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def query(self, _prompt):
        return None

    async def receive_response(self):
        for message in self._messages:
            yield message


def _assistant_with_tool_result(payload: dict[str, Any]):
    """Build an AssistantMessage carrying a single ToolResultBlock with payload."""
    from claude_agent_sdk import AssistantMessage, ToolResultBlock

    block = ToolResultBlock(
        tool_use_id="tu_test",
        content=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        is_error=False,
    )
    return AssistantMessage(content=[block], model="claude-haiku")


def _fake_result_message(text: str):
    """Build a ResultMessage stand-in with the SDK's real class.

    The proxy checks `isinstance(sdk_message, ResultMessage)`, so we must
    use the real class. We pass through enough kwargs to instantiate it.
    """
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="success",
        duration_ms=0,
        duration_api_ms=0,
        is_error=False,
        num_turns=1,
        session_id="sdk_sess_1",
        total_cost_usd=0.0,
        result=text,
    )


async def _collect_launch_flow_run(messages, *, image_path=None):
    """Drive stream_my_agent_chat with a fake SDK client and parse SSE.

    Patches in:
      - a fake SDKClient that yields the supplied messages,
      - a fake agent persona with all four specialist skills enabled,
      - a passthrough safety MCP so any future buddy-reply safety gate
        (e.g. PRD §3.4) doesn't silently swallow the response and hide
        the launch_flow contract we are exercising here.
    """
    fake_client = _FakeSDKClient(messages=messages)
    fake_agent = _fake_agent(
        enabled_skills=["image_story", "interactive_story", "kids_daily", "audio_narration"]
    )
    safe_envelope = {"content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]}
    with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=fake_agent)), \
         patch.object(my_agent_proxy, "ClaudeSDKClient", lambda *a, **kw: fake_client), \
         patch.object(
             my_agent_proxy,
             "build_my_agent_context",
             new=AsyncMock(return_value="ctx"),
         ), \
         patch(
             "backend.src.agents.my_agent_proxy.check_content_safety.handler",
             new=AsyncMock(return_value=safe_envelope),
         ):
        chunks: list[str] = []
        async for chunk in my_agent_proxy.stream_my_agent_chat(
            user_id=_TEST_USER_ID,
            child_id=_TEST_CHILD_ID,
            message="hi buddy",
            image_path=image_path,
        ):
            chunks.append(chunk)
    return _parse_sse_events("".join(chunks))


class TestLaunchFlowEvent:
    """When a specialist tool returns a structured payload the proxy must
    emit a typed `launch_flow` SSE event BEFORE the `result` event. This is
    the primitive that lets the My Agent chat hop the user to the matching
    standalone experience page with prefilled query params (#496)."""

    @pytest.mark.asyncio
    async def test_image_story_emits_launch_flow_before_result(self, test_db):
        payload = {
            "response_type": "image_story",
            "payload": {
                "story_id": "stry_abc123",
                "story": "Once upon a time...",
                "child_id": "c_test",
                "age_group": "6-8",
                "themes": ["adventure"],
            },
        }
        events = await _collect_launch_flow_run(
            messages=[
                _assistant_with_tool_result(payload),
                _fake_result_message("Story made!"),
            ],
            image_path="/tmp/x.png",
        )
        names = [e["event"] for e in events]
        assert "launch_flow" in names, f"launch_flow missing from {names}"
        # launch_flow must come before result so the frontend can navigate first.
        assert names.index("launch_flow") < names.index("result")
        launch = next(e for e in events if e["event"] == "launch_flow")
        assert launch["data"]["flow_type"] == "image_story"
        assert launch["data"]["route"] == "/story/stry_abc123"
        prefill = launch["data"]["prefill"]
        assert prefill.get("story_id") == "stry_abc123"
        # Prefill should carry the IDs the target page reads from query params.
        assert "child_id" in prefill

    @pytest.mark.asyncio
    async def test_interactive_story_emits_launch_flow(self, test_db):
        payload = {
            "response_type": "interactive_story",
            "payload": {
                "session_id": "sess_xyz999",
                "title": "Forest Quest",
                "age_group": "6-8",
                "theme": "forest",
            },
        }
        events = await _collect_launch_flow_run(
            messages=[
                _assistant_with_tool_result(payload),
                _fake_result_message("Story started!"),
            ],
        )
        launch = next((e for e in events if e["event"] == "launch_flow"), None)
        assert launch is not None, "launch_flow event missing for interactive_story"
        assert launch["data"]["flow_type"] == "interactive_story"
        assert launch["data"]["route"] == "/interactive-story/sess_xyz999"
        prefill = launch["data"]["prefill"]
        assert prefill.get("session_id") == "sess_xyz999"
        assert prefill.get("age_group") == "6-8"

    @pytest.mark.asyncio
    async def test_kids_daily_emits_launch_flow(self, test_db):
        payload = {
            "response_type": "kids_daily",
            "payload": {
                "episode_id": "ep_777",
                "kid_title": "Today's Big News",
                "age_group": "6-8",
                "category": "science",
            },
        }
        events = await _collect_launch_flow_run(
            messages=[
                _assistant_with_tool_result(payload),
                _fake_result_message("Episode ready!"),
            ],
        )
        launch = next((e for e in events if e["event"] == "launch_flow"), None)
        assert launch is not None, "launch_flow event missing for kids_daily"
        assert launch["data"]["flow_type"] == "kids_daily"
        assert launch["data"]["route"] == "/kids-daily/ep_777"
        prefill = launch["data"]["prefill"]
        assert prefill.get("episode_id") == "ep_777"

    @pytest.mark.asyncio
    async def test_chat_response_does_not_emit_launch_flow(self, test_db):
        """When no specialist fires, response_type defaults to 'chat' and
        the proxy must NOT emit a launch_flow event — otherwise the frontend
        would try to navigate away from a plain text reply."""
        events = await _collect_launch_flow_run(
            messages=[_fake_result_message("Hi friend!")],
        )
        names = [e["event"] for e in events]
        assert "launch_flow" not in names, (
            f"Unexpected launch_flow for plain chat: {names}"
        )
        # We still expect a result event for the chat reply.
        assert "result" in names

    @pytest.mark.asyncio
    async def test_invalid_response_type_does_not_emit_launch_flow(self, test_db):
        """Defensive: an unknown response_type must not produce a
        launch_flow event with an unmapped route. This snapshots the
        whitelist policy so a future agent that returns 'video_story' or
        similar can't silently navigate the user somewhere broken."""
        payload = {"response_type": "video_story", "payload": {"video_id": "v1"}}
        events = await _collect_launch_flow_run(
            messages=[
                _assistant_with_tool_result(payload),
                _fake_result_message("Made a thing."),
            ],
        )
        names = [e["event"] for e in events]
        assert "launch_flow" not in names, (
            f"launch_flow emitted for unknown response_type: {names}"
        )

    @pytest.mark.asyncio
    async def test_missing_id_falls_back_to_landing_route(self, test_db):
        """If the specialist payload has no story_id/session_id/episode_id
        the proxy should still emit launch_flow pointing at the landing
        page so the user lands in the right experience (with prefill) even
        when persistence isn't wired through the buddy yet."""
        payload = {
            "response_type": "image_story",
            "payload": {"child_id": "c_test", "age_group": "6-8"},  # no story_id
        }
        events = await _collect_launch_flow_run(
            messages=[
                _assistant_with_tool_result(payload),
                _fake_result_message("Made a story."),
            ],
            image_path="/tmp/x.png",
        )
        launch = next((e for e in events if e["event"] == "launch_flow"), None)
        assert launch is not None, "launch_flow should still fire without an ID"
        assert launch["data"]["flow_type"] == "image_story"
        # Landing route (no /:id) so the page can pick up where it left off.
        assert launch["data"]["route"] == "/upload"
        assert launch["data"]["prefill"].get("child_id") == "c_test"
