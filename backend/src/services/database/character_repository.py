"""Character repository for structured character CRUD.

Stores character profiles in SQLite. Complements ChromaDB which handles
semantic similarity matching across drawings — this layer handles
structured queries (list, count, update traits).

Issue: #160 | Parent Epic: #42
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .connection import db_manager


class CharacterRepository:
    def __init__(self):
        self._db = db_manager

    async def upsert_character(
        self,
        child_id: str,
        name: str,
        description: Optional[str] = None,
        visual_features: Optional[Dict[str, Any]] = None,
        traits: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Insert a new character or update an existing one.

        On conflict (same child_id + name): increments appearance_count,
        updates description/visual_features/traits/last_seen_at.

        Returns the character row as a dict.
        """
        now = datetime.now().isoformat()
        features_json = json.dumps(visual_features, ensure_ascii=False) if visual_features else None
        traits_json = json.dumps(traits, ensure_ascii=False) if traits else None

        await self._db.execute(
            """
            INSERT INTO characters (child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(child_id, name)
            DO UPDATE SET
                description = COALESCE(excluded.description, characters.description),
                visual_features = COALESCE(excluded.visual_features, characters.visual_features),
                traits = COALESCE(excluded.traits, characters.traits),
                appearance_count = characters.appearance_count + 1,
                last_seen_at = excluded.last_seen_at
            """,
            (child_id, name, description, features_json, traits_json, now, now),
        )
        await self._db.commit()

        return await self.get_character(child_id, name)

    async def get_characters(self, child_id: str) -> List[Dict[str, Any]]:
        """Return all characters for a child, ordered by appearance_count DESC."""
        rows = await self._db.fetchall(
            "SELECT * FROM characters WHERE child_id = ? ORDER BY appearance_count DESC",
            (child_id,),
        )
        return [self._deserialize(row) for row in rows]

    async def get_character(self, child_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Return a single character or None."""
        row = await self._db.fetchone(
            "SELECT * FROM characters WHERE child_id = ? AND name = ?",
            (child_id, name),
        )
        if not row:
            return None
        return self._deserialize(row)

    async def increment_appearance(self, child_id: str, name: str) -> bool:
        """Increment appearance_count and update last_seen_at.

        Returns True if character existed, False otherwise.
        """
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            """
            UPDATE characters
            SET appearance_count = appearance_count + 1, last_seen_at = ?
            WHERE child_id = ? AND name = ?
            """,
            (now, child_id, name),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    def _deserialize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON fields from a raw DB row."""
        result = dict(row)
        for field in ("visual_features", "traits"):
            val = result.get(field)
            if isinstance(val, str):
                try:
                    result[field] = json.loads(val)
                except json.JSONDecodeError:
                    result[field] = None
        return result


character_repo = CharacterRepository()
