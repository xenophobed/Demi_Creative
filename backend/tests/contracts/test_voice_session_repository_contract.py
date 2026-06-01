"""
VoiceSessionRepository contract tests (#612).

Locks the persistence layer for Talk-to-Buddy realtime voice sessions.
The repository is the audit + quota source of truth used by the WS
broker (#615); these tests freeze the surface so the broker can develop
against it without hitting a moving target.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from backend.src.services.database import (
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.voice_session_repository import (
    TERMINATION_REASONS,
    VoiceSessionRepository,
)


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)
    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    # Seed a user — voice_sessions has FK → users so we need this row.
    now = datetime.now().isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (user_id, username, email, password_hash, display_name,
                           is_active, is_verified, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("voice_parent", "voice_parent", "vp@test.com", "h", "VP", 1, 1, now, now),
    )
    await db_manager.commit()

    yield fresh

    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
def repo():
    # Singleton imported from the package — it shares db_manager state
    # so the in-memory test DB applies.
    return voice_session_repo


# ---------------------- create_session --------------------------------------

class TestCreateSession:
    @pytest.mark.asyncio
    async def test_create_returns_data_with_canonical_fields(self, test_db, repo):
        session = await repo.create_session(
            user_id="voice_parent",
            child_id="child_alpha",
            provider="mock",
        )
        assert session.session_id.startswith("voice_sess_")
        assert session.user_id == "voice_parent"
        assert session.child_id == "child_alpha"
        assert session.provider == "mock"
        assert session.ended_at is None
        assert session.duration_seconds is None
        assert session.termination_reason is None
        # Sanity: started_at is a parseable ISO timestamp
        datetime.fromisoformat(session.started_at)

    @pytest.mark.asyncio
    async def test_create_with_explicit_session_id(self, test_db, repo):
        session = await repo.create_session(
            user_id="voice_parent",
            child_id="child_alpha",
            session_id="voice_sess_explicit_123",
        )
        assert session.session_id == "voice_sess_explicit_123"

    @pytest.mark.asyncio
    async def test_each_create_generates_unique_id(self, test_db, repo):
        a = await repo.create_session(user_id="voice_parent", child_id="c1")
        b = await repo.create_session(user_id="voice_parent", child_id="c1")
        assert a.session_id != b.session_id


# ---------------------- end_session -----------------------------------------

class TestEndSession:
    @pytest.mark.asyncio
    async def test_end_session_writes_all_close_fields(self, test_db, repo):
        session = await repo.create_session(
            user_id="voice_parent", child_id="child_alpha", provider="mock",
        )
        closed = await repo.end_session(
            session_id=session.session_id,
            reason="user_ended",
            duration_seconds=120,
            safety_score=0.97,
        )
        assert closed is not None
        assert closed.ended_at is not None
        assert closed.duration_seconds == 120
        assert closed.transcript_safety_score == 0.97
        assert closed.termination_reason == "user_ended"

    @pytest.mark.asyncio
    async def test_end_session_is_idempotent(self, test_db, repo):
        session = await repo.create_session(
            user_id="voice_parent", child_id="child_alpha",
        )
        first = await repo.end_session(
            session_id=session.session_id,
            reason="user_ended",
            duration_seconds=60,
        )
        second = await repo.end_session(
            session_id=session.session_id,
            reason="timeout",
            duration_seconds=999,
        )
        # The second call must NOT clobber — both reads return the
        # original close payload.
        assert first is not None
        assert second is not None
        assert second.termination_reason == "user_ended"
        assert second.duration_seconds == 60

    @pytest.mark.asyncio
    async def test_end_unknown_session_returns_none(self, test_db, repo):
        result = await repo.end_session(
            session_id="voice_sess_never_existed",
            reason="user_ended",
        )
        assert result is None

    def test_termination_reasons_taxonomy_locked(self):
        # PRD §3.16.4 enumerates these exact reasons. If anyone changes
        # the set this fails until tests + PRD are updated together.
        assert TERMINATION_REASONS == frozenset({
            "user_ended",
            "client_disconnect",
            "timeout",
            "quota",
            "safety_fail",
            "provider_error",
            "consent_revoked",
        })


# ---------------------- list_for_child + sum_seconds_in_window --------------

class TestQuotaQueries:
    @pytest.mark.asyncio
    async def test_list_for_child_returns_newest_first(self, test_db, repo):
        for i in range(3):
            s = await repo.create_session(
                user_id="voice_parent", child_id="child_alpha",
            )
            await repo.end_session(
                session_id=s.session_id,
                reason="user_ended",
                duration_seconds=30 + i,
            )
        rows = await repo.list_for_child(
            user_id="voice_parent", child_id="child_alpha",
        )
        assert len(rows) == 3
        # Newest first — last created should be index 0.
        assert rows[0].duration_seconds == 32

    @pytest.mark.asyncio
    async def test_sum_seconds_in_window_only_counts_ended_sessions(self, test_db, repo):
        # Two ended sessions + one still in flight.
        for duration in (45, 60):
            s = await repo.create_session(
                user_id="voice_parent", child_id="child_alpha",
            )
            await repo.end_session(
                session_id=s.session_id,
                reason="user_ended",
                duration_seconds=duration,
            )
        # Open session — should NOT contribute.
        await repo.create_session(
            user_id="voice_parent", child_id="child_alpha",
        )

        an_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        total = await repo.sum_seconds_in_window(
            user_id="voice_parent",
            child_id="child_alpha",
            since_iso=an_hour_ago,
        )
        assert total == 105

    @pytest.mark.asyncio
    async def test_sum_seconds_respects_window_boundary(self, test_db, repo):
        s = await repo.create_session(
            user_id="voice_parent", child_id="child_alpha",
        )
        await repo.end_session(
            session_id=s.session_id,
            reason="user_ended",
            duration_seconds=200,
        )
        # Window starts in the future — nothing inside.
        future = (datetime.now() + timedelta(minutes=5)).isoformat()
        assert await repo.sum_seconds_in_window(
            user_id="voice_parent",
            child_id="child_alpha",
            since_iso=future,
        ) == 0

    @pytest.mark.asyncio
    async def test_sum_seconds_scoped_to_user_child(self, test_db, repo):
        s = await repo.create_session(
            user_id="voice_parent", child_id="child_alpha",
        )
        await repo.end_session(
            session_id=s.session_id, reason="user_ended", duration_seconds=120,
        )
        # Same user, different child → 0
        an_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        assert await repo.sum_seconds_in_window(
            user_id="voice_parent", child_id="child_beta", since_iso=an_hour_ago,
        ) == 0


# ---------------------- get_by_id -------------------------------------------

class TestGetById:
    @pytest.mark.asyncio
    async def test_get_unknown_returns_none(self, test_db, repo):
        assert await repo.get_by_id("voice_sess_does_not_exist") is None

    @pytest.mark.asyncio
    async def test_get_returns_canonical_row(self, test_db, repo):
        s = await repo.create_session(
            user_id="voice_parent", child_id="child_alpha", provider="mock",
        )
        fetched = await repo.get_by_id(s.session_id)
        assert fetched is not None
        assert fetched.session_id == s.session_id
        assert fetched.provider == "mock"


# ---------------------- Instantiation seam ----------------------------------

class TestRepositoryInjection:
    def test_repository_can_be_built_with_explicit_db(self):
        # The broker (#615) may want a non-singleton repo for testing.
        custom = VoiceSessionRepository(db=db_manager)
        assert custom._db is db_manager
