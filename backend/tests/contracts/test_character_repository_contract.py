"""
Character Repository Contract Tests

Defines the expected interface and behavior of CharacterRepository
before implementation. Tests CRUD operations and constraints.

Parent Epic: #42 (Memory System)
Issue: #160
"""

import json
import pytest
from datetime import datetime

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.character_repository import (
    CharacterRepository,
    character_repo,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def db():
    """In-memory database for testing."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    # Create the characters table directly
    await manager.execute(
        """
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            visual_features TEXT,
            traits TEXT,
            appearance_count INTEGER DEFAULT 1,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(child_id, name)
        )
        """
    )
    await manager.execute(
        "CREATE INDEX IF NOT EXISTS idx_characters_child_id ON characters(child_id)"
    )
    await manager.commit()
    yield manager
    await manager.disconnect()


@pytest.fixture
def repo(db):
    """CharacterRepository wired to in-memory db."""
    r = CharacterRepository()
    r._db = db
    return r


# ============================================================================
# upsert_character
# ============================================================================


class TestUpsertCharacter:
    """Contract: upsert_character inserts or updates a character."""

    @pytest.mark.asyncio
    async def test_insert_new_character(self, repo):
        result = await repo.upsert_character(
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever with lightning bolts",
            visual_features={"colors": ["gold", "blue"], "accessories": ["cape"]},
            traits=["brave", "fast"],
        )

        assert result is not None
        assert result["name"] == "Lightning Dog"
        assert result["child_id"] == "child-1"
        assert result["appearance_count"] == 1

    @pytest.mark.asyncio
    async def test_upsert_existing_character_increments_count(self, repo):
        await repo.upsert_character(
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever",
        )
        result = await repo.upsert_character(
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever with lightning bolts",
        )

        assert result["appearance_count"] == 2
        assert result["description"] == "A fast golden retriever with lightning bolts"

    @pytest.mark.asyncio
    async def test_upsert_updates_last_seen(self, repo):
        first = await repo.upsert_character(
            child_id="child-1",
            name="Star Cat",
        )
        second = await repo.upsert_character(
            child_id="child-1",
            name="Star Cat",
        )

        assert second["last_seen_at"] >= first["last_seen_at"]

    @pytest.mark.asyncio
    async def test_different_children_same_character_name(self, repo):
        await repo.upsert_character(child_id="child-1", name="Hero")
        await repo.upsert_character(child_id="child-2", name="Hero")

        chars_1 = await repo.get_characters("child-1")
        chars_2 = await repo.get_characters("child-2")

        assert len(chars_1) == 1
        assert len(chars_2) == 1


# ============================================================================
# get_characters
# ============================================================================


class TestGetCharacters:
    """Contract: get_characters returns all characters for a child."""

    @pytest.mark.asyncio
    async def test_returns_all_characters_for_child(self, repo):
        await repo.upsert_character(child_id="child-1", name="Dog")
        await repo.upsert_character(child_id="child-1", name="Cat")
        await repo.upsert_character(child_id="child-2", name="Bird")

        chars = await repo.get_characters("child-1")
        assert len(chars) == 2
        names = {c["name"] for c in chars}
        assert names == {"Dog", "Cat"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_unknown_child(self, repo):
        chars = await repo.get_characters("nonexistent")
        assert chars == []

    @pytest.mark.asyncio
    async def test_ordered_by_appearance_count_desc(self, repo):
        await repo.upsert_character(child_id="child-1", name="Rare")
        await repo.upsert_character(child_id="child-1", name="Popular")
        await repo.upsert_character(child_id="child-1", name="Popular")
        await repo.upsert_character(child_id="child-1", name="Popular")

        chars = await repo.get_characters("child-1")
        assert chars[0]["name"] == "Popular"
        assert chars[0]["appearance_count"] == 3


# ============================================================================
# get_character
# ============================================================================


class TestGetCharacter:
    """Contract: get_character returns a single character or None."""

    @pytest.mark.asyncio
    async def test_returns_character_when_found(self, repo):
        await repo.upsert_character(
            child_id="child-1",
            name="Lightning Dog",
            description="fast dog",
        )

        char = await repo.get_character("child-1", "Lightning Dog")
        assert char is not None
        assert char["name"] == "Lightning Dog"
        assert char["description"] == "fast dog"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repo):
        char = await repo.get_character("child-1", "Nonexistent")
        assert char is None


# ============================================================================
# increment_appearance
# ============================================================================


class TestIncrementAppearance:
    """Contract: increment_appearance bumps the count and updates last_seen."""

    @pytest.mark.asyncio
    async def test_increments_count(self, repo):
        await repo.upsert_character(child_id="child-1", name="Dog")

        result = await repo.increment_appearance("child-1", "Dog")
        assert result is True

        char = await repo.get_character("child-1", "Dog")
        assert char["appearance_count"] == 2

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_character(self, repo):
        result = await repo.increment_appearance("child-1", "Ghost")
        assert result is False


# ============================================================================
# JSON fields
# ============================================================================


class TestJsonFields:
    """Contract: visual_features and traits are stored as JSON."""

    @pytest.mark.asyncio
    async def test_visual_features_roundtrip(self, repo):
        features = {"colors": ["red", "blue"], "shapes": ["circle"]}
        await repo.upsert_character(
            child_id="child-1",
            name="Shape Monster",
            visual_features=features,
        )

        char = await repo.get_character("child-1", "Shape Monster")
        assert char["visual_features"] == features

    @pytest.mark.asyncio
    async def test_traits_roundtrip(self, repo):
        traits = ["brave", "curious", "kind"]
        await repo.upsert_character(
            child_id="child-1",
            name="Hero",
            traits=traits,
        )

        char = await repo.get_character("child-1", "Hero")
        assert char["traits"] == traits
