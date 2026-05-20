"""
API Routes Package

Contains route modules for each feature domain.
"""

from . import (
    image_to_story,
    interactive_story,
    audio,
    video,
    voice,
    users,
    kids_daily,
    inspiration_daily,
    subscriptions,
    artifacts,
    admin_artifacts,
    achievements,
    library,
    memory,
    usage,
)

__all__ = [
    "image_to_story",
    "interactive_story",
    "audio",
    "video",
    "voice",
    "users",
    "kids_daily",
    "inspiration_daily",
    "subscriptions",
    "artifacts",
    "admin_artifacts",
    "achievements",
    "library",
    "memory",
    "usage",
]
