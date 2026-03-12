"""
Preference Repository Contract Tests

Locks the shape and behavior of PreferenceRepository before adding
new features (memory API, privacy controls). Tests profile normalization,
bump logic, morning show scoring, and score bounds.

Parent Epic: #42 | Issue: #163
"""

import pytest
from datetime import datetime

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.preference_repository import PreferenceRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def db():
    """In-memory database for testing."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await manager.execute(
        """
        CREATE TABLE IF NOT EXISTS child_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id TEXT UNIQUE NOT NULL,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    await manager.commit()
    yield manager
    await manager.disconnect()


@pytest.fixture
def repo(db):
    r = PreferenceRepository()
    r._db = db
    return r


# ============================================================================
# Profile normalization
# ============================================================================


class TestProfileNormalization:
    """Contract: _normalize_profile always returns all required keys."""

    @pytest.mark.asyncio
    async def test_empty_profile_has_all_keys(self, repo):
        profile = await repo.get_profile("new-child")
        assert "themes" in profile and isinstance(profile["themes"], dict)
        assert "concepts" in profile and isinstance(profile["concepts"], dict)
        assert "interests" in profile and isinstance(profile["interests"], dict)
        assert "recent_choices" in profile and isinstance(profile["recent_choices"], list)
        assert "morning_show" in profile and isinstance(profile["morning_show"], dict)

    @pytest.mark.asyncio
    async def test_normalize_repairs_corrupted_profile(self, repo):
        """If stored data has wrong types, normalization fixes them."""
        profile = repo._normalize_profile({"themes": "not-a-dict", "recent_choices": 42})
        assert isinstance(profile["themes"], dict)
        assert isinstance(profile["recent_choices"], list)

    @pytest.mark.asyncio
    async def test_morning_show_subkeys_present(self, repo):
        profile = await repo.get_profile("child-1")
        morning = profile["morning_show"]
        assert "topic_scores" in morning and isinstance(morning["topic_scores"], dict)
        assert "topic_stats" in morning and isinstance(morning["topic_stats"], dict)
        assert "last_event_at" in morning


# ============================================================================
# update_from_story_result
# ============================================================================


class TestUpdateFromStoryResult:
    """Contract: update_from_story_result increments themes by +1, concepts by +1."""

    @pytest.mark.asyncio
    async def test_themes_increment_by_one(self, repo):
        await repo.update_from_story_result("child-1", {"themes": ["space", "adventure"]})
        profile = await repo.get_profile("child-1")
        assert profile["themes"]["space"] == 1
        assert profile["themes"]["adventure"] == 1

    @pytest.mark.asyncio
    async def test_themes_accumulate_across_calls(self, repo):
        await repo.update_from_story_result("child-1", {"themes": ["space"]})
        await repo.update_from_story_result("child-1", {"themes": ["space"]})
        profile = await repo.get_profile("child-1")
        assert profile["themes"]["space"] == 2

    @pytest.mark.asyncio
    async def test_concepts_extracted_from_dicts(self, repo):
        await repo.update_from_story_result("child-1", {
            "concepts": [{"term": "gravity"}, {"term": "orbit"}]
        })
        profile = await repo.get_profile("child-1")
        assert profile["concepts"]["gravity"] == 1
        assert profile["concepts"]["orbit"] == 1

    @pytest.mark.asyncio
    async def test_concepts_extracted_from_strings(self, repo):
        await repo.update_from_story_result("child-1", {"concepts": ["gravity"]})
        profile = await repo.get_profile("child-1")
        assert profile["concepts"]["gravity"] == 1


# ============================================================================
# update_from_choices
# ============================================================================


class TestUpdateFromChoices:
    """Contract: update_from_choices increments interests by +2, caps recent_choices at 20."""

    @pytest.mark.asyncio
    async def test_interests_increment_by_two(self, repo):
        await repo.update_from_choices(
            "child-1",
            choice_history=["a"],
            session_data={"interests": ["robots"]},
        )
        profile = await repo.get_profile("child-1")
        assert profile["interests"]["robots"] == 2

    @pytest.mark.asyncio
    async def test_theme_from_session_bumped_by_two(self, repo):
        await repo.update_from_choices(
            "child-1",
            choice_history=[],
            session_data={"theme": "underwater"},
        )
        profile = await repo.get_profile("child-1")
        assert profile["themes"]["underwater"] == 2

    @pytest.mark.asyncio
    async def test_recent_choices_capped_at_20(self, repo):
        choices = [f"choice-{i}" for i in range(30)]
        await repo.update_from_choices(
            "child-1",
            choice_history=choices,
            session_data={},
        )
        profile = await repo.get_profile("child-1")
        assert len(profile["recent_choices"]) == 20


# ============================================================================
# update_from_morning_show
# ============================================================================


class TestUpdateFromMorningShow:
    """Contract: morning show events update scores within bounds."""

    @pytest.mark.asyncio
    async def test_start_event_adds_0_2(self, repo):
        score = await repo.update_from_morning_show("child-1", "space", "start", 0.0)
        assert score == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_complete_event_adds_1_0(self, repo):
        score = await repo.update_from_morning_show("child-1", "space", "complete", 1.0)
        assert score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_abandon_event_subtracts_0_6(self, repo):
        score = await repo.update_from_morning_show("child-1", "space", "abandon", 0.3)
        assert score == pytest.approx(-0.6)

    @pytest.mark.asyncio
    async def test_score_bounded_below_at_negative_5(self, repo):
        # Drive score well below -5
        for _ in range(15):
            score = await repo.update_from_morning_show("child-1", "boring", "abandon", 0.3)
        assert score >= -5.0

    @pytest.mark.asyncio
    async def test_score_bounded_above_at_20(self, repo):
        # Drive score well above 20
        for _ in range(25):
            score = await repo.update_from_morning_show("child-1", "awesome", "complete", 1.0)
        assert score <= 20.0

    @pytest.mark.asyncio
    async def test_stats_tracked_correctly(self, repo):
        await repo.update_from_morning_show("child-1", "space", "start", 0.0)
        await repo.update_from_morning_show("child-1", "space", "complete", 1.0)
        await repo.update_from_morning_show("child-1", "space", "abandon", 0.2)

        profile = await repo.get_profile("child-1")
        stats = profile["morning_show"]["topic_stats"]["space"]
        assert stats["started"] == 1
        assert stats["completed"] == 1
        assert stats["abandoned"] == 1
