"""
Database Package

Database module with adapter pattern: SQLite (dev) or PostgreSQL (prod).
"""

from .adapter import CursorResult, DatabaseAdapter, create_adapter
from .connection import DatabaseManager, db_manager
from .story_repository import StoryRepository, story_repo
from .session_repository import SessionRepository, session_repo
from .user_repository import UserRepository, user_repo, UserData
from .preference_repository import PreferenceRepository, preference_repo
from .character_repository import CharacterRepository, character_repo
from .voice_repository import VoiceRepository, voice_repo
from .favorite_repository import FavoriteRepository, favorite_repo
from .subscription_repository import (
    SubscriptionRepository,
    subscription_repo,
    DuplicateSubscriptionError,
    MaxSubscriptionsExceededError,
)
from .usage_repository import UsageRepository, usage_repo
from .referral_repository import ReferralRepository, referral_repo
from .vector_repository import VectorRepository, vector_repo
from .agent_repository import AgentRepository, AgentData, agent_repo
from .agent_chat_repository import (
    AgentChatRepository,
    AgentChatSession,
    AgentChatMessage,
    agent_chat_repo,
)
from .group_repository import (
    GroupRepository,
    group_repo,
    GroupData,
    MembershipData,
)
from .hub_post_repository import (
    HubPostRepository,
    hub_post_repo,
    HubPostData,
)
from .hub_reaction_repository import (
    HubReactionRepository,
    hub_reaction_repo,
    ReactionData,
)
from .achievement_repository import (
    AchievementRepository,
    AchievementData,
    achievement_repo,
)

__all__ = [
    "CursorResult",
    "DatabaseAdapter",
    "create_adapter",
    "DatabaseManager",
    "db_manager",
    "StoryRepository",
    "story_repo",
    "SessionRepository",
    "session_repo",
    "UserRepository",
    "user_repo",
    "UserData",
    "PreferenceRepository",
    "preference_repo",
    "CharacterRepository",
    "character_repo",
    "VoiceRepository",
    "voice_repo",
    "FavoriteRepository",
    "favorite_repo",
    "SubscriptionRepository",
    "subscription_repo",
    "DuplicateSubscriptionError",
    "MaxSubscriptionsExceededError",
    "UsageRepository",
    "usage_repo",
    "ReferralRepository",
    "referral_repo",
    "VectorRepository",
    "vector_repo",
    "AgentRepository",
    "AgentData",
    "agent_repo",
    "AgentChatRepository",
    "AgentChatSession",
    "AgentChatMessage",
    "agent_chat_repo",
    "GroupRepository",
    "group_repo",
    "GroupData",
    "MembershipData",
    "HubPostRepository",
    "hub_post_repo",
    "HubPostData",
    "HubReactionRepository",
    "hub_reaction_repo",
    "ReactionData",
    "AchievementRepository",
    "AchievementData",
    "achievement_repo",
]
