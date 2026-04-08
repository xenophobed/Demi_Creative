"""
Referral Status API and Auto-Upgrade Tests (#350)

Tests for:
- GET /me/referrals endpoint
- Auto-upgrade logic when threshold reached
- Tier-based quota enforcement
"""

import os
import sys

import pytest
import pytest_asyncio

from backend.src.api.deps import _get_daily_quota
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.referral_repository import ReferralRepository
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository
from backend.src.services.user_service import UserService


@pytest_asyncio.fixture
async def env():
    """Full test environment with in-memory DB."""
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

    # Patch module-level referral_repo
    _mod = sys.modules["backend.src.services.user_service"]
    _orig = _mod.referral_repo
    _mod.referral_repo = ref_repo

    yield {
        "svc": svc,
        "user_repo": user_repo,
        "ref_repo": ref_repo,
        "db": db,
    }

    _mod.referral_repo = _orig
    await db.disconnect()


class TestAutoUpgrade:
    """qualify_and_maybe_upgrade promotes referrer at threshold."""

    @pytest.mark.asyncio
    async def test_qualify_upgrades_at_threshold(self, env):
        svc, user_repo, ref_repo = env["svc"], env["user_repo"], env["ref_repo"]

        referrer = await svc.register(
            username="upgrader", email="upgrader@test.com", password="password123"
        )
        referrer_user = referrer.user

        # Create 10 referrals and qualify 9 (below threshold)
        referred_ids = []
        for i in range(10):
            r = await svc.register(
                username=f"ref_{i}",
                email=f"ref_{i}@test.com",
                password="password123",
                referral_code=referrer_user.referral_code,
            )
            referred_ids.append(r.user.user_id)

        for uid in referred_ids[:9]:
            await svc.qualify_and_maybe_upgrade(uid)

        # Referrer should still be free
        user = await user_repo.get_by_id(referrer_user.user_id)
        assert user.membership_tier == "free"

        # Qualify the 10th — should trigger upgrade
        upgraded = await svc.qualify_and_maybe_upgrade(referred_ids[9])
        assert upgraded is True

        user = await user_repo.get_by_id(referrer_user.user_id)
        assert user.membership_tier == "plus"

    @pytest.mark.asyncio
    async def test_already_plus_not_affected(self, env):
        svc, user_repo, ref_repo = env["svc"], env["user_repo"], env["ref_repo"]

        referrer = await svc.register(
            username="already_plus",
            email="already_plus@test.com",
            password="password123",
        )
        await user_repo.update_membership_tier(referrer.user.user_id, "plus")

        r = await svc.register(
            username="extra_ref",
            email="extra_ref@test.com",
            password="password123",
            referral_code=referrer.user.referral_code,
        )
        result = await svc.qualify_and_maybe_upgrade(r.user.user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_qualify_nonexistent_returns_false(self, env):
        result = await env["svc"].qualify_and_maybe_upgrade("nonexistent-id")
        assert result is False


class TestTierBasedQuota:
    """_get_daily_quota returns tier-appropriate limits."""

    def test_free_tier_quota(self):
        # Clear env override if set
        orig = os.environ.pop("DAILY_GENERATION_QUOTA", None)
        try:
            assert _get_daily_quota("free") == 3
        finally:
            if orig is not None:
                os.environ["DAILY_GENERATION_QUOTA"] = orig


@pytest.mark.asyncio
class TestReferralStatusEndpoint:
    """HTTP-level checks for referral share link base URL resolution."""

    async def test_share_url_uses_request_origin_when_frontend_url_missing(
        self, test_client, monkeypatch
    ):
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

        async with test_client as client:
            resp = await client.get(
                "/api/v1/users/me/referrals",
                headers={"Origin": "https://kids.example.cn"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["share_url"].startswith("https://kids.example.cn/login?ref=")

    async def test_share_url_ignores_placeholder_frontend_url(
        self, test_client, monkeypatch
    ):
        monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/users/me/referrals",
                headers={"Origin": "https://real.app.domain"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["share_url"].startswith("https://real.app.domain/login?ref=")

    def test_plus_tier_quota(self):
        orig = os.environ.pop("DAILY_GENERATION_QUOTA", None)
        try:
            assert _get_daily_quota("plus") == 9
        finally:
            if orig is not None:
                os.environ["DAILY_GENERATION_QUOTA"] = orig

    def test_env_override_takes_precedence(self):
        os.environ["DAILY_GENERATION_QUOTA"] = "20"
        try:
            assert _get_daily_quota("free") == 20
            assert _get_daily_quota("plus") == 20
        finally:
            del os.environ["DAILY_GENERATION_QUOTA"]

    def test_unknown_tier_returns_default(self):
        orig = os.environ.pop("DAILY_GENERATION_QUOTA", None)
        try:
            assert _get_daily_quota("unknown") == 6
        finally:
            if orig is not None:
                os.environ["DAILY_GENERATION_QUOTA"] = orig
