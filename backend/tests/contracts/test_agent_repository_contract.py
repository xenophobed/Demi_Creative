"""
Agent Repository Contract Tests (#439)

Defines the expected interface and behavior of AgentRepository.
Tests upsert semantics, idempotency, and ID format.

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #439
"""

import re

import pytest
import pytest_asyncio

from backend.src.services.database.agent_repository import (
    AgentData,
    AgentRepository,
    agent_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def db():
    """In-memory database with full schema for agent tests."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def repo(db):
    """AgentRepository bound to the test database."""
    r = AgentRepository()
    r._db = db
    return r


@pytest_asyncio.fixture
async def user(db):
    """Create a user (FK target for user_agents.user_id)."""
    user_repo_instance = UserRepository()
    user_repo_instance._db = db
    return await user_repo_instance.create_user(
        username="agent_user",
        email="agent@test.com",
        password_hash="h",
    )


# ============================================================================
# Contract: Module exports
# ============================================================================


class TestModuleExports:
    """agent_repository module exports expected symbols."""

    def test_singleton_exists(self):
        assert agent_repo is not None

    def test_singleton_is_repository(self):
        assert isinstance(agent_repo, AgentRepository)

    def test_dataclass_fields(self):
        # AgentData must expose every field documented in the spec.
        expected = {
            "agent_id",
            "user_id",
            "child_id",
            "agent_name",
            "agent_avatar_id",
            "agent_title",
            "created_at",
            "updated_at",
        }
        actual = {f.name for f in AgentData.__dataclass_fields__.values()}
        assert expected.issubset(actual), (
            f"AgentData missing fields: {expected - actual}"
        )


# ============================================================================
# Contract: get_agent
# ============================================================================


class TestGetAgent:
    """get_agent(user_id, child_id) returns the row or None."""

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, repo, user):
        """No row -> None."""
        result = await repo.get_agent(user.user_id, "child_not_there")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_data_when_present(self, repo, user):
        """After upsert -> get_agent returns AgentData."""
        await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_a",
            agent_name="Sparkle",
            agent_avatar_id="emoji:🦊",
            agent_title="Story Wizard",
        )
        got = await repo.get_agent(user.user_id, "child_a")
        assert got is not None
        assert isinstance(got, AgentData)
        assert got.agent_name == "Sparkle"
        assert got.agent_avatar_id == "emoji:🦊"
        assert got.agent_title == "Story Wizard"
        assert got.user_id == user.user_id
        assert got.child_id == "child_a"


# ============================================================================
# Contract: upsert_agent — insert path
# ============================================================================


class TestUpsertAgentInsert:
    """upsert_agent creates a new row when none exists."""

    @pytest.mark.asyncio
    async def test_creates_row_when_missing(self, repo, user):
        """First call inserts a row and returns AgentData."""
        result = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_b",
            agent_name="Buddy",
            agent_avatar_id="emoji:🐶",
            agent_title="Brave Lion",
        )
        assert isinstance(result, AgentData)
        assert result.agent_name == "Buddy"
        assert result.created_at == result.updated_at  # First write -> equal

    @pytest.mark.asyncio
    async def test_agent_id_pattern(self, repo, user):
        """agent_id must follow agt_<12 hex chars> for sortable, debuggable IDs."""
        result = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_c",
            agent_name="Buddy",
            agent_avatar_id="emoji:🐶",
            agent_title="Brave Lion",
        )
        assert re.fullmatch(r"agt_[0-9a-f]{12}", result.agent_id), (
            f"agent_id format wrong: {result.agent_id}"
        )


# ============================================================================
# Contract: upsert_agent — update path
# ============================================================================


class TestUpsertAgentUpdate:
    """upsert_agent updates the existing row in place when one exists."""

    @pytest.mark.asyncio
    async def test_updates_in_place_for_same_pair(self, repo, user):
        """Re-upsert with the same (user_id, child_id) keeps a single row."""
        first = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_d",
            agent_name="Buddy",
            agent_avatar_id="emoji:🐶",
            agent_title="Brave Lion",
        )

        second = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_d",
            agent_name="Friend",
            agent_avatar_id="emoji:🦊",
            agent_title="Story Wizard",
        )

        # Same agent_id (stable) but changed payload.
        assert second.agent_id == first.agent_id
        assert second.agent_name == "Friend"
        assert second.agent_avatar_id == "emoji:🦊"
        assert second.agent_title == "Story Wizard"

    @pytest.mark.asyncio
    async def test_created_at_unchanged_updated_at_advances(self, repo, user):
        """created_at is preserved, updated_at advances on re-upsert."""
        import asyncio

        first = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_e",
            agent_name="Buddy",
            agent_avatar_id="emoji:🐶",
            agent_title="Brave Lion",
        )
        # Sleep enough to guarantee a distinct ISO timestamp.
        await asyncio.sleep(0.005)
        second = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_e",
            agent_name="Friend",
            agent_avatar_id="emoji:🦊",
            agent_title="Story Wizard",
        )
        assert second.created_at == first.created_at
        assert second.updated_at >= first.updated_at
        assert second.updated_at != first.created_at or second.updated_at > first.updated_at

    @pytest.mark.asyncio
    async def test_distinct_pairs_get_distinct_rows(self, repo, user):
        """Different (user_id, child_id) yield two rows with distinct agent_ids."""
        a = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_f1",
            agent_name="A",
            agent_avatar_id="emoji:🐶",
            agent_title="Brave Lion",
        )
        b = await repo.upsert_agent(
            user_id=user.user_id,
            child_id="child_f2",
            agent_name="B",
            agent_avatar_id="emoji:🐱",
            agent_title="Story Wizard",
        )
        assert a.agent_id != b.agent_id
