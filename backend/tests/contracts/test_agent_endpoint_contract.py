"""
Agent Endpoint Contract Tests (#439)

Black-box contract on PUT/GET /api/v1/me/agent. Locks in:
  - Avatar whitelist enforcement (INVALID_AVATAR).
  - Safety check is invoked on agent_name and on free-text agent_title.
  - Curated titles bypass the safety check (pre-vetted).
  - Safety MCP failures must surface as 503 SAFETY_UNAVAILABLE
    (fail-closed, never silent pass-through).
  - Upsert is idempotent on (user_id, child_id).
  - Distinct (user_id, child_id) pairs map to distinct rows.

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #439
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import db_manager, agent_repo
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData, UserRepository


# ---------------------------------------------------------------------------
# Test users — two distinct identities so we can probe (user, child) keying
# ---------------------------------------------------------------------------


_TEST_USER_A = UserData(
    user_id="agent_test_user_a",
    username="agent_user_a",
    email="a@test.com",
    password_hash="h",
    display_name="A",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)


_current_user_holder = {"user": _TEST_USER_A}


async def _override_current_user() -> UserData:
    return _current_user_holder["user"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_db():
    """In-memory DB shared with the global db_manager so the route sees it.

    Also seeds the auth-overridden test user into the users table so
    the FK on user_agents.user_id is satisfied.
    """
    # Save and replace the adapter on the global db_manager so app code
    # using `from .database import agent_repo` hits our test DB.
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    # Seed the user row directly so FK(user_id -> users.user_id) is
    # satisfied for the deterministic user_id we pinned on _TEST_USER_A.
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
            "TESTCODE",
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
    """AsyncClient with auth dependency overridden to return _TEST_USER_A."""
    _current_user_holder["user"] = _TEST_USER_A
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


def _safety_response(score: float) -> dict:
    """Build the MCP-shaped result envelope the safety tool returns."""
    return {
        "content": [
            {"type": "text", "text": json.dumps({"safety_score": score})}
        ]
    }


def _valid_body(**overrides) -> dict:
    body = {
        "agent_name": "Sparkle",
        "agent_avatar_id": "emoji:🦊",
        "agent_title": "Story Wizard",  # curated -> skips title safety
        "child_id": "child_test_001",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Avatar whitelist
# ---------------------------------------------------------------------------


class TestAvatarWhitelist:
    """Avatar must come from the curated emoji whitelist."""

    @pytest.mark.asyncio
    async def test_rejects_avatar_outside_whitelist(self, client):
        # 🦖 is intentionally NOT in the curated list.
        body = _valid_body(agent_avatar_id="emoji:🦖")
        # Even though we hit the avatar branch first, mock safety to be safe.
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_AVATAR"

    @pytest.mark.asyncio
    async def test_accepts_avatar_in_whitelist(self, client):
        body = _valid_body(agent_avatar_id="emoji:🐶")
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Safety check on name
# ---------------------------------------------------------------------------


class TestNameSafety:
    """Agent name must always pass the safety check."""

    @pytest.mark.asyncio
    async def test_unsafe_name_rejected(self, client):
        # Mock returns safety_score below 0.85 -> route must reject.
        body = _valid_body(agent_name="something_unsafe")
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.50)),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "UNSAFE_AGENT_NAME"

    @pytest.mark.asyncio
    async def test_safe_name_accepted(self, client):
        body = _valid_body(agent_name="Sparkle")
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Curated title bypass
# ---------------------------------------------------------------------------


class TestCuratedTitleBypass:
    """Curated titles skip the safety check; free-text titles do not."""

    @pytest.mark.asyncio
    async def test_curated_title_skips_title_safety_check(self, client):
        """Brave Lion is in CURATED_TITLES -> safety MCP called once (for name only)."""
        body = _valid_body(agent_title="Brave Lion")
        mock_safety = AsyncMock(return_value=_safety_response(0.99))
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=mock_safety,
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 200, r.text
        # Exactly one call — for the name. The title bypassed because curated.
        assert mock_safety.call_count == 1

    @pytest.mark.asyncio
    async def test_free_text_title_invokes_title_safety_check(self, client):
        """Non-curated title -> safety MCP called twice (title + name)."""
        body = _valid_body(agent_title="My Cool Title")
        mock_safety = AsyncMock(return_value=_safety_response(0.99))
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=mock_safety,
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 200, r.text
        # Title check + name check = 2 calls.
        assert mock_safety.call_count == 2


# ---------------------------------------------------------------------------
# Fail-closed when safety MCP is unavailable
# ---------------------------------------------------------------------------


class TestSafetyFailClosed:
    """Safety MCP failure must surface as 503 SAFETY_UNAVAILABLE."""

    @pytest.mark.asyncio
    async def test_mcp_raises_returns_503(self, client):
        """When the MCP tool raises, the route must return 503 with SAFETY_UNAVAILABLE."""
        body = _valid_body()  # curated title, so only name is safety-checked
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "SAFETY_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_mcp_error_envelope_returns_503(self, client):
        """When the MCP returns an error envelope (no safety_score), fail closed."""
        body = _valid_body()
        bad = {
            "content": [
                {"type": "text", "text": json.dumps({"error": "MCP unavailable"})}
            ]
        }
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=bad),
        ):
            r = await client.put("/api/v1/me/agent", json=body)
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "SAFETY_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Upsert idempotency and key separation
# ---------------------------------------------------------------------------


class TestUpsertIdempotency:
    """PUT /me/agent must be idempotent on (user_id, child_id)."""

    @pytest.mark.asyncio
    async def test_repeated_put_same_body_same_agent_id(self, client):
        body = _valid_body(child_id="child_idempotent")
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r1 = await client.put("/api/v1/me/agent", json=body)
            r2 = await client.put("/api/v1/me/agent", json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["agent_id"] == r2.json()["agent_id"]

    @pytest.mark.asyncio
    async def test_different_child_id_yields_distinct_agent(self, client):
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            r1 = await client.put(
                "/api/v1/me/agent", json=_valid_body(child_id="child_one")
            )
            r2 = await client.put(
                "/api/v1/me/agent", json=_valid_body(child_id="child_two")
            )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["agent_id"] != r2.json()["agent_id"]


# ---------------------------------------------------------------------------
# GET /me/agent
# ---------------------------------------------------------------------------


class TestGetAgent:
    """GET /api/v1/me/agent returns 404 when no row exists."""

    @pytest.mark.asyncio
    async def test_unknown_child_id_returns_404(self, client):
        r = await client.get(
            "/api/v1/me/agent", params={"child_id": "child_does_not_exist"}
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "AGENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_agent_after_upsert(self, client):
        body = _valid_body(child_id="child_get_test")
        with patch(
            "backend.src.api.routes.agents.check_content_safety.handler",
            new=AsyncMock(return_value=_safety_response(0.99)),
        ):
            put = await client.put("/api/v1/me/agent", json=body)
        assert put.status_code == 200
        get = await client.get(
            "/api/v1/me/agent", params={"child_id": "child_get_test"}
        )
        assert get.status_code == 200
        assert get.json()["agent_id"] == put.json()["agent_id"]
