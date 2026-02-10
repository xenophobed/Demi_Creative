"""
Services Package

业务逻辑和服务层
"""

# Legacy session manager (deprecated, use database.session_repo instead)
from .session_manager import SessionManager, SessionData, session_manager

# Database modules
from .database import (
    DatabaseManager,
    db_manager,
    StoryRepository,
    story_repo,
    SessionRepository,
    session_repo,
    UserRepository,
    user_repo,
    UserData,
)

# User service
from .user_service import UserService, user_service, AuthResult, TokenData

__all__ = [
    # Legacy (deprecated)
    "SessionManager",
    "SessionData",
    "session_manager",
    # Database
    "DatabaseManager",
    "db_manager",
    "StoryRepository",
    "story_repo",
    "SessionRepository",
    "session_repo",
    "UserRepository",
    "user_repo",
    "UserData",
    # User service
    "UserService",
    "user_service",
    "AuthResult",
    "TokenData",
]
