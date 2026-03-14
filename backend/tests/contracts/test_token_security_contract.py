"""
Token Security Contract Tests

Ensures:
- Tokens are stored as SHA-256 hashes, never as plaintext
- Token validation works correctly with hashed storage
- Password change revokes all existing tokens
- New login after password change produces a working token

Related: #191
"""

import hashlib
import pytest

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.user_service import UserService


@pytest.fixture
async def db(tmp_path):
    """Create an in-memory test database with full schema."""
    db_path = str(tmp_path / "test_tokens.db")
    manager = DatabaseManager(db_path=db_path)
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


@pytest.fixture
async def service(db):
    """UserService wired to the test database."""
    svc = UserService()
    svc._db = db
    # Wire the repo to use the same DB
    svc._repo._db = db
    return svc


async def _register_user(service: UserService, username: str = "testuser") -> "AuthResult":
    """Helper: register a user and return the AuthResult."""
    result = await service.register(
        username=username,
        email=f"{username}@example.com",
        password="secure-password-123",
        display_name="Test User",
    )
    assert result.success, f"Registration failed: {result.error}"
    return result


class TestTokenHashedAtRest:
    """Tokens stored in the database must be hashed, not plaintext."""

    @pytest.mark.asyncio
    async def test_stored_token_differs_from_raw_token(self, service, db):
        """The token column in the DB must NOT contain the raw token."""
        result = await _register_user(service)
        raw_token = result.token.access_token

        row = await db.fetchone(
            "SELECT token FROM tokens WHERE user_id = ?",
            (result.user.user_id,),
        )
        assert row is not None, "Token row should exist"
        assert row["token"] != raw_token, (
            "Raw token must not be stored in the database"
        )

    @pytest.mark.asyncio
    async def test_stored_token_is_sha256_of_raw(self, service, db):
        """The stored value must be the SHA-256 hex digest of the raw token."""
        result = await _register_user(service)
        raw_token = result.token.access_token
        expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        row = await db.fetchone(
            "SELECT token FROM tokens WHERE user_id = ?",
            (result.user.user_id,),
        )
        assert row["token"] == expected_hash


class TestTokenValidation:
    """Token validation must work correctly with hashed storage."""

    @pytest.mark.asyncio
    async def test_validate_with_correct_raw_token(self, service):
        """Validating with the raw token the user received must succeed."""
        result = await _register_user(service)
        raw_token = result.token.access_token

        user = await service.validate_token(raw_token)
        assert user is not None
        assert user.user_id == result.user.user_id

    @pytest.mark.asyncio
    async def test_validate_with_wrong_token_fails(self, service):
        """A random token must not validate."""
        await _register_user(service)
        user = await service.validate_token("totally-wrong-token")
        assert user is None

    @pytest.mark.asyncio
    async def test_logout_with_raw_token(self, service):
        """Logout using the raw token must succeed and invalidate it."""
        result = await _register_user(service)
        raw_token = result.token.access_token

        logged_out = await service.logout(raw_token)
        assert logged_out is True

        user = await service.validate_token(raw_token)
        assert user is None


class TestPasswordChangeRevokesTokens:
    """Changing password must revoke all existing tokens."""

    @pytest.mark.asyncio
    async def test_old_token_rejected_after_password_change(self, service):
        """After password change, previously valid tokens must be rejected."""
        result = await _register_user(service)
        old_token = result.token.access_token

        # Verify old token works before password change
        user = await service.validate_token(old_token)
        assert user is not None

        # Change password
        change_result = await service.change_password(
            user_id=result.user.user_id,
            old_password="secure-password-123",
            new_password="new-secure-password-456",
        )
        assert change_result.success

        # Old token must now be rejected
        user = await service.validate_token(old_token)
        assert user is None, "Old token must be revoked after password change"

    @pytest.mark.asyncio
    async def test_new_login_works_after_password_change(self, service):
        """After password change, login with new password produces a working token."""
        result = await _register_user(service)

        # Change password
        await service.change_password(
            user_id=result.user.user_id,
            old_password="secure-password-123",
            new_password="new-secure-password-456",
        )

        # Login with new password
        login_result = await service.login(
            username_or_email="testuser",
            password="new-secure-password-456",
        )
        assert login_result.success
        new_token = login_result.token.access_token

        # New token must work
        user = await service.validate_token(new_token)
        assert user is not None
        assert user.user_id == result.user.user_id

    @pytest.mark.asyncio
    async def test_multiple_tokens_all_revoked(self, service):
        """If a user has multiple tokens, all are revoked on password change."""
        result = await _register_user(service)
        token1 = result.token.access_token

        # Login again to create a second token
        login2 = await service.login(
            username_or_email="testuser",
            password="secure-password-123",
        )
        token2 = login2.token.access_token

        # Both tokens should work
        assert await service.validate_token(token1) is not None
        assert await service.validate_token(token2) is not None

        # Change password
        await service.change_password(
            user_id=result.user.user_id,
            old_password="secure-password-123",
            new_password="new-secure-password-456",
        )

        # Both tokens must be revoked
        assert await service.validate_token(token1) is None
        assert await service.validate_token(token2) is None
