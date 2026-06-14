"""
Voice session telemetry contract tests (#609 Phase D).

Locks the structured-event layer the ops dashboards + Parent Dashboard
scrape for the Talk-to-Buddy realtime voice surface. The contract:

  1. ``voice_telemetry`` exposes a canonical emitter per event, each
     writing a flat structured log record (``event=<name>`` in the
     record's ``extra``) so a JSON formatter serialises them un-nested.
  2. The events are PII-free: emitters take IDs, durations, and
     categorical fields ONLY — never transcript text or raw audio. The
     emitter signatures encode this (there is no ``text`` parameter).
  3. ``direction`` on a safety rejection is constrained to
     ``utterance`` | ``reply`` (any other value normalises to
     ``unknown`` rather than leaking a free-form string downstream).
  4. The broker fires ``voice_session_started`` once at session open and
     ``voice_session_ended`` once at close during a real mock WS session.
  5. The broker fires ``voice_session_safety_rejection`` when a turn is
     blocked, carrying the direction.

No network: the Mock provider + a bypassed safety MCP keep the broker
deterministic, mirroring ``test_voice_broker_contract.py``.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services import voice_telemetry as vt
from backend.src.services.database import (
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.realtime_voice_service import MockRealtimeVoiceProvider
from backend.src.services.user_service import UserData
from backend.src.services.voice_ephemeral_token import mint_voice_token


# ---------------------------------------------------------------------------
# 1. Each emitter writes a structured record with event=<name> + fields.
# ---------------------------------------------------------------------------

def _records_for(caplog, event: str):
    return [r for r in caplog.records if getattr(r, "event", "") == event]


class TestEmitterRecords:
    def test_started_emits_canonical_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_started(
                session_id="voice_sess_1",
                age_group="6-8",
                agent_id="agent_42",
                provider="mock",
            )
        rec = _records_for(caplog, vt.VOICE_SESSION_STARTED)
        assert rec, "expected a voice_session_started record"
        r = rec[-1]
        assert r.session_id == "voice_sess_1"
        assert r.age_group == "6-8"
        assert r.agent_id == "agent_42"
        assert r.provider == "mock"

    def test_ended_emits_duration_and_reason(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_ended(
                session_id="voice_sess_2",
                duration_seconds=187,
                ended_reason="user_ended",
            )
        r = _records_for(caplog, vt.VOICE_SESSION_ENDED)[-1]
        assert r.session_id == "voice_sess_2"
        assert r.duration_seconds == 187
        assert r.ended_reason == "user_ended"

    def test_safety_rejection_emits_direction_and_category(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_safety_rejection(
                session_id="voice_sess_3",
                direction="reply",
                category="reply_unsafe",
            )
        r = _records_for(caplog, vt.VOICE_SESSION_SAFETY_REJECTION)[-1]
        assert r.session_id == "voice_sess_3"
        assert r.direction == "reply"
        assert r.category == "reply_unsafe"

    def test_launch_flow_emitted_carries_flow(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_launch_flow_emitted(
                session_id="voice_sess_4",
                flow="image_story",
            )
        r = _records_for(caplog, vt.VOICE_SESSION_LAUNCH_FLOW_EMITTED)[-1]
        assert r.session_id == "voice_sess_4"
        assert r.flow == "image_story"

    def test_first_audio_ms_carries_value(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_first_audio_ms(
                session_id="voice_sess_5",
                first_audio_ms=812,
                age_group="9-12",
            )
        r = _records_for(caplog, vt.VOICE_SESSION_FIRST_AUDIO_MS)[-1]
        assert r.session_id == "voice_sess_5"
        assert r.first_audio_ms == 812
        assert r.age_group == "9-12"

    def test_interruption_count_carries_count(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_interruption_count(
                session_id="voice_sess_6",
                count=3,
            )
        r = _records_for(caplog, vt.VOICE_SESSION_INTERRUPTION_COUNT)[-1]
        assert r.session_id == "voice_sess_6"
        assert r.count == 3


# ---------------------------------------------------------------------------
# 2 + 3. PII-free + direction normalisation.
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_emitters_take_no_transcript_text(self):
        # Structural guarantee: none of the emitters accept a ``text`` or
        # ``transcript`` kwarg, so a caller cannot accidentally leak child
        # speech into the telemetry stream.
        import inspect

        for name in (
            "emit_voice_session_started",
            "emit_voice_session_ended",
            "emit_voice_session_safety_rejection",
            "emit_voice_session_launch_flow_emitted",
            "emit_voice_session_first_audio_ms",
            "emit_voice_session_interruption_count",
        ):
            params = set(inspect.signature(getattr(vt, name)).parameters)
            assert "text" not in params, f"{name} must not accept text"
            assert "transcript" not in params, f"{name} must not accept transcript"

    def test_unknown_direction_normalises(self, caplog):
        with caplog.at_level(logging.INFO, logger=vt.__name__):
            vt.emit_voice_session_safety_rejection(
                session_id="voice_sess_norm",
                direction="sideways",  # not utterance|reply
                category="x",
            )
        r = _records_for(caplog, vt.VOICE_SESSION_SAFETY_REJECTION)[-1]
        assert r.direction == "unknown"


# ---------------------------------------------------------------------------
# Broker integration — events fire during a real mock WS session.
# ---------------------------------------------------------------------------

PARENT_USER = UserData(
    user_id="voice_telemetry_parent",
    username="voice_telemetry_parent",
    email="parent@telemetry-test.com",
    password_hash="h",
    display_name="Parent",
    role="parent",
    created_at="",
    updated_at="",
)


async def _override_current_user() -> UserData:
    return PARENT_USER


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
                           is_active, is_verified, role, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            PARENT_USER.user_id, PARENT_USER.username, PARENT_USER.email,
            PARENT_USER.password_hash, PARENT_USER.display_name, 1, 1, "parent",
            now, now,
        ),
    )
    await db_manager.commit()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def consented_child(test_db):
    repo = ChildProfileRepository(db_manager)
    profile = await repo.create(
        user_id=PARENT_USER.user_id,
        child_id="child_telemetry_alpha",
        name="Ada",
        age_group="6-8",
        is_default=True,
    )
    await repo.update_consent(
        user_id=PARENT_USER.user_id,
        child_id=profile.child_id,
        microphone_consent=True,
        voice_conversation_consent=True,
        voice_session_quota_seconds=600,
    )
    return profile


async def _bypass_safety(text: str, target_age: int):
    return {"safety_score": 0.99, "passed": True}


async def _fail_safety(text: str, target_age: int):
    return {"safety_score": 0.10, "passed": False}


class TestBrokerEmitsLifecycleEvents:
    @pytest.mark.asyncio
    async def test_started_and_ended_fire_during_session(
        self, test_db, consented_child, monkeypatch, caplog,
    ):
        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
            provider="mock",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
        monkeypatch.setattr(voice_realtime, "_safety_check_text", _bypass_safety)
        try:
            with caplog.at_level(logging.INFO, logger=vt.__name__):
                client = TestClient(app)
                with client.websocket_connect(
                    f"/api/v1/me/agent/voice/stream?token={token}"
                ) as ws:
                    # Drive one full turn so the server deterministically
                    # progresses past start_session (emitting `started`)
                    # and forwards audio (emitting `first_audio_ms`). A
                    # bare client_done can race the portal thread's close
                    # before the broker reaches those emit points.
                    audio_b64 = base64.b64encode(b"\x00" * 200).decode("ascii")
                    ws.send_json({"type": "audio_chunk", "seq": 0, "audio_b64": audio_b64})
                    ws.send_json({"type": "vad_end", "seq": 0})
                    while True:
                        ev = ws.receive_json()
                        if ev["type"] == "audio_chunk":
                            break
                    ws.send_json({"type": "client_done"})
                    # Drain until the server closes the socket. The broker's
                    # finally block sends `session_end` and THEN closes the
                    # WS — by the time the client observes the close, every
                    # close-time telemetry emit (ended/first_audio/
                    # interruption) has already fired.
                    with pytest.raises(WebSocketDisconnect):
                        while True:
                            ws.receive_json()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        started = _records_for(caplog, vt.VOICE_SESSION_STARTED)
        ended = _records_for(caplog, vt.VOICE_SESSION_ENDED)
        first_audio = _records_for(caplog, vt.VOICE_SESSION_FIRST_AUDIO_MS)
        interruptions = _records_for(caplog, vt.VOICE_SESSION_INTERRUPTION_COUNT)
        assert len(started) == 1, "expected exactly one started event"
        assert len(ended) == 1, "expected exactly one ended event"
        assert started[0].session_id == persisted.session_id
        assert started[0].age_group == "6-8"
        assert ended[0].session_id == persisted.session_id
        assert ended[0].ended_reason == "user_ended"
        assert ended[0].duration_seconds >= 0
        # A completed turn forwarded audio → first-audio + interruption
        # (count 0) events fire exactly once at close.
        assert len(first_audio) == 1
        assert first_audio[0].first_audio_ms >= 0
        assert len(interruptions) == 1
        assert interruptions[0].count == 0

    @pytest.mark.asyncio
    async def test_safety_rejection_fires_on_blocked_reply(
        self, test_db, consented_child, monkeypatch, caplog,
    ):
        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
            provider="mock",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
        # Force the reply-side safety gate to fail so a safety_block fires.
        monkeypatch.setattr(voice_realtime, "_safety_check_text", _fail_safety)
        try:
            with caplog.at_level(logging.INFO, logger=vt.__name__):
                client = TestClient(app)
                with client.websocket_connect(
                    f"/api/v1/me/agent/voice/stream?token={token}"
                ) as ws:
                    audio_b64 = base64.b64encode(b"\x00" * 200).decode("ascii")
                    ws.send_json({"type": "audio_chunk", "seq": 0, "audio_b64": audio_b64})
                    ws.send_json({"type": "vad_end", "seq": 0})
                    # Drain until the safety_block envelope arrives.
                    while True:
                        ev = ws.receive_json()
                        if ev["type"] == "safety_block":
                            break
                    ws.send_json({"type": "client_done"})
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        rejections = _records_for(caplog, vt.VOICE_SESSION_SAFETY_REJECTION)
        assert rejections, "expected a safety rejection telemetry event"
        assert rejections[-1].direction == "reply"
