"""
Character Repository Contract Tests

Defines the expected interface and behavior of CharacterRepository
before implementation. Tests CRUD operations and constraints.

Parent Epic: #42 (Memory System)
Issue: #160, #288
"""

import json
from datetime import datetime

import pytest

from backend.src.services.database.character_repository import (
    CharacterRepository,
    character_repo,
)
from backend.src.services.database.connection import DatabaseManager

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
            user_id TEXT NOT NULL DEFAULT '',
            child_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            visual_features TEXT,
            traits TEXT,
            appearance_count INTEGER DEFAULT 1,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(user_id, child_id, name)
        )
        """
    )
    await manager.execute(
        "CREATE INDEX IF NOT EXISTS idx_characters_user_child ON characters(user_id, child_id)"
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
            user_id="user-1",
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever with lightning bolts",
            visual_features={"colors": ["gold", "blue"], "accessories": ["cape"]},
            traits=["brave", "fast"],
        )

        assert result is not None
        assert result["name"] == "Lightning Dog"
        assert result["child_id"] == "child-1"
        assert result["user_id"] == "user-1"
        assert result["appearance_count"] == 1

    @pytest.mark.asyncio
    async def test_upsert_existing_character_increments_count(self, repo):
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever",
        )
        result = await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Lightning Dog",
            description="A fast golden retriever with lightning bolts",
        )

        assert result["appearance_count"] == 2
        assert result["description"] == "A fast golden retriever with lightning bolts"

    @pytest.mark.asyncio
    async def test_upsert_normalizes_name_and_merges_whitespace_case_variants(
        self, repo
    ):
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Lightning Dog",
            description="First version",
        )
        result = await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="  lightning   dog  ",
            description="Second version",
        )

        chars = await repo.get_characters("user-1", "child-1")
        assert len(chars) == 1
        assert chars[0]["appearance_count"] == 2
        assert result["appearance_count"] == 2

    @pytest.mark.asyncio
    async def test_upsert_updates_last_seen(self, repo):
        first = await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Star Cat",
        )
        second = await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Star Cat",
        )

        assert second["last_seen_at"] >= first["last_seen_at"]

    @pytest.mark.asyncio
    async def test_different_children_same_character_name(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Hero")
        await repo.upsert_character(user_id="user-1", child_id="child-2", name="Hero")

        chars_1 = await repo.get_characters("user-1", "child-1")
        chars_2 = await repo.get_characters("user-1", "child-2")

        assert len(chars_1) == 1
        assert len(chars_2) == 1


# ============================================================================
# user_id scoping (#288)
# ============================================================================


class TestUserIdScoping:
    """Contract: characters are scoped by user_id to prevent cross-user data leakage."""

    @pytest.mark.asyncio
    async def test_two_users_same_child_id_get_separate_characters(self, repo):
        """Two users with the same child_id must not see each other's characters."""
        await repo.upsert_character(
            user_id="user-alice",
            child_id="child-1",
            name="Lightning Dog",
            description="Alice's dog",
        )
        await repo.upsert_character(
            user_id="user-bob",
            child_id="child-1",
            name="Lightning Dog",
            description="Bob's dog",
        )

        alice_chars = await repo.get_characters("user-alice", "child-1")
        bob_chars = await repo.get_characters("user-bob", "child-1")

        assert len(alice_chars) == 1
        assert len(bob_chars) == 1
        assert alice_chars[0]["description"] == "Alice's dog"
        assert bob_chars[0]["description"] == "Bob's dog"

    @pytest.mark.asyncio
    async def test_get_character_scoped_by_user_id(self, repo):
        """get_character must only return the character belonging to the given user."""
        await repo.upsert_character(
            user_id="user-alice",
            child_id="child-1",
            name="Star Cat",
            description="Alice's cat",
        )

        found = await repo.get_character("user-alice", "child-1", "Star Cat")
        not_found = await repo.get_character("user-bob", "child-1", "Star Cat")

        assert found is not None
        assert found["description"] == "Alice's cat"
        assert not_found is None

    @pytest.mark.asyncio
    async def test_increment_appearance_scoped_by_user_id(self, repo):
        """increment_appearance must only affect the character for the given user."""
        await repo.upsert_character(
            user_id="user-alice", child_id="child-1", name="Dog"
        )
        await repo.upsert_character(user_id="user-bob", child_id="child-1", name="Dog")

        result = await repo.increment_appearance("user-alice", "child-1", "Dog")
        assert result is True

        alice_char = await repo.get_character("user-alice", "child-1", "Dog")
        bob_char = await repo.get_character("user-bob", "child-1", "Dog")

        assert alice_char["appearance_count"] == 2
        assert bob_char["appearance_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_user_id_is_valid_default(self, repo):
        """Empty string user_id works as default for backward compatibility."""
        result = await repo.upsert_character(
            user_id="",
            child_id="child-1",
            name="Bunny",
        )
        assert result is not None
        assert result["user_id"] == ""

        chars = await repo.get_characters("", "child-1")
        assert len(chars) == 1


# ============================================================================
# get_characters
# ============================================================================


class TestGetCharacters:
    """Contract: get_characters returns all characters for a child."""

    @pytest.mark.asyncio
    async def test_returns_all_characters_for_child(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Dog")
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Cat")
        await repo.upsert_character(user_id="user-1", child_id="child-2", name="Bird")

        chars = await repo.get_characters("user-1", "child-1")
        assert len(chars) == 2
        names = {c["name"] for c in chars}
        assert names == {"Dog", "Cat"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_unknown_child(self, repo):
        chars = await repo.get_characters("user-1", "nonexistent")
        assert chars == []

    @pytest.mark.asyncio
    async def test_ordered_by_appearance_count_desc(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Rare")
        await repo.upsert_character(
            user_id="user-1", child_id="child-1", name="Popular"
        )
        await repo.upsert_character(
            user_id="user-1", child_id="child-1", name="Popular"
        )
        await repo.upsert_character(
            user_id="user-1", child_id="child-1", name="Popular"
        )

        chars = await repo.get_characters("user-1", "child-1")
        assert chars[0]["name"] == "Popular"
        assert chars[0]["appearance_count"] == 3

    @pytest.mark.asyncio
    async def test_merges_legacy_duplicate_rows_by_normalized_name(self, repo):
        now = datetime.now().isoformat()
        await repo._db.execute(
            """
            INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user-1",
                "child-1",
                "Star Cat",
                "first",
                json.dumps({"fur": "silver"}),
                json.dumps(["curious"]),
                2,
                now,
                now,
            ),
        )
        await repo._db.execute(
            """
            INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user-1",
                "child-1",
                " star   cat ",
                "second",
                json.dumps({"eyes": "blue"}),
                json.dumps(["gentle"]),
                3,
                now,
                now,
            ),
        )
        await repo._db.commit()

        chars = await repo.get_characters("user-1", "child-1")
        assert len(chars) == 1
        assert chars[0]["name"] == "Star Cat"
        assert chars[0]["appearance_count"] == 5
        assert set(chars[0]["traits"]) == {"curious", "gentle"}


# ============================================================================
# get_character
# ============================================================================


class TestGetCharacter:
    """Contract: get_character returns a single character or None."""

    @pytest.mark.asyncio
    async def test_returns_character_when_found(self, repo):
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Lightning Dog",
            description="fast dog",
        )

        char = await repo.get_character("user-1", "child-1", "Lightning Dog")
        assert char is not None
        assert char["name"] == "Lightning Dog"
        assert char["description"] == "fast dog"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repo):
        char = await repo.get_character("user-1", "child-1", "Nonexistent")
        assert char is None


# ============================================================================
# increment_appearance
# ============================================================================


class TestIncrementAppearance:
    """Contract: increment_appearance bumps the count and updates last_seen."""

    @pytest.mark.asyncio
    async def test_increments_count(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Dog")

        result = await repo.increment_appearance("user-1", "child-1", "Dog")
        assert result is True

        char = await repo.get_character("user-1", "child-1", "Dog")
        assert char["appearance_count"] == 2

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_character(self, repo):
        result = await repo.increment_appearance("user-1", "child-1", "Ghost")
        assert result is False


# ============================================================================
# decrement_appearance
# ============================================================================


class TestDecrementAppearance:
    """Contract: decrement_appearance reduces count and removes row at zero."""

    @pytest.mark.asyncio
    async def test_decrements_count_by_one(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Dog")
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Dog")

        changed = await repo.decrement_appearance("user-1", "child-1", "Dog")
        assert changed == 1
        char = await repo.get_character("user-1", "child-1", "Dog")
        assert char is not None
        assert char["appearance_count"] == 1

    @pytest.mark.asyncio
    async def test_removes_row_when_count_hits_zero(self, repo):
        await repo.upsert_character(user_id="user-1", child_id="child-1", name="Dog")

        changed = await repo.decrement_appearance("user-1", "child-1", "Dog")
        assert changed == 1
        char = await repo.get_character("user-1", "child-1", "Dog")
        assert char is None

    @pytest.mark.asyncio
    async def test_decrements_across_normalized_variants(self, repo):
        now = datetime.now().isoformat()
        await repo._db.execute(
            """
            INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user-1", "child-1", "Star Cat", "first", None, None, 1, now, now),
        )
        await repo._db.execute(
            """
            INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user-1", "child-1", "star-cat", "second", None, None, 2, now, now),
        )
        await repo._db.commit()

        changed = await repo.decrement_appearance("user-1", "child-1", "STAR CAT")
        assert changed == 1
        chars = await repo.get_characters("user-1", "child-1")
        assert len(chars) == 1
        assert chars[0]["appearance_count"] == 2


# ============================================================================
# JSON fields
# ============================================================================


class TestJsonFields:
    """Contract: visual_features and traits are stored as JSON."""

    @pytest.mark.asyncio
    async def test_visual_features_roundtrip(self, repo):
        features = {"colors": ["red", "blue"], "shapes": ["circle"]}
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Shape Monster",
            visual_features=features,
        )

        char = await repo.get_character("user-1", "child-1", "Shape Monster")
        assert char["visual_features"] == features

    @pytest.mark.asyncio
    async def test_traits_roundtrip(self, repo):
        traits = ["brave", "curious", "kind"]
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-1",
            name="Hero",
            traits=traits,
        )

        char = await repo.get_character("user-1", "child-1", "Hero")
        assert char["traits"] == traits

    @pytest.mark.asyncio
    async def test_enriched_upsert_stores_and_retrieves_all_fields(self, repo):
        """Issue #289: upsert with visual_features + traits stores both,
        and get_characters returns them deserialized."""
        visual_features = {
            "features": ["blue clothes", "pointy ears", "long tail"],
            "description_summary": "A puppy wearing blue clothes",
        }
        traits = ["brave", "loyal", "playful"]

        await repo.upsert_character(
            user_id="user-1",
            child_id="child-enrich",
            name="Lightning Dog",
            description="A fast golden retriever",
            visual_features=visual_features,
            traits=traits,
        )

        # Verify via get_characters (the list query used by routes)
        chars = await repo.get_characters("user-1", "child-enrich")
        assert len(chars) == 1
        char = chars[0]
        assert char["name"] == "Lightning Dog"
        assert char["description"] == "A fast golden retriever"
        assert char["visual_features"] == visual_features
        assert char["traits"] == traits
        assert char["appearance_count"] == 1

    @pytest.mark.asyncio
    async def test_enriched_upsert_updates_features_on_conflict(self, repo):
        """Issue #289: second upsert with richer data overwrites previous."""
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-enrich2",
            name="Star Cat",
            description="A cat",
            visual_features={"description_summary": "A cat"},
        )
        await repo.upsert_character(
            user_id="user-1",
            child_id="child-enrich2",
            name="Star Cat",
            description="A sparkly cat with a star on its forehead",
            visual_features={"features": ["star forehead", "sparkly fur"]},
            traits=["curious", "gentle"],
        )

        char = await repo.get_character("user-1", "child-enrich2", "Star Cat")
        assert char["appearance_count"] == 2
        assert char["visual_features"] == {"features": ["star forehead", "sparkly fur"]}
        assert char["traits"] == ["curious", "gentle"]


# ============================================================================
# get_characters_grouped — main/other by appearance frequency (Issue #746)
# ============================================================================


class TestGroupedByFrequency:
    """Contract: 'Main characters' are the top-N most frequently appearing.

    Regression for #746 — grouping used to be gated by main_story_count
    (was this character a story's lead), which mis-sorted frequent supporting
    characters into 'other' and one-off leads into 'main'.
    """

    @pytest.fixture
    async def db_with_stories(self, db):
        """Augment the in-memory db with a minimal stories table."""
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS stories (
                story_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                child_id TEXT NOT NULL,
                characters TEXT,
                created_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        await db.commit()
        return db

    @pytest.mark.asyncio
    async def test_top5_by_appearance_are_main(self, db_with_stories):
        repo = CharacterRepository()
        repo._db = db_with_stories

        # frequency: Star=6, Comet=5, Nova=4, Luna=3, Sol=2, Pip=1
        seeds = [("Star", 6), ("Comet", 5), ("Nova", 4), ("Luna", 3), ("Sol", 2), ("Pip", 1)]
        for name, freq in seeds:
            for _ in range(freq):
                await repo.upsert_character(
                    user_id="u1", child_id="c1", name=name, description=f"{name}"
                )

        # Make the least-frequent character (Pip) the lead of a story.
        await db_with_stories.execute(
            "INSERT INTO stories (story_id, user_id, child_id, characters, created_at) VALUES (?, ?, ?, ?, ?)",
            ("s1", "u1", "c1", json.dumps([{"character_name": "Pip"}]), "2026-01-01"),
        )
        await db_with_stories.commit()

        grouped = await repo.get_characters_grouped("u1", "c1")
        main_names = [c["name"] for c in grouped["main_characters"]]
        other_names = [c["name"] for c in grouped["other_characters"]]

        assert main_names == ["Star", "Comet", "Nova", "Luna", "Sol"]
        assert other_names == ["Pip"]
        # A one-off story lead with the lowest frequency must NOT be main.
        assert all(c["character_role"] == "main" for c in grouped["main_characters"])
        pip = grouped["other_characters"][0]
        assert pip["character_role"] == "other"
        assert pip["main_story_count"] == 1  # still reported, just not gating

    @pytest.mark.asyncio
    async def test_fewer_than_limit_all_main(self, db_with_stories):
        repo = CharacterRepository()
        repo._db = db_with_stories
        for name in ["A", "B", "C"]:
            await repo.upsert_character(user_id="u2", child_id="c2", name=name)

        grouped = await repo.get_characters_grouped("u2", "c2")
        assert len(grouped["main_characters"]) == 3
        assert grouped["other_characters"] == []
