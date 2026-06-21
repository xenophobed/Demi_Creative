"""Contract tests: non-character entities (settings/props) are filtered (#742).

Story extraction mines a `characters` list from generated story JSON with no
guard, so settings ("The Enchanted Forest") and props ("The Mirror") were
stored as characters and surfaced in the Morning Show guest picker. The
repository must:
  1. classify such names as non-characters,
  2. skip persisting them on write (upsert returns None), and
  3. exclude any already-stored ones on read.

Parent Epic: #42 (Memory System) | Issue: #742
"""

import pytest

from backend.src.services.database.character_repository import CharacterRepository
from backend.src.services.database.connection import DatabaseManager


@pytest.fixture
async def db():
    manager = DatabaseManager(":memory:")
    await manager.connect()
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
    # Minimal stories table so get_characters_grouped's main-count query runs.
    await manager.execute(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            child_id TEXT,
            characters TEXT,
            created_at TEXT
        )
        """
    )
    await manager.commit()
    yield manager
    await manager.disconnect()


@pytest.fixture
def repo(db):
    r = CharacterRepository()
    r._db = db
    return r


# Names that should be rejected as settings/props.
NON_CHARACTER_NAMES = [
    "The Mirror",
    "The Enchanted Forest",
    "The Sparkling Ocean",
    "A Magical Castle",
    "The Kingdom",
]

# Real characters that must always pass.
CHARACTER_NAMES = [
    "Ember",
    "Luna",
    "Squirrel",
    "Fox Kit",
    "Rabbit",
    "Stella",
    "Hero",
    "Dog",
    "The Wizard",  # an article alone is not enough — wizard is animate
]


@pytest.mark.parametrize("name", NON_CHARACTER_NAMES)
def test_classifier_flags_settings_and_props(name):
    assert CharacterRepository._is_non_character_name(name) is True


@pytest.mark.parametrize("name", CHARACTER_NAMES)
def test_classifier_keeps_real_characters(name):
    assert CharacterRepository._is_non_character_name(name) is False


class TestWriteSkip:
    @pytest.mark.asyncio
    async def test_upsert_skips_non_character(self, repo):
        result = await repo.upsert_character(
            user_id="u1", child_id="c1", name="The Mirror",
            description="A magical mirror that forgot its own beauty",
        )
        assert result is None
        rows = await repo.get_characters("u1", "c1")
        assert rows == []

    @pytest.mark.asyncio
    async def test_upsert_keeps_real_character(self, repo):
        result = await repo.upsert_character(
            user_id="u1", child_id="c1", name="Ember",
            description="A wise young deer",
        )
        assert result is not None
        assert result["name"] == "Ember"


class TestReadExclusion:
    @pytest.mark.asyncio
    async def test_existing_junk_excluded_on_read(self, repo, db):
        # Simulate already-polluted data inserted before the fix existed.
        now = "2026-01-01T00:00:00"
        for name in ["Stella", "The Mirror", "The Enchanted Forest"]:
            await db.execute(
                "INSERT INTO characters (user_id, child_id, name, appearance_count, first_seen_at, last_seen_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                ("u1", "c1", name, now, now),
            )
        await db.commit()

        names = {c["name"] for c in await repo.get_characters("u1", "c1")}
        assert names == {"Stella"}

    @pytest.mark.asyncio
    async def test_grouped_view_excludes_junk(self, repo, db):
        now = "2026-01-01T00:00:00"
        for name in ["Luna", "The Sparkling Ocean"]:
            await db.execute(
                "INSERT INTO characters (user_id, child_id, name, appearance_count, first_seen_at, last_seen_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                ("u1", "c1", name, now, now),
            )
        await db.commit()

        grouped = await repo.get_characters_grouped("u1", "c1")
        all_names = {c["name"] for c in grouped["characters"]}
        assert all_names == {"Luna"}
