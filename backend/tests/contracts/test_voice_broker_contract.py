"""
Voice broker contract tests (#615).

Covers the REST `/voice/session` + WS `/voice/stream` real implementation
(the 501 stubs from #611 are replaced). Tests use the Mock provider so
no real Whisper/ElevenLabs calls fire. The point is to lock the
broker's event ordering and gate semantics — provider correctness is
covered by `test_hybrid_realtime_voice_contract.py`.
"""

import base64
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services.database import (
    child_profile_repo,
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


PARENT_USER = UserData(
    user_id="voice_broker_parent",
    username="voice_broker_parent",
    email="parent@broker-test.com",
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
                           is_active, is_verified, role, parent_email, consent_status,
                           membership_tier, referral_code, referred_by,
                           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            PARENT_USER.user_id, PARENT_USER.username, PARENT_USER.email,
            PARENT_USER.password_hash, PARENT_USER.display_name, 1, 1, "parent",
            None, "not_required", "free", "VOICEBKR", None, now, now,
        ),
    )
    await db_manager.commit()

    yield fresh

    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def consented_child(test_db):
    """A child profile with BOTH consents granted and a generous quota."""
    repo = ChildProfileRepository(db_manager)
    profile = await repo.create(
        user_id=PARENT_USER.user_id,
        child_id="child_voice_alpha",
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
    """Test helper: short-circuit the safety MCP so existing broker
    contract tests don't trigger real Anthropic calls.

    The voice broker (#645) added a per-reply safety gate; this fixture
    keeps the mock-provider happy path deterministic. Other suites
    (test_voice_safety_pre_tts_contract.py) cover the gate semantics.
    """
    return {"safety_score": 0.99, "passed": True}


@pytest_asyncio.fixture
async def client(test_db, monkeypatch):
    app.dependency_overrides[get_current_user] = _override_current_user
    # Force the mock provider so we never call real Whisper/ElevenLabs.
    voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
    monkeypatch.setattr(
        voice_realtime, "_safety_check_text", _bypass_safety,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)
    voice_realtime._set_test_provider_override(None)


# ============================================================================
# REST /session contract
# ============================================================================

class TestSessionEndpoint:
    @pytest.mark.asyncio
    async def test_happy_path_returns_token_and_ws_url(self, client, consented_child):
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["session_id"].startswith("voice_sess_")
        assert len(body["ephemeral_token"]) > 20
        assert body["ws_url"] == "/api/v1/me/agent/voice/stream"
        assert body["provider_config"]["provider"] == "mock"

    @pytest.mark.asyncio
    async def test_unknown_child_returns_404(self, client, test_db):
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": "child_does_not_exist"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "CHILD_PROFILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_missing_voice_consent_returns_409(self, client, test_db):
        # Create a child with mic consent but NOT voice_conversation_consent.
        repo = ChildProfileRepository(db_manager)
        await repo.create(
            user_id=PARENT_USER.user_id,
            child_id="child_no_voice",
            name="No-voice",
            age_group="6-8",
        )
        await repo.update_consent(
            user_id=PARENT_USER.user_id,
            child_id="child_no_voice",
            microphone_consent=True,
        )

        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": "child_no_voice"},
        )
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "VOICE_CONSENT_REQUIRED"
        assert "voice_conversation_consent" in detail["missing"]
        assert "microphone_consent" not in detail["missing"]

    @pytest.mark.asyncio
    async def test_missing_microphone_consent_returns_409(self, client, test_db):
        repo = ChildProfileRepository(db_manager)
        await repo.create(
            user_id=PARENT_USER.user_id,
            child_id="child_no_mic",
            name="No-mic",
            age_group="6-8",
        )
        # Only voice_conversation_consent without microphone_consent — broker
        # still refuses since the mic is the precondition.
        await repo.update_consent(
            user_id=PARENT_USER.user_id,
            child_id="child_no_mic",
            voice_conversation_consent=True,
        )

        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": "child_no_mic"},
        )
        assert response.status_code == 409
        assert "microphone_consent" in response.json()["detail"]["missing"]

    @pytest.mark.asyncio
    async def test_quota_exhausted_returns_429(self, client, test_db):
        repo = ChildProfileRepository(db_manager)
        await repo.create(
            user_id=PARENT_USER.user_id,
            child_id="child_quota",
            name="Q",
            age_group="6-8",
        )
        await repo.update_consent(
            user_id=PARENT_USER.user_id,
            child_id="child_quota",
            microphone_consent=True,
            voice_conversation_consent=True,
            voice_session_quota_seconds=60,
        )
        # Pre-debit the quota by inserting an already-ended session.
        s = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id="child_quota",
        )
        await voice_session_repo.end_session(
            session_id=s.session_id,
            reason="user_ended",
            duration_seconds=120,
        )

        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": "child_quota"},
        )
        assert response.status_code == 429
        assert response.json()["detail"]["code"] == "VOICE_QUOTA_EXHAUSTED"


# ============================================================================
# WS broker contract (sync TestClient — WS support)
# ============================================================================

class TestWebSocketBroker:
    def _setup_sync_test_client(self):
        """Sync TestClient with the same overrides as the async client."""
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
        # The broker now runs a per-reply safety gate (#645). Bypass it
        # for the sync TestClient tests so deterministic mock-provider
        # bytes still flow through the WS without hitting Anthropic.
        self._saved_safety = voice_realtime._safety_check_text
        voice_realtime._safety_check_text = _bypass_safety  # type: ignore[assignment]
        return TestClient(app)

    def _teardown_sync_test_client(self):
        app.dependency_overrides.pop(get_current_user, None)
        voice_realtime._set_test_provider_override(None)
        voice_realtime._safety_check_text = self._saved_safety  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_bad_token_closes_with_auth_failed(
        self, test_db, consented_child,
    ):
        client = self._setup_sync_test_client()
        try:
            with client.websocket_connect(
                "/api/v1/me/agent/voice/stream?token=not-a-real-token"
            ) as ws:
                envelope = ws.receive_json()
                assert envelope["type"] == "error"
                assert envelope["code"] == "auth_failed"
        finally:
            self._teardown_sync_test_client()

    @pytest.mark.asyncio
    async def test_missing_token_closes_with_auth_failed(
        self, test_db, consented_child,
    ):
        client = self._setup_sync_test_client()
        try:
            with client.websocket_connect(
                "/api/v1/me/agent/voice/stream"
            ) as ws:
                envelope = ws.receive_json()
                assert envelope["type"] == "error"
                assert envelope["code"] == "auth_failed"
        finally:
            self._teardown_sync_test_client()

    @pytest.mark.asyncio
    async def test_happy_path_vad_end_emits_transcript_and_audio(
        self, test_db, consented_child,
    ):
        # First mint a valid token via REST so the token has a real
        # session_id row in voice_sessions (end_session lookup needs it).
        from backend.src.services.voice_ephemeral_token import mint_voice_token

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

        client = self._setup_sync_test_client()
        try:
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                # Push one audio chunk, then VAD-end.
                audio_b64 = base64.b64encode(b"\x00" * 200).decode("ascii")
                ws.send_json({
                    "type": "audio_chunk", "seq": 0, "audio_b64": audio_b64,
                })
                ws.send_json({"type": "vad_end", "seq": 0})

                events: list = []
                # Drain until we've seen final_transcript + assistant_text + at
                # least one audio_chunk back, then client_done to close.
                while True:
                    ev = ws.receive_json()
                    events.append(ev)
                    if ev["type"] == "audio_chunk":
                        break

                event_types = [e["type"] for e in events]
                assert "final_transcript" in event_types
                assert "assistant_text" in event_types
                assert event_types[-1] == "audio_chunk"
                # MockRealtimeVoiceProvider returns this canned transcript.
                transcripts = [
                    e for e in events if e["type"] == "final_transcript"
                ]
                assert transcripts[0]["text"] == "hello buddy this is a mock transcript"

                ws.send_json({"type": "client_done"})
        finally:
            self._teardown_sync_test_client()

    @pytest.mark.asyncio
    async def test_token_is_single_use_replay_rejected(
        self, test_db, consented_child,
    ):
        from backend.src.services.voice_ephemeral_token import mint_voice_token

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

        client = self._setup_sync_test_client()
        try:
            # First use — verify drains the nonce.
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({"type": "client_done"})

            # Second use of the same token must be rejected.
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                envelope = ws.receive_json()
                assert envelope["type"] == "error"
                assert envelope["code"] == "auth_failed"
        finally:
            self._teardown_sync_test_client()

    @pytest.mark.asyncio
    async def test_bad_event_type_emits_bad_event_error(
        self, test_db, consented_child,
    ):
        from backend.src.services.voice_ephemeral_token import mint_voice_token

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

        client = self._setup_sync_test_client()
        try:
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({"type": "wat", "garbage": 42})
                envelope = ws.receive_json()
                assert envelope["type"] == "error"
                assert envelope["code"] == "bad_event"
                ws.send_json({"type": "client_done"})
        finally:
            self._teardown_sync_test_client()


# ============================================================================
# Session-row writes
# ============================================================================

class TestSessionRowPersistence:
    @pytest.mark.asyncio
    async def test_broker_calls_end_session_on_client_done(
        self, test_db, consented_child, monkeypatch,
    ):
        """The broker MUST close the session row when the client sends
        `client_done`. Spying on `end_session` avoids the SQLite
        in-memory cross-context visibility issue we'd hit if we queried
        the DB after the TestClient sync→async bridge exits.
        """
        from backend.src.services.voice_ephemeral_token import mint_voice_token
        from unittest.mock import AsyncMock

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

        end_spy = AsyncMock(return_value=None)
        # Patch the module-level singleton the broker imports from.
        monkeypatch.setattr(
            voice_realtime.voice_session_repo,
            "end_session",
            end_spy,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _bypass_safety,
        )
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({"type": "client_done"})
                # Drain until the server closes the socket so the broker's
                # finally block (where end_session is called) has fully run
                # before we assert. Without this the assertion races the
                # portal thread — any added latency on the session-start
                # path (e.g. the #609 telemetry agent_id lookup) could let
                # the assertion fire before end_session is awaited.
                with pytest.raises(WebSocketDisconnect):
                    while True:
                        ws.receive_json()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        assert end_spy.await_count == 1, "broker must call end_session exactly once"
        call_kwargs = end_spy.await_args.kwargs
        assert call_kwargs["session_id"] == persisted.session_id
        assert call_kwargs["reason"] == "user_ended"
        assert call_kwargs["duration_seconds"] is not None
        assert call_kwargs["duration_seconds"] >= 0
