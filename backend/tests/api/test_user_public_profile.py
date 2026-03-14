"""
Tests for public user profile endpoint.

Verifies that GET /api/v1/users/{user_id} only exposes public fields
and that authenticated endpoints still return the full profile.

Fixes #186 — public user lookup must not expose private account fields.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.src.services.user_service import UserData

# The user returned by the mocked repository
_PUBLIC_USER = UserData(
    user_id="public_user_123",
    username="alice",
    email="alice@secret.example.com",
    password_hash="hashed_pw",
    display_name="Alice W.",
    avatar_url="https://cdn.example.com/alice.png",
    is_active=True,
    is_verified=True,
    created_at="2025-06-01T00:00:00",
    updated_at="2025-06-01T00:00:00",
    last_login_at="2025-06-15T12:00:00",
)

PRIVATE_FIELDS = {"email", "is_active", "is_verified", "last_login_at"}
PUBLIC_FIELDS = {"user_id", "username", "display_name", "avatar_url", "created_at"}


@pytest.mark.asyncio
async def test_public_profile_returns_only_public_fields(test_client):
    """GET /api/v1/users/{user_id} must return only public fields."""
    with patch(
        "backend.src.services.database.user_repo",
    ) as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=_PUBLIC_USER)
        resp = await test_client.get(f"/api/v1/users/{_PUBLIC_USER.user_id}")

    assert resp.status_code == 200
    data = resp.json()

    # All public fields present
    for field in PUBLIC_FIELDS:
        assert field in data, f"Expected public field '{field}' in response"

    # No private fields leaked
    for field in PRIVATE_FIELDS:
        assert field not in data, f"Private field '{field}' must NOT appear in public profile"


@pytest.mark.asyncio
async def test_public_profile_values_are_correct(test_client):
    """Returned public field values must match the stored user."""
    with patch(
        "backend.src.services.database.user_repo",
    ) as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=_PUBLIC_USER)
        resp = await test_client.get(f"/api/v1/users/{_PUBLIC_USER.user_id}")

    data = resp.json()
    assert data["user_id"] == _PUBLIC_USER.user_id
    assert data["username"] == _PUBLIC_USER.username
    assert data["display_name"] == _PUBLIC_USER.display_name
    assert data["avatar_url"] == _PUBLIC_USER.avatar_url


@pytest.mark.asyncio
async def test_public_profile_404_for_unknown_user(test_client):
    """GET /api/v1/users/{unknown_id} returns 404."""
    with patch(
        "backend.src.services.database.user_repo",
    ) as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=None)
        resp = await test_client.get("/api/v1/users/nonexistent_user")

    assert resp.status_code == 404


# Authenticated user with valid timestamps for _user_to_response
_AUTH_USER = UserData(
    user_id="test_user",
    username="test_user",
    email="test@example.com",
    password_hash="test_hash",
    display_name="Test User",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="2025-01-01T00:00:00",
    updated_at="2025-01-01T00:00:00",
    last_login_at="2025-06-15T12:00:00",
)


@pytest.mark.asyncio
async def test_authenticated_me_returns_full_profile(test_client):
    """GET /api/v1/users/me (authenticated) must still include private fields."""
    from backend.src.main import app
    from backend.src.api.deps import get_current_user

    async def _override():
        return _AUTH_USER

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await test_client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer fake_token"},
        )
    finally:
        # Restore the original test override from conftest
        from backend.tests.api.conftest import _fake_get_current_user
        app.dependency_overrides[get_current_user] = _fake_get_current_user

    assert resp.status_code == 200
    data = resp.json()

    # Private fields must be present on authenticated endpoint
    for field in ("email", "is_active", "is_verified"):
        assert field in data, f"Authenticated /me must include '{field}'"

    # Verify private fields are NOT in the public model's field set
    from backend.src.api.models import PublicUserResponse
    public_field_names = set(PublicUserResponse.model_fields.keys())
    for field in PRIVATE_FIELDS:
        assert field not in public_field_names, (
            f"'{field}' must not be in PublicUserResponse schema"
        )
