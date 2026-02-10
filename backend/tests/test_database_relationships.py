"""
Database Relationship Tests

Tests for user-story and user-session relationships.
Verifies:
- User can have multiple stories
- User can have multiple sessions
- Story can be queried with user info
- Proper foreign key relationships
"""

import asyncio
import os
import sys
import pytest
import pytest_asyncio
import uuid
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.user_repository import UserRepository, UserData
from src.services.database.story_repository import StoryRepository
from src.services.database.session_repository import SessionRepository


@pytest_asyncio.fixture
async def repos():
    """Create all repositories with shared in-memory test database."""
    # Create in-memory database
    db = DatabaseManager(':memory:')
    await db.connect()
    await init_schema(db)

    # Create repositories with shared database
    user_repo = UserRepository()
    user_repo._db = db

    story_repo = StoryRepository()
    story_repo._db = db

    session_repo = SessionRepository()
    session_repo._db = db

    yield {
        'db': db,
        'user': user_repo,
        'story': story_repo,
        'session': session_repo
    }

    # Cleanup
    await db.disconnect()


class TestUserStoryRelationship:
    """Tests for user-story relationships."""

    @pytest.mark.asyncio
    async def test_create_story_with_user_id(self, repos):
        """Test creating a story associated with a user."""
        user_repo = repos['user']
        story_repo = repos['story']

        # Create test user
        test_user = await user_repo.create_user(
            username='testuser',
            email='test@example.com',
            password_hash='hashed_password_123',
            display_name='Test User'
        )

        story_data = {
            'story_id': str(uuid.uuid4()),
            'user_id': test_user.user_id,
            'child_id': 'child_001',
            'age_group': '5-7',
            'story': {
                'text': 'Once upon a time, there was a brave little rabbit...',
                'word_count': 50
            },
            'educational_value': {
                'themes': ['courage', 'friendship'],
                'concepts': ['bravery'],
                'moral': 'Be brave and kind'
            },
            'characters': [{'name': 'Rabbit', 'role': 'hero'}],
            'safety_score': 0.95
        }

        story_id = await story_repo.create(story_data)
        assert story_id == story_data['story_id']

        # Verify story has user_id
        story = await story_repo.get_by_id(story_id)
        assert story is not None
        assert story['user_id'] == test_user.user_id

    @pytest.mark.asyncio
    async def test_list_stories_by_user(self, repos):
        """Test querying all stories for a specific user."""
        user_repo = repos['user']
        story_repo = repos['story']

        test_user = await user_repo.create_user(
            username='testuser2',
            email='test2@example.com',
            password_hash='hashed_password_123',
            display_name='Test User 2'
        )

        # Create multiple stories for the user
        for i in range(3):
            await story_repo.create({
                'story_id': str(uuid.uuid4()),
                'user_id': test_user.user_id,
                'child_id': f'child_{i}',
                'age_group': '5-7',
                'story': {'text': f'Story {i}', 'word_count': 10},
                'educational_value': {'themes': [], 'concepts': [], 'moral': ''},
                'characters': []
            })

        # Create a story for a different user (no user_id)
        await story_repo.create({
            'story_id': str(uuid.uuid4()),
            'user_id': None,
            'child_id': 'other_child',
            'age_group': '5-7',
            'story': {'text': 'Other story', 'word_count': 5},
            'educational_value': {'themes': [], 'concepts': [], 'moral': ''},
            'characters': []
        })

        # Query stories by user
        user_stories = await story_repo.list_by_user(test_user.user_id)
        assert len(user_stories) == 3

        # Verify all stories belong to the user
        for story in user_stories:
            assert story['user_id'] == test_user.user_id

    @pytest.mark.asyncio
    async def test_count_stories_by_user(self, repos):
        """Test counting stories for a user."""
        user_repo = repos['user']
        story_repo = repos['story']

        test_user = await user_repo.create_user(
            username='testuser3',
            email='test3@example.com',
            password_hash='hashed_password_123'
        )

        # Initially no stories
        count = await story_repo.count_by_user(test_user.user_id)
        assert count == 0

        # Add stories
        for i in range(5):
            await story_repo.create({
                'story_id': str(uuid.uuid4()),
                'user_id': test_user.user_id,
                'child_id': 'child_001',
                'age_group': '5-7',
                'story': {'text': f'Story {i}', 'word_count': 10},
                'educational_value': {'themes': [], 'concepts': [], 'moral': ''},
                'characters': []
            })

        count = await story_repo.count_by_user(test_user.user_id)
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_story_with_user_info(self, repos):
        """Test getting a story with author information."""
        user_repo = repos['user']
        story_repo = repos['story']

        test_user = await user_repo.create_user(
            username='testuser4',
            email='test4@example.com',
            password_hash='hashed_password_123',
            display_name='Test User 4'
        )

        story_id = str(uuid.uuid4())
        await story_repo.create({
            'story_id': story_id,
            'user_id': test_user.user_id,
            'child_id': 'child_001',
            'age_group': '5-7',
            'story': {'text': 'A wonderful story', 'word_count': 20},
            'educational_value': {'themes': ['love'], 'concepts': [], 'moral': 'Love conquers all'},
            'characters': []
        })

        # Get story with user info
        story = await story_repo.get_with_user(story_id)
        assert story is not None
        assert story['author'] is not None
        assert story['author']['username'] == 'testuser4'
        assert story['author']['display_name'] == 'Test User 4'

    @pytest.mark.asyncio
    async def test_story_without_user(self, repos):
        """Test getting a story without a user (anonymous)."""
        story_repo = repos['story']

        story_id = str(uuid.uuid4())
        await story_repo.create({
            'story_id': story_id,
            'user_id': None,
            'child_id': 'anonymous_child',
            'age_group': '3-5',
            'story': {'text': 'Anonymous story', 'word_count': 10},
            'educational_value': {'themes': [], 'concepts': [], 'moral': ''},
            'characters': []
        })

        story = await story_repo.get_with_user(story_id)
        assert story is not None
        assert story['author'] is None


class TestUserSessionRelationship:
    """Tests for user-session relationships."""

    @pytest.mark.asyncio
    async def test_create_session_with_user_id(self, repos):
        """Test creating a session associated with a user."""
        user_repo = repos['user']
        session_repo = repos['session']

        test_user = await user_repo.create_user(
            username='session_user1',
            email='session1@example.com',
            password_hash='hashed_password_123'
        )

        session = await session_repo.create_session(
            child_id='child_001',
            story_title='The Magic Forest',
            age_group='5-7',
            interests=['animals', 'magic'],
            theme='adventure',
            user_id=test_user.user_id
        )

        assert session is not None
        assert session.user_id == test_user.user_id
        assert session.story_title == 'The Magic Forest'

    @pytest.mark.asyncio
    async def test_list_sessions_by_user(self, repos):
        """Test querying all sessions for a specific user."""
        user_repo = repos['user']
        session_repo = repos['session']

        test_user = await user_repo.create_user(
            username='session_user2',
            email='session2@example.com',
            password_hash='hashed_password_123'
        )

        # Create multiple sessions for the user
        for i in range(3):
            await session_repo.create_session(
                child_id=f'child_{i}',
                story_title=f'Story {i}',
                age_group='5-7',
                interests=['fun'],
                user_id=test_user.user_id
            )

        # Create a session without user
        await session_repo.create_session(
            child_id='other_child',
            story_title='Other Story',
            age_group='5-7',
            interests=['fun'],
            user_id=None
        )

        # Query sessions by user
        user_sessions = await session_repo.list_by_user(test_user.user_id)
        assert len(user_sessions) == 3

        for session in user_sessions:
            assert session.user_id == test_user.user_id

    @pytest.mark.asyncio
    async def test_count_sessions_by_user(self, repos):
        """Test counting sessions for a user."""
        user_repo = repos['user']
        session_repo = repos['session']

        test_user = await user_repo.create_user(
            username='session_user3',
            email='session3@example.com',
            password_hash='hashed_password_123'
        )

        count = await session_repo.count_by_user(test_user.user_id)
        assert count == 0

        for i in range(4):
            await session_repo.create_session(
                child_id='child_001',
                story_title=f'Story {i}',
                age_group='5-7',
                interests=['fun'],
                user_id=test_user.user_id
            )

        count = await session_repo.count_by_user(test_user.user_id)
        assert count == 4


class TestUserWithStats:
    """Tests for user statistics."""

    @pytest.mark.asyncio
    async def test_get_user_with_stats(self, repos):
        """Test getting user with story and session counts."""
        user_repo = repos['user']
        story_repo = repos['story']
        session_repo = repos['session']

        test_user = await user_repo.create_user(
            username='stats_user1',
            email='stats1@example.com',
            password_hash='hashed_password_123'
        )

        # Create stories
        for i in range(3):
            await story_repo.create({
                'story_id': str(uuid.uuid4()),
                'user_id': test_user.user_id,
                'child_id': 'child_001',
                'age_group': '5-7',
                'story': {'text': f'Story {i}', 'word_count': 10},
                'educational_value': {'themes': [], 'concepts': [], 'moral': ''},
                'characters': []
            })

        # Create sessions
        for i in range(2):
            await session_repo.create_session(
                child_id='child_001',
                story_title=f'Session {i}',
                age_group='5-7',
                interests=['fun'],
                user_id=test_user.user_id
            )

        # Get user with stats
        user_with_stats = await user_repo.get_with_stats(test_user.user_id)
        assert user_with_stats is not None
        assert user_with_stats.story_count == 3
        assert user_with_stats.session_count == 2
        assert user_with_stats.username == 'stats_user1'

    @pytest.mark.asyncio
    async def test_get_user_stories_with_pagination(self, repos):
        """Test getting user stories with pagination."""
        user_repo = repos['user']
        story_repo = repos['story']

        test_user = await user_repo.create_user(
            username='pagination_user',
            email='pagination@example.com',
            password_hash='hashed_password_123'
        )

        # Create 10 stories
        for i in range(10):
            await story_repo.create({
                'story_id': str(uuid.uuid4()),
                'user_id': test_user.user_id,
                'child_id': 'child_001',
                'age_group': '5-7',
                'story': {'text': f'Story content {i}', 'word_count': 10 + i},
                'educational_value': {'themes': [f'theme_{i}'], 'concepts': [], 'moral': ''},
                'characters': []
            })

        # Get first page
        result = await user_repo.get_user_stories(test_user.user_id, limit=5, offset=0)
        assert result is not None
        assert len(result['stories']) == 5
        assert result['total'] == 10
        assert result['user']['username'] == 'pagination_user'

        # Get second page
        result2 = await user_repo.get_user_stories(test_user.user_id, limit=5, offset=5)
        assert len(result2['stories']) == 5


class TestDatabaseMigration:
    """Tests for database schema migration."""

    @pytest.mark.asyncio
    async def test_schema_has_user_id_columns(self, repos):
        """Verify user_id columns exist in stories and sessions tables."""
        db = repos['db']

        # Check stories table
        stories_info = await db.fetchall("PRAGMA table_info(stories)")
        stories_columns = [col['name'] for col in stories_info]
        assert 'user_id' in stories_columns

        # Check sessions table
        sessions_info = await db.fetchall("PRAGMA table_info(sessions)")
        sessions_columns = [col['name'] for col in sessions_info]
        assert 'user_id' in sessions_columns

    @pytest.mark.asyncio
    async def test_indexes_exist(self, repos):
        """Verify indexes are created for user_id columns."""
        db = repos['db']

        indexes = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%user_id%'"
        )
        index_names = [idx['name'] for idx in indexes]

        assert 'idx_stories_user_id' in index_names
        assert 'idx_sessions_user_id' in index_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
