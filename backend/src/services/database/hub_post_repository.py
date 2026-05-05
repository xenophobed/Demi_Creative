"""
Hub Post Repository (#447)

CRUD for the hub_posts table — the privacy-critical surface of Epic #437.

The defining behaviour: when a post is created, the agent persona is
snapshotted onto the post row. Subsequent edits to the agent never
propagate to existing posts. This is what makes the COPPA invariant
in #450 enforceable — feed reads project from snapshot fields and
never join the users or user_agents table.

Reads NEVER join `users`. They MAY join `user_agents` only when the
caller is the post's own author (e.g. a "you posted as ..." preview);
the public feed read paths must use _row_to_post() exclusively.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import uuid4

from .connection import db_manager


@dataclass
class HubPostData:
    """A hub post row, including the immutable agent persona snapshot."""
    post_id: str
    group_id: str
    author_user_id: str
    author_child_id: str
    author_agent_id: str
    # Snapshot fields — NEVER read from user_agents at fetch time:
    agent_name_snapshot: str
    agent_avatar_id_snapshot: str
    agent_title_snapshot: str
    source_artifact_type: str  # 'art_story' | 'interactive_story' | 'kids_daily'
    source_id: str
    caption: Optional[str]
    safety_score: float
    created_at: str
    removed_at: Optional[str]
    removed_reason: Optional[str]


class HubPostRepository:
    def __init__(self, db=None, *, agent_repository=None):
        self._db = db if db is not None else db_manager
        # Lazily resolved to avoid circular imports at module load.
        self._agent_repo = agent_repository

    def _resolve_agent_repo(self):
        if self._agent_repo is not None:
            return self._agent_repo
        from .agent_repository import agent_repo
        return agent_repo

    @staticmethod
    def _row_to_post(row) -> HubPostData:
        return HubPostData(
            post_id=row["post_id"],
            group_id=row["group_id"],
            author_user_id=row["author_user_id"],
            author_child_id=row["author_child_id"],
            author_agent_id=row["author_agent_id"],
            agent_name_snapshot=row["agent_name_snapshot"],
            agent_avatar_id_snapshot=row["agent_avatar_id_snapshot"],
            agent_title_snapshot=row["agent_title_snapshot"],
            source_artifact_type=row["source_artifact_type"],
            source_id=row["source_id"],
            caption=row["caption"],
            safety_score=row["safety_score"],
            created_at=row["created_at"],
            removed_at=row["removed_at"],
            removed_reason=row["removed_reason"],
        )

    # --- write -----------------------------------------------------------

    async def create_post(
        self,
        *,
        group_id: str,
        user_id: str,
        child_id: str,
        source_artifact_type: str,
        source_id: str,
        caption: Optional[str] = None,
        safety_score: float = 1.0,
    ) -> HubPostData:
        """
        Create a hub post with persona snapshot from the user's current
        agent for (user_id, child_id).

        Raises:
            LookupError("AGENT_REQUIRED"): no agent exists for the
                (user_id, child_id) pair — the route should map this
                to HTTP 412.
            ValueError: bad source_artifact_type.
        """
        if source_artifact_type not in (
            "art_story",
            "interactive_story",
            "kids_daily",
        ):
            raise ValueError(
                "source_artifact_type must be 'art_story', 'interactive_story', or 'kids_daily'"
            )

        agent_repo = self._resolve_agent_repo()
        agent = await agent_repo.get_agent(user_id, child_id)
        if agent is None:
            raise LookupError("AGENT_REQUIRED")

        post_id = uuid4().hex
        now = datetime.now().isoformat()

        await self._db.execute(
            """
            INSERT INTO hub_posts (
                post_id, group_id, author_user_id, author_child_id, author_agent_id,
                agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot,
                source_artifact_type, source_id, caption, safety_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                group_id,
                user_id,
                child_id,
                agent.agent_id,
                # Snapshot the persona at write time.
                agent.agent_name,
                agent.agent_avatar_id,
                agent.agent_title,
                source_artifact_type,
                source_id,
                caption,
                safety_score,
                now,
            ),
        )
        await self._db.commit()

        return HubPostData(
            post_id=post_id,
            group_id=group_id,
            author_user_id=user_id,
            author_child_id=child_id,
            author_agent_id=agent.agent_id,
            agent_name_snapshot=agent.agent_name,
            agent_avatar_id_snapshot=agent.agent_avatar_id,
            agent_title_snapshot=agent.agent_title,
            source_artifact_type=source_artifact_type,
            source_id=source_id,
            caption=caption,
            safety_score=safety_score,
            created_at=now,
            removed_at=None,
            removed_reason=None,
        )

    async def soft_delete(
        self, post_id: str, *, reason: Optional[str] = None
    ) -> bool:
        """Mark a post as removed; feed reads filter removed_at IS NULL."""
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            """
            UPDATE hub_posts SET removed_at = ?, removed_reason = ?
            WHERE post_id = ? AND removed_at IS NULL
            """,
            (now, reason, post_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # --- read ------------------------------------------------------------

    async def get_by_id(self, post_id: str) -> Optional[HubPostData]:
        """
        Fetch a single post. NOTE: this does not filter removed_at,
        because admin paths legitimately need to see removed rows.
        Feed reads MUST use list_by_group instead.
        """
        row = await self._db.fetchone(
            """
            SELECT post_id, group_id, author_user_id, author_child_id, author_agent_id,
                   agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot,
                   source_artifact_type, source_id, caption, safety_score,
                   created_at, removed_at, removed_reason
            FROM hub_posts
            WHERE post_id = ?
            """,
            (post_id,),
        )
        return self._row_to_post(row) if row else None

    async def list_by_group(
        self,
        group_id: str,
        *,
        limit: int = 20,
        before: Optional[Tuple[str, str]] = None,
    ) -> List[HubPostData]:
        """
        Recency-ordered feed for a group. Excludes soft-deleted rows.

        Critically: this query selects ONLY hub_posts columns. It NEVER
        joins users or user_agents — that is what keeps the COPPA
        invariant in #450 holding for the public feed endpoint.

        Pagination uses a tuple cursor (created_at, post_id) so removals
        mid-paginate don't shift the window.
        """
        if before is None:
            rows = await self._db.fetchall(
                """
                SELECT post_id, group_id, author_user_id, author_child_id, author_agent_id,
                       agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot,
                       source_artifact_type, source_id, caption, safety_score,
                       created_at, removed_at, removed_reason
                FROM hub_posts
                WHERE group_id = ? AND removed_at IS NULL
                ORDER BY created_at DESC, post_id DESC
                LIMIT ?
                """,
                (group_id, limit),
            )
        else:
            cursor_created_at, cursor_post_id = before
            rows = await self._db.fetchall(
                """
                SELECT post_id, group_id, author_user_id, author_child_id, author_agent_id,
                       agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot,
                       source_artifact_type, source_id, caption, safety_score,
                       created_at, removed_at, removed_reason
                FROM hub_posts
                WHERE group_id = ?
                  AND removed_at IS NULL
                  AND (
                       created_at < ?
                    OR (created_at = ? AND post_id < ?)
                  )
                ORDER BY created_at DESC, post_id DESC
                LIMIT ?
                """,
                (group_id, cursor_created_at, cursor_created_at, cursor_post_id, limit),
            )
        return [self._row_to_post(r) for r in rows]


hub_post_repo = HubPostRepository()
