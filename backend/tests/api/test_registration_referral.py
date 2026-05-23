"""
Registration Referral Tests (#349)

Tests that registration accepts an optional referral_code parameter
and creates referral records when the code is valid.
"""

import uuid

import pytest
import pytest_asyncio

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository
from backend.src.services.database.referral_repository import ReferralRepository
from backend.src.services.user_service import UserService


@pytest_asyncio.fixture
async def service():
    """UserService with in-memory database."""
    db = DatabaseManager(":memory:")
    await db.connect()
    await init_schema(db)

    user_repo = UserRepository()
    user_repo._db = db

    ref_repo = ReferralRepository()
    ref_repo._db = db

    svc = UserService()
    svc._repo = user_repo
    svc._db = db

    # Patch the module-level referral_repo used inside register().
    # Note: `backend.src.services.user_service` resolves to the UserService
    # singleton due to __init__.py re-export, so we use sys.modules instead.
    import sys
    _us_mod = sys.modules["backend.src.services.user_service"]
    _original_ref_repo = _us_mod.referral_repo
    _us_mod.referral_repo = ref_repo

    yield {"svc": svc, "user_repo": user_repo, "ref_repo": ref_repo, "db": db}

    _us_mod.referral_repo = _original_ref_repo
    await db.disconnect()


@pytest_asyncio.fixture
async def referrer(service):
    """Create a referrer user and return their data."""
    result = await service["svc"].register(
        username="referrer", email="referrer@test.com", password="password123"
    )
    return result.user


class TestRegistrationWithReferralCode:
    """Registration accepts optional referral_code."""

    @pytest.mark.asyncio
    async def test_register_without_referral_code(self, service):
        result = await service["svc"].register(
            username="noreferral", email="noreferral@test.com",
            password="password123"
        )
        assert result.success is True
        assert result.user.role == "parent"
        assert result.user.consent_status == "not_required"
        assert result.user.referred_by is None

    @pytest.mark.asyncio
    async def test_child_signup_requires_parent_email(self, service):
        result = await service["svc"].register(
            username="child_no_parent",
            email="child_no_parent@test.com",
            password="password123",
            role="child",
        )
        assert result.success is False
        assert result.error == "Parent email is required for child sign-up"

    @pytest.mark.asyncio
    async def test_child_signup_stores_parent_consent_pending(self, service):
        result = await service["svc"].register(
            username="child_with_parent",
            email="child_with_parent@test.com",
            password="password123",
            role="child",
            parent_email="Parent@Test.com",
        )
        assert result.success is True
        assert result.user.role == "child"
        assert result.user.parent_email == "parent@test.com"
        assert result.user.consent_status == "pending_parent_consent"

    @pytest.mark.asyncio
    async def test_parent_registration_stores_default_child_id(self, service):
        result = await service["svc"].register(
            username="parent_with_child",
            email="parent_with_child@test.com",
            password="password123",
            child_id="child_alpha",
            child_name="Ada",
            child_age_group="6-8",
            child_interests=["Space", "Music"],
        )

        assert result.success is True
        assert result.user.role == "parent"
        assert result.user.default_child_id == "child_alpha"

        stored = await service["user_repo"].get_by_id(result.user.user_id)
        assert stored.default_child_id == "child_alpha"

    @pytest.mark.asyncio
    async def test_parent_approval_token_approves_child_signup(self, service):
        result = await service["svc"].register(
            username="child_pending",
            email="child_pending@test.com",
            password="password123",
            role="child",
            parent_email="Parent@Test.com",
        )

        token = service["svc"].create_parent_approval_token(
            result.user.user_id,
            result.user.parent_email,
        )
        approved = await service["svc"].approve_parent_approval_token(token)

        assert approved.success is True
        assert approved.user.consent_status == "approved"

        stored = await service["user_repo"].get_by_id(result.user.user_id)
        assert stored.consent_status == "approved"

    @pytest.mark.asyncio
    async def test_parent_approval_token_rejects_invalid_or_expired(self, service):
        result = await service["svc"].register(
            username="child_expired",
            email="child_expired@test.com",
            password="password123",
            role="child",
            parent_email="parent@test.com",
        )

        invalid = await service["svc"].approve_parent_approval_token("not-a-token")
        assert invalid.success is False
        assert invalid.error == "Invalid approval token"

        expired_token = service["svc"].create_parent_approval_token(
            result.user.user_id,
            result.user.parent_email,
            expires_in_seconds=-1,
        )
        expired = await service["svc"].approve_parent_approval_token(expired_token)
        assert expired.success is False
        assert expired.error == "Approval token has expired"

        stored = await service["user_repo"].get_by_id(result.user.user_id)
        assert stored.consent_status == "pending_parent_consent"

    @pytest.mark.asyncio
    async def test_register_with_valid_referral_code(self, service, referrer):
        result = await service["svc"].register(
            username="referred1", email="referred1@test.com",
            password="password123",
            referral_code=referrer.referral_code
        )
        assert result.success is True
        assert result.user.referred_by == referrer.referral_code

    @pytest.mark.asyncio
    async def test_valid_referral_creates_referral_record(self, service, referrer):
        result = await service["svc"].register(
            username="referred2", email="referred2@test.com",
            password="password123",
            referral_code=referrer.referral_code
        )
        ref = await service["ref_repo"].get_referral_by_referred_user(result.user.user_id)
        assert ref is not None
        assert ref["referrer_user_id"] == referrer.user_id
        assert ref["referral_code"] == referrer.referral_code
        assert ref["is_qualified"] == 0

    @pytest.mark.asyncio
    async def test_register_with_invalid_referral_code(self, service):
        result = await service["svc"].register(
            username="badreferral", email="badreferral@test.com",
            password="password123",
            referral_code="INVALID1"
        )
        assert result.success is True
        assert result.user.referred_by is None

    @pytest.mark.asyncio
    async def test_invalid_referral_no_record_created(self, service):
        result = await service["svc"].register(
            username="badreferral2", email="badreferral2@test.com",
            password="password123",
            referral_code="XXXXXXXX"
        )
        ref = await service["ref_repo"].get_referral_by_referred_user(result.user.user_id)
        assert ref is None

    @pytest.mark.asyncio
    async def test_referral_count_increments(self, service, referrer):
        for i in range(3):
            await service["svc"].register(
                username=f"ref_count_{i}", email=f"ref_count_{i}@test.com",
                password="password123",
                referral_code=referrer.referral_code
            )
        count = await service["ref_repo"].get_referral_count(referrer.user_id)
        assert count == 3
