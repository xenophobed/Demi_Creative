"""
Hub Reactions Endpoint Contract Tests (#454)

Locks the surface of:
  POST /api/v1/hub/posts/{post_id}/reactions
  GET  /api/v1/hub/posts/{post_id}/reactions

Coverage:
  - Idempotent toggle (insert -> active=True; remove -> active=False)
  - Invalid reaction_type rejected (400)
  - Public post: any auth user can react
  - Private post: non-member rejected (403); member OK
  - Soft-deleted post: 404 POST_NOT_FOUND
  - User can hold all three reactions simultaneously

Parent Epic: #437
Issue: #454
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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


_OWNER = UserData(
    user_id="rx_owner",
    username="rx_owner",
    email="rxo@test.com",
    password_hash="h",
    display_name="Owner",
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
    default_child_id="rx-owner-child",
)
_PEER = UserData(
    user_id="rx_peer",
    username="rx_peer",
    email="rxp@test.com",
    password_hash="h",
    display_name="Peer",
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
    default_child_id="rx-peer-child",
)

_holder: dict = {"user": _OWNER}


async def _override_current_user() -> UserData:
    return _holder["user"]


def _switch(user: UserData) -> None:
    _holder["user"] = user


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    from datetime import datetime as _dt
    now = _dt.now().isoformat()
    for u in (_OWNER, _PEER):
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
    _holder["user"] = _OWNER
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


def _safety(score: float) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps({"safety_score": score})}]
    }


async def _seed_buddy(user: UserData) -> None:
    await agent_repo.upsert_agent(
        user_id=user.user_id,
        child_id=user.default_child_id,
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦁",
        agent_title="Brave Lion",
    )


async def _make_public_post(client: AsyncClient) -> str:
    await _seed_buddy(_OWNER)
    r1 = await client.post(
        "/api/v1/hub/groups",
        json={"name": "Reacts", "visibility": "public"},
    )
    gid = r1.json()["group_id"]
    with patch(
        "backend.src.api.routes.hub.posts.check_content_safety.handler",
        new=AsyncMock(return_value=_safety(0.99)),
    ):
        r2 = await client.post(
            f"/api/v1/hub/groups/{gid}/posts",
            json={"source_artifact_type": "art_story", "source_id": "x"},
        )
    return r2.json()["post_id"]


# ---------------------------------------------------------------------------
# Toggle
# ---------------------------------------------------------------------------


class TestToggle:
    @pytest.mark.asyncio
    async def test_first_call_inserts_then_second_removes(self, client):
        post_id = await _make_public_post(client)
        # Switch to peer so the reactor isn't the author (more realistic).
        _switch(_PEER)
        r1 = await client.post(
            f"/api/v1/hub/posts/{post_id}/reactions",
            json={"reaction_type": "heart"},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["active"] is True
        assert r1.json()["counts"]["heart"] == 1
        assert "heart" in r1.json()["viewer_reactions"]

        r2 = await client.post(
            f"/api/v1/hub/posts/{post_id}/reactions",
            json={"reaction_type": "heart"},
        )
        assert r2.status_code == 200
        assert r2.json()["active"] is False
        assert r2.json()["counts"]["heart"] == 0
        assert r2.json()["viewer_reactions"] == []

    @pytest.mark.asyncio
    async def test_invalid_reaction_type_rejected(self, client):
        post_id = await _make_public_post(client)
        r = await client.post(
            f"/api/v1/hub/posts/{post_id}/reactions",
            json={"reaction_type": "thumbs_down"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_REACTION_TYPE"

    @pytest.mark.asyncio
    async def test_user_can_hold_all_three(self, client):
        post_id = await _make_public_post(client)
        _switch(_PEER)
        for kind in ("heart", "star", "wow"):
            r = await client.post(
                f"/api/v1/hub/posts/{post_id}/reactions",
                json={"reaction_type": kind},
            )
            assert r.status_code == 200, r.text
            assert r.json()["active"] is True

        # GET to confirm.
        r = await client.get(f"/api/v1/hub/posts/{post_id}/reactions")
        assert r.status_code == 200
        body = r.json()
        assert sorted(body["viewer_reactions"]) == ["heart", "star", "wow"]
        assert body["counts"] == {"heart": 1, "star": 1, "wow": 1}


class TestVisibilityGate:
    @pytest.mark.asyncio
    async def test_post_in_private_group_rejects_non_member(self, client):
        await _seed_buddy(_OWNER)
        # Owner creates private group + post.
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "P", "visibility": "private"},
        )
        gid = r1.json()["group_id"]
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety.handler",
            new=AsyncMock(return_value=_safety(0.99)),
        ):
            r2 = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "secret"},
            )
        post_id = r2.json()["post_id"]

        _switch(_PEER)
        r = await client.post(
            f"/api/v1/hub/posts/{post_id}/reactions",
            json={"reaction_type": "heart"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "NOT_A_MEMBER"

    @pytest.mark.asyncio
    async def test_unknown_post_returns_404(self, client):
        r = await client.post(
            "/api/v1/hub/posts/missing/reactions",
            json={"reaction_type": "heart"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "POST_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_soft_deleted_post_returns_404(self, client):
        post_id = await _make_public_post(client)
        await hub_post_repo.soft_delete(post_id, reason="test")
        _switch(_PEER)
        r = await client.post(
            f"/api/v1/hub/posts/{post_id}/reactions",
            json={"reaction_type": "heart"},
        )
        assert r.status_code == 404


class TestGetReactions:
    @pytest.mark.asyncio
    async def test_get_returns_zero_counts_when_empty(self, client):
        post_id = await _make_public_post(client)
        r = await client.get(f"/api/v1/hub/posts/{post_id}/reactions")
        assert r.status_code == 200
        body = r.json()
        assert body["counts"] == {"heart": 0, "star": 0, "wow": 0}
        assert body["viewer_reactions"] == []
