"""
WebRTC direct-mode transport contract tests (#647).

Locks the REST `/voice/session` surface and its safety-preserving transport
policy:

  - ``prefer_webrtc=true`` on the OpenAI Realtime provider still yields
    ``transport: "ws"``. Direct browser → OpenAI delivery is disabled until
    assistant output can pass through the server-side pre-delivery safety gate.
  - ``prefer_webrtc=true`` on a non-OpenAI provider (mock / hybrid)
    gracefully degrades to ``transport: "ws"`` (no 4xx — the WS broker
    is the universal fallback, never a refusal).
  - ``prefer_webrtc`` omitted → ``transport: "ws"`` (regression
    contract — pre-#647 clients keep current behavior).
  - The ``voice_sessions`` row records the transport used so the
    Phase D dashboard can compute adoption + p50 latency split.

Mock + Stub providers are used here — no real Anthropic / OpenAI calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services.database import (
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.sql_compat import column_exists
from backend.src.services.realtime_voice_service import (
    FinalTranscript,
    MockRealtimeVoiceProvider,
    SessionHandle,
)
from backend.src.services.user_service import UserData


PARENT_USER = UserData(
    user_id="voice_webrtc_parent",
    username="voice_webrtc_parent",
    email="parent@webrtc-test.com",
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
            None, "not_required", "free", "VOICEWRTC", None, now, now,
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
        child_id="child_webrtc_alpha",
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


# ---------------------------------------------------------------------------
# Minimal stub OpenAI-shaped provider so we don't hit the network. Mirrors
# the relevant slice of StubOpenAIRealtimeProvider from the broker tests.
# ---------------------------------------------------------------------------

class StubOpenAIProvider:
    name: str = "openai_realtime"

    def __init__(self, *, client_secret: str = "ek_stub_webrtc_xyz") -> None:
        self._secret = client_secret
        self.start_calls: int = 0
        self.close_calls: int = 0

    async def start_session(
        self, *, user_id: str, child_id: str, target_age: int,
        persona: str = "buddy_default",
        voice_premium_voice: bool = False,
        voice_premium_voice_consent: bool = False,
        **_kwargs: Any,
    ) -> SessionHandle:
        self.start_calls += 1
        return SessionHandle(
            session_id=f"voice_openai_stub_{user_id}_{child_id}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={
                "openai_client_secret": self._secret,
                "model": "gpt-realtime-mini",
                "expires_at": 1_900_000_000,
                "prompt_cache_hit": False,
            },
        )

    async def push_audio(self, handle: SessionHandle, audio_bytes: bytes) -> None:  # pragma: no cover
        return None

    async def finalize_utterance(self, handle: SessionHandle) -> FinalTranscript:  # pragma: no cover
        return FinalTranscript(
            success=True, text="", language="en", duration_ms=0,
            safety_passed=True, provider=self.name,
        )

    async def close(self, handle: SessionHandle) -> None:
        self.close_calls += 1


@pytest_asyncio.fixture
async def openai_client(test_db, monkeypatch):
    app.dependency_overrides[get_current_user] = _override_current_user
    voice_realtime._set_test_provider_override(StubOpenAIProvider())
    monkeypatch.setattr(voice_realtime, "_safety_check_text", _bypass_safety)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)
    voice_realtime._set_test_provider_override(None)


@pytest_asyncio.fixture
async def mock_client(test_db, monkeypatch):
    app.dependency_overrides[get_current_user] = _override_current_user
    voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
    monkeypatch.setattr(voice_realtime, "_safety_check_text", _bypass_safety)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)
    voice_realtime._set_test_provider_override(None)


# ===========================================================================
# Schema contract
# ===========================================================================

class TestSchemaContract:
    """The ``transport`` column exists and accepts both literal values."""

    @pytest.mark.asyncio
    async def test_voice_sessions_transport_column_exists(self, test_db):
        assert await column_exists(test_db, "voice_sessions", "transport")

    @pytest.mark.asyncio
    async def test_voice_sessions_transport_accepts_ws_and_webrtc(self, test_db):
        # FK requires a user row — fixture already seeded one.
        for sid, transport in [("vs_ws_1", "ws"), ("vs_rtc_1", "webrtc")]:
            await voice_session_repo.create_session(
                user_id=PARENT_USER.user_id,
                child_id="child_schema",
                provider="openai_realtime",
                session_id=sid,
                transport=transport,
            )
            persisted = await voice_session_repo.get_by_id(sid)
            assert persisted is not None
            assert persisted.transport == transport


# ===========================================================================
# REST /session contract — prefer_webrtc behavior
# ===========================================================================

class TestPreferWebRTCWithOpenAIProvider:
    """The OpenAI path stays on the server-relay transport for safety."""

    @pytest.mark.asyncio
    async def test_prefer_webrtc_true_stays_on_server_relay(
        self, openai_client, consented_child,
    ):
        response = await openai_client.post(
            "/api/v1/me/agent/voice/session?prefer_webrtc=true",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transport"] == "ws"
        assert body["openai_realtime_client_secret"] is None, (
            "direct-mode credentials must not be exposed while WebRTC is disabled"
        )

    @pytest.mark.asyncio
    async def test_prefer_webrtc_true_records_server_relay_transport(
        self, openai_client, consented_child,
    ):
        response = await openai_client.post(
            "/api/v1/me/agent/voice/session?prefer_webrtc=true",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["session_id"]
        persisted = await voice_session_repo.get_by_id(session_id)
        assert persisted is not None
        assert persisted.transport == "ws"


class TestPreferWebRTCWithMockProvider:
    """Non-OpenAI providers gracefully degrade to WS (never 4xx)."""

    @pytest.mark.asyncio
    async def test_mock_provider_falls_back_to_ws_silently(
        self, mock_client, consented_child,
    ):
        # The mock provider has no WebRTC story — the route must not 4xx;
        # the client gets ``transport: "ws"`` and runs the relay path.
        response = await mock_client.post(
            "/api/v1/me/agent/voice/session?prefer_webrtc=true",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transport"] == "ws"

    @pytest.mark.asyncio
    async def test_mock_provider_records_ws_transport_in_row(
        self, mock_client, consented_child,
    ):
        response = await mock_client.post(
            "/api/v1/me/agent/voice/session?prefer_webrtc=true",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["session_id"]
        persisted = await voice_session_repo.get_by_id(session_id)
        assert persisted is not None
        assert persisted.transport == "ws"


class TestDefaultTransportRegression:
    """``prefer_webrtc`` omitted → ``transport: "ws"`` for both providers."""

    @pytest.mark.asyncio
    async def test_openai_default_is_ws_when_prefer_webrtc_omitted(
        self, openai_client, consented_child,
    ):
        response = await openai_client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transport"] == "ws"
        # The pre-mint of the secret still happens for the WS path so the
        # client can stash it for a follow-up WebRTC try — that contract
        # is locked by the existing ``test_voice_broker_openai_provider_contract``
        # tests. Here we only assert the transport default.

    @pytest.mark.asyncio
    async def test_default_records_ws_transport_in_row(
        self, openai_client, consented_child,
    ):
        response = await openai_client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["session_id"]
        persisted = await voice_session_repo.get_by_id(session_id)
        assert persisted is not None
        assert persisted.transport == "ws"

    @pytest.mark.asyncio
    async def test_prefer_webrtc_false_is_equivalent_to_omitted(
        self, openai_client, consented_child,
    ):
        # Explicit false from a client that's flipped its flag off should
        # behave the same as the omitted default — pure WS path.
        response = await openai_client.post(
            "/api/v1/me/agent/voice/session?prefer_webrtc=false",
            json={"child_id": consented_child.child_id},
        )
        assert response.status_code == 200, response.text
        assert response.json()["transport"] == "ws"
