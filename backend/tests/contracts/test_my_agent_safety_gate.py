"""
My Agent Safety Gate Contract Tests (#498)

Locks down the per-reply safety enforcement that runs on every buddy chat
turn before delivery. Specifically tests the `enforce_chat_safety` helper
in isolation so we don't need to drive the full SSE stream:

  - Safe replies pass through untouched and the score is reported.
  - Below-threshold replies trigger a retry through
    `suggest_content_improvements`. If the retry passes, the improved
    text is returned with the retry score.
  - When the retry also fails, the safe fallback message is returned
    with `used_fallback=True` and a `below_threshold` reason.
  - Age-aware threshold: ages 3-5 reject score 0.87 (threshold 0.90);
    ages 6-8 accept the same score (threshold 0.85).
  - When the safety MCP raises, we fail closed with the fallback and
    a `safety_unavailable` reason — no retry attempted, no model trust.

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #498
"""

from __future__ import annotations

import json
from datetime import datetime as _dt
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.src.agents import my_agent_proxy
from backend.src.services.database import db_manager
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema


_TEST_USER_ID = "safety_gate_user"
_TEST_CHILD_ID = "safety_gate_child"


@pytest_asyncio.fixture
async def test_db():
    """Local in-memory DB fixture (mirrors test_my_agent_proxy.test_db).

    A separate fixture is used here to keep the safety-gate tests independent
    of the proxy test module — if the proxy fixture is removed or renamed
    these tests still run.
    """
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

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
            "safety_gate_user",
            "safety@test.com",
            "h",
            "Safety",
            1,
            1,
            "child",
            "free",
            "TESTSAFE",
            None,
            now,
            now,
        ),
    )
    await db_manager.commit()

    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


def _safety_envelope(score: float) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps({"safety_score": score})}]}


def _improvement_envelope(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps({"improved_content": text})}]}


class TestSafeReplyPassesThrough:
    """A reply meeting the threshold for its age group must be returned
    untouched. We assert the helper does NOT call the improvement MCP
    (no needless latency) and reports `used_fallback=False`."""

    @pytest.mark.asyncio
    async def test_safe_reply_returns_unchanged(self):
        safety_mock = AsyncMock(return_value=_safety_envelope(0.95))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock):
            text, score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "Let's draw a happy fox.",
                age_group="6-8",
                allow_retry=True,
            )
        assert text == "Let's draw a happy fox."
        assert score == 0.95
        assert used_fallback is False
        assert reason == "ok"


class TestUnsafeRetryThenFallback:
    """Below-threshold replies trigger a single retry via
    `suggest_content_improvements`. When the retry rewrite STILL fails,
    the helper returns the safe fallback message and `used_fallback=True`."""

    @pytest.mark.asyncio
    async def test_retry_recovers_with_improved_text(self):
        # First call: original is unsafe. Second call: rewrite is safe.
        safety_mock = AsyncMock(side_effect=[
            _safety_envelope(0.50),
            _safety_envelope(0.95),
        ])
        improve_mock = AsyncMock(return_value=_improvement_envelope("A friendlier fox story."))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock), \
             patch(
                 "backend.src.mcp_servers.safety_check_server.suggest_content_improvements.handler",
                 new=improve_mock,
             ):
            text, score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "An unsafe-sounding reply.",
                age_group="6-8",
                allow_retry=True,
            )
        assert text == "A friendlier fox story."
        assert score == 0.95
        assert used_fallback is False
        assert reason == "improved"
        assert safety_mock.await_count == 2, "Helper should re-score the improved text"
        assert improve_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_retry_failure_uses_fallback(self):
        # Both scoring calls return unsafe → fallback message.
        safety_mock = AsyncMock(side_effect=[
            _safety_envelope(0.50),
            _safety_envelope(0.60),
        ])
        improve_mock = AsyncMock(return_value=_improvement_envelope("Still bad rewrite."))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock), \
             patch(
                 "backend.src.mcp_servers.safety_check_server.suggest_content_improvements.handler",
                 new=improve_mock,
             ):
            text, score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "An unsafe-sounding reply.",
                age_group="6-8",
                allow_retry=True,
            )
        assert text == "Let's try that again — what would you like to make?"
        assert used_fallback is True
        assert reason == "below_threshold"
        # First score is what the helper reports back so observability
        # surfaces the original failure score, not the retry score.
        assert score == 0.50


class TestAgeAwareThreshold:
    """Threshold is 0.90 for ages 3-5, 0.85 elsewhere. A score of 0.87
    must FAIL for 3-5 but PASS for 6-8."""

    @pytest.mark.asyncio
    async def test_score_087_blocked_for_3_5(self):
        safety_mock = AsyncMock(side_effect=[
            _safety_envelope(0.87),
            _safety_envelope(0.80),  # retry also below 0.90
        ])
        improve_mock = AsyncMock(return_value=_improvement_envelope("Still under threshold."))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock), \
             patch(
                 "backend.src.mcp_servers.safety_check_server.suggest_content_improvements.handler",
                 new=improve_mock,
             ):
            text, _score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "Borderline reply.",
                age_group="3-5",
                allow_retry=True,
            )
        # 0.87 < 0.90 → must be blocked.
        assert used_fallback is True
        assert reason == "below_threshold"
        assert text == "Let's try that again — what would you like to make?"

    @pytest.mark.asyncio
    async def test_score_087_passes_for_6_8(self):
        safety_mock = AsyncMock(return_value=_safety_envelope(0.87))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock):
            text, score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "Borderline reply.",
                age_group="6-8",
                allow_retry=True,
            )
        # 0.87 >= 0.85 → passes unchanged.
        assert used_fallback is False
        assert reason == "ok"
        assert text == "Borderline reply."
        assert score == 0.87

    @pytest.mark.asyncio
    async def test_threshold_helper_returns_correct_values(self):
        assert my_agent_proxy._threshold_for_age("3-5") == 0.90
        assert my_agent_proxy._threshold_for_age("6-8") == 0.85
        assert my_agent_proxy._threshold_for_age("9-12") == 0.85
        assert my_agent_proxy._threshold_for_age(None) == 0.85


class TestMcpErrorFailsClosed:
    """If the safety MCP raises, the helper must return the safe
    fallback without attempting an improvement rewrite (we don't trust
    a degraded service to deliver clean text either)."""

    @pytest.mark.asyncio
    async def test_handler_raise_fails_closed(self):
        safety_mock = AsyncMock(side_effect=RuntimeError("boom"))
        improve_mock = AsyncMock(return_value=_improvement_envelope("ignored"))
        with patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock), \
             patch(
                 "backend.src.mcp_servers.safety_check_server.suggest_content_improvements.handler",
                 new=improve_mock,
             ):
            text, _score, used_fallback, reason = await my_agent_proxy.enforce_chat_safety(
                "Some reply.",
                age_group="6-8",
                allow_retry=True,
            )
        assert used_fallback is True
        assert reason == "safety_unavailable"
        assert text == "Let's try that again — what would you like to make?"
        # We must NOT have called the improvement MCP — the safety MCP
        # is down so its rewrite path can't be trusted either.
        assert improve_mock.await_count == 0


class TestStreamLevelGate:
    """End-to-end: stream_my_agent_chat must inject an unsafe reply
    through the gate before the SSE result event. We patch the SDK so
    the stream produces a known unsafe ResultMessage, then assert the
    delivered message is the fallback, not the original.

    This is the contract test required by #498 AC: 'Contract test that
    injects an unsafe LLM response and confirms it is blocked'."""

    @pytest.mark.asyncio
    async def test_injected_unsafe_reply_is_blocked_before_delivery(self, test_db):
        from backend.tests.contracts.test_my_agent_proxy import (
            _FakeSdkClient,
            _FakeResultMessage,
            _FakeOptions,
            _fake_agent,
            _parse_sse_events,
        )
        unsafe = "Some unsafe-sounding LLM reply we should never deliver."
        fake_client = _FakeSdkClient(result_text=unsafe)
        safety_mock = AsyncMock(side_effect=[
            _safety_envelope(0.40),
            _safety_envelope(0.50),  # retry also fails
        ])
        improve_mock = AsyncMock(return_value=_improvement_envelope("still bad"))
        with patch.object(my_agent_proxy, "ClaudeSDKClient", lambda options: fake_client), \
             patch.object(my_agent_proxy, "ClaudeAgentOptions", _FakeOptions), \
             patch.object(my_agent_proxy, "ResultMessage", _FakeResultMessage), \
             patch.object(
                 my_agent_proxy.agent_repo,
                 "get_agent",
                 new=AsyncMock(return_value=_fake_agent(enabled_skills=["image_story"])),
             ), \
             patch.object(
                 my_agent_proxy,
                 "build_my_agent_context",
                 new=AsyncMock(return_value="(ctx)"),
             ), \
             patch.object(my_agent_proxy.check_content_safety, "handler", new=safety_mock), \
             patch(
                 "backend.src.mcp_servers.safety_check_server.suggest_content_improvements.handler",
                 new=improve_mock,
             ):
            chunks: list[str] = []
            async for chunk in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="say something",
                age_group="6-8",
            ):
                chunks.append(chunk)

        events = _parse_sse_events("".join(chunks))
        result = next(e for e in events if e["event"] == "result")
        # The unsafe text must NOT have been delivered.
        assert result["data"]["message"] != unsafe
        assert unsafe not in "".join(chunks)
        # A safety_blocked telemetry event must be present.
        blocked = [e for e in events if e["event"] == "safety_blocked"]
        assert blocked, "Expected safety_blocked SSE event after injected unsafe reply"
        assert blocked[0]["data"]["reason"] == "below_threshold"
