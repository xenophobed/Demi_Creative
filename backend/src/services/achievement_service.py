"""Server-owned achievement badge definitions and award service (#536)."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from .database.achievement_repository import AchievementRepository, achievement_repo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AchievementDefinition:
    """Deterministic badge definition owned by the server."""

    achievement_id: str
    title: str
    description: str
    icon: str
    category: str
    award_event: str


FIRST_STORY = "first_story"
FIRST_INTERACTIVE_ENDING = "first_interactive_ending"
FIRST_KIDS_DAILY_LISTEN = "first_kids_daily_listen"
FIRST_SHARED_POST = "first_shared_post"
FIRST_VIDEO = "first_video"
MULTIPLE_THEMES_TRIED = "multiple_themes_tried"


ACHIEVEMENT_DEFINITIONS: tuple[AchievementDefinition, ...] = tuple(
    sorted(
        (
            AchievementDefinition(
                achievement_id=FIRST_STORY,
                title="Story Starter",
                description="Completed a first picture story.",
                icon="image",
                category="storytelling",
                award_event=FIRST_STORY,
            ),
            AchievementDefinition(
                achievement_id=FIRST_INTERACTIVE_ENDING,
                title="Adventure Finisher",
                description="Finished an interactive story path.",
                icon="git-branch",
                category="storytelling",
                award_event=FIRST_INTERACTIVE_ENDING,
            ),
            AchievementDefinition(
                achievement_id=FIRST_KIDS_DAILY_LISTEN,
                title="Curious Listener",
                description="Listened to a Kids Daily episode.",
                icon="newspaper",
                category="learning",
                award_event=FIRST_KIDS_DAILY_LISTEN,
            ),
            AchievementDefinition(
                achievement_id=FIRST_SHARED_POST,
                title="Kindly Shared",
                description="Shared a safe creation with a group.",
                icon="share-2",
                category="community",
                award_event=FIRST_SHARED_POST,
            ),
            AchievementDefinition(
                achievement_id=FIRST_VIDEO,
                title="Movie Maker",
                description="Made a story video from a creation.",
                icon="video",
                category="creativity",
                award_event=FIRST_VIDEO,
            ),
            AchievementDefinition(
                achievement_id=MULTIPLE_THEMES_TRIED,
                title="Theme Explorer",
                description="Tried more than one story theme.",
                icon="palette",
                category="creativity",
                award_event=MULTIPLE_THEMES_TRIED,
            ),
        ),
        key=lambda item: item.achievement_id,
    )
)

_DEFINITIONS_BY_ID = {
    definition.achievement_id: definition for definition in ACHIEVEMENT_DEFINITIONS
}
_DEFINITIONS_BY_EVENT = {
    definition.award_event: definition for definition in ACHIEVEMENT_DEFINITIONS
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

    async def award_event(self, user_id: str, child_id: str, event: str) -> dict:
        """Award the badge attached to a known server event."""
        definition = _DEFINITIONS_BY_EVENT.get(event)
        if definition is None:
            raise UnknownAchievementError(event)
        return await self.award(user_id, child_id, definition.achievement_id)

    async def award_event_safely(
        self, user_id: str, child_id: str | None, event: str
    ) -> None:
        """Best-effort award hook for creation flows.

        Badge persistence should never block story, video, or sharing
        completion. Unknown events still surface in tests through
        ``award_event``; this helper is deliberately fail-soft for routes.
        """
        if not child_id:
            return
        try:
            await self.award_event(user_id, child_id, event)
        except Exception:
            logger.warning(
                "Achievement award skipped: user_id=%s child_id=%s event=%s",
                user_id,
                child_id,
                event,
                exc_info=True,
            )

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
