"""
Voice cost telemetry + tier selection contract tests (#648).

Locks the behaviour the broker depends on for per-session cost estimation
and the tier-selection policy that keeps the OpenAI Realtime spend
manageable. Specifically:

  1. ``OPENAI_REALTIME_MODEL_DEFAULT`` stays ``gpt-realtime-mini`` so any
     accidental flip to the premium tier is caught here.
  2. ``OpenAIRealtimeProvider`` selects the mini model unless the child
     profile sets BOTH ``voice_premium_voice`` AND
     ``voice_premium_voice_consent``. Only one flag set → still mini
     (fail closed — escalation requires both signals).
  3. ``VOICE_MODEL_RATES_USD_PER_MIN`` exposes the cached/uncached blend
     per model from PRD §3.16.8 within ±5%.
  4. ``estimate_session_cost_usd`` produces a per-minute USD figure with
     the same ±5% tolerance for a known (duration, model, cache state).
  5. ``voice_session_repo`` persists ``model``, ``cost_estimate_usd``,
     and ``prompt_cache_hit`` (extending ``end_session`` or via a new
     ``record_cost`` API), and ``get_by_id`` surfaces them.
  6. The broker emits a structured ``voice_session_end`` log entry with
     all the canonical fields when closing a session.
  7. Hybrid / Mock providers still work — cost columns are NULL on
     non-OpenAI sessions and the close path does not crash.

The OpenAI upstream is never touched; tests rely on the existing
``provider_unavailable`` degraded path so no network is required.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import pytest
import pytest_asyncio

from backend.src.services import realtime_voice_service as rtvs
from backend.src.services.database import (
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)
    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    now = datetime.now().isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (user_id, username, email, password_hash, display_name,
                           is_active, is_verified, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("cost_parent", "cost_parent", "cp@test.com", "h", "Cost Parent", 1, 1, now, now),
    )
    await db_manager.commit()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


# ---------------------------------------------------------------------------
# 1. Default model constant — guardrail against accidental escalation.
# ---------------------------------------------------------------------------

class TestDefaultModelConstant:
    def test_default_model_is_mini(self):
        # Lock the constant. If anyone bumps this to the premium tier,
        # the test forces an explicit PRD update + reviewer awareness.
        assert rtvs.OPENAI_REALTIME_MODEL_DEFAULT == "gpt-realtime-mini"

    def test_escalated_model_is_premium(self):
        assert rtvs.OPENAI_REALTIME_MODEL_ESCALATED == "gpt-realtime-2"


# ---------------------------------------------------------------------------
# 2. Tier-selection policy in OpenAIRealtimeProvider.start_session
# ---------------------------------------------------------------------------

class TestTierSelection:
    """Provider.start_session honours the per-child premium-voice flags."""

    @pytest.mark.asyncio
    async def test_default_session_uses_mini(self, monkeypatch):
        # No env, no premium flags → mini.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = rtvs.OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert handle.provider_state["model"] == "gpt-realtime-mini"

    @pytest.mark.asyncio
    async def test_premium_disabled_by_default_stays_mini(self, monkeypatch):
        # Cheapest-everywhere cost policy: without VOICE_ALLOW_PREMIUM_REALTIME=1,
        # even a dual opt-in profile stays on the mini tier.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("VOICE_ALLOW_PREMIUM_REALTIME", raising=False)
        provider = rtvs.OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
            voice_premium_voice=True,
            voice_premium_voice_consent=True,
        )
        assert handle.provider_state["model"] == "gpt-realtime-mini"

    @pytest.mark.asyncio
    async def test_escalation_requires_both_flags_true(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Premium escalation is opt-in via env (cheapest-everywhere default is
        # OFF). Enable it here to exercise the dual-flag escalation policy.
        monkeypatch.setenv("VOICE_ALLOW_PREMIUM_REALTIME", "1")
        provider = rtvs.OpenAIRealtimeProvider()

        # Only opt-in flag set → still mini (fail closed).
        h1 = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
            voice_premium_voice=True,
            voice_premium_voice_consent=False,
        )
        assert h1.provider_state["model"] == "gpt-realtime-mini"

        # Only consent flag set → still mini.
        h2 = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
            voice_premium_voice=False,
            voice_premium_voice_consent=True,
        )
        assert h2.provider_state["model"] == "gpt-realtime-mini"

        # Both flags set AND premium allowed → escalate.
        h3 = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
            voice_premium_voice=True,
            voice_premium_voice_consent=True,
        )
        assert h3.provider_state["model"] == "gpt-realtime-2"


# ---------------------------------------------------------------------------
# 3. Rate table — PRD §3.16.8 numbers within ±5%.
# ---------------------------------------------------------------------------

class TestRateTable:
    """The blended rates are the load-bearing input to cost estimates."""

    def test_table_exposes_both_models(self):
        rates = rtvs.VOICE_MODEL_RATES_USD_PER_MIN
        assert "gpt-realtime-mini" in rates
        assert "gpt-realtime-2" in rates

    def test_each_model_has_cached_and_uncached_rates(self):
        rates = rtvs.VOICE_MODEL_RATES_USD_PER_MIN
        for model, sub in rates.items():
            assert "cached" in sub, f"missing cached rate for {model}"
            assert "uncached" in sub, f"missing uncached rate for {model}"
            assert sub["cached"] < sub["uncached"], (
                f"cached rate should be lower than uncached for {model}"
            )

    @pytest.mark.parametrize(
        "model,kind,expected_usd_per_min",
        [
            ("gpt-realtime-mini", "cached", 0.075),
            ("gpt-realtime-mini", "uncached", 0.215),
            ("gpt-realtime-2", "cached", 0.20),
            ("gpt-realtime-2", "uncached", 0.43),
        ],
    )
    def test_rate_within_5pct_of_prd(self, model, kind, expected_usd_per_min):
        actual = rtvs.VOICE_MODEL_RATES_USD_PER_MIN[model][kind]
        tolerance = expected_usd_per_min * 0.05
        assert abs(actual - expected_usd_per_min) <= tolerance, (
            f"{model}/{kind} rate {actual} drifted >5% from PRD value "
            f"{expected_usd_per_min}"
        )


# ---------------------------------------------------------------------------
# 4. Per-session cost estimate helper.
# ---------------------------------------------------------------------------

class TestEstimateSessionCost:
    """``estimate_session_cost_usd`` should be linear in duration."""

    def test_zero_duration_is_zero_cost(self):
        cost = rtvs.estimate_session_cost_usd(
            model="gpt-realtime-mini",
            duration_seconds=0,
            prompt_cache_hit=False,
        )
        assert cost == 0.0

    @pytest.mark.parametrize(
        "model,duration_s,cache_hit,expected_usd",
        [
            # 60s at uncached mini = $0.215
            ("gpt-realtime-mini", 60, False, 0.215),
            # 120s at cached mini = $0.15
            ("gpt-realtime-mini", 120, True, 0.15),
            # 60s at uncached premium = $0.43
            ("gpt-realtime-2", 60, False, 0.43),
            # 300s at cached premium = $1.00
            ("gpt-realtime-2", 300, True, 1.00),
        ],
    )
    def test_cost_within_5pct(self, model, duration_s, cache_hit, expected_usd):
        actual = rtvs.estimate_session_cost_usd(
            model=model,
            duration_seconds=duration_s,
            prompt_cache_hit=cache_hit,
        )
        tolerance = max(expected_usd * 0.05, 1e-6)
        assert abs(actual - expected_usd) <= tolerance, (
            f"cost {actual} drifted >5% from expected {expected_usd}"
        )

    def test_unknown_model_returns_zero(self):
        # Defensive: a brand-new model name should not crash the broker;
        # cost estimation returns 0 and we'll backfill the rate later.
        assert rtvs.estimate_session_cost_usd(
            model="gpt-realtime-future",
            duration_seconds=60,
            prompt_cache_hit=False,
        ) == 0.0


# ---------------------------------------------------------------------------
# 5. voice_session_repo persists cost telemetry columns.
# ---------------------------------------------------------------------------

class TestVoiceSessionRepoCostColumns:
    @pytest.mark.asyncio
    async def test_end_session_persists_cost_columns(self, test_db):
        session = await voice_session_repo.create_session(
            user_id="cost_parent",
            child_id="child_cost_a",
            provider="openai_realtime",
        )
        closed = await voice_session_repo.end_session(
            session_id=session.session_id,
            reason="user_ended",
            duration_seconds=180,
            safety_score=0.95,
            model="gpt-realtime-mini",
            cost_estimate_usd=0.645,  # 180s uncached mini → ~$0.645
            prompt_cache_hit=False,
        )
        assert closed is not None
        assert closed.model == "gpt-realtime-mini"
        assert closed.cost_estimate_usd == pytest.approx(0.645, rel=0.01)
        assert closed.prompt_cache_hit is False

    @pytest.mark.asyncio
    async def test_get_by_id_returns_cost_columns(self, test_db):
        session = await voice_session_repo.create_session(
            user_id="cost_parent",
            child_id="child_cost_b",
            provider="openai_realtime",
        )
        await voice_session_repo.end_session(
            session_id=session.session_id,
            reason="user_ended",
            duration_seconds=60,
            model="gpt-realtime-2",
            cost_estimate_usd=0.43,
            prompt_cache_hit=False,
        )
        row = await voice_session_repo.get_by_id(session.session_id)
        assert row is not None
        assert row.model == "gpt-realtime-2"
        assert row.cost_estimate_usd == pytest.approx(0.43, rel=0.01)

    @pytest.mark.asyncio
    async def test_legacy_end_session_call_still_works(self, test_db):
        # The pre-#648 broker (and the Hybrid/Mock paths) call end_session
        # without cost args. The repo must keep accepting that shape and
        # leave cost columns NULL.
        session = await voice_session_repo.create_session(
            user_id="cost_parent",
            child_id="child_cost_c",
            provider="hybrid",
        )
        closed = await voice_session_repo.end_session(
            session_id=session.session_id,
            reason="user_ended",
            duration_seconds=45,
        )
        assert closed is not None
        assert closed.model is None
        assert closed.cost_estimate_usd is None
        assert closed.prompt_cache_hit is None


# ---------------------------------------------------------------------------
# 6. Structured ``voice_session_end`` log emitted at close.
# ---------------------------------------------------------------------------

class TestStructuredSessionEndLog:
    """The ops team greps these JSON logs to spot runaway spend."""

    def test_log_helper_emits_canonical_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger=rtvs.__name__):
            rtvs.log_voice_session_end(
                session_id="voice_openai_test_123",
                model="gpt-realtime-mini",
                duration_seconds=180,
                cost_estimate_usd=0.645,
                prompt_cache_hit=False,
                first_audio_ms=743,
                ended_reason="user_ended",
            )

        matches = [
            r for r in caplog.records
            if "voice_session_end" in r.getMessage()
            or getattr(r, "event", "") == "voice_session_end"
        ]
        assert matches, "expected a voice_session_end log line"
        record = matches[-1]

        # The structured fields land in record.__dict__ via the logging
        # ``extra`` keyword. We assert the canonical set is present and
        # carries the values we passed in.
        expected = {
            "event": "voice_session_end",
            "session_id": "voice_openai_test_123",
            "model": "gpt-realtime-mini",
            "duration_s": 180,
            "cost_estimate_usd": pytest.approx(0.645, rel=0.01),
            "prompt_cache_hit": False,
            "first_audio_ms": 743,
            "ended_reason": "user_ended",
        }
        for key, expected_value in expected.items():
            assert hasattr(record, key), f"missing log field {key}"
            actual_value = getattr(record, key)
            if isinstance(expected_value, float) or hasattr(expected_value, "expected"):
                assert actual_value == expected_value, (
                    f"log field {key}: {actual_value} != {expected_value}"
                )
            else:
                assert actual_value == expected_value, (
                    f"log field {key}: {actual_value!r} != {expected_value!r}"
                )


# ---------------------------------------------------------------------------
# 7. Hybrid / Mock providers — no regression.
# ---------------------------------------------------------------------------

class TestNonOpenAIProvidersStillWork:
    @pytest.mark.asyncio
    async def test_mock_provider_start_session_does_not_carry_model_state(self):
        provider = rtvs.MockRealtimeVoiceProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Mock doesn't deal in models — provider_state shouldn't grow a
        # ``model`` key by accident.
        assert "model" not in handle.provider_state

    @pytest.mark.asyncio
    async def test_estimate_cost_safe_for_non_openai_sessions(self):
        # Broker passes the provider's ``model`` straight through; for
        # Mock/Hybrid this is the empty string or None. Either should
        # round-trip to zero cost without raising.
        assert rtvs.estimate_session_cost_usd(
            model="", duration_seconds=120, prompt_cache_hit=False,
        ) == 0.0
        assert rtvs.estimate_session_cost_usd(
            model=None, duration_seconds=120, prompt_cache_hit=False,  # type: ignore[arg-type]
        ) == 0.0
