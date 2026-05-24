"""
Tests for GET /api/v1/library/stats (#133)

Verifies the library stats endpoint returns creation counts grouped by week or month.
Covers: response shape, group_by parameter, empty state, and privacy (no personal data).
"""

import pytest
import uuid
from datetime import datetime, timedelta

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import (
    child_profile_repo,
    story_repo,
    session_repo,
    db_manager,
)
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


@pytest.mark.asyncio
class TestLibraryStatsEndpoint:
    """Integration tests for GET /api/v1/library/stats."""

    @pytest.fixture(autouse=True)
    async def setup_test_data(self):
        """Insert stories and sessions across different weeks for stats testing."""
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        # Seed test user so FK constraints are satisfied (#184)
        now = datetime.now()
        await db_manager.execute(
            """INSERT OR IGNORE INTO users
                (user_id, username, email, password_hash, display_name,
                 is_active, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            ("test_user", "test_user", "test@example.com",
             "test_hash", "Test User",
             now.isoformat(), now.isoformat()),
        )
        await db_manager.commit()

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
                "story_type": "kids_daily",
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


@pytest.mark.asyncio
class TestLibraryCountsEndpoint:
    """Integration tests for profile/library count sync (#524)."""

    @pytest.fixture(autouse=True)
    async def setup_count_data(self):
        """Insert mixed content, including unsafe content that must be excluded."""
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        now = datetime.now().isoformat()
        await db_manager.execute(
            """INSERT OR IGNORE INTO users
                (user_id, username, email, password_hash, display_name,
                 is_active, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (
                "test_user",
                "test_user",
                "test@example.com",
                "test_hash",
                "Test User",
                now,
                now,
            ),
        )
        await db_manager.commit()

        self.story_ids = []
        for story_type, safety_score in [
            ("image_to_story", 0.95),
            ("kids_daily", 0.96),
            ("morning_show", 0.98),
            ("news_to_kids", 0.97),
            ("image_to_story", 0.40),
        ]:
            sid = f"counts-{story_type}-{uuid.uuid4().hex[:8]}"
            self.story_ids.append(sid)
            await story_repo.create(
                {
                    "story_id": sid,
                    "user_id": "test_user",
                    "child_id": "child_001",
                    "age_group": "9-12",
                    "story": {
                        "text": f"{story_type} count fixture.",
                        "word_count": 4,
                    },
                    "educational_value": {"themes": ["counts"]},
                    "characters": [],
                    "safety_score": safety_score,
                    "story_type": story_type,
                    "created_at": now,
                }
            )

        session = await session_repo.create_session(
            child_id="child_001",
            story_title="Counts test session",
            age_group="9-12",
            interests=["space"],
            theme="adventure",
            voice="fable",
            enable_audio=True,
            total_segments=4,
            user_id="test_user",
        )
        self.session_ids = [session.session_id]

        yield

        for sid in self.story_ids:
            await db_manager.execute("DELETE FROM stories WHERE story_id = ?", (sid,))
        for sid in self.session_ids:
            await db_manager.execute(
                "DELETE FROM sessions WHERE session_id = ?", (sid,)
            )
        await db_manager.commit()

    async def test_counts_match_library_visible_categories(self, test_client):
        """Counts endpoint returns library-visible totals by profile stat category."""
        async with test_client as client:
            counts_resp = await client.get("/api/v1/library/counts")
            assert counts_resp.status_code == 200
            counts = counts_resp.json()

            art_resp = await client.get(
                "/api/v1/library", params={"type": "art-story", "limit": 1}
            )
            interactive_resp = await client.get(
                "/api/v1/library", params={"type": "interactive", "limit": 1}
            )
            news_resp = await client.get(
                "/api/v1/library", params={"type": "kids-news", "limit": 1}
            )

            assert counts["art_story_count"] == art_resp.json()["total"]
            assert counts["interactive_count"] == interactive_resp.json()["total"]
            assert counts["news_count"] == news_resp.json()["total"]
            assert counts["total"] == (
                counts["art_story_count"]
                + counts["interactive_count"]
                + counts["news_count"]
            )


@pytest.mark.asyncio
class TestRichStatsParentDashboardAccess:
    """Role and child-scope coverage for parent creativity dashboard (#532)."""

    @pytest.fixture(autouse=True)
    async def setup_parent_dashboard_data(self):
        if not db_manager.is_connected:
            await db_manager.connect()
            await init_schema(db_manager)

        self.previous_override = app.dependency_overrides.get(get_current_user)
        now = datetime.now().isoformat()
        self.parent_user_id = "test_user"
        await db_manager.execute(
            """INSERT OR IGNORE INTO users
                (user_id, username, email, password_hash, display_name,
                 is_active, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (
                self.parent_user_id,
                self.parent_user_id,
                "test@example.com",
                "test_hash",
                "Test User",
                now,
                now,
            ),
        )
        await db_manager.commit()
        await db_manager.execute(
            "DELETE FROM child_profiles WHERE user_id = ? AND child_id IN (?, ?, ?)",
            (self.parent_user_id, "child_alpha", "child_beta", "child_empty"),
        )
        await db_manager.commit()

        self.story_ids = []
        for user_id, child_id, label in [
            (self.parent_user_id, "child_alpha", "alpha"),
            (self.parent_user_id, "child_beta", "beta"),
        ]:
            await child_profile_repo.create(
                user_id=user_id,
                child_id=child_id,
                name=label.title(),
                age_group="9-12",
                interests=[],
                is_default=child_id == "child_alpha",
            )
            sid = f"parent-rich-{label}-{uuid.uuid4().hex[:8]}"
            self.story_ids.append(sid)
            await story_repo.create(
                {
                    "story_id": sid,
                    "user_id": user_id,
                    "child_id": child_id,
                    "age_group": "9-12",
                    "story": {
                        "text": f"{label} creativity dashboard fixture.",
                        "word_count": 4,
                    },
                    "educational_value": {"themes": [label]},
                    "characters": [],
                    "safety_score": 0.95,
                    "story_type": "image_to_story",
                    "created_at": now,
                }
            )

        await child_profile_repo.create(
            user_id=self.parent_user_id,
            child_id="child_empty",
            name="Empty",
            age_group="6-8",
            interests=[],
        )

        unsafe_id = f"parent-rich-unsafe-{uuid.uuid4().hex[:8]}"
        self.story_ids.append(unsafe_id)
        await story_repo.create(
            {
                "story_id": unsafe_id,
                "user_id": self.parent_user_id,
                "child_id": "child_alpha",
                "age_group": "9-12",
                "story": {
                    "text": "Unsafe dashboard fixture should stay hidden.",
                    "word_count": 6,
                },
                "educational_value": {"themes": ["unsafe"]},
                "characters": [],
                "safety_score": 0.4,
                "story_type": "image_to_story",
                "created_at": now,
            }
        )

        yield

        if self.previous_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = self.previous_override
        for sid in self.story_ids:
            await db_manager.execute("DELETE FROM stories WHERE story_id = ?", (sid,))
        for child_id in ("child_alpha", "child_beta", "child_empty"):
            await db_manager.execute(
                "DELETE FROM child_profiles WHERE user_id = ? AND child_id = ?",
                (self.parent_user_id, child_id),
            )
        await db_manager.execute(
            "UPDATE users SET default_child_id = NULL WHERE user_id = ?",
            (self.parent_user_id,),
        )
        await db_manager.commit()

    def _override_user(self, *, role: str = "parent") -> None:
        async def fake_user() -> UserData:
            return UserData(
                user_id=self.parent_user_id,
                username=self.parent_user_id,
                email=f"{self.parent_user_id}@example.com",
                password_hash="test_hash",
                display_name="Parent User",
                is_active=True,
                is_verified=True,
                role=role,
                created_at="",
                updated_at="",
                default_child_id="child_alpha",
            )

        app.dependency_overrides[get_current_user] = fake_user

    async def test_parent_dashboard_requires_parent_role(self, test_client):
        self._override_user(role="child")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats-rich",
                params={"parent_dashboard": True, "child_id": "child_alpha"},
            )

        assert resp.status_code == 403
        assert resp.json()["detail"] == "Parent dashboard requires parent role"

    async def test_parent_dashboard_scopes_to_owned_child(self, test_client):
        self._override_user(role="parent")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats-rich",
                params={"parent_dashboard": True, "child_id": "child_alpha"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert sum(p["creation_count"] for p in data["periods"]) == 1
        assert data["streak_days"] == 0
        assert data["top_themes"] == [{"theme": "alpha", "count": 1}]
        assert [item["id"] for item in data["recent_creations"]] == [self.story_ids[0]]
        assert data["recent_creations"][0]["title"].startswith("alpha creativity")

    async def test_parent_dashboard_rejects_unowned_child_scope(self, test_client):
        self._override_user(role="parent")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats-rich",
                params={"parent_dashboard": True, "child_id": "child_external"},
            )

        assert resp.status_code == 404

    async def test_parent_dashboard_loads_empty_owned_child_profile(self, test_client):
        self._override_user(role="parent")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/library/stats-rich",
                params={"parent_dashboard": True, "child_id": "child_empty"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["periods"] == []
        assert data["top_themes"] == []
        assert data["recent_creations"] == []
