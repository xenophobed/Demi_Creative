"""
Session Manager

Interactive story session management system using JSON file storage
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict


@dataclass
class SessionData:
    """Session data structure"""
    session_id: str
    child_id: str
    story_title: str
    age_group: str
    interests: List[str]
    theme: Optional[str]
    voice: str
    enable_audio: bool

    # Story progress
    current_segment: int
    total_segments: int
    choice_history: List[str]

    # Story content
    segments: List[Dict[str, Any]]  # Generated segments

    # Metadata
    status: str  # active, completed, expired
    created_at: str
    updated_at: str
    expires_at: str

    # Fields with defaults must come last
    # Audio tracking
    audio_urls: Optional[Dict[int, str]] = None  # segment_id -> audio_url

    # Educational summary (after completion)
    educational_summary: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.audio_urls is None:
            self.audio_urls = {}


class SessionManager:
    """Session manager"""

    def __init__(self, sessions_dir: str = "./data/sessions"):
        """
        Initialize session manager

        Args:
            sessions_dir: Session data storage directory
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Default expiry: 24 hours
        self.default_expiry_hours = 24

    def _get_session_path(self, session_id: str) -> Path:
        """Get session file path"""
        return self.sessions_dir / f"{session_id}.json"

    def create_session(
        self,
        child_id: str,
        story_title: str,
        age_group: str,
        interests: List[str],
        theme: Optional[str] = None,
        voice: str = "fable",
        enable_audio: bool = True,
        total_segments: int = 5
    ) -> SessionData:
        """
        Create new session

        Args:
            child_id: Child ID
            story_title: Story title
            age_group: Age group
            interests: Interest tags
            theme: Story theme
            voice: Voice type
            enable_audio: Whether to generate audio
            total_segments: Expected total segments

        Returns:
            SessionData: Session data
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=self.default_expiry_hours)

        session_data = SessionData(
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
            expires_at=expires_at.isoformat()
        )

        self._save_session(session_data)
        return session_data

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Get session data

        Args:
            session_id: Session ID

        Returns:
            SessionData or None (if not found)
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return None

        try:
            with open(session_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if expired
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now() > expires_at and data['status'] == 'active':
                data['status'] = 'expired'
                self._save_session_dict(session_id, data)

            # Ensure backwards compatibility with audio_urls field
            if 'audio_urls' not in data:
                data['audio_urls'] = {}

            return SessionData(**data)
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None

    def update_session(
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
        Update session data

        Args:
            session_id: Session ID
            segment: New story segment
            choice_id: Selected choice ID
            status: New status
            educational_summary: Educational summary
            audio_url: Audio URL for segment
            segment_id: Segment ID for audio

        Returns:
            bool: Whether update succeeded
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Update segments
        if segment:
            session.segments.append(segment)
            session.current_segment = len(session.segments)

        # Update choice history
        if choice_id:
            session.choice_history.append(choice_id)

        # Update status
        if status:
            session.status = status

        # Update educational summary
        if educational_summary:
            session.educational_summary = educational_summary

        # Update audio URL
        if audio_url and segment_id is not None:
            if session.audio_urls is None:
                session.audio_urls = {}
            session.audio_urls[segment_id] = audio_url

        # Update timestamp
        session.updated_at = datetime.now().isoformat()

        self._save_session(session)
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session

        Args:
            session_id: Session ID

        Returns:
            bool: Whether deletion succeeded
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return False

        try:
            session_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            return False

    def list_sessions(
        self,
        child_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[SessionData]:
        """
        List sessions

        Args:
            child_id: Filter by child ID (optional)
            status: Filter by status (optional)

        Returns:
            List[SessionData]: List of sessions
        """
        sessions = []

        for session_path in self.sessions_dir.glob("*.json"):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Filter conditions
                if child_id and data.get('child_id') != child_id:
                    continue
                if status and data.get('status') != status:
                    continue

                sessions.append(SessionData(**data))
            except Exception as e:
                print(f"Error loading session {session_path.name}: {e}")

        # Sort by update time descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions

        Returns:
            int: Number of cleaned sessions
        """
        cleaned = 0
        now = datetime.now()

        for session_path in self.sessions_dir.glob("*.json"):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                expires_at = datetime.fromisoformat(data['expires_at'])

                # Delete sessions expired for over 7 days
                if now > expires_at + timedelta(days=7):
                    session_path.unlink()
                    cleaned += 1
            except Exception as e:
                print(f"Error processing session {session_path.name}: {e}")

        return cleaned

    def _save_session(self, session: SessionData):
        """Save session data"""
        session_path = self._get_session_path(session.session_id)

        try:
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(session), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")
            raise

    def _save_session_dict(self, session_id: str, data: Dict[str, Any]):
        """Save session data (dict format)"""
        session_path = self._get_session_path(session_id)

        try:
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving session {session_id}: {e}")
            raise


# Global session manager instance
session_manager = SessionManager()
