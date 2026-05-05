"""
Hub Group Endpoint Contract Tests (#448)

Locks the surface of:
  GET  /api/v1/hub/groups
  POST /api/v1/hub/groups
  GET  /api/v1/hub/groups/{group_id}
  POST /api/v1/hub/groups/{group_id}/join

Privacy guarantees verified:
  - Non-owner GET /hub/groups/{id} scrubs invite_token
  - List response scrubs invite_token for the caller's joined privates
  - Create response DOES expose invite_token (to the inviter, once)

Parent Epic: #437
Issue: #448
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import db_manager, group_repo
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


_OWNER = UserData(
    user_id="hub_owner",
    username="hub_owner",
    email="hub_owner@test.com",
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
    user_id="hub_peer",
    username="hub_peer",
    email="hub_peer@test.com",
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
    user_id="hub_fresh",
    username="hub_fresh",
    email="hub_fresh@test.com",
    password_hash="h",
    display_name="Fresh",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
    nickname=None,
    onboarded_at=None,        # NOT onboarded
    parent_consent_at=None,
    default_child_id=None,
)


_holder: dict = {"user": _OWNER}


async def _override_current_user() -> UserData:
    return _holder["user"]


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    # Seed both owner and peer rows so FKs on hub_groups / memberships hold.
    from datetime import datetime as _dt
    now = _dt.now().isoformat()
    for user in (_OWNER, _PEER, _FRESH):
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
                user.user_id,
                user.username,
                user.email,
                user.password_hash,
                user.display_name,
                1,
                1,
                "child",
                "free",
                f"CODE_{user.user_id}",
                None,
                now,
                now,
                user.onboarded_at,
                user.parent_consent_at,
                user.default_child_id,
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


def _switch_user(user: UserData) -> None:
    _holder["user"] = user


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateGroup:
    @pytest.mark.asyncio
    async def test_public_create_returns_no_invite_token_in_payload(self, client):
        r = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Dragons", "visibility": "public"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["visibility"] == "public"
        # Public groups never have an invite_token.
        assert body.get("invite_token") in (None, "")
        assert body["slug"] == "dragons"

    @pytest.mark.asyncio
    async def test_private_create_exposes_invite_token_to_owner(self, client):
        r = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Cousins", "visibility": "private"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["visibility"] == "private"
        assert body["invite_token"], "create response must expose invite_token to owner"
        assert len(body["invite_token"]) >= 16

    @pytest.mark.asyncio
    async def test_create_requires_onboarded(self, client):
        _switch_user(_FRESH)
        r = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Should fail", "visibility": "public"},
        )
        assert r.status_code == 412
        assert r.json()["detail"]["code"] == "ONBOARDING_REQUIRED"

    @pytest.mark.asyncio
    async def test_invalid_visibility_rejected(self, client):
        r = await client.post(
            "/api/v1/hub/groups",
            json={"name": "x", "visibility": "everyone"},
        )
        # Either Pydantic 422 (string mismatch) or our 400 INVALID_VISIBILITY.
        assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGetGroup:
    @pytest.mark.asyncio
    async def test_owner_sees_invite_token(self, client):
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Mine", "visibility": "private"},
        )
        gid = r1.json()["group_id"]
        # Same owner GET — should see the token.
        r2 = await client.get(f"/api/v1/hub/groups/{gid}")
        assert r2.status_code == 200
        assert r2.json()["invite_token"], "owner must see invite_token on GET"

    @pytest.mark.asyncio
    async def test_non_owner_does_not_see_invite_token(self, client):
        # Owner creates.
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "OwnerOnly", "visibility": "private"},
        )
        gid = r1.json()["group_id"]
        # Switch to a different user; GET must scrub the token.
        _switch_user(_PEER)
        r2 = await client.get(f"/api/v1/hub/groups/{gid}")
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("invite_token") in (None, ""), (
            "non-owner GET must NOT expose invite_token"
        )

    @pytest.mark.asyncio
    async def test_unknown_group_returns_404(self, client):
        r = await client.get("/api/v1/hub/groups/does-not-exist")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "GROUP_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_by_slug_returns_same_group_as_by_id(self, client):
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "SlugLookup", "visibility": "public"},
        )
        assert r1.status_code == 201, r1.text
        gid = r1.json()["group_id"]
        slug = r1.json()["slug"]
        assert slug == "sluglookup"

        r_by_id = await client.get(f"/api/v1/hub/groups/{gid}")
        r_by_slug = await client.get(f"/api/v1/hub/groups/{slug}")
        assert r_by_id.status_code == 200, r_by_id.text
        assert r_by_slug.status_code == 200, r_by_slug.text
        assert r_by_id.json()["group_id"] == r_by_slug.json()["group_id"]


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------


class TestJoinGroup:
    @pytest.mark.asyncio
    async def test_public_open_join(self, client):
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "PubJoin", "visibility": "public"},
        )
        gid = r1.json()["group_id"]
        _switch_user(_PEER)
        r2 = await client.post(f"/api/v1/hub/groups/{gid}/join")
        assert r2.status_code == 200, r2.text
        assert r2.json()["role"] == "member"

    @pytest.mark.asyncio
    async def test_private_requires_invite_token(self, client):
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "PrivJoin", "visibility": "private"},
        )
        token = r1.json()["invite_token"]
        gid = r1.json()["group_id"]

        _switch_user(_PEER)
        # No token — 403.
        r2 = await client.post(f"/api/v1/hub/groups/{gid}/join")
        assert r2.status_code == 403
        assert r2.json()["detail"]["code"] == "INVALID_INVITE_TOKEN"

        # Wrong token — 403.
        r3 = await client.post(f"/api/v1/hub/groups/{gid}/join?invite=bogus")
        assert r3.status_code == 403

        # Right token — 200.
        r4 = await client.post(
            f"/api/v1/hub/groups/{gid}/join?invite={token}"
        )
        assert r4.status_code == 200, r4.text

    @pytest.mark.asyncio
    async def test_join_requires_onboarded(self, client):
        r1 = await client.post(
            "/api/v1/hub/groups",
            json={"name": "Need-onboard", "visibility": "public"},
        )
        gid = r1.json()["group_id"]
        _switch_user(_FRESH)
        r2 = await client.post(f"/api/v1/hub/groups/{gid}/join")
        assert r2.status_code == 412
        assert r2.json()["detail"]["code"] == "ONBOARDING_REQUIRED"

    @pytest.mark.asyncio
    async def test_unknown_group_returns_404(self, client):
        r = await client.post("/api/v1/hub/groups/missing/join")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListGroups:
    @pytest.mark.asyncio
    async def test_list_includes_public_and_my_private(self, client):
        # Owner creates one of each.
        await client.post(
            "/api/v1/hub/groups",
            json={"name": "PublicOne", "visibility": "public"},
        )
        await client.post(
            "/api/v1/hub/groups",
            json={"name": "PrivateOne", "visibility": "private"},
        )

        # Owner lists — should see both.
        r = await client.get("/api/v1/hub/groups")
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        names = {it["name"] for it in items}
        assert {"PublicOne", "PrivateOne"} <= names

        # Switch to peer (not a member) — sees public, NOT the private.
        _switch_user(_PEER)
        r2 = await client.get("/api/v1/hub/groups")
        names2 = {it["name"] for it in r2.json()["items"]}
        assert "PublicOne" in names2
        assert "PrivateOne" not in names2

    @pytest.mark.asyncio
    async def test_list_scrubs_invite_token_for_non_owners(self, client):
        await client.post(
            "/api/v1/hub/groups",
            json={"name": "Hidden token", "visibility": "private"},
        )
        # Owner list — invite_token is None in the listing payload because
        # we keep the create-response as the only place it's exposed.
        r = await client.get("/api/v1/hub/groups")
        assert r.status_code == 200
        for it in r.json()["items"]:
            # The list endpoint does NOT echo invite_token even to owners,
            # because list payloads are wider blast-radius than create.
            assert it.get("invite_token") in (None, "")
