"""Server-owned achievement badge definitions and award service (#536)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .database.achievement_repository import AchievementRepository, achievement_repo


@dataclass(frozen=True)
class AchievementDefinition:
    """Deterministic badge definition owned by the server."""

    achievement_id: str
    title: str
    description: str
    icon: str
    category: str
    award_event: str


ACHIEVEMENT_DEFINITIONS: tuple[AchievementDefinition, ...] = tuple(
    sorted(
        (
            AchievementDefinition(
                achievement_id="first_audio_narration",
                title="Voice Explorer",
                description="Listened to a story with narration.",
                icon="volume-2",
                category="care",
                award_event="first_audio_narration",
            ),
            AchievementDefinition(
                achievement_id="first_character_created",
                title="Character Keeper",
                description="Created a reusable story character.",
                icon="sparkles",
                category="creativity",
                award_event="first_character_created",
            ),
            AchievementDefinition(
                achievement_id="first_image_story",
                title="Picture Story Starter",
                description="Turned a picture into a story.",
                icon="image",
                category="storytelling",
                award_event="first_image_story",
            ),
            AchievementDefinition(
                achievement_id="first_interactive_story",
                title="Choice Maker",
                description="Started an interactive story.",
                icon="git-branch",
                category="storytelling",
                award_event="first_interactive_story",
            ),
            AchievementDefinition(
                achievement_id="first_kids_daily",
                title="Curious Listener",
                description="Explored one Kids Daily episode.",
                icon="newspaper",
                category="learning",
                award_event="first_kids_daily",
            ),
        ),
        key=lambda item: item.achievement_id,
    )
)

_DEFINITIONS_BY_ID = {
    definition.achievement_id: definition for definition in ACHIEVEMENT_DEFINITIONS
}


class UnknownAchievementError(ValueError):
    """Raised when a caller asks to award a badge the server does not define."""


class AchievementService:
    """Validates badge definitions and delegates persistence to the repository."""

    def __init__(self, repo: AchievementRepository | None = None):
        self._repo = repo if repo is not None else achievement_repo

    def list_definitions(self) -> list[dict]:
        """Return all deterministic server-owned badge definitions."""
        return [asdict(definition) for definition in ACHIEVEMENT_DEFINITIONS]

    async def award(
        self, user_id: str, child_id: str, achievement_id: str
    ) -> dict:
        """Award a known achievement idempotently."""
        definition = _DEFINITIONS_BY_ID.get(achievement_id)
        if definition is None:
            raise UnknownAchievementError(achievement_id)

        award, created = await self._repo.award(
            user_id=user_id,
            child_id=child_id,
            achievement_id=definition.achievement_id,
            source_event=definition.award_event,
        )
        return {
            "achievement": asdict(award),
            "definition": asdict(definition),
            "created": created,
        }

    async def list_for_child(self, user_id: str, child_id: str) -> dict:
        """List awards for one user-owned child profile."""
        awards = await self._repo.list_for_child(user_id, child_id)
        definitions = self.list_definitions()
        definitions_by_id = {
            definition["achievement_id"]: definition for definition in definitions
        }
        items = []
        for award in awards:
            item = asdict(award)
            item["definition"] = definitions_by_id.get(award.achievement_id)
            items.append(item)

        return {
            "child_id": child_id,
            "items": items,
            "total": len(items),
            "available_definitions": definitions,
        }


achievement_service = AchievementService()
