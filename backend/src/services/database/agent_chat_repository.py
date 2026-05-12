"""Repository for lightweight My Agent chat state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from .connection import db_manager


@dataclass
class AgentChatSession:
    session_id: str
    user_id: str
    child_id: str
    sdk_session_id: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class AgentChatMessage:
    message_id: str
    session_id: str
    role: str
    text: str
    result_metadata: dict[str, Any]
    created_at: str


class AgentChatRepository:
    """CRUD helpers for My Agent chat sessions and messages."""

    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    async def get_or_create_session(
        self,
        *,
        user_id: str,
        child_id: str,
        session_id: Optional[str] = None,
    ) -> AgentChatSession:
        if session_id:
            existing = await self.get_session(session_id, user_id=user_id)
            if existing is not None:
                return existing

        now = datetime.now().isoformat()
        new_session_id = session_id or f"agtchat_{uuid4().hex[:16]}"
        await self._db.execute(
            """
            INSERT INTO agent_chat_sessions (
                session_id, user_id, child_id, sdk_session_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_session_id, user_id, child_id, None, now, now),
        )
        await self._db.commit()
        return AgentChatSession(
            session_id=new_session_id,
            user_id=user_id,
            child_id=child_id,
            sdk_session_id=None,
            created_at=now,
            updated_at=now,
        )

    async def get_session(
        self, session_id: str, *, user_id: Optional[str] = None
    ) -> Optional[AgentChatSession]:
        if user_id:
            row = await self._db.fetchone(
                """
                SELECT session_id, user_id, child_id, sdk_session_id, created_at, updated_at
                FROM agent_chat_sessions
                WHERE session_id = ? AND user_id = ?
                """,
                (session_id, user_id),
            )
        else:
            row = await self._db.fetchone(
                """
                SELECT session_id, user_id, child_id, sdk_session_id, created_at, updated_at
                FROM agent_chat_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
        return self._row_to_session(row) if row else None

    async def set_sdk_session_id(self, session_id: str, sdk_session_id: str) -> None:
        await self._db.execute(
            """
            UPDATE agent_chat_sessions
            SET sdk_session_id = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (sdk_session_id, datetime.now().isoformat(), session_id),
        )
        await self._db.commit()

    async def add_message(
        self,
        *,
        session_id: str,
        role: str,
        text: str,
        result_metadata: Optional[dict[str, Any]] = None,
    ) -> AgentChatMessage:
        now = datetime.now().isoformat()
        message_id = f"agtmsg_{uuid4().hex[:16]}"
        metadata = result_metadata or {}
        await self._db.execute(
            """
            INSERT INTO agent_chat_messages (
                message_id, session_id, role, text, result_metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                role,
                text,
                json.dumps(metadata, ensure_ascii=False),
                now,
            ),
        )
        await self._db.execute(
            "UPDATE agent_chat_sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        await self._db.commit()
        return AgentChatMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            text=text,
            result_metadata=metadata,
            created_at=now,
        )

    async def list_recent_messages(
        self, session_id: str, *, limit: int = 12
    ) -> list[AgentChatMessage]:
        rows = await self._db.fetchall(
            """
            SELECT message_id, session_id, role, text, result_metadata, created_at
            FROM agent_chat_messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        return [self._row_to_message(row) for row in reversed(rows)]

    @staticmethod
    def _row_to_session(row: dict[str, Any]) -> AgentChatSession:
        return AgentChatSession(
            session_id=row["session_id"],
            user_id=row["user_id"],
            child_id=row["child_id"],
            sdk_session_id=row.get("sdk_session_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_message(row: dict[str, Any]) -> AgentChatMessage:
        try:
            metadata = json.loads(row.get("result_metadata") or "{}")
        except ValueError:
            metadata = {}
        return AgentChatMessage(
            message_id=row["message_id"],
            session_id=row["session_id"],
            role=row["role"],
            text=row["text"],
            result_metadata=metadata,
            created_at=row["created_at"],
        )


agent_chat_repo = AgentChatRepository()
