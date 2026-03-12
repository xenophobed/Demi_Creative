"""
Preference Retention & Privacy Contract Tests (#164)

Tests data minimization: recent_choices cap, topic score decay,
delete_profile, and get_profile_with_metadata.

Parent Epic: #42 | Issue: #164
"""

import json
import pytest
from datetime import datetime, timedelta

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.preference_repository import PreferenceRepository


@pytest.fixture
async def db():
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


class TestRecentChoicesCap:
    """Contract: recent_choices capped at 50 on save."""

    @pytest.mark.asyncio
    async def test_cap_at_50_on_save(self, repo):
        choices = [f"choice-{i}" for i in range(70)]
        await repo.update_from_choices("child-1", choice_history=choices, session_data={})
        profile = await repo.get_profile("child-1")
        assert len(profile["recent_choices"]) <= 50

    @pytest.mark.asyncio
    async def test_retention_trims_on_read(self, repo):
        """_apply_retention also trims recent_choices."""
        profile = repo._empty_profile()
        profile["recent_choices"] = [f"c-{i}" for i in range(60)]
        result = repo._apply_retention(profile)
        assert len(result["recent_choices"]) == 50


class TestTopicScoreDecay:
    """Contract: topic scores decay by 50% if not updated in 6 months."""

    @pytest.mark.asyncio
    async def test_scores_decay_after_6_months(self, repo):
        stale_date = (datetime.now() - timedelta(days=200)).isoformat()
        profile = repo._empty_profile()
        profile["morning_show"]["topic_scores"] = {"space": 10.0, "robots": 4.0}
        profile["morning_show"]["last_event_at"] = stale_date

        result = repo._apply_retention(profile)
        assert result["morning_show"]["topic_scores"]["space"] == 5.0
        assert result["morning_show"]["topic_scores"]["robots"] == 2.0

    @pytest.mark.asyncio
    async def test_scores_no_decay_if_recent(self, repo):
        recent_date = datetime.now().isoformat()
        profile = repo._empty_profile()
        profile["morning_show"]["topic_scores"] = {"space": 10.0}
        profile["morning_show"]["last_event_at"] = recent_date

        result = repo._apply_retention(profile)
        assert result["morning_show"]["topic_scores"]["space"] == 10.0

    @pytest.mark.asyncio
    async def test_scores_no_decay_if_no_event(self, repo):
        profile = repo._empty_profile()
        profile["morning_show"]["topic_scores"] = {"space": 10.0}
        # last_event_at is None by default
        result = repo._apply_retention(profile)
        assert result["morning_show"]["topic_scores"]["space"] == 10.0


class TestDeleteProfile:
    """Contract: delete_profile removes the row."""

    @pytest.mark.asyncio
    async def test_delete_existing_profile(self, repo):
        await repo.update_from_story_result("child-del", {"themes": ["space"]})
        deleted = await repo.delete_profile("child-del")
        assert deleted is True

        profile = await repo.get_profile("child-del")
        assert profile["themes"] == {}

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, repo):
        deleted = await repo.delete_profile("ghost-child")
        assert deleted is False


class TestGetProfileWithMetadata:
    """Contract: get_profile_with_metadata includes timestamps."""

    @pytest.mark.asyncio
    async def test_includes_timestamps_after_save(self, repo):
        await repo.update_from_story_result("child-ts", {"themes": ["ocean"]})
        result = await repo.get_profile_with_metadata("child-ts")
        assert "profile" in result
        assert "last_updated_at" in result
        assert result["last_updated_at"] is not None
        assert "data_collected_since" in result

    @pytest.mark.asyncio
    async def test_new_child_returns_none_timestamps(self, repo):
        result = await repo.get_profile_with_metadata("new-child")
        assert result["data_collected_since"] is None
        assert result["last_updated_at"] is None
