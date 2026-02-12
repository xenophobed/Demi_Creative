"""
Story Repository

CRUD operations for story data with user relationship support.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from .connection import db_manager


class StoryRepository:
    """Story repository with user relationship support."""

    def __init__(self):
        self._db = db_manager

    async def create(self, story_data: Dict[str, Any]) -> str:
        """
        Create a new story.

        Args:
            story_data: Story data including optional user_id

        Returns:
            str: Story ID
        """
        story_id = story_data['story_id']
        now = datetime.now().isoformat()

        # Extract story content
        story_content = story_data.get('story', {})
        educational_value = story_data.get('educational_value', {})
        characters = story_data.get('characters', [])

        await self._db.execute(
            """
            INSERT INTO stories (
                story_id, user_id, child_id, age_group, story_text, word_count,
                themes, concepts, moral, characters, analysis,
                safety_score, image_path, image_url, audio_url,
                story_type, created_at, stored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                story_id,
                story_data.get('user_id'),  # New: user_id foreign key
                story_data.get('child_id', ''),
                story_data.get('age_group', ''),
                story_content.get('text', ''),
                story_content.get('word_count', 0),
                json.dumps(educational_value.get('themes', []), ensure_ascii=False),
                json.dumps(educational_value.get('concepts', []), ensure_ascii=False),
                educational_value.get('moral'),
                json.dumps(characters, ensure_ascii=False),
                json.dumps(story_data.get('analysis', {}), ensure_ascii=False),
                story_data.get('safety_score', 0.9),
                story_data.get('image_path'),
                story_data.get('image_url'),
                story_data.get('audio_url'),
                story_data.get('story_type', 'image_to_story'),
                story_data.get('created_at', now),
                now
            )
        )
        await self._db.commit()

        return story_id

    async def get_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a story by ID

        Args:
            story_id: Story ID

        Returns:
            Optional[Dict]: Story data or None
        """
        row = await self._db.fetchone(
            "SELECT * FROM stories WHERE story_id = ?",
            (story_id,)
        )

        if not row:
            return None

        return self._row_to_dict(row)

    async def list_by_child(self, child_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get a list of stories for a specific child

        Args:
            child_id: Child ID
            limit: Maximum number of results to return

        Returns:
            List[Dict]: List of stories
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM stories
            WHERE child_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (child_id, limit)
        )

        return [self._row_to_dict(row) for row in rows]

    async def list_by_user_and_child(
        self,
        user_id: str,
        child_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get stories scoped to a specific user AND child profile.

        Args:
            user_id: Owner's user ID
            child_id: Child profile ID
            limit: Maximum number of stories to return

        Returns:
            List[Dict]: Stories matching both user_id and child_id
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM stories
            WHERE user_id = ? AND child_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, child_id, limit),
        )
        return [self._row_to_dict(row) for row in rows]

    async def list_all(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get all stories.

        Args:
            limit: Maximum number of stories to return

        Returns:
            List[Dict]: List of stories
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM stories
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [self._row_to_dict(row) for row in rows]

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all stories belonging to a specific user.

        Args:
            user_id: User's unique ID
            limit: Maximum number of stories to return
            offset: Number of stories to skip (for pagination)

        Returns:
            List[Dict]: List of stories owned by the user
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM stories
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        )

        return [self._row_to_dict(row) for row in rows]

    async def count_by_user(self, user_id: str) -> int:
        """
        Count total stories for a user.

        Args:
            user_id: User's unique ID

        Returns:
            int: Total number of stories
        """
        row = await self._db.fetchone(
            "SELECT COUNT(*) as count FROM stories WHERE user_id = ?",
            (user_id,)
        )
        return row['count'] if row else 0

    async def get_with_user(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a story with its author's information (JOIN query).

        Args:
            story_id: Story's unique ID

        Returns:
            Optional[Dict]: Story with user info, or None if not found
        """
        row = await self._db.fetchone(
            """
            SELECT
                s.*,
                u.username as author_username,
                u.display_name as author_display_name,
                u.avatar_url as author_avatar_url
            FROM stories s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.story_id = ?
            """,
            (story_id,)
        )

        if not row:
            return None

        result = self._row_to_dict(dict(row))
        # Add author information
        result['author'] = {
            'username': row.get('author_username'),
            'display_name': row.get('author_display_name'),
            'avatar_url': row.get('author_avatar_url')
        } if row.get('author_username') else None

        return result

    async def update_user_id(self, story_id: str, user_id: str) -> bool:
        """
        Associate a story with a user (for migration or ownership transfer).

        Args:
            story_id: Story's unique ID
            user_id: User's unique ID

        Returns:
            bool: True if updated successfully
        """
        cursor = await self._db.execute(
            "UPDATE stories SET user_id = ? WHERE story_id = ?",
            (user_id, story_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete(self, story_id: str) -> bool:
        """
        Delete a story.

        Args:
            story_id: Story's unique ID

        Returns:
            bool: True if deleted successfully
        """
        cursor = await self._db.execute(
            "DELETE FROM stories WHERE story_id = ?",
            (story_id,)
        )
        await self._db.commit()

        return cursor.rowcount > 0

    async def delete_by_user(self, user_id: str) -> int:
        """
        Delete all stories belonging to a user.

        Args:
            user_id: User's unique ID

        Returns:
            int: Number of stories deleted
        """
        cursor = await self._db.execute(
            "DELETE FROM stories WHERE user_id = ?",
            (user_id,)
        )
        await self._db.commit()
        return cursor.rowcount

    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert database row to API response format.

        Args:
            row: Database row dictionary

        Returns:
            Dict: Formatted story data
        """
        # Parse JSON fields
        themes = json.loads(row.get('themes') or '[]')
        concepts = json.loads(row.get('concepts') or '[]')
        characters = json.loads(row.get('characters') or '[]')
        analysis = json.loads(row.get('analysis') or '{}')

        return {
            "story_id": row['story_id'],
            "user_id": row.get('user_id'),  # Owner's user ID
            "child_id": row['child_id'],
            "age_group": row['age_group'],
            "story": {
                "text": row['story_text'],
                "word_count": row['word_count'],
                "age_adapted": True
            },
            "image_url": row.get('image_url'),
            "image_path": row.get('image_path'),
            "audio_url": row.get('audio_url'),
            "educational_value": {
                "themes": themes,
                "concepts": concepts,
                "moral": row.get('moral')
            },
            "characters": characters,
            "analysis": analysis,
            "story_type": row.get('story_type', 'image_to_story'),
            "safety_score": row.get('safety_score', 0.9),
            "created_at": row['created_at'],
            "stored_at": row['stored_at']
        }


# Global story repository instance
story_repo = StoryRepository()
