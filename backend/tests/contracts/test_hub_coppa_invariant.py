"""COPPA Invariant Contract Tests for Content Hub

Locks the privacy guardrail for Content Hub (Epic #437): hub read endpoints
MUST NEVER return any users-table column. Originally landed skip-guarded
in #450 — once #449 ships routes/hub/posts.py, the import succeeds and
these tests run for real.

The walker positive-control test runs unconditionally — it guarantees the
generic helper actually fails on a planted violation, so we never get a
false sense of safety from any skipped test.

Related: #450 (this file), parent epic #437, depends on #447 + #448 + #449.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.contracts._pii_walker import assert_no_pii

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import (
    agent_repo,
    db_manager,
    group_repo,
    hub_post_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


# Import-based skip guard. With #448 + #449 on the branch the import
# succeeds; we keep the guard so the file stays robust if someone refactors
# the hub package away.
try:
    from backend.src.api.routes import hub  # type: ignore  # noqa: F401

    _HUB_AVAILABLE = True
except Exception:  # pragma: no cover
    _HUB_AVAILABLE = False


# Forbidden lists — single-sourced design contract.
FORBIDDEN_USER_KEYS: frozenset[str] = frozenset(
    {
        "user_id",
        "username",
        "email",
        "display_name",
        "avatar_url",
        "role",
        "membership_tier",
        "referral_code",
        "referred_by",
        "password_hash",
        "parent_consent_at",
        "nickname",
        "onboarded_at",
        "default_child_id",
    }
)


_CANARY_EMAIL = "pii.canary@test.invalid"
_CANARY_DISPLAY_NAME = "USER_PII_DISPLAY_NAME_xZ8q"
_CANARY_USERNAME = "user_pii_canary_username_xZ8q"


_TEST_USER = UserData(
    user_id="coppa_test_user",
    username=_CANARY_USERNAME,
    email=_CANARY_EMAIL,
    password_hash="not-a-real-hash",  # noqa: S106 - test fixture
    display_name=_CANARY_DISPLAY_NAME,
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at="2026-01-01T00:00:00",
    parent_consent_at="2026-01-01T00:00:00",
    default_child_id="coppa-child",
)


async def _override_current_user() -> UserData:
    return _TEST_USER


# ---------------------------------------------------------------------------
# Positive control — runs unconditionally.
# ---------------------------------------------------------------------------
def test_walker_catches_planted_pii_in_fixture() -> None:
    """Positive control: the walker must fail on a deliberately planted leak."""
    poisoned_payload = {
        "posts": [{"post_id": "p1", "author": {"user_id": "uX"}}]
    }
    with pytest.raises(AssertionError) as excinfo:
        assert_no_pii(
            poisoned_payload,
            forbidden_keys=FORBIDDEN_USER_KEYS,
            forbidden_strings=set(),
        )
    assert "user_id" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Hub-dependent fixtures
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
            created_at, updated_at, onboarded_at, parent_consent_at,
            default_child_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "COPPACODE",
            None,
            now,
            now,
            _TEST_USER.onboarded_at,
            _TEST_USER.parent_consent_at,
            _TEST_USER.default_child_id,
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


async def _seed_buddy() -> None:
    await agent_repo.upsert_agent(
        user_id=_TEST_USER.user_id,
        child_id=_TEST_USER.default_child_id,
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦁",
        agent_title="Brave Lion",
    )


# ---------------------------------------------------------------------------
# Hub-dependent tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HUB_AVAILABLE, reason="hub routes not yet implemented (#449)"
)
@pytest.mark.asyncio
async def test_get_group_posts_response_contains_no_user_pii(client) -> None:
    await _seed_buddy()

    # Owner creates a public group + a post.
    r1 = await client.post(
        "/api/v1/hub/groups",
        json={"name": "COPPA Public", "visibility": "public"},
    )
    assert r1.status_code == 201, r1.text
    group_id = r1.json()["group_id"]

    with patch(
        "backend.src.api.routes.hub.posts.check_content_safety.handler",
        new=AsyncMock(return_value=_safety_response(0.99)),
    ):
        r2 = await client.post(
            f"/api/v1/hub/groups/{group_id}/posts",
            json={
                "source_artifact_type": "art_story",
                "source_id": "story-1",
                "caption": "Made this!",
            },
        )
    assert r2.status_code == 201, r2.text

    r3 = await client.get(f"/api/v1/hub/groups/{group_id}/posts")
    assert r3.status_code == 200, r3.text
    payload = r3.json()

    canary_strings = {
        _CANARY_EMAIL,
        _CANARY_DISPLAY_NAME,
        _CANARY_USERNAME,
        _TEST_USER.user_id,
    }

    assert_no_pii(
        payload,
        forbidden_keys=FORBIDDEN_USER_KEYS,
        forbidden_strings=canary_strings,
    )


@pytest.mark.skipif(
    not _HUB_AVAILABLE, reason="hub routes not yet implemented (#449)"
)
@pytest.mark.asyncio
async def test_get_group_detail_response_contains_no_user_pii(client) -> None:
    await _seed_buddy()
    r1 = await client.post(
        "/api/v1/hub/groups",
        json={"name": "COPPA Detail", "visibility": "public"},
    )
    assert r1.status_code == 201, r1.text
    group_id = r1.json()["group_id"]

    r2 = await client.get(f"/api/v1/hub/groups/{group_id}")
    assert r2.status_code == 200, r2.text
    payload = r2.json()

    canary_strings = {
        _CANARY_EMAIL,
        _CANARY_DISPLAY_NAME,
        _CANARY_USERNAME,
        _TEST_USER.user_id,
    }

    assert_no_pii(
        payload,
        forbidden_keys=FORBIDDEN_USER_KEYS,
        forbidden_strings=canary_strings,
    )
