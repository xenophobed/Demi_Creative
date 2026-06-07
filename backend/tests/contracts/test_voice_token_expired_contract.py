"""
Expired-token WS handshake contract (#608 rescoped).

The ephemeral-token unit tests (#614) cover the verify-level behavior
(``test_expired_token_returns_none``). This story explicitly pins the
END-TO-END behavior at the WebSocket handshake: an expired token MUST
surface as ``error.code=auth_failed`` and close with policy code 1008,
identical to the bad-token / replay paths.

This guards against a regression where a future change to the broker
might swallow the expired case as a different error code (e.g.
``token_expired``), breaking the frontend's single auth-failure handler.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

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
from backend.src.services.realtime_voice_service import MockRealtimeVoiceProvider
from backend.src.services.user_service import UserData
from backend.src.services.voice_ephemeral_token import (
    _reset_nonce_store_for_tests,
    mint_voice_token,
)


PARENT_USER = UserData(
    user_id="voice_expired_parent",
    username="voice_expired_parent",
    email="parent@expired-test.com",
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
            None, "not_required", "free", "EXPRTK", None, now, now,
        ),
    )
    await db_manager.commit()
    _reset_nonce_store_for_tests()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def consented_child(test_db):
    repo = ChildProfileRepository(db_manager)
    profile = await repo.create(
        user_id=PARENT_USER.user_id,
        child_id="child_expired_alpha",
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


class TestExpiredTokenWsHandshake:
    @pytest.mark.asyncio
    async def test_expired_token_ws_handshake_returns_auth_failed(
        self, test_db, consented_child,
    ):
        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
            provider="mock",
        )
        # Mint with a zero TTL so the token is expired by the time
        # the WS handshake runs.
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=consented_child.child_id,
            ttl_seconds=0,
        )
        # Tiny sleep so PyJWT's clock check counts it as expired.
        time.sleep(0.01)

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                envelope = ws.receive_json()
                # The broker must surface expired tokens with the SAME
                # ``auth_failed`` code as bad / replayed tokens. The
                # frontend handles all three with a single recovery
                # path; a divergent code would break that.
                assert envelope["type"] == "error"
                assert envelope["code"] == "auth_failed", (
                    f"expired token must surface as auth_failed, "
                    f"got: {envelope}"
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)
