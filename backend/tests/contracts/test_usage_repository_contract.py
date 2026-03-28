"""Contract tests for UsageRepository — daily generation quota tracking.

Verifies the schema and query invariants before implementation.

Issue: #314 | Parent Epic: #313
"""

import pytest
from datetime import date, timedelta

from src.services.database.connection import DatabaseManager
from src.services.database.usage_repository import UsageRepository
from src.services.database.schema import init_schema


@pytest.fixture
async def repo():
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    repo = UsageRepository()
    repo._db = manager
    yield repo
    await manager.disconnect()


class TestGetUsageToday:
    async def test_returns_zero_for_new_user(self, repo):
        result = await repo.get_usage_today("user_a")
        assert result == 0

    async def test_returns_correct_count_after_increment(self, repo):
        await repo.increment("user_a", "image_to_story")
        await repo.increment("user_a", "image_to_story")
        result = await repo.get_usage_today("user_a")
        assert result == 2

    async def test_different_features_share_daily_pool(self, repo):
        await repo.increment("user_a", "image_to_story")
        await repo.increment("user_a", "interactive_story")
        result = await repo.get_usage_today("user_a")
        assert result == 2

    async def test_different_users_are_independent(self, repo):
        await repo.increment("user_a", "image_to_story")
        await repo.increment("user_a", "image_to_story")
        await repo.increment("user_b", "image_to_story")
        assert await repo.get_usage_today("user_a") == 2
        assert await repo.get_usage_today("user_b") == 1

    async def test_only_counts_todays_usage(self, repo):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        await repo._db.execute(
            "INSERT INTO daily_usage (user_id, usage_date, feature, count) VALUES (?, ?, ?, ?)",
            ("user_a", yesterday, "image_to_story", 5),
        )
        await repo._db.commit()
        result = await repo.get_usage_today("user_a")
        assert result == 0


class TestIncrement:
    async def test_first_increment_creates_row(self, repo):
        await repo.increment("user_a", "image_to_story")
        result = await repo.get_usage_today("user_a")
        assert result == 1

    async def test_second_increment_updates_row(self, repo):
        await repo.increment("user_a", "image_to_story")
        await repo.increment("user_a", "image_to_story")
        result = await repo.get_usage_today("user_a")
        assert result == 2

    async def test_increment_is_idempotent_per_feature(self, repo):
        for _ in range(5):
            await repo.increment("user_a", "interactive_story")
        result = await repo.get_usage_today("user_a")
        assert result == 5


class TestGetQuotaStatus:
    async def test_returns_full_status_dict(self, repo):
        status = await repo.get_quota_status("user_a", limit=3)
        assert status["used"] == 0
        assert status["limit"] == 3
        assert status["remaining"] == 3
        assert "resets_at" in status

    async def test_remaining_decreases_after_use(self, repo):
        await repo.increment("user_a", "image_to_story")
        status = await repo.get_quota_status("user_a", limit=3)
        assert status["used"] == 1
        assert status["remaining"] == 2

    async def test_remaining_never_negative(self, repo):
        for _ in range(5):
            await repo.increment("user_a", "image_to_story")
        status = await repo.get_quota_status("user_a", limit=3)
        assert status["remaining"] == 0

    async def test_resets_at_is_tomorrow_midnight_utc(self, repo):
        status = await repo.get_quota_status("user_a", limit=3)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert status["resets_at"].startswith(tomorrow)
