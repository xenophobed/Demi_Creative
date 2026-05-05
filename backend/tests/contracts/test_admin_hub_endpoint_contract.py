"""
Admin Hub Moderation Contract Tests (#456)

Locks the surface of:
  POST /api/v1/admin/hub/posts/{post_id}/remove

Coverage:
  - Non-admin caller -> 403
  - Unknown post_id -> 404 POST_NOT_FOUND
  - Happy path: removed_at + removed_reason set; post disappears from
    GET /hub/groups/{id}/posts
  - Idempotent: replay returns already_removed=True with the same
    removed_at unchanged
  - Provenance: hub_posts.removed_reason is preserved verbatim

Parent Epic: #437
Issue: #456
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_admin_user, get_current_user
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


_ADMIN = UserData(
    user_id="admin_user",
    username="admin_user",
    email="admin@test.com",
    password_hash="h",
    display_name="Admin",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    role="parent",
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at="2026-01-01T00:00:00",
    parent_consent_at="2026-01-01T00:00:00",
    default_child_id="admin-child",
)
_NON_ADMIN = UserData(
    user_id="non_admin",
    username="non_admin",
    email="non_admin@test.com",
    password_hash="h",
    display_name="Plain",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    role="child",
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at="2026-01-01T00:00:00",
    parent_consent_at="2026-01-01T00:00:00",
    default_child_id="non-admin-child",
)

_holder: dict = {"current": _ADMIN, "admin": _ADMIN}


async def _override_current_user() -> UserData:
    return _holder["current"]


async def _override_admin_user() -> UserData:
    # The route uses Depends(get_admin_user). The override returns the
    # holder's admin (set to non-admin user when we want to simulate
    # the 403 path) — we trip the 403 ourselves by raising HTTPException
    # in the override when the simulated caller is not admin.
    user = _holder["admin"]
    if user is _NON_ADMIN:
        from fastapi import HTTPException, status as _s
        raise HTTPException(
            status_code=_s.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    from datetime import datetime as _dt
    now = _dt.now().isoformat()
    for u in (_ADMIN, _NON_ADMIN):
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
                u.user_id,
                u.username,
                u.email,
                u.password_hash,
                u.display_name,
                1,
                1,
                u.role,
                "free",
                f"CODE_{u.user_id}",
                None,
                now,
                now,
                u.onboarded_at,
                u.parent_consent_at,
                u.default_child_id,
            ),
        )
    await db_manager.commit()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def client(test_db):
    _holder["current"] = _ADMIN
    _holder["admin"] = _ADMIN
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_admin_user] = _override_admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_admin_user, None)


def _safety(score: float) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps({"safety_score": score})}]
    }


async def _create_post(client: AsyncClient) -> str:
    """Owner creates buddy + group + a post; returns post_id."""
    await agent_repo.upsert_agent(
        user_id=_ADMIN.user_id,
        child_id=_ADMIN.default_child_id,
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦁",
        agent_title="Brave Lion",
    )
    r1 = await client.post(
        "/api/v1/hub/groups",
        json={"name": "Mod", "visibility": "public"},
    )
    assert r1.status_code == 201, r1.text
    gid = r1.json()["group_id"]
    with patch(
        "backend.src.api.routes.hub.posts.check_content_safety.handler",
        new=AsyncMock(return_value=_safety(0.99)),
    ):
        r2 = await client.post(
            f"/api/v1/hub/groups/{gid}/posts",
            json={"source_artifact_type": "art_story", "source_id": "to-remove"},
        )
    assert r2.status_code == 201, r2.text
    return r2.json()["post_id"], gid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRemoveHubPost:
    @pytest.mark.asyncio
    async def test_unknown_post_returns_404(self, client):
        r = await client.post(
            "/api/v1/admin/hub/posts/missing/remove",
            json={"reason": "spam"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "POST_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_non_admin_caller_returns_403(self, client):
        post_id, _gid = await _create_post(client)
        # Flip the simulated admin to non-admin -> override raises 403.
        _holder["admin"] = _NON_ADMIN
        r = await client.post(
            f"/api/v1/admin/hub/posts/{post_id}/remove",
            json={"reason": "spam"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_remove_marks_post_and_strips_from_feed(self, client):
        post_id, gid = await _create_post(client)

        r = await client.post(
            f"/api/v1/admin/hub/posts/{post_id}/remove",
            json={"reason": "tmp policy violation"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["post_id"] == post_id
        assert body["removed_at"]
        assert body["removed_reason"] == "tmp policy violation"
        assert body["already_removed"] is False

        # Feed must no longer include it.
        feed = await client.get(f"/api/v1/hub/groups/{gid}/posts")
        ids = {p["post_id"] for p in feed.json()["items"]}
        assert post_id not in ids

    @pytest.mark.asyncio
    async def test_idempotent_replay(self, client):
        post_id, _gid = await _create_post(client)
        r1 = await client.post(
            f"/api/v1/admin/hub/posts/{post_id}/remove",
            json={"reason": "first"},
        )
        first = r1.json()
        r2 = await client.post(
            f"/api/v1/admin/hub/posts/{post_id}/remove",
            json={"reason": "second-should-be-ignored"},
        )
        second = r2.json()
        assert r2.status_code == 200
        assert second["already_removed"] is True
        # First reason wins; second call doesn't overwrite.
        assert second["removed_reason"] == "first"
        assert second["removed_at"] == first["removed_at"]

    @pytest.mark.asyncio
    async def test_no_reason_is_allowed(self, client):
        post_id, _gid = await _create_post(client)
        r = await client.post(
            f"/api/v1/admin/hub/posts/{post_id}/remove",
            json={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["removed_reason"] is None
