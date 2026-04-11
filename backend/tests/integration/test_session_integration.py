"""
Session Integration Tests

Session manager integration tests
"""

import pytest
from datetime import datetime, timedelta

from backend.src.services import SessionManager


@pytest.fixture
def session_manager():
    """Create a test session manager"""
    manager = SessionManager(sessions_dir="./data/test_sessions")
    yield manager

    # Clean up test sessions
    import shutil
    from pathlib import Path
    test_dir = Path("./data/test_sessions")
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestSessionManager:
    """Session manager tests"""

    def test_create_session(self, session_manager):
        """Test creating a session"""
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals", "adventure"],
            theme="Forest exploration",
            voice="fable",
            enable_audio=True,
            total_segments=5
        )

        assert session.session_id is not None
        assert session.child_id == "test_child_001"
        assert session.story_title == "Test story"
        assert session.age_group == "6-8"
        assert session.interests == ["animals", "adventure"]
        assert session.status == "active"
        assert session.current_segment == 0
        assert session.total_segments == 5
        assert len(session.choice_history) == 0

    def test_get_session(self, session_manager):
        """Test getting a session"""
        # Create session
        created_session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Get session
        retrieved_session = session_manager.get_session(created_session.session_id)

        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.child_id == created_session.child_id
        assert retrieved_session.story_title == created_session.story_title

    def test_get_nonexistent_session(self, session_manager):
        """Test getting a nonexistent session"""
        session = session_manager.get_session("nonexistent_id")
        assert session is None

    def test_update_session(self, session_manager):
        """Test updating a session"""
        # Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Update session
        segment = {
            "segment_id": 1,
            "text": "Story segment one",
            "choices": []
        }

        success = session_manager.update_session(
            session_id=session.session_id,
            segment=segment,
            choice_id="choice_0_a"
        )

        assert success is True

        # Verify update
        updated_session = session_manager.get_session(session.session_id)
        assert len(updated_session.segments) == 1
        assert updated_session.current_segment == 1
        assert "choice_0_a" in updated_session.choice_history

    def test_delete_session(self, session_manager):
        """Test deleting a session"""
        # Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Delete session
        success = session_manager.delete_session(session.session_id)
        assert success is True

        # Verify deletion
        retrieved_session = session_manager.get_session(session.session_id)
        assert retrieved_session is None

    def test_list_sessions(self, session_manager):
        """Test listing sessions"""
        # Create multiple sessions
        for i in range(3):
            session_manager.create_session(
                child_id=f"test_child_{i:03d}",
                story_title=f"Story {i}",
                age_group="6-8",
                interests=["animals"]
            )

        # List all sessions
        all_sessions = session_manager.list_sessions()
        assert len(all_sessions) == 3

        # Filter by child ID
        child_sessions = session_manager.list_sessions(child_id="test_child_001")
        assert len(child_sessions) == 1
        assert child_sessions[0].child_id == "test_child_001"

    def test_list_sessions_by_status(self, session_manager):
        """Test listing sessions by status"""
        # Create active session
        active_session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Active story",
            age_group="6-8",
            interests=["animals"]
        )

        # Create completed session
        completed_session = session_manager.create_session(
            child_id="test_child_002",
            story_title="Completed story",
            age_group="6-8",
            interests=["adventure"]
        )

        session_manager.update_session(
            session_id=completed_session.session_id,
            status="completed"
        )

        # Filter by status
        active_sessions = session_manager.list_sessions(status="active")
        completed_sessions = session_manager.list_sessions(status="completed")

        assert len(active_sessions) == 1
        assert len(completed_sessions) == 1
        assert active_sessions[0].status == "active"
        assert completed_sessions[0].status == "completed"

    def test_session_expiry(self, session_manager):
        """Test session expiry"""
        # Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Manually set expiry time to the past
        from pathlib import Path
        import json

        session_path = session_manager._get_session_path(session.session_id)
        with open(session_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Set to expired 1 hour ago
        past_time = datetime.now() - timedelta(hours=1)
        data['expires_at'] = past_time.isoformat()

        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Get session (should be automatically marked as expired)
        expired_session = session_manager.get_session(session.session_id)

        assert expired_session.status == "expired"

    def test_cleanup_expired_sessions(self, session_manager):
        """Test cleaning up expired sessions"""
        # Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Set to expired 8 days ago
        from pathlib import Path
        import json

        session_path = session_manager._get_session_path(session.session_id)
        with open(session_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        old_time = datetime.now() - timedelta(days=8)
        data['expires_at'] = old_time.isoformat()

        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Clean up expired sessions
        cleaned = session_manager.cleanup_expired_sessions()

        assert cleaned == 1

        # Verify session has been deleted
        retrieved_session = session_manager.get_session(session.session_id)
        assert retrieved_session is None

    def test_update_educational_summary(self, session_manager):
        """Test updating educational summary"""
        # Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals"]
        )

        # Update educational summary
        edu_summary = {
            "themes": ["courage", "friendship"],
            "concepts": ["decision-making", "cooperation"],
            "moral": "Unity is strength"
        }

        success = session_manager.update_session(
            session_id=session.session_id,
            educational_summary=edu_summary
        )

        assert success is True

        # Verify update
        updated_session = session_manager.get_session(session.session_id)
        assert updated_session.educational_summary is not None
        assert updated_session.educational_summary["themes"] == ["courage", "friendship"]
        assert updated_session.educational_summary["moral"] == "Unity is strength"


class TestSessionLifecycle:
    """Session lifecycle tests"""

    def test_complete_session_lifecycle(self, session_manager):
        """Test complete session lifecycle"""
        # 1. Create session
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="Full story",
            age_group="6-8",
            interests=["animals", "adventure"],
            total_segments=3
        )

        assert session.status == "active"
        assert session.current_segment == 0

        # 2. Add first segment
        segment_1 = {
            "segment_id": 1,
            "text": "Story begins...",
            "choices": [
                {"choice_id": "c1_a", "text": "Option A", "emoji": "🅰️"},
                {"choice_id": "c1_b", "text": "Option B", "emoji": "🅱️"}
            ]
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=segment_1,
            choice_id="c1_a"
        )

        # 3. Add second segment
        segment_2 = {
            "segment_id": 2,
            "text": "Story continues...",
            "choices": [
                {"choice_id": "c2_a", "text": "Option A", "emoji": "🅰️"}
            ]
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=segment_2,
            choice_id="c2_a"
        )

        # 4. Add ending
        ending = {
            "segment_id": 3,
            "text": "Story ends!",
            "choices": [],
            "is_ending": True
        }

        edu_summary = {
            "themes": ["courage"],
            "concepts": ["decision-making"],
            "moral": "Bravely face challenges"
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=ending,
            status="completed",
            educational_summary=edu_summary
        )

        # 5. Verify final state
        final_session = session_manager.get_session(session.session_id)

        assert final_session.status == "completed"
        assert final_session.current_segment == 3
        assert len(final_session.segments) == 3
        assert len(final_session.choice_history) == 2
        assert final_session.educational_summary is not None
