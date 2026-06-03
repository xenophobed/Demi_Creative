"""
Talk to Buddy realtime voice — foundation contract tests (#611, epic #605).

This sub-story locks in the wire contract WITHOUT the implementation.
The route bodies return 501 / a documented WS error envelope; these
tests assert the contract surface so the frontend (#607.x) can code
against fixed shapes while sub-stories #606.2-#606.5 fill in the real
backend.

Anything that wants to "test the WS broker" or "test the OpenAI
provider" belongs in a later sub-story's contract test. This file
exists to make sure the FOUNDATION is honest about being a stub.
"""

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.api.models import (
    VoiceSessionStartRequest,
    VoiceSessionStartResponse,
    VoiceWSClientDoneEvent,
    VoiceWSErrorEvent,
    VoiceWSPartialTranscriptEvent,
    VoiceWSSafetyBlockEvent,
)
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services.database import db_manager
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.sql_compat import column_exists
from backend.src.services.user_service import UserData


PARENT_USER = UserData(
    user_id="voice_realtime_parent",
    username="voice_realtime_parent",
    email="parent@voice-test.com",
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
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def client(test_db):
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


# -------------------- Schema migration contract --------------------

class TestSchemaContract:
    """Migration adds three columns + creates the voice_sessions table."""

    @pytest.mark.asyncio
    async def test_voice_conversation_consent_column_exists(self, test_db):
        assert await column_exists(test_db, "child_profiles", "voice_conversation_consent")

    @pytest.mark.asyncio
    async def test_voice_persona_column_exists(self, test_db):
        assert await column_exists(test_db, "child_profiles", "voice_persona")

    @pytest.mark.asyncio
    async def test_voice_session_quota_seconds_column_exists(self, test_db):
        assert await column_exists(test_db, "child_profiles", "voice_session_quota_seconds")

    @pytest.mark.asyncio
    async def test_voice_sessions_table_has_expected_columns(self, test_db):
        # Sanity-check the new table's surface by inserting + reading back.
        # The voice_sessions FK requires a user row to exist first.
        await db_manager.execute(
            """
            INSERT INTO users (user_id, username, email, password_hash, display_name,
                               is_active, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("u1", "u1", "u1@test.com", "h", "U", 1, 1, "", ""),
        )
        await db_manager.execute(
            """
            INSERT INTO voice_sessions
                (session_id, user_id, child_id, started_at, ended_at,
                 duration_seconds, transcript_safety_score, termination_reason, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("voice_sess_1", "u1", "c1", "2026-06-01T00:00:00", None, None, None, None, None),
        )
        await db_manager.commit()
        row = await db_manager.fetchone(
            "SELECT * FROM voice_sessions WHERE session_id = ?", ("voice_sess_1",)
        )
        assert row is not None
        assert row["user_id"] == "u1"
        assert row["child_id"] == "c1"


# -------------------- Pydantic discriminated-union contract --------------------

class TestPydanticContracts:
    """Each Pydantic model imports + serializes cleanly."""

    def test_session_request_round_trips(self):
        req = VoiceSessionStartRequest(child_id="child_abc")
        assert req.persona is None
        as_json = req.model_dump()
        rehydrated = VoiceSessionStartRequest(**as_json)
        assert rehydrated.child_id == "child_abc"

    def test_session_response_required_fields(self):
        # Constructing the response forces all required fields to be present.
        from datetime import datetime
        resp = VoiceSessionStartResponse(
            session_id="voice_sess_xyz",
            ephemeral_token="t" * 32,
            expires_at=datetime(2026, 6, 1, 0, 1, 0),
            ws_url="/api/v1/me/agent/voice/stream",
            provider_config={"provider": "mock", "sample_rate_hz": 16_000, "audio_format": "pcm16"},
        )
        assert resp.provider_config.provider == "mock"

    def test_partial_transcript_event_discriminator(self):
        ev = VoiceWSPartialTranscriptEvent(type="partial_transcript", text="hello", seq=0)
        assert ev.type == "partial_transcript"

    def test_safety_block_direction_validates(self):
        ev = VoiceWSSafetyBlockEvent(
            type="safety_block", direction="reply", fallback_text="Let's try a different idea"
        )
        assert ev.direction in ("utterance", "reply")

    def test_client_done_event_round_trip(self):
        ev = VoiceWSClientDoneEvent(type="client_done")
        assert ev.type == "client_done"

    def test_error_event_carries_code_and_message(self):
        ev = VoiceWSErrorEvent(type="error", code="not_implemented", message="stub")
        assert ev.code == "not_implemented"


# -------------------- REST endpoint contract --------------------

class TestRestEndpointContract:
    """Foundation-PR REST contract is now superseded by #615.

    The 501 stub from #611 has been replaced by the real broker
    (test coverage lives in test_voice_broker_contract.py). What
    remains here is the request-validation invariant — Pydantic
    422 must fire BEFORE any route handler runs.
    """

    @pytest.mark.asyncio
    async def test_post_session_no_longer_returns_501(self, client):
        # Once #615 landed, the body is real — an unauthorized/missing-child
        # call surfaces a 404, NOT 501. The 501 detail code is gone.
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": "child_realtime_voice"},
        )
        assert response.status_code != 501
        body = response.json()
        if "detail" in body and isinstance(body["detail"], dict):
            assert body["detail"].get("code") != "VOICE_REALTIME_NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_post_session_validates_request_shape(self, client):
        # Missing required child_id → 422 from Pydantic, BEFORE the
        # route handler runs. This invariant survives #615.
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"persona": "buddy_default"},
        )
        assert response.status_code == 422


# -------------------- WebSocket endpoint contract --------------------

class TestWebSocketContract:
    """The WS handshake is now real (#615). Foundation-stub behavior is gone.

    The remaining invariant: a connection with NO token still gets an
    error envelope (now `auth_failed`, not `not_implemented`). Full WS
    coverage lives in test_voice_broker_contract.py.
    """

    def test_ws_without_token_emits_auth_failed(self):
        from fastapi.testclient import TestClient

        with TestClient(app) as test_client:
            with test_client.websocket_connect(
                "/api/v1/me/agent/voice/stream"
            ) as ws:
                envelope = ws.receive_json()
                assert envelope["type"] == "error"
                assert envelope["code"] == "auth_failed"

    def test_documented_error_shape_still_validates(self):
        # The error envelope the broker sends matches VoiceWSErrorEvent.
        # We synthesize a representative payload and round-trip it.
        envelope = json.loads(
            json.dumps({"type": "error", "code": "auth_failed", "message": "x"})
        )
        ev = VoiceWSErrorEvent(**envelope)
        assert ev.code == "auth_failed"
