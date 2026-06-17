"""Contract tests for the #655/#657 glue PR — realtime tool calls wired
end-to-end through the broker.

What this PR locks in:

1. The OpenAI Realtime system prompt no longer tells the model "do not
   invoke tools" — it lists the available tools instead.
2. ``session.update`` registers tool definitions on session open.
3. ``_ev_to_reply_events`` translates ``response.function_call_arguments.done``
   into a ``ReplyEvent(kind="function_call")``.
4. ``OpenAIRealtimeProvider.send_function_call_output`` sends the
   correct two-event sequence (``conversation.item.create`` of type
   ``function_call_output`` + ``response.create``) to the upstream.
5. The broker's ``_dispatch_function_call`` routes envelopes by type:
   - ``launch_flow`` → WS event to client + ack to model
   - ``tool_result`` → ack to model with full payload
   - ``end_call`` → flag the outer loop to close with the documented reason

Tests intentionally avoid hitting OpenAI — they exercise the in-process
seams with mocked WS / provider objects.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

from backend.src.services.realtime_voice_service import (
    OpenAIRealtimeProvider,
    ReplyEvent,
    SessionHandle,
    _ev_to_reply_events,
)


# ---------------------------------------------------------------------------
# (1) System prompt no longer suppresses tools
# ---------------------------------------------------------------------------

def test_system_prompt_invites_tool_use():
    """The model used to be told 'do not invoke tools'. Now we list the
    available tools so it can actually call them."""
    from backend.src.services.realtime_voice_service import (
        _build_openai_system_prompt,
    )
    prompt = _build_openai_system_prompt(persona="buddy_default", target_age=7)
    # Negative: must NOT carry the old suppression line
    assert "Do not invoke tools" not in prompt
    assert "do not invoke tools" not in prompt
    # Positive: must list the load-bearing tools by name
    for tool_name in (
        "launch_image_story",
        "launch_interactive_story",
        "launch_kids_daily",
        "recall_memory",
        "end_call",
    ):
        assert tool_name in prompt, f"system prompt is missing {tool_name!r}"


# ---------------------------------------------------------------------------
# (2) session.update registers tool definitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_update_includes_tool_definitions(monkeypatch):
    """When the upstream WS opens, session.update must carry the full
    tool definitions list so the model knows what it can call."""
    from backend.src.services import realtime_voice_service as svc

    # Pretend we have keys + the opt-in flag for the upstream WS path.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_REALTIME_OPEN_UPSTREAM", "1")

    # Stub the httpx client_secrets POST.
    fake_resp = SimpleNamespace(
        json=lambda: {"client_secret": {"value": "ek-test", "expires_at": 9999999999}},
        raise_for_status=lambda: None,
    )

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return fake_resp

    monkeypatch.setattr(svc, "_httpx_AsyncClient", _FakeAsyncClient)

    # Stub the websockets.connect call so we capture the session.update payload.
    sent_payloads: List[str] = []

    class _FakeWS:
        async def send(self, payload: str) -> None:
            sent_payloads.append(payload)

        async def close(self) -> None:
            return None

        async def recv(self) -> str:
            return "{}"

    async def _fake_connect(*args, **kwargs):
        return _FakeWS()

    # The provider may use websockets.connect or a similar entry — patch
    # the symbol at module level so we don't need to know which.
    monkeypatch.setattr(svc, "websockets_connect", _fake_connect, raising=False)
    # Some implementations import via ``from websockets import connect``;
    # patch both shapes so the test is robust.
    import websockets
    monkeypatch.setattr(websockets, "connect", _fake_connect)

    provider = OpenAIRealtimeProvider()
    handle = await provider.start_session(
        user_id="u1", child_id="c1", target_age=7, persona="buddy_default",
    )

    if handle.provider_state.get("provider_unavailable"):
        pytest.skip("upstream WS path not exercised in this env")

    # Find the session.update payload among the sent events.
    updates = [
        json.loads(p) for p in sent_payloads if "session.update" in p
    ]
    assert updates, "session.update was never sent to upstream"
    session_block = updates[0].get("session") or {}
    tools = session_block.get("tools")
    assert isinstance(tools, list), "tools list missing from session.update"
    assert tools, "tools list is empty — model would not know which tools exist"
    tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
    # The six tools E3 (#655) defined.
    expected = {
        "launch_image_story",
        "launch_interactive_story",
        "launch_kids_daily",
        "recall_memory",
        "safety_review_reply",
        "end_call",
    }
    assert expected.issubset(tool_names), (
        f"missing tools in session.update: {expected - tool_names}"
    )


# ---------------------------------------------------------------------------
# (3) _ev_to_reply_events handles function_call_arguments.done
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ev_to_reply_events_translates_function_call():
    """An upstream ``response.function_call_arguments.done`` event must
    surface as a ``function_call`` ReplyEvent carrying call_id, name,
    and parsed args."""
    ev = {
        "type": "response.function_call_arguments.done",
        "call_id": "call_abc",
        "name": "launch_image_story",
        "arguments": json.dumps({"child_id": "c1", "age_group": "6-8"}),
    }
    out: List[ReplyEvent] = [r async for r in _ev_to_reply_events(ev)]
    assert len(out) == 1
    assert out[0].kind == "function_call"
    assert out[0].call_id == "call_abc"
    assert out[0].name == "launch_image_story"
    assert out[0].args == {"child_id": "c1", "age_group": "6-8"}


@pytest.mark.asyncio
async def test_ev_to_reply_events_function_call_malformed_args_coerces_to_empty():
    """If the model sends malformed JSON args, the broker must not crash
    — it gets an empty dict and the handler's error path responds."""
    ev = {
        "type": "response.function_call_arguments.done",
        "call_id": "call_bad",
        "name": "launch_image_story",
        "arguments": "{not-json",
    }
    out: List[ReplyEvent] = [r async for r in _ev_to_reply_events(ev)]
    assert len(out) == 1
    assert out[0].kind == "function_call"
    assert out[0].args == {}


# ---------------------------------------------------------------------------
# (4) send_function_call_output sends the two-event sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_function_call_output_emits_item_create_then_response_create():
    """OpenAI Realtime requires every function call to be paired with a
    function_call_output AND a response.create. Skipping either leaves
    the model waiting."""
    provider = OpenAIRealtimeProvider()
    sent: List[Dict[str, Any]] = []

    class _CapturingWS:
        async def send(self, payload: str) -> None:
            sent.append(json.loads(payload))

    handle = SessionHandle(
        session_id="s1", user_id="u1", child_id="c1",
        target_age=7, persona="buddy_default",
        provider_state={"upstream_ws": _CapturingWS()},
    )

    await provider.send_function_call_output(
        handle, call_id="call_xyz", output='{"status":"launched"}',
    )

    assert len(sent) == 2, f"expected 2 upstream events, got {len(sent)}: {sent}"
    assert sent[0]["type"] == "conversation.item.create"
    assert sent[0]["item"]["type"] == "function_call_output"
    assert sent[0]["item"]["call_id"] == "call_xyz"
    assert sent[0]["item"]["output"] == '{"status":"launched"}'
    assert sent[1]["type"] == "response.create"


@pytest.mark.asyncio
async def test_send_function_call_output_silent_when_degraded():
    """A degraded session (no upstream WS) silently drops — the broker
    must not crash a turn just because the upstream went away."""
    provider = OpenAIRealtimeProvider()
    handle = SessionHandle(
        session_id="s1", user_id="u1", child_id="c1",
        target_age=7, persona="buddy_default",
        provider_state={},  # no upstream_ws
    )
    # Should not raise.
    await provider.send_function_call_output(
        handle, call_id="call_xyz", output="{}",
    )


# ---------------------------------------------------------------------------
# (5) Broker's _dispatch_function_call routes envelopes correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_launch_flow_emits_ws_event_and_acks_model(monkeypatch):
    """When a tool call returns a ``launch_flow`` envelope, the client
    gets a WS event AND the model gets a function_call_output ack."""
    from backend.src.api.routes import voice_realtime as broker

    async def _fake_handle_tool_call(name, args, ctx):
        return {
            "type": "launch_flow",
            "payload": {
                "flow_type": "image_story",
                "route": "/image-to-story",
                "prefill": {"child_id": "c1"},
            },
        }

    monkeypatch.setattr(broker, "handle_tool_call", _fake_handle_tool_call)

    ws_events: List[Dict[str, Any]] = []

    async def _capture_send_event(ws, event):
        ws_events.append(event)

    monkeypatch.setattr(broker, "_send_event", _capture_send_event)

    provider = SimpleNamespace(send_function_call_output=AsyncMock())
    handle = SessionHandle(
        session_id="s1", user_id="u1", child_id="c1",
        target_age=7, persona="buddy_default", provider_state={},
    )
    state: Dict[str, Any] = {}
    ev = ReplyEvent(
        kind="function_call",
        call_id="call_1",
        name="launch_image_story",
        args={"child_id": "c1"},
    )

    await broker._dispatch_function_call(
        websocket=object(),
        provider=provider,
        handle=handle,
        target_age=7,
        ev=ev,
        state=state,
    )

    # WS event was emitted with the launch_flow payload merged in.
    assert any(e.get("type") == "launch_flow" for e in ws_events), (
        f"no launch_flow WS event emitted; got: {ws_events}"
    )
    flow_event = next(e for e in ws_events if e["type"] == "launch_flow")
    assert flow_event["flow_type"] == "image_story"
    assert flow_event["route"] == "/image-to-story"

    # Model got an ack.
    provider.send_function_call_output.assert_awaited_once()
    call = provider.send_function_call_output.await_args
    assert call.kwargs["call_id"] == "call_1"
    ack_payload = json.loads(call.kwargs["output"])
    assert ack_payload == {"status": "launched", "flow_type": "image_story"}

    # No end_call triggered.
    assert not state.get("end_call_requested")


@pytest.mark.asyncio
async def test_dispatch_end_call_sets_state_flag_and_skips_ack(monkeypatch):
    """``end_call`` envelopes flag the outer broker loop to close —
    no ack is sent because we're closing anyway."""
    from backend.src.api.routes import voice_realtime as broker

    async def _fake_handle_tool_call(name, args, ctx):
        return {
            "type": "end_call",
            "payload": {"ended_reason": "voice_tool_end_call", "reason": "kid_said_bye"},
        }

    monkeypatch.setattr(broker, "handle_tool_call", _fake_handle_tool_call)
    monkeypatch.setattr(broker, "_send_event", AsyncMock())

    provider = SimpleNamespace(send_function_call_output=AsyncMock())
    handle = SessionHandle(
        session_id="s1", user_id="u1", child_id="c1",
        target_age=7, persona="buddy_default", provider_state={},
    )
    state: Dict[str, Any] = {}

    await broker._dispatch_function_call(
        websocket=object(),
        provider=provider,
        handle=handle,
        target_age=7,
        ev=ReplyEvent(kind="function_call", call_id="cz", name="end_call", args={}),
        state=state,
    )

    assert state.get("end_call_requested") is True
    assert state.get("end_call_reason") == "voice_tool_end_call"
    provider.send_function_call_output.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_tool_result_acks_with_full_payload(monkeypatch):
    """Non-launch / non-end envelopes (the ``tool_result`` lane —
    including handler error envelopes) feed the whole payload back to
    the model so it can continue the conversation with the lookup."""
    from backend.src.api.routes import voice_realtime as broker

    payload = {"matches": [{"title": "the dragon story", "id": "story_42"}]}

    async def _fake_handle_tool_call(name, args, ctx):
        return {"type": "tool_result", "payload": payload}

    monkeypatch.setattr(broker, "handle_tool_call", _fake_handle_tool_call)
    monkeypatch.setattr(broker, "_send_event", AsyncMock())

    provider = SimpleNamespace(send_function_call_output=AsyncMock())
    handle = SessionHandle(
        session_id="s1", user_id="u1", child_id="c1",
        target_age=7, persona="buddy_default", provider_state={},
    )

    await broker._dispatch_function_call(
        websocket=object(),
        provider=provider,
        handle=handle,
        target_age=7,
        ev=ReplyEvent(
            kind="function_call", call_id="rm1",
            name="recall_memory", args={"query": "dragon"},
        ),
        state={},
    )

    provider.send_function_call_output.assert_awaited_once()
    call = provider.send_function_call_output.await_args
    assert call.kwargs["call_id"] == "rm1"
    assert json.loads(call.kwargs["output"]) == payload


@pytest.mark.asyncio
async def test_dispatch_passes_correct_age_group_to_handler(monkeypatch):
    """The broker pre-binds child_id + age_group into ToolContext — the
    model can never inject another child's ID by accident."""
    from backend.src.api.routes import voice_realtime as broker

    captured = {}

    async def _fake_handle_tool_call(name, args, ctx):
        captured["ctx"] = ctx
        return {"type": "tool_result", "payload": {}}

    monkeypatch.setattr(broker, "handle_tool_call", _fake_handle_tool_call)
    monkeypatch.setattr(broker, "_send_event", AsyncMock())

    provider = SimpleNamespace(send_function_call_output=AsyncMock())
    handle = SessionHandle(
        session_id="sess_xyz", user_id="user_a", child_id="child_b",
        target_age=4, persona="buddy_default", provider_state={},
    )

    await broker._dispatch_function_call(
        websocket=object(),
        provider=provider,
        handle=handle,
        target_age=4,
        ev=ReplyEvent(kind="function_call", call_id="c1", name="recall_memory", args={}),
        state={},
    )

    ctx = captured["ctx"]
    assert ctx.user_id == "user_a"
    assert ctx.child_id == "child_b"
    assert ctx.age_group == "3-5"  # target_age=4 → 3-5 band
    assert ctx.session_id == "sess_xyz"
