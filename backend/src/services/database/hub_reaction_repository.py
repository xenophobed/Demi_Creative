"""
Hub Reaction Repository (#447)

Idempotent toggle of (post_id, user_id, reaction_type) reactions.
Three reaction types only — heart / star / wow — per PRD §3.12.5.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from .connection import db_manager


_VALID_REACTIONS = ("heart", "star", "wow")


@dataclass
class ReactionData:
    post_id: str
    user_id: str
    reaction_type: str
    created_at: str


class HubReactionRepository:
    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    @staticmethod
    def _row_to_reaction(row) -> ReactionData:
        return ReactionData(
            post_id=row["post_id"],
            user_id=row["user_id"],
            reaction_type=row["reaction_type"],
            created_at=row["created_at"],
        )

    async def toggle(
        self, *, post_id: str, user_id: str, reaction_type: str
    ) -> bool:
        """Toggle a reaction.

        If the (post, user, type) row exists, delete it and return False.
        Otherwise insert it and return True.

        Raises ValueError on unknown reaction_type so the route can
        return a 400 with a clear code.
        """
        if reaction_type not in _VALID_REACTIONS:
            raise ValueError(
                f"reaction_type must be one of {_VALID_REACTIONS!r}"
            )

        existing = await self._db.fetchone(
            """
            SELECT 1 FROM hub_post_reactions
            WHERE post_id = ? AND user_id = ? AND reaction_type = ?
            """,
            (post_id, user_id, reaction_type),
        )

        if existing is not None:
            await self._db.execute(
                """
                DELETE FROM hub_post_reactions
                WHERE post_id = ? AND user_id = ? AND reaction_type = ?
                """,
                (post_id, user_id, reaction_type),
            )
            await self._db.commit()
            return False

        await self._db.execute(
            """
            INSERT INTO hub_post_reactions (
                post_id, user_id, reaction_type, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (post_id, user_id, reaction_type, datetime.now().isoformat()),
        )
        await self._db.commit()
        return True

    async def counts_for_post(self, post_id: str) -> Dict[str, int]:
        """Return {'heart': N, 'star': N, 'wow': N} (zero for missing types)."""
        rows = await self._db.fetchall(
            """
            SELECT reaction_type, COUNT(*) AS n
            FROM hub_post_reactions
            WHERE post_id = ?
            GROUP BY reaction_type
            """,
            (post_id,),
        )
        out: Dict[str, int] = {r: 0 for r in _VALID_REACTIONS}
        for row in rows:
            out[row["reaction_type"]] = int(row["n"])
        return out

    async def reactions_by_user(
        self, post_id: str, user_id: str
    ) -> List[str]:
        """Which reaction types this user has placed on this post."""
        rows = await self._db.fetchall(
            """
            SELECT reaction_type FROM hub_post_reactions
            WHERE post_id = ? AND user_id = ?
            """,
            (post_id, user_id),
        )
        return [row["reaction_type"] for row in rows]


hub_reaction_repo = HubReactionRepository()
