"""
Referral Repository Contract Tests

Defines the expected interface and behavior of ReferralRepository.
Tests CRUD operations, qualification, counting, and constraints.

Parent Epic: #346 (Referral-Based Membership)
Issue: #348
"""

import pytest
import pytest_asyncio

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.referral_repository import (
    ReferralRepository,
    referral_repo,
)
from backend.src.services.database.user_repository import UserRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def db():
    """In-memory database with full schema for referral tests."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def repo(db):
    """ReferralRepository bound to test database."""
    r = ReferralRepository()
    r._db = db
    return r


@pytest_asyncio.fixture
async def user_repo(db):
    """UserRepository bound to test database."""
    r = UserRepository()
    r._db = db
    return r


@pytest_asyncio.fixture
async def two_users(user_repo):
    """Create a referrer and a referred user."""
    referrer = await user_repo.create_user(
        username="referrer", email="referrer@test.com", password_hash="h"
    )
    referred = await user_repo.create_user(
        username="referred", email="referred@test.com", password_hash="h"
    )
    return referrer, referred


# ============================================================================
# Contract: Module exports
# ============================================================================


class TestModuleExports:
    """referral_repository module exports expected symbols."""

    def test_singleton_exists(self):
        assert referral_repo is not None

    def test_singleton_is_repository(self):
        assert isinstance(referral_repo, ReferralRepository)


# ============================================================================
# Contract: create_referral
# ============================================================================


class TestCreateReferralContract:
    """create_referral returns a dict with required keys."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self, repo, two_users):
        referrer, referred = two_users
        result = await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        assert isinstance(result, dict)
        assert "referrer_user_id" in result
        assert "referred_user_id" in result
        assert "referral_code" in result
        assert "is_qualified" in result
        assert "created_at" in result
        assert "qualified_at" in result

    @pytest.mark.asyncio
    async def test_new_referral_is_unqualified(self, repo, two_users):
        referrer, referred = two_users
        result = await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        assert result["is_qualified"] == 0
        assert result["qualified_at"] is None

    @pytest.mark.asyncio
    async def test_duplicate_referred_user_raises(self, repo, two_users, user_repo):
        referrer, referred = two_users
        await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        with pytest.raises(Exception):
            await repo.create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )


# ============================================================================
# Contract: qualify_referral
# ============================================================================


class TestQualifyReferralContract:
    """qualify_referral sets is_qualified=1 and qualified_at timestamp."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, repo, two_users):
        referrer, referred = two_users
        await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        result = await repo.qualify_referral(referred.user_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_sets_qualified_fields(self, repo, two_users):
        referrer, referred = two_users
        await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        await repo.qualify_referral(referred.user_id)
        ref = await repo.get_referral_by_referred_user(referred.user_id)
        assert ref["is_qualified"] == 1
        assert ref["qualified_at"] is not None

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent(self, repo):
        result = await repo.qualify_referral("nonexistent-user-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_idempotent_does_not_requalify(self, repo, two_users):
        referrer, referred = two_users
        await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        await repo.qualify_referral(referred.user_id)
        ref1 = await repo.get_referral_by_referred_user(referred.user_id)
        result = await repo.qualify_referral(referred.user_id)
        assert result is False  # already qualified
        ref2 = await repo.get_referral_by_referred_user(referred.user_id)
        assert ref2["qualified_at"] == ref1["qualified_at"]  # unchanged


# ============================================================================
# Contract: get_referral_count
# ============================================================================


class TestGetReferralCountContract:
    """get_referral_count returns correct totals and qualified counts."""

    @pytest.mark.asyncio
    async def test_zero_for_new_user(self, repo, user_repo):
        user = await user_repo.create_user(
            username="lonely", email="lonely@test.com", password_hash="h"
        )
        assert await repo.get_referral_count(user.user_id) == 0

    @pytest.mark.asyncio
    async def test_total_count(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r1", email="r1@test.com", password_hash="h"
        )
        for i in range(3):
            referred = await user_repo.create_user(
                username=f"n{i}", email=f"n{i}@test.com", password_hash="h"
            )
            await repo.create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
        assert await repo.get_referral_count(referrer.user_id) == 3

    @pytest.mark.asyncio
    async def test_qualified_only_count(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r2", email="r2@test.com", password_hash="h"
        )
        for i in range(4):
            referred = await user_repo.create_user(
                username=f"q{i}", email=f"q{i}@test.com", password_hash="h"
            )
            await repo.create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
            if i < 2:
                await repo.qualify_referral(referred.user_id)
        assert await repo.get_referral_count(referrer.user_id) == 4
        assert await repo.get_referral_count(referrer.user_id, qualified_only=True) == 2


# ============================================================================
# Contract: check_upgrade_eligible
# ============================================================================


class TestCheckUpgradeEligibleContract:
    """check_upgrade_eligible returns bool based on qualified referral threshold."""

    @pytest.mark.asyncio
    async def test_not_eligible_below_threshold(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r3", email="r3@test.com", password_hash="h"
        )
        assert await repo.check_upgrade_eligible(referrer.user_id, threshold=3) is False

    @pytest.mark.asyncio
    async def test_eligible_at_threshold(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r4", email="r4@test.com", password_hash="h"
        )
        for i in range(3):
            referred = await user_repo.create_user(
                username=f"e{i}", email=f"e{i}@test.com", password_hash="h"
            )
            await repo.create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
            await repo.qualify_referral(referred.user_id)
        assert await repo.check_upgrade_eligible(referrer.user_id, threshold=3) is True

    @pytest.mark.asyncio
    async def test_default_threshold_is_10(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r5", email="r5@test.com", password_hash="h"
        )
        # 3 qualified referrals — not enough for default threshold of 10
        for i in range(3):
            referred = await user_repo.create_user(
                username=f"d{i}", email=f"d{i}@test.com", password_hash="h"
            )
            await repo.create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
            await repo.qualify_referral(referred.user_id)
        assert await repo.check_upgrade_eligible(referrer.user_id) is False


# ============================================================================
# Contract: get_referrals_by_user / get_referral_by_referred_user
# ============================================================================


class TestLookupContract:
    """Lookup methods return expected shapes."""

    @pytest.mark.asyncio
    async def test_get_referrals_by_user_returns_list(self, repo, user_repo):
        referrer = await user_repo.create_user(
            username="r6", email="r6@test.com", password_hash="h"
        )
        result = await repo.get_referrals_by_user(referrer.user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_referral_by_referred_user_returns_none(self, repo):
        result = await repo.get_referral_by_referred_user("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_referral_by_referred_user_returns_dict(self, repo, two_users):
        referrer, referred = two_users
        await repo.create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        result = await repo.get_referral_by_referred_user(referred.user_id)
        assert isinstance(result, dict)
        assert result["referred_user_id"] == referred.user_id
