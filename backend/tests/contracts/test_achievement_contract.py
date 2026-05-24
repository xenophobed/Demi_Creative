"""Achievement badge contract tests (#536).

Server-owned achievement badges are deterministic, safe, and scoped to the
authenticated user's child profile.
"""

import pytest
import pytest_asyncio

from backend.src.services.achievement_service import (
    ACHIEVEMENT_DEFINITIONS,
    AchievementService,
    UnknownAchievementError,
)
from backend.src.services.database.achievement_repository import (
    AchievementData,
    AchievementRepository,
    achievement_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema


@pytest_asyncio.fixture
async def db():
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    for user_id in ("user_a", "user_b"):
        await manager.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, referral_code,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_id,
                f"{user_id}@example.com",
                "h",
                f"code_{user_id}",
                "2026-05-20T00:00:00",
                "2026-05-20T00:00:00",
            ),
        )
    await manager.commit()
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def repo(db):
    return AchievementRepository(db)


class TestAchievementDefinitions:
    def test_definitions_are_deterministic_and_unique(self):
        ids = [definition.achievement_id for definition in ACHIEVEMENT_DEFINITIONS]

        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))

    def test_definitions_are_server_owned_badges(self):
        for definition in ACHIEVEMENT_DEFINITIONS:
            assert definition.achievement_id
            assert definition.title
            assert definition.description
            assert definition.icon
            assert definition.category in {
                "creativity",
                "storytelling",
                "learning",
                "care",
            }
            assert definition.award_event in {
                "first_image_story",
                "first_interactive_story",
                "first_kids_daily",
                "first_character_created",
                "first_audio_narration",
            }

    def test_definitions_do_not_reward_unsafe_sharing_or_excessive_usage(self):
        unsafe_terms = {
            "share",
            "shared",
            "sharing",
            "publish",
            "viral",
            "streak",
            "10",
            "100",
            "unlimited",
        }
        text = " ".join(
            " ".join(
                [
                    definition.achievement_id,
                    definition.title,
                    definition.description,
                    definition.award_event,
                ]
            )
            for definition in ACHIEVEMENT_DEFINITIONS
        ).lower()

        for term in unsafe_terms:
            assert term not in text


class TestAchievementSchema:
    @pytest.mark.asyncio
    async def test_child_achievements_schema_exists(self, db):
        row = await db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='child_achievements'"
        )

        assert row is not None

    @pytest.mark.asyncio
    async def test_uniqueness_is_user_child_achievement(self, db):
        indexes = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='child_achievements'"
        )
        index_names = {row["name"] for row in indexes}

        assert "idx_child_achievements_user_child" in index_names


class TestAchievementRepository:
    @pytest.mark.asyncio
    async def test_singleton_exists(self):
        assert isinstance(achievement_repo, AchievementRepository)

    @pytest.mark.asyncio
    async def test_award_creates_row(self, repo):
        result, created = await repo.award(
            user_id="user_a",
            child_id="child_a",
            achievement_id="first_image_story",
            source_event="first_image_story",
        )

        assert created is True
        assert isinstance(result, AchievementData)
        assert result.user_id == "user_a"
        assert result.child_id == "child_a"
        assert result.achievement_id == "first_image_story"

    @pytest.mark.asyncio
    async def test_award_is_idempotent_for_same_user_child(self, repo):
        first, first_created = await repo.award(
            "user_a", "child_a", "first_image_story", "first_image_story"
        )
        second, second_created = await repo.award(
            "user_a", "child_a", "first_image_story", "first_image_story"
        )
        rows = await repo.list_for_child("user_a", "child_a")

        assert first_created is True
        assert second_created is False
        assert second.awarded_at == first.awarded_at
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_ownership_scope_includes_user_and_child(self, repo):
        await repo.award("user_a", "child_a", "first_image_story", "first_image_story")
        await repo.award("user_a", "child_b", "first_image_story", "first_image_story")
        await repo.award("user_b", "child_a", "first_image_story", "first_image_story")

        assert len(await repo.list_for_child("user_a", "child_a")) == 1
        assert len(await repo.list_for_child("user_a", "child_b")) == 1
        assert len(await repo.list_for_child("user_b", "child_a")) == 1

    @pytest.mark.asyncio
    async def test_list_does_not_cross_user_boundary(self, repo):
        await repo.award("user_a", "shared_child", "first_image_story", "first_image_story")
        await repo.award(
            "user_b",
            "shared_child",
            "first_interactive_story",
            "first_interactive_story",
        )

        rows = await repo.list_for_child("user_a", "shared_child")

        assert [row.achievement_id for row in rows] == ["first_image_story"]


class TestAchievementService:
    @pytest.mark.asyncio
    async def test_service_rejects_unknown_achievement(self, repo):
        service = AchievementService(repo)

        with pytest.raises(UnknownAchievementError):
            await service.award("user_a", "child_a", "not_real")

    @pytest.mark.asyncio
    async def test_service_returns_definition_with_award(self, repo):
        service = AchievementService(repo)

        result = await service.award("user_a", "child_a", "first_image_story")

        assert result["achievement"]["achievement_id"] == "first_image_story"
        assert result["definition"]["achievement_id"] == "first_image_story"
        assert result["created"] is True
