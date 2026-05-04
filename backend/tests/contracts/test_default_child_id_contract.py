"""
default_child_id Wiring Contract Tests (#455)

Locks the cross-device buddy-identity invariant: PUT /me/agent must persist
the active child profile on users.default_child_id when none is set, and
must NEVER overwrite it on subsequent calls (set-once semantics).

Without this contract, a user logging in on a fresh browser would generate
a new local child_id, miss the existing buddy lookup, and re-trigger the
onboarding modal unwanted.

Parent Epic: #436
Issue: #455
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import agent_repo, db_manager, user_repo
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


_TEST_USER = UserData(
    user_id="dcid_user",
    username="dcid_user",
    email="dcid@test.com",
    password_hash="h",
    display_name="DCID",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)


_user_holder = {"user": _TEST_USER}


async def _override_current_user() -> UserData:
    # Re-fetch fresh to capture default_child_id changes from prior writes.
    fresh = await user_repo.get_by_id(_TEST_USER.user_id)
    return fresh if fresh else _user_holder["user"]


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
            _TEST_USER.user_id,
            _TEST_USER.username,
            _TEST_USER.email,
            _TEST_USER.password_hash,
            _TEST_USER.display_name,
            1,
            1,
            "child",
            "free",
            "DCIDCODE",
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
async def client(test_db):
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


def _safety_response(score: float) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps({"safety_score": score})}]
    }


def _valid_body(child_id: str = "child_first") -> dict:
    return {
        "agent_name": "Sparkle",
        "agent_avatar_id": "emoji:🦊",
        "agent_title": "Story Wizard",
        "child_id": child_id,
    }


# ---------------------------------------------------------------------------
# Set-on-first-PUT
# ---------------------------------------------------------------------------


class TestSetsOnFirstPut:
    @pytest.mark.asyncio
    async def test_first_put_writes_default_child_id(self, client):
        # Sanity: starts unset.
        before = await user_repo.get_by_id(_TEST_USER.user_id)
        assert before.default_child_id is None

        with patch(
            "backend.src.api.routes.agents.check_content_safety",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r = await client.put("/api/v1/me/agent", json=_valid_body("child_first"))
        assert r.status_code == 200, r.text

        after = await user_repo.get_by_id(_TEST_USER.user_id)
        assert after.default_child_id == "child_first"


# ---------------------------------------------------------------------------
# Set-once semantics: never overwrite
# ---------------------------------------------------------------------------


class TestNeverOverwrites:
    @pytest.mark.asyncio
    async def test_second_put_for_different_child_does_not_change_default(
        self, client
    ):
        # Pre-set default_child_id to child-A by the first PUT.
        with patch(
            "backend.src.api.routes.agents.check_content_safety",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r1 = await client.put("/api/v1/me/agent", json=_valid_body("child-A"))
            assert r1.status_code == 200, r1.text

        mid = await user_repo.get_by_id(_TEST_USER.user_id)
        assert mid.default_child_id == "child-A"

        # Now PUT a SECOND agent for a DIFFERENT child profile.
        with patch(
            "backend.src.api.routes.agents.check_content_safety",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r2 = await client.put("/api/v1/me/agent", json=_valid_body("child-B"))
            assert r2.status_code == 200, r2.text

        # default_child_id MUST still be child-A.
        after = await user_repo.get_by_id(_TEST_USER.user_id)
        assert after.default_child_id == "child-A", (
            "default_child_id was overwritten on a subsequent PUT — set-once "
            "semantics broken"
        )

        # But the agent for child-B must still have been created.
        agent_b = await agent_repo.get_agent(_TEST_USER.user_id, "child-B")
        assert agent_b is not None, "agent for child-B was not persisted"
        assert agent_b.child_id == "child-B"
