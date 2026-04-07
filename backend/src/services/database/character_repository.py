"""Character repository for structured character CRUD.

Stores character profiles in SQLite. Complements ChromaDB which handles
semantic similarity matching across drawings — this layer handles
structured queries (list, count, update traits).

Issue: #160 | Parent Epic: #42
"""

import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from .connection import db_manager


class CharacterRepository:
    def __init__(self):
        self._db = db_manager

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Normalize display name by trimming and removing invisible chars."""
        if not isinstance(name, str):
            return ""
        cleaned = unicodedata.normalize("NFKC", name)
        cleaned = re.sub(r"[\u200B-\u200D\uFEFF]", "", cleaned)
        cleaned = " ".join(cleaned.split())
        return cleaned.strip()

    @classmethod
    def _normalized_name_key(cls, name: str) -> str:
        """Build key used for dedupe and matching.

        Ignores case, spacing, and punctuation/symbol differences.
        """
        cleaned = cls._sanitize_name(name)
        if not cleaned:
            return ""
        compact = "".join(
            ch
            for ch in cleaned
            if not ch.isspace() and unicodedata.category(ch)[0] not in {"P", "S"}
        )
        return (compact or cleaned).casefold()

    @staticmethod
    def _merge_traits(existing: Any, incoming: Any) -> List[str]:
        merged: List[str] = []
        for source in (existing, incoming):
            if isinstance(source, list):
                for item in source:
                    if isinstance(item, str) and item not in merged:
                        merged.append(item)
        return merged

    @staticmethod
    def _pick_description(existing: Any, incoming: Any) -> Optional[str]:
        candidates = [
            c for c in (existing, incoming) if isinstance(c, str) and c.strip()
        ]
        if not candidates:
            return None
        return max(candidates, key=len)

    @staticmethod
    def _pick_visual_features(existing: Any, incoming: Any) -> Any:
        existing_score = len(existing) if isinstance(existing, dict) else 0
        incoming_score = len(incoming) if isinstance(incoming, dict) else 0
        if incoming_score > existing_score:
            return incoming
        return existing if existing is not None else incoming

    @staticmethod
    def _display_name_score(name: str) -> int:
        if not isinstance(name, str) or not name:
            return 0
        score = 0
        if any(ch.isupper() for ch in name):
            score += 2
        if name[:1].isupper():
            score += 1
        if name == name.title():
            score += 1
        return score

    async def _find_by_normalized_name(
        self, user_id: str, child_id: str, name: str
    ) -> Optional[Dict[str, Any]]:
        target = self._normalized_name_key(name)
        if not target:
            return None
        rows = await self._db.fetchall(
            "SELECT * FROM characters WHERE user_id = ? AND child_id = ?",
            (user_id, child_id),
        )
        for row in rows:
            parsed = self._deserialize(row)
            if self._normalized_name_key(parsed.get("name", "")) == target:
                return parsed
        return None

    async def upsert_character(
        self,
        user_id: str,
        child_id: str,
        name: str,
        description: Optional[str] = None,
        visual_features: Optional[Dict[str, Any]] = None,
        traits: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Insert a new character or update an existing one.

        On conflict (same user_id + child_id + name): increments appearance_count,
        updates description/visual_features/traits/last_seen_at.

        Args:
            user_id: Owner's user ID — scopes characters per account (#288).
            child_id: Child profile ID.
            name: Character name.

        Returns the character row as a dict.
        """
        cleaned_name = self._sanitize_name(name)
        if not cleaned_name:
            raise ValueError("Character name cannot be empty")

        canonical = await self._find_by_normalized_name(user_id, child_id, cleaned_name)
        target_name = canonical["name"] if canonical else cleaned_name

        now = datetime.now().isoformat()
        features_json = (
            json.dumps(visual_features, ensure_ascii=False) if visual_features else None
        )
        traits_json = json.dumps(traits, ensure_ascii=False) if traits else None

        await self._db.execute(
            """
            INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(user_id, child_id, name)
            DO UPDATE SET
                description = COALESCE(excluded.description, characters.description),
                visual_features = COALESCE(excluded.visual_features, characters.visual_features),
                traits = COALESCE(excluded.traits, characters.traits),
                appearance_count = characters.appearance_count + 1,
                last_seen_at = excluded.last_seen_at
            """,
            (
                user_id,
                child_id,
                target_name,
                description,
                features_json,
                traits_json,
                now,
                now,
            ),
        )
        await self._db.commit()

        return await self.get_character(user_id, child_id, target_name)

    async def get_characters(self, user_id: str, child_id: str) -> List[Dict[str, Any]]:
        """Return all characters for a child, merged by normalized name."""
        rows = await self._db.fetchall(
            "SELECT * FROM characters WHERE user_id = ? AND child_id = ? ORDER BY appearance_count DESC",
            (user_id, child_id),
        )
        deserialized = [self._deserialize(row) for row in rows]

        merged: Dict[str, Dict[str, Any]] = {}
        for item in deserialized:
            key = self._normalized_name_key(item.get("name", ""))
            if not key:
                continue

            if key not in merged:
                merged[key] = dict(item)
                merged[key]["name"] = self._sanitize_name(merged[key].get("name", ""))
                continue

            current = merged[key]
            current["appearance_count"] = int(current.get("appearance_count", 0)) + int(
                item.get("appearance_count", 0)
            )
            current["description"] = self._pick_description(
                current.get("description"), item.get("description")
            )
            current_name = self._sanitize_name(current.get("name", ""))
            incoming_name = self._sanitize_name(item.get("name", ""))
            if self._display_name_score(incoming_name) > self._display_name_score(
                current_name
            ):
                current["name"] = incoming_name
            current["visual_features"] = self._pick_visual_features(
                current.get("visual_features"), item.get("visual_features")
            )
            current["traits"] = self._merge_traits(
                current.get("traits"), item.get("traits")
            )

            first_seen = [
                v
                for v in (current.get("first_seen_at"), item.get("first_seen_at"))
                if v
            ]
            last_seen = [
                v for v in (current.get("last_seen_at"), item.get("last_seen_at")) if v
            ]
            if first_seen:
                current["first_seen_at"] = min(first_seen)
            if last_seen:
                current["last_seen_at"] = max(last_seen)

        return sorted(
            merged.values(),
            key=lambda c: (
                int(c.get("appearance_count", 0)),
                c.get("last_seen_at", ""),
            ),
            reverse=True,
        )

    async def _get_main_story_counts(
        self, user_id: str, child_id: str
    ) -> Dict[str, int]:
        """Count how many stories each character appears as the first character.

        We treat the first character in each story's `characters` list as the
        story protagonist (main character) for gallery grouping.
        """
        rows = await self._db.fetchall(
            """
            SELECT characters
            FROM stories
            WHERE user_id = ? AND child_id = ?
            ORDER BY created_at DESC
            """,
            (user_id, child_id),
        )

        counts: Dict[str, int] = {}
        for row in rows:
            raw = row.get("characters")
            if not raw:
                continue

            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(parsed, list):
                continue

            lead_name = ""
            for item in parsed:
                candidate = ""
                if isinstance(item, dict):
                    candidate = (
                        item.get("character_name")
                        or item.get("name")
                        or item.get("characterName")
                        or ""
                    )
                elif isinstance(item, str):
                    candidate = item

                token = self._sanitize_name(str(candidate or ""))
                if token:
                    lead_name = token
                    break

            if not lead_name:
                continue

            key = self._normalized_name_key(lead_name)
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1

        return counts

    async def get_characters_grouped(
        self, user_id: str, child_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return character gallery split into main/supporting groups."""
        characters = await self.get_characters(user_id, child_id)
        main_story_counts = await self._get_main_story_counts(user_id, child_id)

        main_characters: List[Dict[str, Any]] = []
        other_characters: List[Dict[str, Any]] = []

        for item in characters:
            entry = dict(item)
            key = self._normalized_name_key(entry.get("name", ""))
            main_count = int(main_story_counts.get(key, 0)) if key else 0
            entry["main_story_count"] = main_count
            entry["character_role"] = "main" if main_count > 0 else "other"

            if main_count > 0:
                main_characters.append(entry)
            else:
                other_characters.append(entry)

        main_characters.sort(
            key=lambda c: (
                int(c.get("main_story_count", 0)),
                int(c.get("appearance_count", 0)),
                c.get("last_seen_at", ""),
            ),
            reverse=True,
        )
        other_characters.sort(
            key=lambda c: (
                int(c.get("appearance_count", 0)),
                c.get("last_seen_at", ""),
            ),
            reverse=True,
        )

        # Keep backward compatibility for existing consumers.
        all_characters = main_characters + other_characters
        return {
            "characters": all_characters,
            "main_characters": main_characters,
            "other_characters": other_characters,
        }

    async def get_character(
        self, user_id: str, child_id: str, name: str
    ) -> Optional[Dict[str, Any]]:
        """Return a single character or None."""
        cleaned_name = self._sanitize_name(name)
        if not cleaned_name:
            return None
        row = await self._db.fetchone(
            "SELECT * FROM characters WHERE user_id = ? AND child_id = ? AND name = ?",
            (user_id, child_id, cleaned_name),
        )
        if not row:
            return await self._find_by_normalized_name(user_id, child_id, cleaned_name)
        parsed = self._deserialize(row)
        parsed["name"] = self._sanitize_name(parsed.get("name", ""))
        return parsed

    async def increment_appearance(
        self, user_id: str, child_id: str, name: str
    ) -> bool:
        """Increment appearance_count and update last_seen_at.

        Returns True if character existed, False otherwise.
        """
        existing = await self._find_by_normalized_name(user_id, child_id, name)
        if not existing:
            return False
        target_name = existing.get("name", "")

        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            """
            UPDATE characters
            SET appearance_count = appearance_count + 1, last_seen_at = ?
            WHERE user_id = ? AND child_id = ? AND name = ?
            """,
            (now, user_id, child_id, target_name),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def decrement_appearance(
        self, user_id: str, child_id: str, name: str, amount: int = 1
    ) -> int:
        """Decrement appearance_count for a character name.

        Matches name using normalized key and decrements across all variants.
        Removes rows whose count reaches zero.

        Returns:
            int: Actual decremented amount.
        """
        if amount <= 0:
            return 0

        target = self._normalized_name_key(name)
        if not target:
            return 0

        rows = await self._db.fetchall(
            "SELECT name, appearance_count FROM characters WHERE user_id = ? AND child_id = ?",
            (user_id, child_id),
        )
        matches = [
            {
                "name": row.get("name", ""),
                "appearance_count": int(row.get("appearance_count") or 0),
            }
            for row in rows
            if self._normalized_name_key(row.get("name", "")) == target
        ]
        if not matches:
            return 0

        # Decrement from the smallest buckets first so stale duplicates are cleaned up.
        matches.sort(key=lambda item: item["appearance_count"])
        remaining = amount
        decremented = 0

        for item in matches:
            if remaining <= 0:
                break
            current = max(0, int(item.get("appearance_count") or 0))
            if current <= 0:
                continue

            token = item["name"]
            if current <= remaining:
                await self._db.execute(
                    "DELETE FROM characters WHERE user_id = ? AND child_id = ? AND name = ?",
                    (user_id, child_id, token),
                )
                decremented += current
                remaining -= current
            else:
                next_count = current - remaining
                await self._db.execute(
                    "UPDATE characters SET appearance_count = ? WHERE user_id = ? AND child_id = ? AND name = ?",
                    (next_count, user_id, child_id, token),
                )
                decremented += remaining
                remaining = 0

        await self._db.commit()
        return decremented

    async def delete_character(self, user_id: str, child_id: str, name: str) -> bool:
        """Delete one character by exact name.

        Returns True when a row is deleted, False when not found.
        """
        target = self._normalized_name_key(name)
        if not target:
            return False

        rows = await self._db.fetchall(
            "SELECT name FROM characters WHERE user_id = ? AND child_id = ?",
            (user_id, child_id),
        )
        names_to_delete = [
            row["name"]
            for row in rows
            if self._normalized_name_key(row.get("name", "")) == target
        ]
        if not names_to_delete:
            return False

        placeholders = ",".join("?" for _ in names_to_delete)
        cursor = await self._db.execute(
            f"DELETE FROM characters WHERE user_id = ? AND child_id = ? AND name IN ({placeholders})",
            (user_id, child_id, *names_to_delete),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_characters_for_child(self, user_id: str, child_id: str) -> int:
        """Delete all characters for one child and return deleted row count."""
        cursor = await self._db.execute(
            "DELETE FROM characters WHERE user_id = ? AND child_id = ?",
            (user_id, child_id),
        )
        await self._db.commit()
        return int(cursor.rowcount or 0)

    def _deserialize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON fields from a raw DB row."""
        result = dict(row)
        if isinstance(result.get("name"), str):
            result["name"] = self._sanitize_name(result["name"])
        for field in ("visual_features", "traits"):
            val = result.get(field)
            if isinstance(val, str):
                try:
                    result[field] = json.loads(val)
                except json.JSONDecodeError:
                    result[field] = None
        return result


character_repo = CharacterRepository()
