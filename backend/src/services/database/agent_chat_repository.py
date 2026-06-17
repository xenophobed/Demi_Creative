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
    title: str = ""
    last_message_preview: str = ""
    archived_at: Optional[str] = None


# Bound on the assistant-reply snippet stored for the sidebar (#566).
# Keeps the list query light and the row preview short.
_PREVIEW_MAX_CHARS = 120


@dataclass
class AgentChatMessage:
    message_id: str
    session_id: str
    role: str
    text: str
    input_modality: str
    output_modality: str
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
            title="",
            last_message_preview="",
            archived_at=None,
        )

    async def get_session(
        self, session_id: str, *, user_id: Optional[str] = None
    ) -> Optional[AgentChatSession]:
        if user_id:
            row = await self._db.fetchone(
                """
                SELECT session_id, user_id, child_id, sdk_session_id,
                       title, last_message_preview, archived_at, created_at, updated_at
                FROM agent_chat_sessions
                WHERE session_id = ? AND user_id = ?
                """,
                (session_id, user_id),
            )
        else:
            row = await self._db.fetchone(
                """
                SELECT session_id, user_id, child_id, sdk_session_id,
                       title, last_message_preview, archived_at, created_at, updated_at
                FROM agent_chat_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
        return self._row_to_session(row) if row else None

    async def list_sessions_for_user(
        self,
        user_id: str,
        child_id: Optional[str] = None,
        *,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentChatSession]:
        """List a user's chat sessions, most-recently-updated first.

        Always scoped by ``user_id`` (required) — cross-user isolation
        precedent #288 / #178. ``child_id`` narrows further when the
        active child profile is known. Archived rows are hidden unless
        ``include_archived`` is set.
        """
        clauses = ["user_id = ?"]
        params: list[Any] = [user_id]
        if child_id:
            clauses.append("child_id = ?")
            params.append(child_id)
        if not include_archived:
            clauses.append("archived_at IS NULL")
        where = " AND ".join(clauses)
        params.extend([limit, offset])
        rows = await self._db.fetchall(
            f"""
            SELECT session_id, user_id, child_id, sdk_session_id,
                   title, last_message_preview, archived_at, created_at, updated_at
            FROM agent_chat_sessions
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        return [self._row_to_session(row) for row in rows]

    async def list_messages(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 200,
        before_created_at: Optional[str] = None,
    ) -> list[AgentChatMessage]:
        """Return a session's full history in chronological order.

        Auth-checked: a session that does not belong to ``user_id``
        yields ``[]`` (never another user's history). We resolve the
        owner with one cheap lookup rather than a JOIN so the isolation
        rule stays obvious at the call site.
        """
        owner = await self.get_session(session_id, user_id=user_id)
        if owner is None:
            return []
        if before_created_at:
            rows = await self._db.fetchall(
                """
                SELECT message_id, session_id, role, text,
                       input_modality, output_modality,
                       result_metadata, created_at
                FROM agent_chat_messages
                WHERE session_id = ? AND created_at < ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, before_created_at, limit),
            )
        else:
            rows = await self._db.fetchall(
                """
                SELECT message_id, session_id, role, text,
                       input_modality, output_modality,
                       result_metadata, created_at
                FROM agent_chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
        return [self._row_to_message(row) for row in rows]

    async def rename_session(
        self, session_id: str, *, user_id: str, title: str
    ) -> bool:
        """Set a session's title. No-ops (returns False) for a foreign
        user_id so a cross-tenant request can never mutate another's row.

        Safety validation of ``title`` is the route layer's job (#568);
        the repo trusts its caller.
        """
        cursor = await self._db.execute(
            """
            UPDATE agent_chat_sessions
            SET title = ?, updated_at = ?
            WHERE session_id = ? AND user_id = ?
            """,
            (title, datetime.now().isoformat(), session_id, user_id),
        )
        await self._db.commit()
        return bool(getattr(cursor, "rowcount", 0))

    async def archive_session(
        self, session_id: str, *, user_id: str, archived: bool = True
    ) -> bool:
        """Soft-hide (or restore) a session. Scoped by user_id."""
        archived_at = datetime.now().isoformat() if archived else None
        cursor = await self._db.execute(
            """
            UPDATE agent_chat_sessions
            SET archived_at = ?, updated_at = ?
            WHERE session_id = ? AND user_id = ?
            """,
            (archived_at, datetime.now().isoformat(), session_id, user_id),
        )
        await self._db.commit()
        return bool(getattr(cursor, "rowcount", 0))

    async def delete_session(self, session_id: str, *, user_id: str) -> bool:
        """Hard-delete a session. Messages cascade via the FK. Scoped by
        user_id — a foreign request no-ops (returns False)."""
        cursor = await self._db.execute(
            "DELETE FROM agent_chat_sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        await self._db.commit()
        return bool(getattr(cursor, "rowcount", 0))

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
        input_modality: str = "text",
        output_modality: str = "text",
        result_metadata: Optional[dict[str, Any]] = None,
    ) -> AgentChatMessage:
        now = datetime.now().isoformat()
        message_id = f"agtmsg_{uuid4().hex[:16]}"
        metadata = result_metadata or {}
        normalized_input = _normalize_modality(input_modality)
        normalized_output = _normalize_modality(output_modality)
        await self._db.execute(
            """
            INSERT INTO agent_chat_messages (
                message_id, session_id, role, text,
                input_modality, output_modality,
                result_metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                role,
                text,
                normalized_input,
                normalized_output,
                json.dumps(metadata, ensure_ascii=False),
                now,
            ),
        )
        # Keep the sidebar preview in sync, but only for buddy replies —
        # the preview answers "what did my buddy last say?", so user
        # turns should not overwrite it.
        if role == "assistant":
            await self._db.execute(
                """
                UPDATE agent_chat_sessions
                SET updated_at = ?, last_message_preview = ?
                WHERE session_id = ?
                """,
                (now, text[:_PREVIEW_MAX_CHARS], session_id),
            )
        else:
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
            input_modality=normalized_input,
            output_modality=normalized_output,
            result_metadata=metadata,
            created_at=now,
        )

    async def list_recent_messages(
        self, session_id: str, *, limit: int = 12
    ) -> list[AgentChatMessage]:
        rows = await self._db.fetchall(
            """
            SELECT message_id, session_id, role, text,
                   input_modality, output_modality,
                   result_metadata, created_at
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
            title=row.get("title") or "",
            last_message_preview=row.get("last_message_preview") or "",
            archived_at=row.get("archived_at"),
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
            input_modality=row.get("input_modality") or "text",
            output_modality=row.get("output_modality") or "text",
            result_metadata=metadata,
            created_at=row["created_at"],
        )


def _normalize_modality(value: str) -> str:
    return value if value in {"text", "voice"} else "text"


agent_chat_repo = AgentChatRepository()
