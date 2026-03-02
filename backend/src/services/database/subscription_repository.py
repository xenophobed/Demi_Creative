"""Topic subscription repository (#94)."""

from datetime import datetime
from typing import Any, Dict, List

from .connection import db_manager


class DuplicateSubscriptionError(Exception):
    """Raised when an active subscription already exists."""


class MaxSubscriptionsExceededError(Exception):
    """Raised when a child exceeds the max allowed subscriptions."""


class SubscriptionRepository:
    """CRUD operations for topic_subscriptions."""

    MAX_SUBSCRIPTIONS_PER_CHILD = 5

    def __init__(self):
        self._db = db_manager

    async def count_active(self, user_id: str, child_id: str) -> int:
        row = await self._db.fetchone(
            """
            SELECT COUNT(*) as count
            FROM topic_subscriptions
            WHERE user_id = ? AND child_id = ? AND is_active = 1
            """,
            (user_id, child_id),
        )
        return int(row["count"]) if row else 0

    async def create(self, user_id: str, child_id: str, topic: str) -> Dict[str, Any]:
        existing = await self._db.fetchone(
            """
            SELECT * FROM topic_subscriptions
            WHERE user_id = ? AND child_id = ? AND topic = ?
            """,
            (user_id, child_id, topic),
        )

        if existing and int(existing.get("is_active", 0)) == 1:
            raise DuplicateSubscriptionError("Subscription already exists")

        if not existing:
            active_count = await self.count_active(user_id, child_id)
            if active_count >= self.MAX_SUBSCRIPTIONS_PER_CHILD:
                raise MaxSubscriptionsExceededError(
                    f"Maximum subscriptions per child is {self.MAX_SUBSCRIPTIONS_PER_CHILD}"
                )

        now = datetime.now().isoformat()

        if existing:
            await self._db.execute(
                """
                UPDATE topic_subscriptions
                SET subscribed_at = ?, is_active = 1
                WHERE user_id = ? AND child_id = ? AND topic = ?
                """,
                (now, user_id, child_id, topic),
            )
        else:
            await self._db.execute(
                """
                INSERT INTO topic_subscriptions (user_id, child_id, topic, subscribed_at, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (user_id, child_id, topic, now),
            )

        await self._db.commit()

        row = await self._db.fetchone(
            """
            SELECT child_id, topic, subscribed_at, is_active
            FROM topic_subscriptions
            WHERE user_id = ? AND child_id = ? AND topic = ?
            """,
            (user_id, child_id, topic),
        )
        if not row:
            raise RuntimeError("Failed to fetch created subscription")
        return self._row_to_dict(row)

    async def deactivate(self, user_id: str, child_id: str, topic: str) -> bool:
        cursor = await self._db.execute(
            """
            UPDATE topic_subscriptions
            SET is_active = 0
            WHERE user_id = ? AND child_id = ? AND topic = ? AND is_active = 1
            """,
            (user_id, child_id, topic),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_active(self, user_id: str, child_id: str) -> List[Dict[str, Any]]:
        rows = await self._db.fetchall(
            """
            SELECT child_id, topic, subscribed_at, is_active
            FROM topic_subscriptions
            WHERE user_id = ? AND child_id = ? AND is_active = 1
            ORDER BY subscribed_at DESC
            """,
            (user_id, child_id),
        )
        return [self._row_to_dict(row) for row in rows]

    async def list_all_active(self) -> List[Dict[str, Any]]:
        rows = await self._db.fetchall(
            """
            SELECT user_id, child_id, topic, subscribed_at, is_active
            FROM topic_subscriptions
            WHERE is_active = 1
            ORDER BY subscribed_at ASC
            """
        )
        return [
            {
                "user_id": row["user_id"],
                "child_id": row["child_id"],
                "topic": row["topic"],
                "subscribed_at": row["subscribed_at"],
                "is_active": bool(row.get("is_active", 1)),
            }
            for row in rows
        ]

    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "child_id": row["child_id"],
            "topic": row["topic"],
            "subscribed_at": row["subscribed_at"],
            "is_active": bool(row.get("is_active", 1)),
        }


subscription_repo = SubscriptionRepository()
