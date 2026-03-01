"""
Favorite Repository

CRUD operations for user favorites (bookmarks) across all content types.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Set

from .connection import db_manager


class FavoriteRepository:
    """Favorite repository for bookmarking library content."""

    def __init__(self):
        self._db = db_manager

    async def add(self, user_id: str, item_type: str, item_id: str) -> bool:
        """
        Add a favorite. Idempotent (INSERT OR IGNORE).

        Args:
            user_id: User's unique ID
            item_type: Content type (art-story, interactive, news)
            item_id: Content item ID

        Returns:
            bool: True on success
        """
        now = datetime.now().isoformat()
        await self._db.execute(
            """
            INSERT OR IGNORE INTO favorites (user_id, item_type, item_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, item_type, item_id, now)
        )
        await self._db.commit()
        return True

    async def remove(self, user_id: str, item_type: str, item_id: str) -> bool:
        """
        Remove a favorite.

        Returns:
            bool: True if removed, False if not found
        """
        cursor = await self._db.execute(
            "DELETE FROM favorites WHERE user_id = ? AND item_type = ? AND item_id = ?",
            (user_id, item_type, item_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def is_favorited(self, user_id: str, item_type: str, item_id: str) -> bool:
        """Check if a specific item is favorited by a user."""
        row = await self._db.fetchone(
            "SELECT 1 FROM favorites WHERE user_id = ? AND item_type = ? AND item_id = ?",
            (user_id, item_type, item_id)
        )
        return row is not None

    async def list_by_user(
        self,
        user_id: str,
        item_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List a user's favorites, optionally filtered by type.

        Returns:
            List of {item_type, item_id, created_at} dicts
        """
        query = "SELECT item_type, item_id, created_at FROM favorites WHERE user_id = ?"
        params: list = [user_id]

        if item_type:
            query += " AND item_type = ?"
            params.append(item_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetchall(query, tuple(params))
        return [dict(row) for row in rows]

    async def get_favorited_ids(
        self,
        user_id: str,
        item_type: str,
        item_ids: List[str]
    ) -> Set[str]:
        """
        Batch check: given item_ids, return the set that are favorited.

        Critical for annotating library results without N+1 queries.
        """
        if not item_ids:
            return set()

        placeholders = ",".join("?" for _ in item_ids)
        rows = await self._db.fetchall(
            f"SELECT item_id FROM favorites WHERE user_id = ? AND item_type = ? AND item_id IN ({placeholders})",
            (user_id, item_type, *item_ids)
        )
        return {row["item_id"] for row in rows}

    async def count_by_user(self, user_id: str) -> int:
        """Count total favorites for a user."""
        row = await self._db.fetchone(
            "SELECT COUNT(*) as count FROM favorites WHERE user_id = ?",
            (user_id,)
        )
        return row["count"] if row else 0


# Global favorite repository instance
favorite_repo = FavoriteRepository()
