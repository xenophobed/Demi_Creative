"""Achievement badge repository (#536).

Persists server-owned badge awards scoped by (user_id, child_id).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .connection import db_manager


@dataclass(frozen=True)
class AchievementData:
    """Persisted achievement award row."""

    user_id: str
    child_id: str
    achievement_id: str
    source_event: str
    awarded_at: str


class AchievementRepository:
    """Repository for child achievement awards."""

    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    async def award(
        self,
        user_id: str,
        child_id: str,
        achievement_id: str,
        source_event: str,
    ) -> tuple[AchievementData, bool]:
        """
        Award an achievement if it is not already present.

        Returns (award, created). The unique key makes repeat awards for the
        same user/child/achievement idempotent.
        """
        existing = await self.get(user_id, child_id, achievement_id)
        if existing is not None:
            return existing, False

        awarded_at = datetime.now(timezone.utc).isoformat()
        result = await self._db.execute(
            """
            INSERT INTO child_achievements (
                user_id, child_id, achievement_id, source_event, awarded_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, child_id, achievement_id) DO NOTHING
            """,
            (user_id, child_id, achievement_id, source_event, awarded_at),
        )
        await self._db.commit()

        created = result.rowcount > 0
        row = await self.get(user_id, child_id, achievement_id)
        if row is None:
            raise RuntimeError("Achievement award insert did not produce a row")
        return row, created

    async def get(
        self, user_id: str, child_id: str, achievement_id: str
    ) -> Optional[AchievementData]:
        """Return one award by owner scope, or None."""
        row = await self._db.fetchone(
            """
            SELECT user_id, child_id, achievement_id, source_event, awarded_at
            FROM child_achievements
            WHERE user_id = ? AND child_id = ? AND achievement_id = ?
            """,
            (user_id, child_id, achievement_id),
        )
        return self._row_to_data(row) if row else None

    async def list_for_child(
        self, user_id: str, child_id: str
    ) -> list[AchievementData]:
        """List achievement awards for one child owned by a user."""
        rows = await self._db.fetchall(
            """
            SELECT user_id, child_id, achievement_id, source_event, awarded_at
            FROM child_achievements
            WHERE user_id = ? AND child_id = ?
            ORDER BY awarded_at ASC, achievement_id ASC
            """,
            (user_id, child_id),
        )
        return [self._row_to_data(row) for row in rows]

    @staticmethod
    def _row_to_data(row: dict) -> AchievementData:
        return AchievementData(
            user_id=row["user_id"],
            child_id=row["child_id"],
            achievement_id=row["achievement_id"],
            source_event=row["source_event"],
            awarded_at=row["awarded_at"],
        )


achievement_repo = AchievementRepository()
