"""Voice repository for cloned voice CRUD.

Stores cloned voice profiles in SQLite. Parents can upload a voice sample
to create a personalized voice for their child's story narration.

Issue: #150 | Parent Epic: #45
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .connection import db_manager


class VoiceRepository:
    def __init__(self):
        self._db = db_manager

    async def create_voice(
        self,
        voice_id: str,
        user_id: str,
        child_id: str,
        display_name: str,
        replicate_voice_id: str,
        voice_file_hash: str,
    ) -> Dict[str, Any]:
        """Create a new cloned voice entry."""
        now = datetime.now().isoformat()
        await self._db.execute(
            """
            INSERT INTO cloned_voices (voice_id, user_id, child_id, display_name,
                replicate_voice_id, voice_file_hash, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (voice_id, user_id, child_id, display_name, replicate_voice_id,
             voice_file_hash, now),
        )
        await self._db.commit()
        return await self.get_voice(voice_id)

    async def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get a single cloned voice by ID."""
        row = await self._db.fetchone(
            "SELECT * FROM cloned_voices WHERE voice_id = ? AND is_active = 1",
            (voice_id,),
        )
        return dict(row) if row else None

    async def get_voices_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active cloned voices for a user."""
        rows = await self._db.fetchall(
            "SELECT * FROM cloned_voices WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]

    async def get_voices_for_child(self, child_id: str) -> List[Dict[str, Any]]:
        """Get all active cloned voices for a child."""
        rows = await self._db.fetchall(
            "SELECT * FROM cloned_voices WHERE child_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (child_id,),
        )
        return [dict(r) for r in rows]

    async def deactivate_voice(self, voice_id: str, user_id: str) -> bool:
        """Soft-delete a cloned voice (must belong to user)."""
        cursor = await self._db.execute(
            "UPDATE cloned_voices SET is_active = 0 WHERE voice_id = ? AND user_id = ?",
            (voice_id, user_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0


voice_repo = VoiceRepository()
