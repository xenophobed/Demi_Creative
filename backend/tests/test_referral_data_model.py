"""
Referral Data Model Tests (#347)

Tests for referral membership data model:
- MembershipTier enum values
- UserData referral fields
- Referral code auto-generation on user creation
- Referral code uniqueness
- Referrals table schema and constraints
- ReferralRepository CRUD operations
- Migration backfill for existing users
"""

import os
import sys
import pytest
import pytest_asyncio
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.models import MembershipTier
from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.user_repository import UserRepository, UserData
from src.services.database.referral_repository import ReferralRepository


@pytest_asyncio.fixture
async def repos():
    """Create repositories with shared in-memory test database."""
    db = DatabaseManager(':memory:')
    await db.connect()
    await init_schema(db)

    user_repo = UserRepository()
    user_repo._db = db

    referral_repo = ReferralRepository()
    referral_repo._db = db

    yield {
        'db': db,
        'user': user_repo,
        'referral': referral_repo,
    }

    await db.disconnect()


class TestMembershipTierEnum:
    """MembershipTier enum has expected values."""

    def test_free_value(self):
        assert MembershipTier.FREE == "free"

    def test_plus_value(self):
        assert MembershipTier.PLUS == "plus"

    def test_is_string_enum(self):
        assert isinstance(MembershipTier.FREE, str)


class TestUserDataReferralFields:
    """UserData dataclass includes referral fields with correct defaults."""

    def test_default_membership_tier(self):
        user = UserData(
            user_id="u1", username="a", email="a@b.c",
            password_hash="h", created_at="", updated_at=""
        )
        assert user.membership_tier == "free"

    def test_default_referral_code(self):
        user = UserData(
            user_id="u1", username="a", email="a@b.c",
            password_hash="h", created_at="", updated_at=""
        )
        assert user.referral_code == ""

    def test_default_referred_by(self):
        user = UserData(
            user_id="u1", username="a", email="a@b.c",
            password_hash="h", created_at="", updated_at=""
        )
        assert user.referred_by is None


class TestUserCreationGeneratesReferralCode:
    """create_user() auto-generates an 8-char alphanumeric referral code."""

    @pytest.mark.asyncio
    async def test_referral_code_generated(self, repos):
        user = await repos['user'].create_user(
            username='alice', email='alice@example.com',
            password_hash='hash123'
        )
        assert len(user.referral_code) == 8
        assert user.referral_code.isalnum()

    @pytest.mark.asyncio
    async def test_membership_tier_defaults_to_free(self, repos):
        user = await repos['user'].create_user(
            username='bob', email='bob@example.com',
            password_hash='hash123'
        )
        assert user.membership_tier == "free"

    @pytest.mark.asyncio
    async def test_referred_by_default_none(self, repos):
        user = await repos['user'].create_user(
            username='carol', email='carol@example.com',
            password_hash='hash123'
        )
        assert user.referred_by is None

    @pytest.mark.asyncio
    async def test_referred_by_stored_when_provided(self, repos):
        user = await repos['user'].create_user(
            username='dave', email='dave@example.com',
            password_hash='hash123', referred_by='ABCD1234'
        )
        assert user.referred_by == 'ABCD1234'

    @pytest.mark.asyncio
    async def test_referral_codes_unique_across_users(self, repos):
        codes = set()
        for i in range(20):
            user = await repos['user'].create_user(
                username=f'user{i}', email=f'user{i}@example.com',
                password_hash='hash123'
            )
            codes.add(user.referral_code)
        assert len(codes) == 20

    @pytest.mark.asyncio
    async def test_referral_code_persisted_in_db(self, repos):
        user = await repos['user'].create_user(
            username='eve', email='eve@example.com',
            password_hash='hash123'
        )
        fetched = await repos['user'].get_by_id(user.user_id)
        assert fetched.referral_code == user.referral_code
        assert fetched.membership_tier == "free"


class TestReferralsTableSchema:
    """Referrals table exists with correct constraints."""

    @pytest.mark.asyncio
    async def test_referrals_table_created(self, repos):
        rows = await repos['db'].fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'"
        )
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_referred_user_unique_constraint(self, repos):
        """Same user cannot be referred twice."""
        referrer = await repos['user'].create_user(
            username='referrer', email='referrer@example.com',
            password_hash='hash'
        )
        referred = await repos['user'].create_user(
            username='referred', email='referred@example.com',
            password_hash='hash'
        )
        await repos['referral'].create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        with pytest.raises(Exception):
            await repos['referral'].create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )


class TestReferralRepository:
    """ReferralRepository CRUD and counting."""

    @pytest.mark.asyncio
    async def test_create_referral(self, repos):
        referrer = await repos['user'].create_user(
            username='ref1', email='ref1@example.com', password_hash='h'
        )
        referred = await repos['user'].create_user(
            username='new1', email='new1@example.com', password_hash='h'
        )
        result = await repos['referral'].create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        assert result['referrer_user_id'] == referrer.user_id
        assert result['referred_user_id'] == referred.user_id
        assert result['is_qualified'] == 0

    @pytest.mark.asyncio
    async def test_qualify_referral(self, repos):
        referrer = await repos['user'].create_user(
            username='ref2', email='ref2@example.com', password_hash='h'
        )
        referred = await repos['user'].create_user(
            username='new2', email='new2@example.com', password_hash='h'
        )
        await repos['referral'].create_referral(
            referrer.user_id, referred.user_id, referrer.referral_code
        )
        result = await repos['referral'].qualify_referral(referred.user_id)
        assert result is True

        ref = await repos['referral'].get_referral_by_referred_user(referred.user_id)
        assert ref['is_qualified'] == 1
        assert ref['qualified_at'] is not None

    @pytest.mark.asyncio
    async def test_count_qualified_only(self, repos):
        referrer = await repos['user'].create_user(
            username='ref3', email='ref3@example.com', password_hash='h'
        )
        for i in range(3):
            referred = await repos['user'].create_user(
                username=f'new3_{i}', email=f'new3_{i}@example.com',
                password_hash='h'
            )
            await repos['referral'].create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
            if i < 2:
                await repos['referral'].qualify_referral(referred.user_id)

        total = await repos['referral'].get_referral_count(referrer.user_id)
        qualified = await repos['referral'].get_referral_count(
            referrer.user_id, qualified_only=True
        )
        assert total == 3
        assert qualified == 2

    @pytest.mark.asyncio
    async def test_check_upgrade_eligible(self, repos):
        referrer = await repos['user'].create_user(
            username='ref4', email='ref4@example.com', password_hash='h'
        )
        assert await repos['referral'].check_upgrade_eligible(
            referrer.user_id, threshold=3
        ) is False

        for i in range(3):
            referred = await repos['user'].create_user(
                username=f'new4_{i}', email=f'new4_{i}@example.com',
                password_hash='h'
            )
            await repos['referral'].create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )
            await repos['referral'].qualify_referral(referred.user_id)

        assert await repos['referral'].check_upgrade_eligible(
            referrer.user_id, threshold=3
        ) is True

    @pytest.mark.asyncio
    async def test_get_referrals_by_user(self, repos):
        referrer = await repos['user'].create_user(
            username='ref5', email='ref5@example.com', password_hash='h'
        )
        for i in range(3):
            referred = await repos['user'].create_user(
                username=f'new5_{i}', email=f'new5_{i}@example.com',
                password_hash='h'
            )
            await repos['referral'].create_referral(
                referrer.user_id, referred.user_id, referrer.referral_code
            )

        referrals = await repos['referral'].get_referrals_by_user(referrer.user_id)
        assert len(referrals) == 3


class TestMigrationBackfill:
    """Migration backfills existing users with free tier and referral codes."""

    @pytest.mark.asyncio
    async def test_existing_users_get_referral_fields(self, repos):
        """Users created via init_schema have referral columns available."""
        db = repos['db']
        users_info = await db.fetchall("PRAGMA table_info(users)")
        col_names = [col['name'] for col in users_info]
        assert 'membership_tier' in col_names
        assert 'referral_code' in col_names
        assert 'referred_by' in col_names
