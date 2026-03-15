"""
Tests for Library API — news items use kid_title (#201)

Verifies that:
- NEWS items use analysis.kid_title as their display title
- NEWS items without kid_title fall back to _extract_title(text)
- MORNING_SHOW items still use kid_title (regression guard)
- ART_STORY items are unaffected and use _extract_title
"""

import pytest
import uuid
from datetime import datetime

from backend.src.services.database import story_repo, db_manager


@pytest.mark.asyncio
class TestLibraryNewsKidTitle:
    """News library cards should display the saved kid-friendly headline."""

    @pytest.fixture(autouse=True)
    async def setup_stories(self):
        """Insert news stories with and without kid_title."""
        if not db_manager.is_connected:
            from backend.src.services.database.schema import init_schema
            await db_manager.connect()
            await init_schema(db_manager)

        uid = uuid.uuid4().hex[:8]
        self.news_with_title_id = f"news-kt-{uid}"
        self.news_without_title_id = f"news-no-kt-{uid}"
        self.morning_id = f"morning-kt-{uid}"
        self.art_id = f"art-kt-{uid}"
        now = datetime.now().isoformat()

        # News story WITH kid_title in analysis
        await story_repo.create({
            "story_id": self.news_with_title_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Scientists discovered a new species of butterfly in the Amazon rainforest today.", "word_count": 12},
            "educational_value": {"themes": ["science"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "news_to_kids",
            "analysis": {"kid_title": "Cool New Butterfly Found!", "category": "science"},
            "created_at": now,
        })

        # News story WITHOUT kid_title in analysis
        await story_repo.create({
            "story_id": self.news_without_title_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "A short news blurb.", "word_count": 4},
            "educational_value": {"themes": ["general"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "news_to_kids",
            "analysis": {"category": "general"},
            "created_at": now,
        })

        # Morning show WITH kid_title (regression guard)
        await story_repo.create({
            "story_id": self.morning_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Good morning kids! Here is the morning show.", "word_count": 8},
            "educational_value": {"themes": ["daily"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "morning_show",
            "analysis": {"kid_title": "Morning Fun Time!", "category": "daily"},
            "created_at": now,
        })

        # Art story (should never use kid_title)
        await story_repo.create({
            "story_id": self.art_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "Once upon a time there was a rainbow dragon.", "word_count": 9},
            "educational_value": {"themes": ["creativity"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "image_to_story",
            "analysis": {"kid_title": "Should Not Appear"},
            "created_at": now,
        })

        yield

        for sid in [self.news_with_title_id, self.news_without_title_id, self.morning_id, self.art_id]:
            await db_manager.execute("DELETE FROM stories WHERE story_id = ?", (sid,))
        await db_manager.commit()

    async def test_news_item_uses_kid_title(self, test_client):
        """News card title should be the kid_title from analysis, not truncated body text."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "news", "limit": 100})
            assert resp.status_code == 200
            items_by_id = {item["id"]: item for item in resp.json()["items"]}

            assert self.news_with_title_id in items_by_id
            assert items_by_id[self.news_with_title_id]["title"] == "Cool New Butterfly Found!"

    async def test_news_item_without_kid_title_falls_back(self, test_client):
        """News card without kid_title should fall back to extracted title from text."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "news", "limit": 100})
            assert resp.status_code == 200
            items_by_id = {item["id"]: item for item in resp.json()["items"]}

            assert self.news_without_title_id in items_by_id
            # Should fall back to _extract_title, not be empty or None
            title = items_by_id[self.news_without_title_id]["title"]
            assert title and len(title) > 0
            assert title != "Cool New Butterfly Found!"

    async def test_morning_show_still_uses_kid_title(self, test_client):
        """Regression: morning show cards must still use kid_title."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "morning-show", "limit": 100})
            assert resp.status_code == 200
            items_by_id = {item["id"]: item for item in resp.json()["items"]}

            assert self.morning_id in items_by_id
            assert items_by_id[self.morning_id]["title"] == "Morning Fun Time!"

    async def test_art_story_ignores_kid_title(self, test_client):
        """Art story cards should use _extract_title, not kid_title from analysis."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"type": "art-story", "limit": 100})
            assert resp.status_code == 200
            items_by_id = {item["id"]: item for item in resp.json()["items"]}

            assert self.art_id in items_by_id
            assert items_by_id[self.art_id]["title"] != "Should Not Appear"
