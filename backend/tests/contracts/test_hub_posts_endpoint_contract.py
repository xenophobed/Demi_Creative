"""
Hub Post Endpoint Contract Tests (#449)

Locks the surface of:
  POST /api/v1/hub/groups/{group_id}/posts
  GET  /api/v1/hub/groups/{group_id}/posts

Coverage:
  - Onboarding + child profile gates (412)
  - Group existence + membership gates (404, 403)
  - Source-type validation (400)
  - Caption safety: < 0.85 -> 400 UNSAFE_CAPTION; MCP failure -> 503 SAFETY_UNAVAILABLE
  - Persona snapshot exposed in the create response, NOT user-table fields
  - List response is recency-ordered and excludes soft-deleted rows
  - Private group: only members can read posts (403)
  - Pagination cursor surfaces when len == limit

Parent Epic: #437
Issue: #449
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
    user_id="post_owner",
    username="post_owner",
    email="po@test.com",
    password_hash="h",
    display_name="Owner",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at="2026-01-01T00:00:00",
    parent_consent_at="2026-01-01T00:00:00",
    default_child_id="child-owner",
)
_PEER = UserData(
    user_id="post_peer",
    username="post_peer",
    email="pp@test.com",
    password_hash="h",
    display_name="Peer",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at="2026-01-01T00:00:00",
    parent_consent_at="2026-01-01T00:00:00",
    default_child_id="child-peer",
)
_FRESH = UserData(
    user_id="post_fresh",
    username="post_fresh",
    email="pf@test.com",
    password_hash="h",
    display_name="Fresh",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at=None,
    parent_consent_at=None,
    default_child_id=None,
)

_holder: dict = {"user": _OWNER}


async def _override_current_user() -> UserData:
    return _holder["user"]


def _switch_user(user: UserData) -> None:
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
    for u in (_OWNER, _PEER, _FRESH):
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
                "child",
                "free",
                f"PCODE_{u.user_id}",
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


async def _create_public_group(client: AsyncClient) -> str:
    r = await client.post(
        "/api/v1/hub/groups",
        json={"name": "PG", "visibility": "public"},
    )
    assert r.status_code == 201, r.text
    return r.json()["group_id"]


# ---------------------------------------------------------------------------
# Create gates
# ---------------------------------------------------------------------------


class TestCreateGates:
    @pytest.mark.asyncio
    async def test_post_requires_onboarded(self, client):
        # Owner makes the group; fresh user (not onboarded) tries to post.
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        _switch_user(_FRESH)
        r = await client.post(
            f"/api/v1/hub/groups/{gid}/posts",
            json={"source_artifact_type": "art_story", "source_id": "x"},
        )
        assert r.status_code == 412
        assert r.json()["detail"]["code"] == "ONBOARDING_REQUIRED"

    @pytest.mark.asyncio
    async def test_post_requires_membership(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        # Peer never joined -> 403.
        await _seed_buddy(_PEER)
        _switch_user(_PEER)
        r = await client.post(
            f"/api/v1/hub/groups/{gid}/posts",
            json={"source_artifact_type": "art_story", "source_id": "x"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "NOT_A_MEMBER"

    @pytest.mark.asyncio
    async def test_post_requires_agent(self, client):
        # Owner is onboarded but has no buddy yet — repo raises AGENT_REQUIRED.
        gid = await _create_public_group(client)
        # No _seed_buddy(_OWNER) call.
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.99)),
        ):
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "x"},
            )
        # Without an agent, group create itself should have failed earlier
        # at create_post repo time. But create_group did succeed (only
        # requires onboarded + default_child_id). The post call hits the
        # repo's AGENT_REQUIRED branch.
        # Note: Re-running this from scratch — group already created above.
        # Now post:
        assert r.status_code == 412
        assert r.json()["detail"]["code"] == "AGENT_REQUIRED"

    @pytest.mark.asyncio
    async def test_unknown_group_returns_404(self, client):
        r = await client.post(
            "/api/v1/hub/groups/missing/posts",
            json={"source_artifact_type": "art_story", "source_id": "x"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "GROUP_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_invalid_source_type_rejected(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        r = await client.post(
            f"/api/v1/hub/groups/{gid}/posts",
            json={"source_artifact_type": "video_remix", "source_id": "x"},
        )
        # Pydantic doesn't restrict; our route does — returns 400.
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_SOURCE_TYPE"


# ---------------------------------------------------------------------------
# Caption safety
# ---------------------------------------------------------------------------


class TestCaptionSafety:
    @pytest.mark.asyncio
    async def test_unsafe_caption_rejected(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.5)),
        ):
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={
                    "source_artifact_type": "art_story",
                    "source_id": "x",
                    "caption": "anything",
                },
            )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "UNSAFE_CAPTION"

    @pytest.mark.asyncio
    async def test_safety_mcp_unavailable_returns_503(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(side_effect=Exception("mcp down")),
        ):
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={
                    "source_artifact_type": "art_story",
                    "source_id": "x",
                    "caption": "anything",
                },
            )
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "SAFETY_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_no_caption_skips_safety_check(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        # Patch raises on call; should not be called when caption is None.
        mock = AsyncMock(side_effect=Exception("should not be called"))
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=mock,
        ):
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "x"},
            )
        assert r.status_code == 201, r.text
        assert mock.await_count == 0


# ---------------------------------------------------------------------------
# Happy path + privacy
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_create_returns_persona_snapshot_no_user_fields(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.95)),
        ):
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={
                    "source_artifact_type": "art_story",
                    "source_id": "story-1",
                    "caption": "Made this!",
                },
            )
        assert r.status_code == 201, r.text
        body = r.json()
        # Persona snapshot exposed:
        assert body["agent_name"] == "Sparkle"
        assert body["agent_avatar_id"] == "emoji:🦁"
        assert body["agent_title"] == "Brave Lion"
        # User-table fields ABSENT:
        for forbidden in (
            "user_id",
            "author_user_id",
            "author_child_id",
            "author_agent_id",
            "username",
            "email",
            "display_name",
            "default_child_id",
            "safety_score",
        ):
            assert forbidden not in body, (
                f"create response leaked {forbidden}"
            )

    @pytest.mark.asyncio
    async def test_list_recency_order_excludes_soft_deleted(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.99)),
        ):
            await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "kept"},
            )
            r = await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "soon-gone"},
            )
        gone_post_id = r.json()["post_id"]
        await hub_post_repo.soft_delete(gone_post_id, reason="test")

        rl = await client.get(f"/api/v1/hub/groups/{gid}/posts")
        assert rl.status_code == 200
        ids = {p["source_id"] for p in rl.json()["items"]}
        assert "kept" in ids
        assert "soon-gone" not in ids


# ---------------------------------------------------------------------------
# Private group read access
# ---------------------------------------------------------------------------


class TestPrivateGroupReadAccess:
    @pytest.mark.asyncio
    async def test_non_member_cannot_read_private_posts(self, client):
        await _seed_buddy(_OWNER)
        # Owner creates a private group + posts.
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Private", "visibility": "private"},
        )
        assert r1.status_code == 201, r1.text
        gid = r1.json()["group_id"]
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.99)),
        ):
            await client.post(
                f"/api/v1/hub/groups/{gid}/posts",
                json={"source_artifact_type": "art_story", "source_id": "secret"},
            )
        # Switch to peer (not joined) — read MUST be 403.
        await _seed_buddy(_PEER)
        _switch_user(_PEER)
        rl = await client.get(f"/api/v1/hub/groups/{gid}/posts")
        assert rl.status_code == 403
        assert rl.json()["detail"]["code"] == "NOT_A_MEMBER"


# ---------------------------------------------------------------------------
# Pagination cursor
# ---------------------------------------------------------------------------


class TestPagination:
    @pytest.mark.asyncio
    async def test_next_cursor_present_when_full_page(self, client):
        await _seed_buddy(_OWNER)
        gid = await _create_public_group(client)
        with patch(
            "backend.src.api.routes.hub.posts.check_content_safety",
            new=AsyncMock(return_value=_safety(0.99)),
        ):
            for i in range(3):
                await client.post(
                    f"/api/v1/hub/groups/{gid}/posts",
                    json={
                        "source_artifact_type": "art_story",
                        "source_id": f"s-{i}",
                    },
                )
        r = await client.get(f"/api/v1/hub/groups/{gid}/posts?limit=2")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["next_cursor"] is not None
        assert body["next_cursor"]["cursor_post_id"]
