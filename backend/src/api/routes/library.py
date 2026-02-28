"""
Library API Routes

Unified content library endpoints: browse, search, and favorite management.
Aggregates stories, interactive sessions, and news into a single API.

Implements: #58, #59, #60
"""

import json
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import (
    LibraryItemType,
    LibraryItem,
    LibraryResponse,
    FavoriteRequest,
    FavoriteResponse,
    ErrorResponse,
)
from ..deps import get_current_user
from ...services.user_service import UserData
from ...services.database import story_repo, session_repo, favorite_repo


router = APIRouter(
    prefix="/api/v1/library",
    tags=["Library"]
)


# ============================================================================
# Helpers
# ============================================================================

def _resolve_story_type(story: dict) -> LibraryItemType:
    """Map the story_type DB field to a LibraryItemType."""
    story_type = story.get("story_type", "image_to_story")
    if story_type == "news_to_kids":
        return LibraryItemType.NEWS
    return LibraryItemType.ART_STORY


def _story_to_library_item(story: dict, is_favorited: bool = False) -> LibraryItem:
    """Convert a story dict from StoryRepository to a LibraryItem."""
    story_content = story.get("story", {})
    ed_value = story.get("educational_value", {})
    text = story_content.get("text", "")
    item_type = _resolve_story_type(story)

    # Compute word count from actual text to ensure accuracy (#76)
    word_count = _count_words(text)

    return LibraryItem(
        id=story["story_id"],
        type=item_type,
        title=_extract_title(text),
        preview=text[:150] if text else "",
        image_url=story.get("image_url"),
        audio_url=story.get("audio_url"),
        created_at=story.get("created_at", ""),
        is_favorited=is_favorited,
        safety_score=story.get("safety_score"),
        word_count=word_count,
        themes=ed_value.get("themes", []),
    )


def _session_to_library_item(session, is_favorited: bool = False) -> LibraryItem:
    """Convert a SessionData to a LibraryItem."""
    # Get first segment text as preview
    preview = ""
    if session.segments:
        preview = session.segments[0].get("text", "")[:150]

    total = session.total_segments or 1
    progress = int((session.current_segment / total) * 100)

    return LibraryItem(
        id=session.session_id,
        type=LibraryItemType.INTERACTIVE,
        title=session.story_title,
        preview=preview,
        image_url=None,
        audio_url=None,
        created_at=session.created_at,
        is_favorited=is_favorited,
        progress=progress,
        status=session.status,
    )


def _extract_title(text: str, max_len: int = 35) -> str:
    """Extract a display title from story text (first sentence or truncated)."""
    if not text:
        return "Untitled Story"
    # Take first sentence
    for sep in ["\u3002", ".", "\uff01", "!", "\n"]:
        idx = text.find(sep)
        if 0 < idx < max_len:
            return text[:idx]
    return text[:max_len] + ("..." if len(text) > max_len else "")


# CJK Unicode ranges for word counting
_CJK_RE = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff'
    r'\U00020000-\U0002a6df\U0002a700-\U0002b73f'
    r'\U0002b740-\U0002b81f\U0002b820-\U0002ceaf]'
)


def _count_words(text: str) -> int:
    """Count words, handling both CJK (character = word) and Latin (space-separated)."""
    if not text:
        return 0
    cjk_chars = len(_CJK_RE.findall(text))
    non_cjk = _CJK_RE.sub('', text)
    latin_words = len(non_cjk.split())
    return cjk_chars + latin_words


# ============================================================================
# GET /api/v1/library — Unified library endpoint (#58)
# ============================================================================

@router.get(
    "",
    response_model=LibraryResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Get unified library",
    description="Returns all user content aggregated and sorted by date",
)
async def get_library(
    type: Optional[LibraryItemType] = Query(None, description="Filter by content type"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Unified library endpoint. Aggregates stories, sessions, and news."""
    all_items: List[LibraryItem] = []

    # Fetch stories (includes both art-story and news types)
    if type is None or type in (LibraryItemType.ART_STORY, LibraryItemType.NEWS):
        stories = await story_repo.list_by_user(user.user_id, limit=200, offset=0)

        # Separate favorites lookups by resolved type
        art_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.ART_STORY]
        news_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.NEWS]
        fav_art_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "art-story", art_ids
        ) if art_ids else set()
        fav_news_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "news", news_ids
        ) if news_ids else set()
        fav_story_ids = fav_art_ids | fav_news_ids

        for s in stories:
            item = _story_to_library_item(s, is_favorited=s["story_id"] in fav_story_ids)
            # Apply type filter
            if type is not None and item.type != type:
                continue
            all_items.append(item)

    # Fetch interactive sessions
    if type is None or type == LibraryItemType.INTERACTIVE:
        sessions = await session_repo.list_by_user(user.user_id, limit=200, offset=0)
        session_ids = [s.session_id for s in sessions]
        fav_session_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "interactive", session_ids
        ) if session_ids else set()

        for s in sessions:
            all_items.append(
                _session_to_library_item(s, is_favorited=s.session_id in fav_session_ids)
            )

    # Sort by created_at descending
    all_items.sort(key=lambda x: x.created_at, reverse=True)

    total = len(all_items)
    paginated = all_items[offset:offset + limit]

    return LibraryResponse(
        items=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# GET /api/v1/library/search — Search endpoint (#59)
# ============================================================================

@router.get(
    "/search",
    response_model=LibraryResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
    summary="Search library",
    description="Search across all library content by keyword",
)
async def search_library(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    type: Optional[LibraryItemType] = Query(None, description="Filter by content type"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Search across all library content using text matching."""
    all_items: List[LibraryItem] = []
    query_lower = q.lower()

    # Search stories (includes both art-story and news types)
    if type is None or type in (LibraryItemType.ART_STORY, LibraryItemType.NEWS):
        stories = await story_repo.list_by_user(user.user_id, limit=200, offset=0)

        art_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.ART_STORY]
        news_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.NEWS]
        fav_art = await favorite_repo.get_favorited_ids(
            user.user_id, "art-story", art_ids
        ) if art_ids else set()
        fav_news = await favorite_repo.get_favorited_ids(
            user.user_id, "news", news_ids
        ) if news_ids else set()
        fav_ids = fav_art | fav_news

        for s in stories:
            item = _story_to_library_item(s, is_favorited=s["story_id"] in fav_ids)
            # Apply type filter
            if type is not None and item.type != type:
                continue

            text = s.get("story", {}).get("text", "")
            themes = json.dumps(s.get("educational_value", {}).get("themes", []))
            characters = json.dumps(s.get("characters", []))
            searchable = f"{text} {themes} {characters}".lower()

            if query_lower in searchable:
                all_items.append(item)

    # Search sessions
    if type is None or type == LibraryItemType.INTERACTIVE:
        sessions = await session_repo.list_by_user(user.user_id, limit=200, offset=0)
        session_ids = [s.session_id for s in sessions]
        fav_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "interactive", session_ids
        ) if session_ids else set()

        for s in sessions:
            searchable = f"{s.story_title} {s.theme or ''}".lower()
            if query_lower in searchable:
                all_items.append(
                    _session_to_library_item(s, is_favorited=s.session_id in fav_ids)
                )

    all_items.sort(key=lambda x: x.created_at, reverse=True)

    total = len(all_items)
    paginated = all_items[offset:offset + limit]

    return LibraryResponse(
        items=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# POST /api/v1/library/favorites — Add favorite (#60)
# ============================================================================

@router.post(
    "/favorites",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}},
    summary="Add favorite",
    description="Add an item to favorites (idempotent)",
)
async def add_favorite(
    request: FavoriteRequest,
    user: UserData = Depends(get_current_user),
):
    """Add an item to favorites. Idempotent — adding twice is a no-op."""
    await favorite_repo.add(user.user_id, request.item_type.value, request.item_id)
    return FavoriteResponse(
        status="favorited",
        item_id=request.item_id,
        item_type=request.item_type.value,
    )


# ============================================================================
# DELETE /api/v1/library/favorites — Remove favorite (#60)
# ============================================================================

@router.delete(
    "/favorites",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Remove favorite",
    description="Remove an item from favorites",
)
async def remove_favorite(
    request: FavoriteRequest,
    user: UserData = Depends(get_current_user),
):
    """Remove an item from favorites."""
    removed = await favorite_repo.remove(
        user.user_id, request.item_type.value, request.item_id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )
