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

from backend.src.api.routes.library import (
    _is_safe,
    _get_visible_story_ids,
    SAFETY_THRESHOLD,
    VISIBLE_LIFECYCLE_STATES,
)
from backend.src.api.models import LibraryItem, LibraryItemType
from backend.src.services.database import story_repo, db_manager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.artifact_repository import (
    ArtifactRepository,
    StoryArtifactLinkRepository,
)
from backend.src.services.models.artifact_models import (
    ArtifactCreate,
    ArtifactType,
    StoryArtifactLinkCreate,
    StoryArtifactRole,
)


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


# ---------------------------------------------------------------------------
# Lifecycle-state visibility filtering (#712 library, #713 search)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLibraryLifecycleFiltering:
    """Library + search must only surface published/candidate content.

    Per PRD §3.6 / §3.7, intermediate (work-in-progress) and archived stories
    must never appear in My Library or search. Legacy stories with no primary
    artifact link have no lifecycle state and stay visible (we don't hide a
    user's existing content).
    """

    @pytest.fixture(autouse=True)
    async def setup_lifecycle_stories(self):
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        self.arepo = ArtifactRepository(db_manager)
        self.lrepo = StoryArtifactLinkRepository(db_manager)
        now = datetime.now().isoformat()

        async def make_story(tag: str) -> str:
            sid = f"lc-{tag}-{uuid.uuid4().hex[:8]}"
            await story_repo.create({
                "story_id": sid,
                "user_id": "test_user",
                "child_id": "child_lc",
                "age_group": "6-8",
                "story": {
                    "text": f"A lifecycle {tag} story about dragons.",
                    "word_count": 6,
                },
                "educational_value": {"themes": ["adventure"]},
                "characters": [],
                "safety_score": 0.99,  # always safe — isolate lifecycle effect
                "story_type": "image_to_story",
                "created_at": now,
            })
            return sid

        async def link_primary(story_id: str, state: str) -> None:
            aid = await self.arepo.create(
                ArtifactCreate(
                    artifact_type=ArtifactType.TEXT,
                    artifact_payload=uuid.uuid4().hex,
                )
            )
            # Walk the valid lifecycle transitions to reach the target state.
            if state == "candidate":
                await self.arepo.update_lifecycle_state(aid, "candidate")
            elif state == "published":
                await self.arepo.update_lifecycle_state(aid, "candidate")
                await self.arepo.update_lifecycle_state(aid, "published")
            elif state == "archived":
                await self.arepo.update_lifecycle_state(aid, "archived")
            # "intermediate" is the default; no transition needed.
            await self.lrepo.upsert(
                StoryArtifactLinkCreate(
                    story_id=story_id,
                    artifact_id=aid,
                    role=StoryArtifactRole.STORY_TEXT,
                    is_primary=True,
                )
            )

        self.published_id = await make_story("pub")
        await link_primary(self.published_id, "published")
        self.candidate_id = await make_story("cand")
        await link_primary(self.candidate_id, "candidate")
        self.intermediate_id = await make_story("inter")
        await link_primary(self.intermediate_id, "intermediate")
        self.archived_id = await make_story("arch")
        await link_primary(self.archived_id, "archived")
        self.legacy_id = await make_story("legacy")  # no artifact link

        self.all_ids = [
            self.published_id,
            self.candidate_id,
            self.intermediate_id,
            self.archived_id,
            self.legacy_id,
        ]

        yield

        for sid in self.all_ids:
            await db_manager.execute(
                "DELETE FROM stories WHERE story_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_visible_states_constant(self):
        """Only published and candidate are visible states."""
        assert VISIBLE_LIFECYCLE_STATES == {"published", "candidate"}

    async def test_get_visible_story_ids_helper(self):
        """The batch helper classifies each lifecycle state correctly."""
        visible = await _get_visible_story_ids(self.all_ids)
        assert self.published_id in visible
        assert self.candidate_id in visible
        assert self.intermediate_id not in visible
        assert self.archived_id not in visible
        assert self.legacy_id in visible, "Legacy (no link) must stay visible"

    async def test_get_visible_story_ids_empty(self):
        """Empty input returns an empty set (no query)."""
        assert await _get_visible_story_ids([]) == set()

    async def test_library_filters_by_lifecycle(self, test_client):
        """GET /api/v1/library hides intermediate/archived, keeps the rest."""
        async with test_client as client:
            resp = await client.get("/api/v1/library", params={"limit": 100})
            assert resp.status_code == 200
            item_ids = [item["id"] for item in resp.json()["items"]]

            assert self.published_id in item_ids
            assert self.candidate_id in item_ids
            assert self.legacy_id in item_ids
            assert self.intermediate_id not in item_ids
            assert self.archived_id not in item_ids

    async def test_search_filters_by_lifecycle(self, test_client):
        """GET /api/v1/library/search hides intermediate/archived stories."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/search",
                params={"q": "dragons", "limit": 100},
            )
            assert resp.status_code == 200
            item_ids = [item["id"] for item in resp.json()["items"]]

            assert self.published_id in item_ids
            assert self.candidate_id in item_ids
            assert self.legacy_id in item_ids
            assert self.intermediate_id not in item_ids
            assert self.archived_id not in item_ids

    async def test_lifecycle_lookup_failure_hides_stories(self, monkeypatch):
        """A failed lifecycle lookup must not expose unverified content."""

        async def fail_lookup(self, story_ids):
            raise RuntimeError("lifecycle store unavailable")

        monkeypatch.setattr(
            StoryArtifactLinkRepository,
            "get_primary_lifecycle_states",
            fail_lookup,
        )

        assert await _get_visible_story_ids(self.all_ids) == set()
