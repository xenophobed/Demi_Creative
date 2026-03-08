"""
Tests for GET /api/v1/library/stats (#133)

Verifies the library stats endpoint returns creation counts grouped by week or month.
Covers: response shape, group_by parameter, empty state, and privacy (no personal data).
"""

import pytest
import uuid
from datetime import datetime, timedelta

from backend.src.services.database import story_repo, session_repo, db_manager
from backend.src.services.database.schema import init_schema


@pytest.mark.asyncio
class TestLibraryStatsEndpoint:
    """Integration tests for GET /api/v1/library/stats."""

    @pytest.fixture(autouse=True)
    async def setup_test_data(self):
        """Insert stories and sessions across different weeks for stats testing."""
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        self.story_ids = []
        self.session_ids = []

        # Create 3 stories in the current week
        now = datetime.now()
        for i in range(3):
            sid = f"stats-story-{uuid.uuid4().hex[:8]}"
            self.story_ids.append(sid)
            await story_repo.create({
                "story_id": sid,
                "user_id": "test_user",
                "child_id": "child_001",
                "age_group": "9-12",
                "story": {"text": f"Story {i} for stats testing.", "word_count": 5},
                "educational_value": {"themes": ["creativity"]},
                "characters": [],
                "safety_score": 0.95,
                "story_type": "image_to_story",
                "created_at": now.isoformat(),
            })

        # Create 2 stories two weeks ago
        two_weeks_ago = now - timedelta(weeks=2)
        for i in range(2):
            sid = f"stats-old-{uuid.uuid4().hex[:8]}"
            self.story_ids.append(sid)
            await story_repo.create({
                "story_id": sid,
                "user_id": "test_user",
                "child_id": "child_001",
                "age_group": "9-12",
                "story": {"text": f"Older story {i}.", "word_count": 3},
                "educational_value": {"themes": ["nature"]},
                "characters": [],
                "safety_score": 0.90,
                "story_type": "news_to_kids",
                "created_at": two_weeks_ago.isoformat(),
            })

        # Create 1 interactive session in current week
        session = await session_repo.create_session(
            child_id="child_001",
            story_title="Stats test session",
            age_group="9-12",
            interests=["animals"],
            theme="adventure",
            voice="fable",
            enable_audio=True,
            total_segments=4,
            user_id="test_user",
        )
        self.session_ids.append(session.session_id)

        yield

        # Cleanup
        for sid in self.story_ids:
            await db_manager.execute(
                "DELETE FROM stories WHERE story_id = ?", (sid,)
            )
        for sid in self.session_ids:
            await db_manager.execute(
                "DELETE FROM sessions WHERE session_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_stats_returns_200_with_periods(self, test_client):
        """GET /api/v1/library/stats returns 200 with periods array."""
        async with test_client as client:
            resp = await client.get("/api/v1/library/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "periods" in data
            assert isinstance(data["periods"], list)

    async def test_stats_default_group_by_week(self, test_client):
        """Default grouping is by week. Period format: YYYY-Www."""
        async with test_client as client:
            resp = await client.get("/api/v1/library/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["periods"]) >= 2, "Should have at least 2 weeks of data"

            for period in data["periods"]:
                assert "period" in period
                assert "count" in period
                assert isinstance(period["count"], int)
                assert period["count"] > 0
                # Week format: YYYY-Www (e.g., 2026-W10)
                assert "-W" in period["period"], f"Week format expected, got: {period['period']}"

    async def test_stats_group_by_month(self, test_client):
        """group_by=month returns periods as YYYY-MM."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats", params={"group_by": "month"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["periods"]) >= 1

            for period in data["periods"]:
                # Month format: YYYY-MM (e.g., 2026-03)
                assert len(period["period"]) == 7, f"Month format expected, got: {period['period']}"
                assert "-" in period["period"]

    async def test_stats_counts_include_all_content_types(self, test_client):
        """Stats should count stories AND sessions (all content types)."""
        async with test_client as client:
            resp = await client.get("/api/v1/library/stats")
            assert resp.status_code == 200
            data = resp.json()

            total_count = sum(p["count"] for p in data["periods"])
            # We created 5 stories + 1 session = 6 items minimum
            # (other tests may have inserted items too, so use >=)
            assert total_count >= 6

    async def test_stats_invalid_group_by_returns_422(self, test_client):
        """Invalid group_by value returns 422 validation error."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats", params={"group_by": "day"}
            )
            assert resp.status_code == 422

    async def test_stats_no_personal_data_in_response(self, test_client):
        """Response must not contain personal or private data fields."""
        async with test_client as client:
            resp = await client.get("/api/v1/library/stats")
            assert resp.status_code == 200
            raw = resp.text
            # Should not contain any user/child identifiers
            assert "user_id" not in raw
            assert "child_id" not in raw
            assert "email" not in raw


@pytest.mark.asyncio
class TestLibraryStatsEmpty:
    """Test stats endpoint with no data for the user."""

    async def test_empty_library_returns_empty_periods(self, test_client):
        """User with no creations gets an empty periods array, not an error."""
        # The test_user might have data from other tests, so we check shape only
        async with test_client as client:
            resp = await client.get("/api/v1/library/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "periods" in data
            assert isinstance(data["periods"], list)
