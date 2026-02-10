"""
Session Repository

CRUD operations for interactive story sessions with user relationship support.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .connection import db_manager


@dataclass
class SessionData:
    """Session data structure (compatible with original SessionManager)."""
    session_id: str
    child_id: str
    story_title: str
    age_group: str
    interests: List[str]
    theme: Optional[str]
    voice: str
    enable_audio: bool
    current_segment: int
    total_segments: int
    choice_history: List[str]
    segments: List[Dict[str, Any]]
    status: str
    created_at: str
    updated_at: str
    expires_at: str
    user_id: Optional[str] = None  # Owner's user ID
    audio_urls: Optional[Dict[int, str]] = None
    educational_summary: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.audio_urls is None:
            self.audio_urls = {}


class SessionRepository:
    """Session repository with user relationship support."""

    def __init__(self):
        self._db = db_manager
        self.default_expiry_hours = 24

    async def create_session(
        self,
        child_id: str,
        story_title: str,
        age_group: str,
        interests: List[str],
        theme: Optional[str] = None,
        voice: str = "fable",
        enable_audio: bool = True,
        total_segments: int = 5,
        user_id: Optional[str] = None  # New: owner's user ID
    ) -> SessionData:
        """
        Create a new interactive story session.

        Args:
            child_id: Child profile ID
            story_title: Story title
            age_group: Age group for content adaptation
            interests: List of interest tags
            theme: Story theme
            voice: Voice type for audio
            enable_audio: Whether to generate audio
            total_segments: Expected total story segments
            user_id: Owner's user ID (optional)

        Returns:
            SessionData: Created session data
        """
        import uuid

        session_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=self.default_expiry_hours)

        await self._db.execute(
            """
            INSERT INTO sessions (
                session_id, user_id, child_id, story_title, age_group, interests,
                theme, voice, enable_audio, current_segment, total_segments,
                choice_history, audio_urls, status, created_at, updated_at,
                expires_at, educational_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,  # New: user_id
                child_id,
                story_title,
                age_group,
                json.dumps(interests, ensure_ascii=False),
                theme,
                voice,
                1 if enable_audio else 0,
                0,
                total_segments,
                json.dumps([], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                "active",
                now.isoformat(),
                now.isoformat(),
                expires_at.isoformat(),
                None
            )
        )
        await self._db.commit()

        return SessionData(
            session_id=session_id,
            child_id=child_id,
            story_title=story_title,
            age_group=age_group,
            interests=interests,
            theme=theme,
            voice=voice,
            enable_audio=enable_audio,
            current_segment=0,
            total_segments=total_segments,
            choice_history=[],
            segments=[],
            status="active",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            user_id=user_id,
            audio_urls={},
            educational_summary=None
        )

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            SessionData 或 None
        """
        row = await self._db.fetchone(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        )

        if not row:
            return None

        # 检查是否过期
        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at and row['status'] == 'active':
            await self._db.execute(
                "UPDATE sessions SET status = 'expired' WHERE session_id = ?",
                (session_id,)
            )
            await self._db.commit()
            row = dict(row)
            row['status'] = 'expired'

        # 获取故事段落
        segments = await self._get_segments(session_id)

        return self._row_to_session(row, segments)

    async def update_session(
        self,
        session_id: str,
        segment: Optional[Dict[str, Any]] = None,
        choice_id: Optional[str] = None,
        status: Optional[str] = None,
        educational_summary: Optional[Dict[str, Any]] = None,
        audio_url: Optional[str] = None,
        segment_id: Optional[int] = None
    ) -> bool:
        """
        更新会话数据

        Args:
            session_id: 会话ID
            segment: 新的故事段落
            choice_id: 选择的选项ID
            status: 新状态
            educational_summary: 教育总结
            audio_url: 段落的音频URL
            segment_id: 音频对应的段落ID

        Returns:
            bool: 是否更新成功
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        now = datetime.now().isoformat()

        # 更新段落
        if segment:
            await self._add_segment(session_id, segment)
            new_segment_count = session.current_segment + 1
            await self._db.execute(
                "UPDATE sessions SET current_segment = ?, updated_at = ? WHERE session_id = ?",
                (new_segment_count, now, session_id)
            )

        # 更新选择历史
        if choice_id:
            new_history = session.choice_history + [choice_id]
            await self._db.execute(
                "UPDATE sessions SET choice_history = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(new_history, ensure_ascii=False), now, session_id)
            )

        # 更新状态
        if status:
            await self._db.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                (status, now, session_id)
            )

        # 更新教育总结
        if educational_summary:
            await self._db.execute(
                "UPDATE sessions SET educational_summary = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(educational_summary, ensure_ascii=False), now, session_id)
            )

        # 更新音频URL
        if audio_url and segment_id is not None:
            audio_urls = session.audio_urls or {}
            audio_urls[segment_id] = audio_url
            await self._db.execute(
                "UPDATE sessions SET audio_urls = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(audio_urls, ensure_ascii=False), now, session_id)
            )

            # 同时更新segment表中的audio_url
            await self._db.execute(
                "UPDATE story_segments SET audio_url = ? WHERE session_id = ? AND segment_id = ?",
                (audio_url, session_id, segment_id)
            )

        await self._db.commit()
        return True

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        # 级联删除会自动删除story_segments
        cursor = await self._db.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        await self._db.commit()

        return cursor.rowcount > 0

    async def list_sessions(
        self,
        child_id: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SessionData]:
        """
        List sessions with optional filters.

        Args:
            child_id: Filter by child profile ID
            status: Filter by status ('active', 'completed', 'expired')
            user_id: Filter by owner user ID
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            List[SessionData]: List of sessions
        """
        query = "SELECT * FROM sessions WHERE 1=1"
        params = []

        if child_id:
            query += " AND child_id = ?"
            params.append(child_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetchall(query, tuple(params))
        sessions = []

        for row in rows:
            segments = await self._get_segments(row['session_id'])
            sessions.append(self._row_to_session(row, segments))

        return sessions

    async def list_by_user(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SessionData]:
        """
        Get all sessions belonging to a specific user.

        Args:
            user_id: User's unique ID
            status: Optional status filter
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            List[SessionData]: Sessions owned by the user
        """
        return await self.list_sessions(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )

    async def count_by_user(self, user_id: str, status: Optional[str] = None) -> int:
        """
        Count total sessions for a user.

        Args:
            user_id: User's unique ID
            status: Optional status filter

        Returns:
            int: Total number of sessions
        """
        query = "SELECT COUNT(*) as count FROM sessions WHERE user_id = ?"
        params = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        row = await self._db.fetchone(query, tuple(params))
        return row['count'] if row else 0

    async def update_user_id(self, session_id: str, user_id: str) -> bool:
        """
        Associate a session with a user.

        Args:
            session_id: Session's unique ID
            user_id: User's unique ID

        Returns:
            bool: True if updated successfully
        """
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            "UPDATE sessions SET user_id = ?, updated_at = ? WHERE session_id = ?",
            (user_id, now, session_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            int: 清理的会话数量
        """
        now = datetime.now()
        cutoff = (now - timedelta(days=7)).isoformat()

        cursor = await self._db.execute(
            """
            DELETE FROM sessions
            WHERE expires_at < ? AND status IN ('expired', 'completed')
            """,
            (cutoff,)
        )
        await self._db.commit()

        return cursor.rowcount

    async def _add_segment(self, session_id: str, segment: Dict[str, Any]) -> None:
        """添加故事段落"""
        await self._db.execute(
            """
            INSERT OR REPLACE INTO story_segments (
                session_id, segment_id, text, audio_url, is_ending,
                choices, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                segment.get('segment_id', 0),
                segment.get('text', ''),
                segment.get('audio_url'),
                1 if segment.get('is_ending', False) else 0,
                json.dumps(segment.get('choices', []), ensure_ascii=False),
                datetime.now().isoformat()
            )
        )

    async def _get_segments(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话的所有故事段落"""
        rows = await self._db.fetchall(
            """
            SELECT * FROM story_segments
            WHERE session_id = ?
            ORDER BY segment_id
            """,
            (session_id,)
        )

        segments = []
        for row in rows:
            segments.append({
                "segment_id": row['segment_id'],
                "text": row['text'],
                "audio_url": row.get('audio_url'),
                "is_ending": bool(row.get('is_ending', 0)),
                "choices": json.loads(row.get('choices') or '[]')
            })

        return segments

    def _row_to_session(self, row: Dict[str, Any], segments: List[Dict[str, Any]]) -> SessionData:
        """Convert database row to SessionData."""
        # Parse JSON fields
        interests = json.loads(row.get('interests') or '[]')
        choice_history = json.loads(row.get('choice_history') or '[]')
        audio_urls_raw = json.loads(row.get('audio_urls') or '{}')
        educational_summary = json.loads(row['educational_summary']) if row.get('educational_summary') else None

        # Convert audio_urls keys to integers
        audio_urls = {int(k): v for k, v in audio_urls_raw.items()} if audio_urls_raw else {}

        return SessionData(
            session_id=row['session_id'],
            child_id=row['child_id'],
            story_title=row['story_title'],
            age_group=row['age_group'],
            interests=interests,
            theme=row.get('theme'),
            voice=row.get('voice', 'fable'),
            enable_audio=bool(row.get('enable_audio', 1)),
            current_segment=row.get('current_segment', 0),
            total_segments=row.get('total_segments', 5),
            choice_history=choice_history,
            segments=segments,
            status=row.get('status', 'active'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            expires_at=row['expires_at'],
            user_id=row.get('user_id'),  # Owner's user ID
            audio_urls=audio_urls,
            educational_summary=educational_summary
        )


# Global session repository instance
session_repo = SessionRepository()
