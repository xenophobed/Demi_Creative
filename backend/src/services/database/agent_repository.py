"""
Agent Repository (#439)

CRUD operations for the user_agents table — the personalized buddy persona
each (user, child) pair has bound to them. Foundation for Epic #436.

Design notes:
- (user_id, child_id) is the natural key; agent_id is a stable surrogate
  used by future hub posts (#447).
- upsert_agent preserves agent_id across updates so external references
  remain valid; only created_at is preserved on update, updated_at always
  refreshes.
- All timestamps are ISO 8601 (UTC-naive isoformat), matching the
  convention used by user_repository and referral_repository.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .connection import db_manager


@dataclass
class AgentData:
    """User agent persona row."""
    agent_id: str
    user_id: str
    child_id: str
    agent_name: str
    agent_avatar_id: str
    agent_title: str
    created_at: str
    updated_at: str


class AgentRepository:
    """Repository for user_agents records."""

    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    async def get_agent(
        self, user_id: str, child_id: str
    ) -> Optional[AgentData]:
        """Look up the agent persona for a (user, child) pair."""
        row = await self._db.fetchone(
            """
            SELECT agent_id, user_id, child_id, agent_name,
                   agent_avatar_id, agent_title, created_at, updated_at
            FROM user_agents
            WHERE user_id = ? AND child_id = ?
            """,
            (user_id, child_id),
        )
        return self._row_to_agent(row) if row else None

    async def get_by_agent_id(self, agent_id: str) -> Optional[AgentData]:
        """Look up an agent by its surrogate agent_id (for #447 hub posts)."""
        row = await self._db.fetchone(
            """
            SELECT agent_id, user_id, child_id, agent_name,
                   agent_avatar_id, agent_title, created_at, updated_at
            FROM user_agents
            WHERE agent_id = ?
            """,
            (agent_id,),
        )
        return self._row_to_agent(row) if row else None

    async def upsert_agent(
        self,
        user_id: str,
        child_id: str,
        agent_name: str,
        agent_avatar_id: str,
        agent_title: str,
    ) -> AgentData:
        """
        Insert a new agent or update the existing one for (user_id, child_id).

        On insert: generates agent_id = f"agt_{uuid4().hex[:12]}" and sets
        both created_at and updated_at to now.
        On update: preserves agent_id and created_at; refreshes updated_at.
        """
        existing = await self.get_agent(user_id, child_id)
        now = datetime.now().isoformat()

        if existing is None:
            agent_id = f"agt_{uuid4().hex[:12]}"
            await self._db.execute(
                """
                INSERT INTO user_agents (
                    agent_id, user_id, child_id,
                    agent_name, agent_avatar_id, agent_title,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    user_id,
                    child_id,
                    agent_name,
                    agent_avatar_id,
                    agent_title,
                    now,
                    now,
                ),
            )
            await self._db.commit()
            return AgentData(
                agent_id=agent_id,
                user_id=user_id,
                child_id=child_id,
                agent_name=agent_name,
                agent_avatar_id=agent_avatar_id,
                agent_title=agent_title,
                created_at=now,
                updated_at=now,
            )

        await self._db.execute(
            """
            UPDATE user_agents
            SET agent_name = ?, agent_avatar_id = ?, agent_title = ?,
                updated_at = ?
            WHERE user_id = ? AND child_id = ?
            """,
            (agent_name, agent_avatar_id, agent_title, now, user_id, child_id),
        )
        await self._db.commit()
        return AgentData(
            agent_id=existing.agent_id,
            user_id=user_id,
            child_id=child_id,
            agent_name=agent_name,
            agent_avatar_id=agent_avatar_id,
            agent_title=agent_title,
            created_at=existing.created_at,
            updated_at=now,
        )

    @staticmethod
    def _row_to_agent(row: dict) -> AgentData:
        return AgentData(
            agent_id=row["agent_id"],
            user_id=row["user_id"],
            child_id=row["child_id"],
            agent_name=row["agent_name"],
            agent_avatar_id=row["agent_avatar_id"],
            agent_title=row["agent_title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# Global agent repository instance — bound to the shared db_manager.
agent_repo = AgentRepository()
