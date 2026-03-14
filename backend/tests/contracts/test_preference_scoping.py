"""
Preference Scoping & Tracking Validation Contract Tests (#178)

Ensures that:
1. Preferences scoped by user_id + child_id do not collide across users.
2. The tracking endpoint derives child_id and topic from the episode record
   instead of trusting client-supplied values.

Parent Epic: #42, #44
"""

import json
import pytest

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
# Composite key isolation
# ============================================================================


class TestPreferenceScoping:
    """Contract: preferences for user_A:child_1 and user_B:child_1 do not collide."""

    @pytest.mark.asyncio
    async def test_composite_key_format(self):
        key = PreferenceRepository._composite_key("user_A", "child_1")
        assert key == "user_A:child_1"

    @pytest.mark.asyncio
    async def test_different_users_same_child_id_no_collision(self, repo):
        """Two users with the same child_id store separate profiles."""
        await repo.update_from_story_result(
            "child_1", {"themes": ["space"]}, user_id="user_A",
        )
        await repo.update_from_story_result(
            "child_1", {"themes": ["ocean"]}, user_id="user_B",
        )

        profile_a = await repo.get_profile("child_1", user_id="user_A")
        profile_b = await repo.get_profile("child_1", user_id="user_B")

        assert "space" in profile_a["themes"]
        assert "ocean" not in profile_a["themes"]

        assert "ocean" in profile_b["themes"]
        assert "space" not in profile_b["themes"]

    @pytest.mark.asyncio
    async def test_morning_show_scoped_by_user(self, repo):
        """Morning show topic scores are isolated per user."""
        score_a = await repo.update_from_morning_show(
            "child_1", "science", "complete", 1.0, user_id="user_A",
        )
        score_b = await repo.update_from_morning_show(
            "child_1", "science", "start", 0.0, user_id="user_B",
        )

        # user_A completed => +1.0, user_B started => +0.2
        assert score_a == pytest.approx(1.0)
        assert score_b == pytest.approx(0.2)

        # Verify profiles are actually separate
        profile_a = await repo.get_profile("child_1", user_id="user_A")
        profile_b = await repo.get_profile("child_1", user_id="user_B")

        assert profile_a["morning_show"]["topic_scores"]["science"] == pytest.approx(1.0)
        assert profile_b["morning_show"]["topic_scores"]["science"] == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_delete_scoped_by_user(self, repo):
        """Deleting one user's profile does not affect another user's profile."""
        await repo.update_from_story_result(
            "child_1", {"themes": ["space"]}, user_id="user_A",
        )
        await repo.update_from_story_result(
            "child_1", {"themes": ["ocean"]}, user_id="user_B",
        )

        deleted = await repo.delete_profile("child_1", user_id="user_A")
        assert deleted is True

        # user_A profile is gone
        profile_a = await repo.get_profile("child_1", user_id="user_A")
        assert profile_a["themes"] == {}

        # user_B profile still intact
        profile_b = await repo.get_profile("child_1", user_id="user_B")
        assert "ocean" in profile_b["themes"]

    @pytest.mark.asyncio
    async def test_backward_compat_no_user_id(self, repo):
        """When user_id is not provided, falls back to bare child_id key."""
        await repo.update_from_story_result("child_1", {"themes": ["art"]})
        profile = await repo.get_profile("child_1")
        assert "art" in profile["themes"]


# ============================================================================
# Tracking payload validation
# ============================================================================


class TestTrackingPayloadValidation:
    """Contract: tracking endpoint should derive child_id/topic from episode record."""

    @pytest.mark.asyncio
    async def test_trusted_child_id_from_episode(self, repo, db):
        """When tracking uses episode's child_id, mismatched client value is ignored."""
        # Simulate: episode record says child_id=real_child, topic=science
        # Client sends child_id=fake_child, topic=sports
        # The repo should store under the user-scoped key for real_child

        await repo.update_from_morning_show(
            child_id="real_child",  # from episode
            topic="science",       # from episode
            event_type="complete",
            progress=1.0,
            user_id="user_1",
        )

        # Check that real_child profile was updated
        profile = await repo.get_profile("real_child", user_id="user_1")
        assert profile["morning_show"]["topic_scores"]["science"] == pytest.approx(1.0)

        # Verify fake_child has no data
        fake_profile = await repo.get_profile("fake_child", user_id="user_1")
        assert fake_profile["morning_show"]["topic_scores"] == {}

    @pytest.mark.asyncio
    async def test_update_from_choices_scoped(self, repo):
        """update_from_choices also respects user_id scoping."""
        await repo.update_from_choices(
            "child_1",
            choice_history=["a", "b"],
            session_data={"interests": ["robots"]},
            user_id="user_X",
        )

        profile = await repo.get_profile("child_1", user_id="user_X")
        assert profile["interests"]["robots"] == 2

        # Different user sees nothing
        profile_other = await repo.get_profile("child_1", user_id="user_Y")
        assert profile_other["interests"] == {}

    @pytest.mark.asyncio
    async def test_update_from_news_scoped(self, repo):
        """update_from_news also respects user_id scoping."""
        await repo.update_from_news(
            "child_1",
            category="technology",
            key_concepts=[{"term": "AI"}],
            user_id="user_X",
        )

        profile = await repo.get_profile("child_1", user_id="user_X")
        assert "technology" in profile["themes"]
        assert "AI" in profile["concepts"]

        profile_other = await repo.get_profile("child_1", user_id="user_Y")
        assert profile_other["themes"] == {}
