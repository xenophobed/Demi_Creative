"""
User Repository

CRUD operations for user data with story relationship support.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .connection import db_manager


@dataclass
class UserData:
    """User data structure."""
    user_id: str
    username: str
    email: str
    password_hash: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_login_at: Optional[str] = None


@dataclass
class UserWithStats(UserData):
    """User data with story statistics."""
    story_count: int = 0
    session_count: int = 0


class UserRepository:
    """User repository with story relationship support."""

    def __init__(self):
        self._db = db_manager

    async def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        display_name: Optional[str] = None
    ) -> UserData:
        """
        Create a new user.

        Args:
            username: Unique username
            email: Email address
            password_hash: Hashed password
            display_name: Display name (defaults to username)

        Returns:
            UserData: Created user data
        """
        user_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        await self._db.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, display_name,
                is_active, is_verified, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                email,
                password_hash,
                display_name or username,
                1,
                0,
                now,
                now
            )
        )
        await self._db.commit()

        return UserData(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name or username,
            is_active=True,
            is_verified=False,
            created_at=now,
            updated_at=now,
            last_login_at=None
        )

    async def get_by_id(self, user_id: str) -> Optional[UserData]:
        """
        根据用户ID获取用户

        Args:
            user_id: 用户ID

        Returns:
            UserData 或 None
        """
        row = await self._db.fetchone(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        return self._row_to_user(row) if row else None

    async def get_by_username(self, username: str) -> Optional[UserData]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            UserData 或 None
        """
        row = await self._db.fetchone(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        return self._row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> Optional[UserData]:
        """
        根据邮箱获取用户

        Args:
            email: 邮箱

        Returns:
            UserData 或 None
        """
        row = await self._db.fetchone(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )
        return self._row_to_user(row) if row else None

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        password_hash: Optional[str] = None
    ) -> bool:
        """
        更新用户信息

        Args:
            user_id: 用户ID
            display_name: 显示名称
            avatar_url: 头像URL
            is_active: 是否激活
            is_verified: 是否验证
            password_hash: 新密码哈希

        Returns:
            bool: 是否更新成功
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        now = datetime.now().isoformat()
        updates = ["updated_at = ?"]
        params = [now]

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)

        if avatar_url is not None:
            updates.append("avatar_url = ?")
            params.append(avatar_url)

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if is_verified is not None:
            updates.append("is_verified = ?")
            params.append(1 if is_verified else 0)

        if password_hash is not None:
            updates.append("password_hash = ?")
            params.append(password_hash)

        params.append(user_id)

        await self._db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
            tuple(params)
        )
        await self._db.commit()
        return True

    async def update_last_login(self, user_id: str) -> bool:
        """
        更新最后登录时间

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否更新成功
        """
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE user_id = ?",
            (now, now, user_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_user(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否删除成功
        """
        cursor = await self._db.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_users(
        self,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[UserData]:
        """
        列出用户

        Args:
            is_active: 按激活状态过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[UserData]: 用户列表
        """
        query = "SELECT * FROM users WHERE 1=1"
        params: List = []

        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetchall(query, tuple(params))
        return [self._row_to_user(row) for row in rows]

    async def check_username_exists(self, username: str) -> bool:
        """检查用户名是否存在"""
        row = await self._db.fetchone(
            "SELECT 1 FROM users WHERE username = ?",
            (username,)
        )
        return row is not None

    async def check_email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        row = await self._db.fetchone(
            "SELECT 1 FROM users WHERE email = ?",
            (email,)
        )
        return row is not None

    # =========================================================================
    # User-Story Relationship Methods
    # =========================================================================

    async def get_with_stats(self, user_id: str) -> Optional[UserWithStats]:
        """
        Get user with story and session counts.

        Args:
            user_id: User's unique ID

        Returns:
            UserWithStats or None if user not found
        """
        row = await self._db.fetchone(
            """
            SELECT
                u.*,
                (SELECT COUNT(*) FROM stories WHERE user_id = u.user_id) as story_count,
                (SELECT COUNT(*) FROM sessions WHERE user_id = u.user_id) as session_count
            FROM users u
            WHERE u.user_id = ?
            """,
            (user_id,)
        )

        if not row:
            return None

        user = self._row_to_user(row)
        return UserWithStats(
            **{k: v for k, v in user.__dict__.items()},
            story_count=row.get('story_count', 0),
            session_count=row.get('session_count', 0)
        )

    async def get_user_stories(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get user with their stories (convenience method).

        Args:
            user_id: User's unique ID
            limit: Maximum stories to return
            offset: Pagination offset

        Returns:
            Dict with user info and stories list
        """
        import json

        user = await self.get_by_id(user_id)
        if not user:
            return None

        # Get stories
        stories = await self._db.fetchall(
            """
            SELECT * FROM stories
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        )

        # Count total
        count_row = await self._db.fetchone(
            "SELECT COUNT(*) as total FROM stories WHERE user_id = ?",
            (user_id,)
        )

        return {
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at
            },
            "stories": [self._story_row_to_dict(s) for s in stories],
            "total": count_row['total'] if count_row else 0,
            "limit": limit,
            "offset": offset
        }

    async def get_user_sessions(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get user with their interactive story sessions.

        Args:
            user_id: User's unique ID
            status: Filter by session status ('active', 'completed', etc.)
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            Dict with user info and sessions list
        """
        import json

        user = await self.get_by_id(user_id)
        if not user:
            return None

        # Build query
        query = "SELECT * FROM sessions WHERE user_id = ?"
        params = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        sessions = await self._db.fetchall(query, tuple(params))

        # Count total
        count_query = "SELECT COUNT(*) as total FROM sessions WHERE user_id = ?"
        count_params = [user_id]
        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        count_row = await self._db.fetchone(count_query, tuple(count_params))

        return {
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url
            },
            "sessions": [self._session_row_to_dict(s) for s in sessions],
            "total": count_row['total'] if count_row else 0,
            "limit": limit,
            "offset": offset
        }

    def _row_to_user(self, row: dict) -> UserData:
        """Convert database row to UserData."""
        return UserData(
            user_id=row['user_id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            display_name=row.get('display_name'),
            avatar_url=row.get('avatar_url'),
            is_active=bool(row.get('is_active', 1)),
            is_verified=bool(row.get('is_verified', 0)),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_login_at=row.get('last_login_at')
        )

    def _story_row_to_dict(self, row: dict) -> Dict[str, Any]:
        """Convert story row to dict (simplified for user listing)."""
        import json
        return {
            "story_id": row['story_id'],
            "child_id": row['child_id'],
            "age_group": row['age_group'],
            "story_preview": row['story_text'][:200] + "..." if len(row['story_text']) > 200 else row['story_text'],
            "word_count": row['word_count'],
            "themes": json.loads(row.get('themes') or '[]'),
            "image_url": row.get('image_url'),
            "audio_url": row.get('audio_url'),
            "created_at": row['created_at']
        }

    def _session_row_to_dict(self, row: dict) -> Dict[str, Any]:
        """Convert session row to dict (simplified for user listing)."""
        import json
        return {
            "session_id": row['session_id'],
            "story_title": row['story_title'],
            "child_id": row['child_id'],
            "age_group": row['age_group'],
            "theme": row.get('theme'),
            "current_segment": row['current_segment'],
            "total_segments": row['total_segments'],
            "status": row['status'],
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }


# Global user repository instance
user_repo = UserRepository()
