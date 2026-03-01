"""
API Routes Package

所有 API 路由定义
"""

from . import image_to_story, interactive_story, audio, video, users, news_to_kids, artifacts, admin_artifacts, library

__all__ = [
    "image_to_story",
    "interactive_story",
    "audio",
    "video",
    "users",
    "news_to_kids",
    "artifacts",
    "admin_artifacts",
    "library",
]
