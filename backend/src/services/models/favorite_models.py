"""
Favorite Domain Models

Pydantic v2 models for the favorites/bookmarking feature.
Used by the FavoriteRepository and library API layer.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LibraryItemType(str, Enum):
    """Valid content types that can be favorited."""
    ART_STORY = "art-story"
    INTERACTIVE = "interactive"
    NEWS = "news"


class FavoriteCreate(BaseModel):
    """Input model for creating a favorite."""
    model_config = ConfigDict(frozen=True)

    user_id: str = Field(..., description="Authenticated user's ID")
    item_type: LibraryItemType = Field(..., description="Content type")
    item_id: str = Field(..., description="ID of the content item")


class Favorite(BaseModel):
    """Domain model for a favorited item (as stored in the DB)."""
    model_config = ConfigDict(frozen=True)

    id: Optional[int] = Field(None, description="DB row ID")
    user_id: str = Field(..., description="Owner's user ID")
    item_type: LibraryItemType = Field(..., description="Content type")
    item_id: str = Field(..., description="ID of the content item")
    created_at: str = Field(..., description="ISO 8601 timestamp when favorited")
