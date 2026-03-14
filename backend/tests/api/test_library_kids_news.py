"""
Tests for Library API KIDS_NEWS union filter (#173/#176)

Verifies that:
- KIDS_NEWS enum value exists as a query-only alias
- GET /api/v1/library?type=kids-news returns both news and morning-show items
- Individual filters (type=news, type=morning-show) still work independently
- GET /api/v1/library/search?type=kids-news returns both types
- Returned items retain their real type (news or morning-show), not kids-news
"""

import pytest
import uuid
from datetime import datetime

from backend.src.api.models import LibraryItemType
from backend.src.services.database import story_repo, db_manager


# ---------------------------------------------------------------------------
# Unit tests for KIDS_NEWS enum
# ---------------------------------------------------------------------------


class TestKidsNewsEnum:
    """Verify KIDS_NEWS enum value exists and has correct string value."""

    def test_kids_news_enum_exists(self):
        assert hasattr(LibraryItemType, "KIDS_NEWS")

    def test_kids_news_enum_value(self):
        assert LibraryItemType.KIDS_NEWS.value == "kids-news"

    def test_kids_news_is_distinct_from_news(self):
        assert LibraryItemType.KIDS_NEWS != LibraryItemType.NEWS

    def test_kids_news_is_distinct_from_morning_show(self):
        assert LibraryItemType.KIDS_NEWS != LibraryItemType.MORNING_SHOW


# ---------------------------------------------------------------------------
# Integration tests for KIDS_NEWS union filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLibraryKidsNewsFilter:
    """Integration tests: kids-news filter returns both news and morning-show items."""

    @pytest.fixture(autouse=True)
    async def setup_test_stories(self):
        """Insert test stories of different types."""
        if not db_manager.is_connected:
            from backend.src.services.database.schema import init_schema
            await db_manager.connect()
            await init_schema(db_manager)

        uid = uuid.uuid4().hex[:8]
        self.news_id = f"news-{uid}"
        self.morning_id = f"morning-{uid}"
        self.art_id = f"art-{uid}"
        now = datetime.now().isoformat()

        # News story
        await story_repo.create({
            "story_id": self.news_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Today in kid news: pandas learn to dance.", "word_count": 8},
            "educational_value": {"themes": ["animals"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "news_to_kids",
            "created_at": now,
        })

        # Morning show story
        await story_repo.create({
            "story_id": self.morning_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Good morning kids! Here is today's morning show.", "word_count": 8},
            "educational_value": {"themes": ["daily"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "morning_show",
            "created_at": now,
        })

        # Art story (should NOT appear in kids-news filter)
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
        for sid in [self.news_id, self.morning_id, self.art_id]:
            await db_manager.execute(
                "DELETE FROM stories WHERE story_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_kids_news_returns_both_news_and_morning_show(self, test_client):
        """GET /api/v1/library?type=kids-news returns news + morning-show items."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "kids-news", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.news_id in item_ids, "News story should appear with kids-news filter"
            assert self.morning_id in item_ids, "Morning show story should appear with kids-news filter"
            assert self.art_id not in item_ids, "Art story should NOT appear with kids-news filter"

    async def test_kids_news_items_retain_real_type(self, test_client):
        """Items returned via kids-news filter keep their real type (news or morning-show)."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "kids-news", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            items_by_id = {item["id"]: item for item in data["items"]}

            if self.news_id in items_by_id:
                assert items_by_id[self.news_id]["type"] == "news"
            if self.morning_id in items_by_id:
                assert items_by_id[self.morning_id]["type"] == "morning-show"

            # No item should have type "kids-news"
            for item in data["items"]:
                assert item["type"] != "kids-news", "kids-news is query-only, never an item type"

    async def test_news_filter_still_works(self, test_client):
        """GET /api/v1/library?type=news returns only news items."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "news", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.news_id in item_ids, "News story should appear with news filter"
            assert self.morning_id not in item_ids, "Morning show should NOT appear with news filter"
            assert self.art_id not in item_ids, "Art story should NOT appear with news filter"

    async def test_morning_show_filter_still_works(self, test_client):
        """GET /api/v1/library?type=morning-show returns only morning-show items."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "morning-show", "limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.morning_id in item_ids, "Morning show should appear with morning-show filter"
            assert self.news_id not in item_ids, "News story should NOT appear with morning-show filter"
            assert self.art_id not in item_ids, "Art story should NOT appear with morning-show filter"

    async def test_search_kids_news_returns_both_types(self, test_client):
        """GET /api/v1/library/search?type=kids-news returns news + morning-show."""
        async with test_client as client:
            # Search for "kids" which appears in both test stories
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "kids", "type": "kids-news", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.news_id in item_ids, "News story should appear in kids-news search"
            assert self.morning_id in item_ids, "Morning show should appear in kids-news search"
            assert self.art_id not in item_ids, "Art story should NOT appear in kids-news search"

    async def test_search_kids_news_items_retain_real_type(self, test_client):
        """Search results via kids-news filter keep their real type."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "kids", "type": "kids-news", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()

            for item in data["items"]:
                assert item["type"] != "kids-news", "kids-news must not appear as item type in search"
