"""AgentChatRepository session-management contract tests (#566).

Locks the repository layer that powers the multi-topic chat sessions
sidebar (PRD §3.11.8). The contract:

  - `agent_chat_sessions` carries `title`, `last_message_preview`, and
    `archived_at` after migration.
  - `list_sessions_for_user` is scoped by user_id (required) + optional
    child_id, sorted by `updated_at DESC`, and excludes archived rows by
    default. Cross-user isolation precedent: #288 / #178.
  - `list_messages` is auth-checked — a foreign user_id gets `[]`, never
    another user's history.
  - `rename_session` / `archive_session` / `delete_session` no-op
    silently for non-matching user_id (never raise, never mutate).
  - `add_message` keeps `last_message_preview` in sync for assistant
    rows only.

Parent Epic: #565
Issue: #566
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from backend.src.services.database.agent_chat_repository import (
    AgentChatRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.sql_compat import column_exists


_USER_A = "user_a"
_USER_B = "user_b"
_CHILD_1 = "child_1"
_CHILD_2 = "child_2"


@pytest_asyncio.fixture
async def repo():
    db = DatabaseManager(":memory:")
    await db.connect()
    await init_schema(db)
    # Seed two users (FK on agent_chat_sessions.user_id).
    from datetime import datetime as _dt

    now = _dt.now().isoformat()
    for uid in (_USER_A, _USER_B):
        await db.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, display_name,
                is_active, is_verified, role,
                membership_tier, referral_code, referred_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid, uid, f"{uid}@test.com", "h", uid, 1, 1, "child",
                "free", f"REF_{uid}", None, now, now,
            ),
        )
    await db.commit()
    yield AgentChatRepository(db=db)
    await db.disconnect()


class TestSchemaColumns:
    @pytest.mark.asyncio
    async def test_session_columns_exist_after_migration(self, repo):
        db = repo._db
        assert await column_exists(db, "agent_chat_sessions", "title")
        assert await column_exists(db, "agent_chat_sessions", "last_message_preview")
        assert await column_exists(db, "agent_chat_sessions", "archived_at")


class TestListSessionsForUser:
    @pytest.mark.asyncio
    async def test_returns_only_callers_sessions(self, repo):
        a = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.get_or_create_session(user_id=_USER_B, child_id=_CHILD_1)

        a_sessions = await repo.list_sessions_for_user(_USER_A)
        ids = {s.session_id for s in a_sessions}
        assert a.session_id in ids
        assert len(ids) == 1  # user B's session is not visible to A

    @pytest.mark.asyncio
    async def test_optional_child_id_filter(self, repo):
        await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_2)

        only_c1 = await repo.list_sessions_for_user(_USER_A, child_id=_CHILD_1)
        assert {s.child_id for s in only_c1} == {_CHILD_1}

        both = await repo.list_sessions_for_user(_USER_A)
        assert {s.child_id for s in both} == {_CHILD_1, _CHILD_2}

    @pytest.mark.asyncio
    async def test_sorted_by_updated_at_desc(self, repo):
        first = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        second = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        # Touch `first` so it becomes most-recently updated.
        await repo.add_message(session_id=first.session_id, role="user", text="hi")

        sessions = await repo.list_sessions_for_user(_USER_A)
        assert sessions[0].session_id == first.session_id
        assert sessions[1].session_id == second.session_id

    @pytest.mark.asyncio
    async def test_excludes_archived_by_default(self, repo):
        live = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        gone = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.archive_session(gone.session_id, user_id=_USER_A)

        default_list = await repo.list_sessions_for_user(_USER_A)
        assert {s.session_id for s in default_list} == {live.session_id}

        with_archived = await repo.list_sessions_for_user(
            _USER_A, include_archived=True
        )
        assert {s.session_id for s in with_archived} == {
            live.session_id,
            gone.session_id,
        }

    @pytest.mark.asyncio
    async def test_pagination(self, repo):
        created = [
            await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
            for _ in range(5)
        ]
        assert created  # silence linters
        page = await repo.list_sessions_for_user(_USER_A, limit=2, offset=0)
        assert len(page) == 2
        page2 = await repo.list_sessions_for_user(_USER_A, limit=2, offset=2)
        assert len(page2) == 2
        # No overlap between pages.
        assert {s.session_id for s in page}.isdisjoint(
            {s.session_id for s in page2}
        )


class TestListMessages:
    @pytest.mark.asyncio
    async def test_returns_chronological_history(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.add_message(session_id=s.session_id, role="user", text="first")
        await repo.add_message(session_id=s.session_id, role="assistant", text="second")

        msgs = await repo.list_messages(s.session_id, user_id=_USER_A)
        assert [m.text for m in msgs] == ["first", "second"]

    @pytest.mark.asyncio
    async def test_foreign_user_gets_empty_list(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.add_message(session_id=s.session_id, role="user", text="secret")

        leaked = await repo.list_messages(s.session_id, user_id=_USER_B)
        assert leaked == []


class TestAutoTitleAndPreview:
    @pytest.mark.asyncio
    async def test_new_session_has_empty_title_and_preview(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        assert s.title == ""
        assert s.last_message_preview == ""
        assert s.archived_at is None

    @pytest.mark.asyncio
    async def test_rename_sets_title(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.rename_session(s.session_id, user_id=_USER_A, title="Dinosaur story")
        reloaded = await repo.get_session(s.session_id, user_id=_USER_A)
        assert reloaded.title == "Dinosaur story"

    @pytest.mark.asyncio
    async def test_add_message_updates_preview_for_assistant_only(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.add_message(session_id=s.session_id, role="user", text="user text")
        after_user = await repo.get_session(s.session_id, user_id=_USER_A)
        assert after_user.last_message_preview == ""  # user msgs don't set preview

        await repo.add_message(
            session_id=s.session_id, role="assistant", text="buddy reply here"
        )
        after_assistant = await repo.get_session(s.session_id, user_id=_USER_A)
        assert after_assistant.last_message_preview == "buddy reply here"

    @pytest.mark.asyncio
    async def test_preview_truncated_to_120_chars(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        long_reply = "x" * 200
        await repo.add_message(
            session_id=s.session_id, role="assistant", text=long_reply
        )
        reloaded = await repo.get_session(s.session_id, user_id=_USER_A)
        assert len(reloaded.last_message_preview) == 120


class TestArchiveAndDelete:
    @pytest.mark.asyncio
    async def test_archive_then_unarchive(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.archive_session(s.session_id, user_id=_USER_A)
        archived = await repo.get_session(s.session_id, user_id=_USER_A)
        assert archived.archived_at is not None

        await repo.archive_session(s.session_id, user_id=_USER_A, archived=False)
        live = await repo.get_session(s.session_id, user_id=_USER_A)
        assert live.archived_at is None

    @pytest.mark.asyncio
    async def test_delete_cascades_to_messages(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)
        await repo.add_message(session_id=s.session_id, role="user", text="hi")
        await repo.delete_session(s.session_id, user_id=_USER_A)

        assert await repo.get_session(s.session_id, user_id=_USER_A) is None
        # Messages gone via FK cascade.
        rows = await repo._db.fetchall(
            "SELECT message_id FROM agent_chat_messages WHERE session_id = ?",
            (s.session_id,),
        )
        assert rows == []

    @pytest.mark.asyncio
    async def test_foreign_user_cannot_rename_archive_or_delete(self, repo):
        s = await repo.get_or_create_session(user_id=_USER_A, child_id=_CHILD_1)

        await repo.rename_session(s.session_id, user_id=_USER_B, title="hijack")
        await repo.archive_session(s.session_id, user_id=_USER_B)
        await repo.delete_session(s.session_id, user_id=_USER_B)

        # Untouched: still owned by A, no title, not archived, still exists.
        survivor = await repo.get_session(s.session_id, user_id=_USER_A)
        assert survivor is not None
        assert survivor.title == ""
        assert survivor.archived_at is None
