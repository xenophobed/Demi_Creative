"""Usage repository — daily AI generation quota tracking.

Tracks how many AI generations each user has consumed on a given date.
All features share a single daily pool (image_to_story, interactive_story,
morning_show/kids_daily all count against the same limit).

Issue: #314 | Parent Epic: #313
"""

from datetime import date, timedelta
from typing import Dict, Any

from .connection import db_manager


class UsageRepository:
    def __init__(self):
        self._db = db_manager

    async def get_usage_today(self, user_id: str) -> int:
        """Return total generation count for user_id today (UTC date)."""
        today = date.today().isoformat()
        row = await self._db.fetchone(
            "SELECT COALESCE(SUM(count), 0) as total FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, today),
        )
        if row is None:
            return 0
        return int(row["total"])

    async def increment(self, user_id: str, feature: str) -> None:
        """Increment usage count for user_id + feature by 1 for today.

        Uses INSERT OR REPLACE with count+1 so it's safe to call without
        checking whether the row exists first.
        """
        today = date.today().isoformat()
        await self._db.execute(
            """
            INSERT INTO daily_usage (user_id, usage_date, feature, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, usage_date, feature)
            DO UPDATE SET count = count + 1
            """,
            (user_id, today, feature),
        )
        await self._db.commit()

    async def get_quota_status(self, user_id: str, limit: int) -> Dict[str, Any]:
        """Return full quota status dict for the API response."""
        used = await self.get_usage_today(user_id)
        remaining = max(0, limit - used)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return {
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "resets_at": f"{tomorrow}T00:00:00Z",
        }


usage_repo = UsageRepository()
