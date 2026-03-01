"""
Tests for Library API Safety Filtering (#81)

Verifies that the library API excludes content with safety_score < 0.85.
Content safety is non-negotiable per project rules.

Tests cover:
- _is_safe() helper function directly
- GET /api/v1/library endpoint filtering
- GET /api/v1/library/search endpoint filtering
"""

import pytest
import uuid
from datetime import datetime

from backend.src.api.routes.library import _is_safe, SAFETY_THRESHOLD
from backend.src.api.models import LibraryItem, LibraryItemType
from backend.src.services.database import story_repo, db_manager
from backend.src.services.database.schema import init_schema


# ---------------------------------------------------------------------------
# Unit tests for _is_safe() helper
# ---------------------------------------------------------------------------


class TestIsSafeHelper:
    """Unit tests for the _is_safe() safety filtering function."""

    def _make_item(self, safety_score=None) -> LibraryItem:
        """Create a minimal LibraryItem with a given safety_score."""
        return LibraryItem(
            id="test-item",
            type=LibraryItemType.ART_STORY,
            title="Test Story",
            preview="Once upon a time...",
            created_at="2026-03-01T00:00:00",
            is_favorited=False,
            safety_score=safety_score,
        )

    def test_threshold_constant_is_0_85(self):
        """Safety threshold MUST be exactly 0.85."""
        assert SAFETY_THRESHOLD == 0.85

    def test_score_above_threshold_passes(self):
        """Items with safety_score > 0.85 are safe."""
        item = self._make_item(safety_score=0.95)
        assert _is_safe(item) is True

    def test_score_at_threshold_passes(self):
        """Items with safety_score == 0.85 are safe (boundary: inclusive)."""
        item = self._make_item(safety_score=0.85)
        assert _is_safe(item) is True

    def test_score_below_threshold_fails(self):
        """Items with safety_score < 0.85 are unsafe and MUST be excluded."""
        item = self._make_item(safety_score=0.84)
        assert _is_safe(item) is False

    def test_score_zero_fails(self):
        """Items with safety_score == 0 are unsafe."""
        item = self._make_item(safety_score=0.0)
        assert _is_safe(item) is False

    def test_score_none_passes(self):
        """Items with no safety_score (None) are allowed through."""
        item = self._make_item(safety_score=None)
        assert _is_safe(item) is True

    def test_score_just_below_threshold_fails(self):
        """Boundary test: 0.849 is below threshold."""
        item = self._make_item(safety_score=0.849)
        assert _is_safe(item) is False

    def test_perfect_score_passes(self):
        """Items with safety_score == 1.0 are safe."""
        item = self._make_item(safety_score=1.0)
        assert _is_safe(item) is True


# ---------------------------------------------------------------------------
# Integration tests for GET /api/v1/library safety filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLibrarySafetyFiltering:
    """Integration tests: library endpoint filters out unsafe content."""

    @pytest.fixture(autouse=True)
    async def setup_test_stories(self):
        """Insert test stories with various safety scores."""
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        self.safe_id = f"safe-{uuid.uuid4().hex[:8]}"
        self.unsafe_id = f"unsafe-{uuid.uuid4().hex[:8]}"
        self.borderline_id = f"border-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        # Safe story (score 0.95)
        await story_repo.create({
            "story_id": self.safe_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "A safe and happy adventure story.", "word_count": 6},
            "educational_value": {"themes": ["friendship"]},
            "characters": [],
            "safety_score": 0.95,
            "story_type": "image_to_story",
            "created_at": now,
        })

        # Unsafe story (score 0.50)
        await story_repo.create({
            "story_id": self.unsafe_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "An unsafe story that should be filtered out.", "word_count": 8},
            "educational_value": {"themes": ["danger"]},
            "characters": [],
            "safety_score": 0.50,
            "story_type": "image_to_story",
            "created_at": now,
        })

        # Borderline story (score exactly 0.85 — should pass)
        await story_repo.create({
            "story_id": self.borderline_id,
            "user_id": "test_user",
            "child_id": "child_001",
            "age_group": "6-8",
            "story": {"text": "A borderline story at the exact threshold.", "word_count": 8},
            "educational_value": {"themes": ["nature"]},
            "characters": [],
            "safety_score": 0.85,
            "story_type": "image_to_story",
            "created_at": now,
        })

        yield

        # Cleanup
        for sid in [self.safe_id, self.unsafe_id, self.borderline_id]:
            await db_manager.execute(
                "DELETE FROM stories WHERE story_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_library_excludes_unsafe_stories(self, test_client):
        """GET /api/v1/library must not return stories with safety_score < 0.85."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"limit": 100})
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.safe_id in item_ids, "Safe story (0.95) should be included"
            assert self.borderline_id in item_ids, "Borderline story (0.85) should be included"
            assert self.unsafe_id not in item_ids, "Unsafe story (0.50) MUST be excluded"

    async def test_library_total_excludes_unsafe(self, test_client):
        """The total count must not include filtered-out unsafe items."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library",
                params={"type": "art-story", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            # Unsafe item should not contribute to total
            assert self.unsafe_id not in item_ids

    async def test_search_excludes_unsafe_stories(self, test_client):
        """GET /api/v1/library/search must not return unsafe stories."""
        async with test_client as client:
            # Search for "story" — should match all three test stories
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "story", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.safe_id in item_ids, "Safe story should appear in search"
            assert self.unsafe_id not in item_ids, "Unsafe story MUST NOT appear in search"

    async def test_search_includes_borderline_safe(self, test_client):
        """Stories at exactly 0.85 threshold should appear in search results."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "borderline", "limit": 100},
            )
            assert resp.status_code == 200
            data = resp.json()
            item_ids = [item["id"] for item in data["items"]]

            assert self.borderline_id in item_ids, "Borderline (0.85) story should appear"
