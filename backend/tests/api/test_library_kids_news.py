"""
Tests for Library API Kids Daily unified filter.

Verifies that:
- Legacy filter values (news, morning-show, kids-news) all resolve to kids-daily
- GET /api/v1/library?type=kids-daily returns all Kids Daily items
- Legacy DB records with story_type='news_to_kids' or 'morning_show' appear under kids-daily
- Art stories are excluded from kids-daily filter
"""

import pytest
import uuid
from datetime import datetime

from backend.src.api.models import LibraryItemType
from backend.src.services.database import story_repo, db_manager


# ---------------------------------------------------------------------------
# Unit tests for LibraryItemType enum
# ---------------------------------------------------------------------------


class TestLibraryItemTypeEnum:
    """Verify legacy enum aliases still exist for API backward compat."""

    def test_kids_daily_enum_exists(self):
        assert hasattr(LibraryItemType, "KIDS_DAILY")

    def test_kids_daily_enum_value(self):
        assert LibraryItemType.KIDS_DAILY.value == "kids-daily"

    def test_legacy_aliases_exist(self):
        """Legacy values are kept for API query param backward compat."""
        assert LibraryItemType.NEWS.value == "news"
        assert LibraryItemType.MORNING_SHOW.value == "morning-show"
        assert LibraryItemType.KIDS_NEWS.value == "kids-news"


# ---------------------------------------------------------------------------
# Integration tests for unified Kids Daily filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLibraryKidsDailyFilter:
    """Integration tests: all news-related filters resolve to kids-daily."""

    @pytest.fixture(autouse=True)
    async def setup_test_stories(self):
        """Insert test stories with various legacy story_types."""
        if not db_manager.is_connected:
            from backend.src.services.database.schema import init_schema
            await db_manager.connect()
            await init_schema(db_manager)

        uid = uuid.uuid4().hex[:8]
        self.legacy_news_id = f"news-{uid}"
        self.legacy_morning_id = f"morning-{uid}"
        self.kids_daily_id = f"daily-{uid}"
        self.art_id = f"art-{uid}"
        now = datetime.now().isoformat()

        # Legacy news_to_kids record
        await story_repo.create({
            "story_id": self.legacy_news_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Today in kids news: pandas learn to dance.", "word_count": 8},
            "educational_value": {"themes": ["animals"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "news_to_kids",
            "created_at": now,
        })

        # Legacy morning_show record
        await story_repo.create({
            "story_id": self.legacy_morning_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Good morning kids! Here is today's show.", "word_count": 8},
            "educational_value": {"themes": ["daily"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "morning_show",
            "created_at": now,
        })

        # New kids_daily record
        await story_repo.create({
            "story_id": self.kids_daily_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Kids daily episode about space exploration.", "word_count": 6},
            "educational_value": {"themes": ["science"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "kids_daily",
            "created_at": now,
        })

        # Art story (should NOT appear in kids-daily filter)
        await story_repo.create({
            "story_id": self.art_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "A wonderful art story about a rainbow.", "word_count": 7},
            "educational_value": {"themes": ["creativity"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "image_to_story",
            "created_at": now,
        })

        yield

        # Cleanup
        for sid in [self.legacy_news_id, self.legacy_morning_id, self.kids_daily_id, self.art_id]:
            await db_manager.execute(
                "DELETE FROM stories WHERE story_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_kids_daily_filter_returns_all_news_types(self, test_client):
        """GET /api/v1/library?type=kids-daily returns all Kids Daily items."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "kids-daily", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.legacy_news_id in item_ids, "Legacy news_to_kids should appear under kids-daily"
            assert self.legacy_morning_id in item_ids, "Legacy morning_show should appear under kids-daily"
            assert self.kids_daily_id in item_ids, "New kids_daily should appear under kids-daily"
            assert self.art_id not in item_ids, "Art story should NOT appear under kids-daily"

    async def test_all_items_have_type_kids_daily(self, test_client):
        """All Kids Daily items should have type='kids-daily' regardless of DB story_type."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "kids-daily", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()

            for item in data["items"]:
                assert item["type"] == "kids-daily", f"Expected kids-daily, got {item['type']}"

    async def test_legacy_news_filter_resolves_to_kids_daily(self, test_client):
        """GET /api/v1/library?type=news now returns all Kids Daily items (unified)."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "news", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            # All news-related types should appear since 'news' maps to kids-daily
            assert self.legacy_news_id in item_ids
            assert self.legacy_morning_id in item_ids
            assert self.kids_daily_id in item_ids
            assert self.art_id not in item_ids

    async def test_legacy_morning_show_filter_resolves_to_kids_daily(self, test_client):
        """GET /api/v1/library?type=morning-show now returns all Kids Daily items."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "morning-show", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.legacy_news_id in item_ids
            assert self.legacy_morning_id in item_ids
            assert self.kids_daily_id in item_ids
            assert self.art_id not in item_ids

    async def test_search_kids_daily_returns_matching(self, test_client):
        """GET /api/v1/library/search?type=kids-daily returns matching Kids Daily items."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "kids", "type": "kids-daily", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.legacy_news_id in item_ids, "Legacy news should appear in kids-daily search"
            assert self.legacy_morning_id in item_ids, "Legacy morning show should appear in kids-daily search"
            assert self.art_id not in item_ids, "Art story should NOT appear in kids-daily search"
