"""Repository for parent-owned child profile records."""

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Optional
from uuid import uuid4

from .connection import db_manager


@dataclass
class ChildProfileData:
    child_id: str
    user_id: str
    name: str
    age_group: str
    interests: list[str]
    avatar: Optional[str]
    is_default: bool
    archived_at: Optional[str]
    created_at: str
    updated_at: str
    camera_consent: bool = False
    microphone_consent: bool = False


class ChildProfileRepository:
    """CRUD operations scoped by account owner."""

    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    async def list_for_user(
        self, user_id: str, *, include_archived: bool = False
    ) -> list[ChildProfileData]:
        query = """
            SELECT child_id, user_id, name, age_group, interests, avatar,
                   is_default, archived_at, camera_consent, microphone_consent,
                   created_at, updated_at
            FROM child_profiles
            WHERE user_id = ?
        """
        params: list[object] = [user_id]
        if not include_archived:
            query += " AND archived_at IS NULL"
        query += " ORDER BY is_default DESC, created_at ASC"

        rows = await self._db.fetchall(query, tuple(params))
        return [self._row_to_profile(row) for row in rows]

    async def get_for_user(
        self, user_id: str, child_id: str, *, include_archived: bool = False
    ) -> Optional[ChildProfileData]:
        query = """
            SELECT child_id, user_id, name, age_group, interests, avatar,
                   is_default, archived_at, camera_consent, microphone_consent,
                   created_at, updated_at
            FROM child_profiles
            WHERE user_id = ? AND child_id = ?
        """
        params: list[object] = [user_id, child_id]
        if not include_archived:
            query += " AND archived_at IS NULL"

        row = await self._db.fetchone(query, tuple(params))
        return self._row_to_profile(row) if row else None

    async def create(
        self,
        *,
        user_id: str,
        name: str,
        age_group: str,
        interests: Optional[list[str]] = None,
        avatar: Optional[str] = None,
        child_id: Optional[str] = None,
        is_default: bool = False,
    ) -> ChildProfileData:
        now = datetime.now().isoformat()
        resolved_child_id = child_id or f"child_{uuid4().hex[:12]}"
        normalized_interests = self._normalize_interests(interests)

        if is_default:
            await self._clear_default(user_id)

        await self._db.execute(
            """
            INSERT INTO child_profiles (
                child_id, user_id, name, age_group, interests, avatar,
                is_default, archived_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_child_id,
                user_id,
                name.strip(),
                age_group,
                json.dumps(normalized_interests, ensure_ascii=False),
                avatar,
                1 if is_default else 0,
                None,
                now,
                now,
            ),
        )
        if is_default:
            await self._sync_user_default(user_id, resolved_child_id)
        await self._db.commit()

        return ChildProfileData(
            child_id=resolved_child_id,
            user_id=user_id,
            name=name.strip(),
            age_group=age_group,
            interests=normalized_interests,
            avatar=avatar,
            is_default=is_default,
            archived_at=None,
            created_at=now,
            updated_at=now,
            camera_consent=False,
            microphone_consent=False,
        )

    async def update(
        self,
        *,
        user_id: str,
        child_id: str,
        name: Optional[str] = None,
        age_group: Optional[str] = None,
        interests: Optional[list[str]] = None,
        avatar: Optional[str] = None,
    ) -> Optional[ChildProfileData]:
        existing = await self.get_for_user(user_id, child_id)
        if existing is None:
            return None

        updates = ["updated_at = ?"]
        params: list[object] = [datetime.now().isoformat()]

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if age_group is not None:
            updates.append("age_group = ?")
            params.append(age_group)
        if interests is not None:
            updates.append("interests = ?")
            params.append(json.dumps(self._normalize_interests(interests), ensure_ascii=False))
        if avatar is not None:
            updates.append("avatar = ?")
            params.append(avatar)

        params.extend([user_id, child_id])
        await self._db.execute(
            f"""
            UPDATE child_profiles
            SET {', '.join(updates)}
            WHERE user_id = ? AND child_id = ? AND archived_at IS NULL
            """,
            tuple(params),
        )
        await self._db.commit()
        return await self.get_for_user(user_id, child_id)

    async def set_default(
        self, *, user_id: str, child_id: str
    ) -> Optional[ChildProfileData]:
        existing = await self.get_for_user(user_id, child_id)
        if existing is None:
            return None

        now = datetime.now().isoformat()
        await self._clear_default(user_id)
        await self._db.execute(
            """
            UPDATE child_profiles
            SET is_default = 1, updated_at = ?
            WHERE user_id = ? AND child_id = ? AND archived_at IS NULL
            """,
            (now, user_id, child_id),
        )
        await self._sync_user_default(user_id, child_id)
        await self._db.commit()
        return await self.get_for_user(user_id, child_id)

    async def update_consent(
        self,
        *,
        user_id: str,
        child_id: str,
        camera_consent: Optional[bool] = None,
        microphone_consent: Optional[bool] = None,
    ) -> Optional[ChildProfileData]:
        existing = await self.get_for_user(user_id, child_id)
        if existing is None:
            return None

        updates = ["updated_at = ?"]
        params: list[object] = [datetime.now().isoformat()]

        if camera_consent is not None:
            updates.append("camera_consent = ?")
            params.append(1 if camera_consent else 0)
        if microphone_consent is not None:
            updates.append("microphone_consent = ?")
            params.append(1 if microphone_consent else 0)

        params.extend([user_id, child_id])
        await self._db.execute(
            f"""
            UPDATE child_profiles
            SET {', '.join(updates)}
            WHERE user_id = ? AND child_id = ? AND archived_at IS NULL
            """,
            tuple(params),
        )
        await self._db.commit()
        return await self.get_for_user(user_id, child_id)

    async def archive(
        self, *, user_id: str, child_id: str
    ) -> Optional[ChildProfileData]:
        existing = await self.get_for_user(user_id, child_id)
        if existing is None:
            return None

        now = datetime.now().isoformat()
        await self._db.execute(
            """
            UPDATE child_profiles
            SET archived_at = ?, is_default = 0, updated_at = ?
            WHERE user_id = ? AND child_id = ? AND archived_at IS NULL
            """,
            (now, now, user_id, child_id),
        )
        if existing.is_default:
            await self._sync_user_default(user_id, None)
        await self._db.commit()
        return await self.get_for_user(user_id, child_id, include_archived=True)

    async def _clear_default(self, user_id: str) -> None:
        await self._db.execute(
            "UPDATE child_profiles SET is_default = 0 WHERE user_id = ?",
            (user_id,),
        )

    async def _sync_user_default(
        self, user_id: str, child_id: Optional[str]
    ) -> None:
        await self._db.execute(
            "UPDATE users SET default_child_id = ?, updated_at = ? WHERE user_id = ?",
            (child_id, datetime.now().isoformat(), user_id),
        )

    @staticmethod
    def _normalize_interests(interests: Optional[list[str]]) -> list[str]:
        if not interests:
            return []
        result = []
        for item in interests:
            token = str(item).strip()
            if token:
                result.append(token)
        return result[:8]

    @classmethod
    def _row_to_profile(cls, row: dict) -> ChildProfileData:
        try:
            interests = json.loads(row.get("interests") or "[]")
        except (TypeError, ValueError):
            interests = []
        if not isinstance(interests, list):
            interests = []

        return ChildProfileData(
            child_id=row["child_id"],
            user_id=row["user_id"],
            name=row["name"],
            age_group=row.get("age_group") or "6-8",
            interests=[str(item) for item in interests],
            avatar=row.get("avatar"),
            is_default=bool(row.get("is_default", 0)),
            archived_at=row.get("archived_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            camera_consent=bool(row.get("camera_consent", 0)),
            microphone_consent=bool(row.get("microphone_consent", 0)),
        )


child_profile_repo = ChildProfileRepository()
