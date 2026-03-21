"""
Tests for parent role feature (#232).

Verifies:
1. UserResponse includes `role` field
2. Authenticated /me endpoint returns role
3. Parent role is NOT exposed on public profile
4. Role defaults to 'child' for existing users
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.src.services.database.user_repository import UserData


# A parent user
_PARENT_USER = UserData(
    user_id="parent_user_1",
    username="parent_jane",
    email="jane@example.com",
    password_hash="hashed_pw",
    display_name="Jane (Parent)",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    role="parent",
    created_at="2025-06-01T00:00:00",
    updated_at="2025-06-01T00:00:00",
    last_login_at="2025-06-15T12:00:00",
)

# A child user (default role)
_CHILD_USER = UserData(
    user_id="child_user_1",
    username="kid_sam",
    email="sam@example.com",
    password_hash="hashed_pw",
    display_name="Sam",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    role="child",
    created_at="2025-06-01T00:00:00",
    updated_at="2025-06-01T00:00:00",
    last_login_at=None,
)


@pytest.mark.asyncio
async def test_me_endpoint_returns_role_for_parent(test_client):
    """GET /api/v1/users/me must include role='parent' for parent users."""
    from backend.src.main import app
    from backend.src.api.deps import get_current_user

    async def _override():
        return _PARENT_USER

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await test_client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer fake_token"},
        )
    finally:
        from backend.tests.api.conftest import _fake_get_current_user
        app.dependency_overrides[get_current_user] = _fake_get_current_user

    assert resp.status_code == 200
    data = resp.json()
    assert "role" in data, "UserResponse must include 'role' field"
    assert data["role"] == "parent"


@pytest.mark.asyncio
async def test_me_endpoint_returns_role_child_by_default(test_client):
    """GET /api/v1/users/me must include role='child' for child users."""
    from backend.src.main import app
    from backend.src.api.deps import get_current_user

    async def _override():
        return _CHILD_USER

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await test_client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer fake_token"},
        )
    finally:
        from backend.tests.api.conftest import _fake_get_current_user
        app.dependency_overrides[get_current_user] = _fake_get_current_user

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "child"


@pytest.mark.asyncio
async def test_public_profile_does_not_expose_role(test_client):
    """GET /api/v1/users/{user_id} must NOT expose role field."""
    with patch(
        "backend.src.services.database.user_repo",
    ) as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=_PARENT_USER)
        resp = await test_client.get(f"/api/v1/users/{_PARENT_USER.user_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert "role" not in data, "Public profile must NOT expose 'role' field"


@pytest.mark.asyncio
async def test_role_defaults_to_child():
    """UserData without explicit role should default to 'child'."""
    user = UserData(
        user_id="u1",
        username="test",
        email="t@t.com",
        password_hash="h",
        created_at="",
        updated_at="",
    )
    assert user.role == "child"
