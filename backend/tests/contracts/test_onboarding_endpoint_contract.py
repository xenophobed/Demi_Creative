"""
Onboarding Endpoint Contract Tests (#440)

Black-box contract on POST /api/v1/me/onboarding/complete. Locks in:
  - 400 PARENT_CONSENT_REQUIRED when parent_consent != True
  - 412 AGENT_REQUIRED when no agent exists for (user, child_id)
  - 200 happy path: both onboarded_at and parent_consent_at set atomically
  - Idempotency: a replay returns the SAME timestamps as the first call
  - 401 when authentication is missing

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #440
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import (
    agent_repo,
    db_manager,
    user_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


# ---------------------------------------------------------------------------
# Test user — auth-overridden to a deterministic identity
# ---------------------------------------------------------------------------


_TEST_USER_A = UserData(
    user_id="onboarding_user_a",
    username="onboarding_a",
    email="ob_a@test.com",
    password_hash="h",
    display_name="OnboardingA",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)


async def _override_current_user() -> UserData:
    return _TEST_USER_A


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
            _TEST_USER_A.user_id,
            _TEST_USER_A.username,
            _TEST_USER_A.email,
            _TEST_USER_A.password_hash,
            _TEST_USER_A.display_name,
            1,
            1,
            "child",
            "free",
            "OBCODE",
            None,
            now,
            now,
        ),
    )
    await db_manager.commit()

    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def auth_client(test_db):
    """AsyncClient with auth dependency overridden to return _TEST_USER_A."""
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def anon_client(test_db):
    """AsyncClient WITHOUT the auth override — exercises the 401 path."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed_agent(child_id: str = "child_001") -> None:
    await agent_repo.upsert_agent(
        user_id=_TEST_USER_A.user_id,
        child_id=child_id,
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦁",
        agent_title="Brave Lion",
    )


# ---------------------------------------------------------------------------
# Parent-consent gate (400)
# ---------------------------------------------------------------------------


class TestParentConsentGate:
    @pytest.mark.asyncio
    async def test_consent_false_rejected(self, auth_client):
        await _seed_agent()
        r = await auth_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": False, "child_id": "child_001"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "PARENT_CONSENT_REQUIRED"


# ---------------------------------------------------------------------------
# Agent-required gate (412)
# ---------------------------------------------------------------------------


class TestAgentRequiredGate:
    @pytest.mark.asyncio
    async def test_no_agent_returns_412(self, auth_client):
        # No _seed_agent() call — there is no agent for this child_id.
        r = await auth_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": True, "child_id": "child_unbound"},
        )
        assert r.status_code == 412
        assert r.json()["detail"]["code"] == "AGENT_REQUIRED"


# ---------------------------------------------------------------------------
# Happy path — both timestamps set atomically
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_first_completion_sets_both_timestamps(self, auth_client):
        await _seed_agent()
        r = await auth_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": True, "child_id": "child_001"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["onboarded_at"] is not None
        assert body["parent_consent_at"] is not None
        assert body["has_agent"] is True

        # Verify the row in the DB also reflects both timestamps.
        fresh = await user_repo.get_by_id(_TEST_USER_A.user_id)
        assert fresh is not None
        assert fresh.onboarded_at is not None
        assert fresh.parent_consent_at is not None


# ---------------------------------------------------------------------------
# Idempotency — same timestamps on replay
# ---------------------------------------------------------------------------


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_same_timestamps(self, auth_client):
        await _seed_agent()
        first = await auth_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": True, "child_id": "child_001"},
        )
        assert first.status_code == 200, first.text
        first_body = first.json()

        second = await auth_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": True, "child_id": "child_001"},
        )
        assert second.status_code == 200, second.text
        second_body = second.json()

        assert first_body["onboarded_at"] == second_body["onboarded_at"], (
            "onboarded_at must not be overwritten on replay"
        )
        assert first_body["parent_consent_at"] == second_body["parent_consent_at"], (
            "parent_consent_at must not be overwritten on replay"
        )


# ---------------------------------------------------------------------------
# Auth gate (401)
# ---------------------------------------------------------------------------


class TestAuthRequired:
    @pytest.mark.asyncio
    async def test_missing_auth_returns_401(self, anon_client):
        r = await anon_client.post(
            "/api/v1/me/onboarding/complete",
            json={"parent_consent": True, "child_id": "child_001"},
        )
        assert r.status_code == 401
