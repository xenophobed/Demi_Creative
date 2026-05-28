"""Agent chat sessions endpoint contract tests (#567, #568).

Black-box contract on the multi-topic session REST surface under
/api/v1/me/agent/sessions (PRD §3.11.8):

  Read (#567):
    - GET /sessions returns only the caller's sessions.
    - GET /sessions/{id}/messages returns chronological history; a
      session the caller does not own 404s (no existence leak).

  Write (#568) cases are appended in the same file as that story lands.

Cross-user isolation precedent: #288 / #178.

Parent Epic: #565
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import agent_chat_repo, db_manager
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserData


_USER_A = UserData(
    user_id="sess_user_a",
    username="sess_user_a",
    email="sa@test.com",
    password_hash="h",
    display_name="A",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)
_USER_B = UserData(
    user_id="sess_user_b",
    username="sess_user_b",
    email="sb@test.com",
    password_hash="h",
    display_name="B",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)
_CHILD_A = "sess_child_a"

_current = {"user": _USER_A}


async def _override_current_user() -> UserData:
    return _current["user"]


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    from datetime import datetime as _dt

    now = _dt.now().isoformat()
    for u in (_USER_A, _USER_B):
        await db_manager.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, display_name,
                is_active, is_verified, role,
                membership_tier, referral_code, referred_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                u.user_id, u.username, u.email, u.password_hash, u.display_name,
                1, 1, "child", "free", f"REF_{u.user_id}", None, now, now,
            ),
        )
    # Seed a child profile for user A so require_owned_child_profile passes.
    await db_manager.execute(
        """
        INSERT INTO child_profiles (
            child_id, user_id, name, age_group, interests, avatar,
            is_default, archived_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_CHILD_A, _USER_A.user_id, "Kiddo", "6-8", "[]", None, 1, None, now, now),
    )
    await db_manager.commit()

    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def client(test_db):
    _current["user"] = _USER_A
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


class TestListSessions:
    @pytest.mark.asyncio
    async def test_lists_only_callers_sessions(self, client):
        a = await agent_chat_repo.get_or_create_session(
            user_id=_USER_A.user_id, child_id=_CHILD_A
        )
        await agent_chat_repo.get_or_create_session(
            user_id=_USER_B.user_id, child_id="other_child"
        )

        r = await client.get("/api/v1/me/agent/sessions")
        assert r.status_code == 200, r.text
        session_ids = {s["session_id"] for s in r.json()["sessions"]}
        assert a.session_id in session_ids
        assert len(session_ids) == 1  # user B's session is invisible

    @pytest.mark.asyncio
    async def test_child_id_filter_requires_owned_profile(self, client):
        # A child_id the caller does not own → 404 from ownership guard.
        r = await client.get("/api/v1/me/agent/sessions", params={"child_id": "not_mine"})
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "CHILD_PROFILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_excludes_archived_by_default(self, client):
        live = await agent_chat_repo.get_or_create_session(
            user_id=_USER_A.user_id, child_id=_CHILD_A
        )
        gone = await agent_chat_repo.get_or_create_session(
            user_id=_USER_A.user_id, child_id=_CHILD_A
        )
        await agent_chat_repo.archive_session(gone.session_id, user_id=_USER_A.user_id)

        r = await client.get("/api/v1/me/agent/sessions")
        ids = {s["session_id"] for s in r.json()["sessions"]}
        assert live.session_id in ids
        assert gone.session_id not in ids

        r2 = await client.get(
            "/api/v1/me/agent/sessions", params={"include_archived": "true"}
        )
        ids2 = {s["session_id"] for s in r2.json()["sessions"]}
        assert gone.session_id in ids2


class TestGetSessionMessages:
    @pytest.mark.asyncio
    async def test_returns_chronological_history(self, client):
        s = await agent_chat_repo.get_or_create_session(
            user_id=_USER_A.user_id, child_id=_CHILD_A
        )
        await agent_chat_repo.add_message(session_id=s.session_id, role="user", text="first")
        await agent_chat_repo.add_message(session_id=s.session_id, role="assistant", text="second")

        r = await client.get(f"/api/v1/me/agent/sessions/{s.session_id}/messages")
        assert r.status_code == 200, r.text
        texts = [m["text"] for m in r.json()["messages"]]
        assert texts == ["first", "second"]

    @pytest.mark.asyncio
    async def test_foreign_session_returns_404(self, client):
        # Session owned by user B; user A (the caller) must get 404.
        b_session = await agent_chat_repo.get_or_create_session(
            user_id=_USER_B.user_id, child_id="other_child"
        )
        await agent_chat_repo.add_message(
            session_id=b_session.session_id, role="user", text="secret"
        )

        r = await client.get(
            f"/api/v1/me/agent/sessions/{b_session.session_id}/messages"
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unknown_session_returns_404(self, client):
        r = await client.get("/api/v1/me/agent/sessions/does_not_exist/messages")
        assert r.status_code == 404
