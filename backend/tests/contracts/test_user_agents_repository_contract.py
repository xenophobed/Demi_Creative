"""
User Agents Schema Contract Tests

Locks the schema contract for the user_agents table introduced in issue #438.
This is the foundation table for Epic #436 (My Agent — personalized buddy
persona). The full repository class lands in #439; here we only cover the
schema-level invariants the repository will rely on:

  - Table is created by init_schema.
  - agent_id is UNIQUE.
  - (user_id, child_id) is UNIQUE — at most one agent per child.
  - ON DELETE CASCADE removes user_agents when the parent user is deleted.

Parent Epic: #436
Issue: #438
"""

import pytest
import pytest_asyncio

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory database with full schema applied."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def user_repo(db):
    """UserRepository bound to test database."""
    repo = UserRepository()
    repo._db = db
    return repo


@pytest_asyncio.fixture
async def parent_user(user_repo):
    """A real user row to satisfy the FK on user_agents.user_id."""
    return await user_repo.create_user(
        username="parent1",
        email="parent1@test.com",
        password_hash="h",
    )


async def _insert_user_agent(
    db: DatabaseManager,
    *,
    agent_id: str,
    user_id: str,
    child_id: str,
    agent_name: str = "Bobo",
    agent_avatar_id: str = "avatar-fox",
    agent_title: str = "Brave Buddy",
    created_at: str = "2026-01-01T00:00:00",
    updated_at: str = "2026-01-01T00:00:00",
) -> None:
    await db.execute(
        """
        INSERT INTO user_agents (
            agent_id, user_id, child_id, agent_name,
            agent_avatar_id, agent_title, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            user_id,
            child_id,
            agent_name,
            agent_avatar_id,
            agent_title,
            created_at,
            updated_at,
        ),
    )
    await db.commit()


# ============================================================================
# Contract: table exists with required columns
# ============================================================================


class TestUserAgentsTableShape:
    """user_agents table is created with the expected columns."""

    @pytest.mark.asyncio
    async def test_table_exists(self, db):
        rows = await db.fetchall("PRAGMA table_info(user_agents)")
        assert len(rows) > 0, "user_agents table not created"

    @pytest.mark.asyncio
    async def test_required_columns(self, db):
        rows = await db.fetchall("PRAGMA table_info(user_agents)")
        cols = {row["name"] for row in rows}
        for required in (
            "id",
            "agent_id",
            "user_id",
            "child_id",
            "agent_name",
            "agent_avatar_id",
            "agent_title",
            "created_at",
            "updated_at",
        ):
            assert required in cols, f"missing column {required}"


# ============================================================================
# Contract: insert + select roundtrip
# ============================================================================


class TestInsertSelectRoundtrip:
    """A row inserted by SQL can be selected back with the same values."""

    @pytest.mark.asyncio
    async def test_roundtrip(self, db, parent_user):
        await _insert_user_agent(
            db,
            agent_id="agent-uuid-1",
            user_id=parent_user.user_id,
            child_id="child-1",
            agent_name="Bobo",
            agent_avatar_id="avatar-fox",
            agent_title="Brave Buddy",
        )
        row = await db.fetchone(
            "SELECT agent_id, user_id, child_id, agent_name, agent_avatar_id, "
            "agent_title FROM user_agents WHERE agent_id = ?",
            ("agent-uuid-1",),
        )
        assert row is not None
        assert row["agent_id"] == "agent-uuid-1"
        assert row["user_id"] == parent_user.user_id
        assert row["child_id"] == "child-1"
        assert row["agent_name"] == "Bobo"
        assert row["agent_avatar_id"] == "avatar-fox"
        assert row["agent_title"] == "Brave Buddy"


# ============================================================================
# Contract: UNIQUE constraints
# ============================================================================


class TestUniqueConstraints:
    """Both agent_id and (user_id, child_id) are UNIQUE."""

    @pytest.mark.asyncio
    async def test_unique_user_id_child_id(self, db, parent_user):
        await _insert_user_agent(
            db,
            agent_id="agent-uuid-a",
            user_id=parent_user.user_id,
            child_id="child-x",
        )
        with pytest.raises(Exception):
            await _insert_user_agent(
                db,
                agent_id="agent-uuid-b",
                user_id=parent_user.user_id,
                child_id="child-x",
            )

    @pytest.mark.asyncio
    async def test_unique_agent_id(self, db, parent_user):
        await _insert_user_agent(
            db,
            agent_id="agent-uuid-shared",
            user_id=parent_user.user_id,
            child_id="child-1",
        )
        with pytest.raises(Exception):
            await _insert_user_agent(
                db,
                agent_id="agent-uuid-shared",
                user_id=parent_user.user_id,
                child_id="child-2",
            )


# ============================================================================
# Contract: ON DELETE CASCADE
# ============================================================================


class TestCascadeOnUserDelete:
    """Deleting the parent user cascades to user_agents rows."""

    @pytest.mark.asyncio
    async def test_cascade_delete(self, db, parent_user):
        await _insert_user_agent(
            db,
            agent_id="agent-cascade-1",
            user_id=parent_user.user_id,
            child_id="child-cascade",
        )
        # Sanity: row exists.
        before = await db.fetchone(
            "SELECT 1 FROM user_agents WHERE agent_id = ?",
            ("agent-cascade-1",),
        )
        assert before is not None

        await db.execute(
            "DELETE FROM users WHERE user_id = ?", (parent_user.user_id,)
        )
        await db.commit()

        after = await db.fetchone(
            "SELECT 1 FROM user_agents WHERE agent_id = ?",
            ("agent-cascade-1",),
        )
        assert after is None, "ON DELETE CASCADE did not remove the user_agents row"


# ============================================================================
# Contract: index on user_id
# ============================================================================


class TestUserIdIndex:
    """idx_user_agents_user index is created for fast lookup-by-user."""

    @pytest.mark.asyncio
    async def test_index_exists(self, db):
        rows = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='user_agents'"
        )
        names = {row["name"] for row in rows}
        assert "idx_user_agents_user" in names
