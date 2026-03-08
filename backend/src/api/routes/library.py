"""
Library API Routes

Unified content library endpoints: browse, search, and favorite management.
Aggregates stories, interactive sessions, and news into a single API.

Implements: #58, #59, #60, #81, #83, #84
"""

import json
from typing import Optional, List

from ...utils.text import count_words
from ...paths import AUDIO_DIR

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import (
    LibraryItemType,
    LibrarySortOrder,
    LibraryItem,
    LibraryResponse,
    LibraryStatsGroupBy,
    LibraryStatsPeriod,
    LibraryStatsResponse,
    FavoriteRequest,
    FavoriteResponse,
    ErrorResponse,
)
from ..deps import get_current_user
from ...services.user_service import UserData
from ...services.database import story_repo, session_repo, favorite_repo
from ...services.database.artifact_repository import StoryArtifactLinkRepository
from ...services.database.connection import db_manager

# Content safety threshold — items below this score are hidden (#81)
SAFETY_THRESHOLD = 0.85

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
    if story_type == "morning_show":
        return LibraryItemType.MORNING_SHOW
    return LibraryItemType.ART_STORY


def _story_to_library_item(
    story: dict,
    is_favorited: bool = False,
    thumbnail_url: Optional[str] = None,
) -> LibraryItem:
    """Convert a story dict from StoryRepository to a LibraryItem."""
    story_content = story.get("story", {})
    ed_value = story.get("educational_value", {})
    text = story_content.get("text", "")
    item_type = _resolve_story_type(story)

    # Compute word count from actual text to ensure accuracy (#76)
    word_count = count_words(text)

    # Extract news category from analysis metadata (#84)
    analysis = story.get("analysis", {})
    category = analysis.get("category") if item_type in (LibraryItemType.NEWS, LibraryItemType.MORNING_SHOW) else None
    duration_seconds = analysis.get("duration_seconds") if item_type == LibraryItemType.MORNING_SHOW else None
    is_new = analysis.get("is_new") if item_type == LibraryItemType.MORNING_SHOW else None
    title = analysis.get("kid_title") if item_type == LibraryItemType.MORNING_SHOW else _extract_title(text)

    audio_url = story.get("audio_url")
    if isinstance(audio_url, str) and audio_url.startswith("/data/audio/"):
        filename = audio_url[len("/data/audio/"):]
        file_path = AUDIO_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            audio_url = None

    return LibraryItem(
        id=story["story_id"],
        type=item_type,
        title=title or _extract_title(text),
        preview=text[:150] if text else "",
        image_url=story.get("image_url"),
        thumbnail_url=thumbnail_url or story.get("image_url"),
        audio_url=audio_url,
        created_at=story.get("created_at", ""),
        is_favorited=is_favorited,
        safety_score=story.get("safety_score"),
        word_count=word_count,
        themes=ed_value.get("themes", []),
        category=category,
        duration_seconds=duration_seconds,
        is_new=is_new,
    )


def _is_safe(item: LibraryItem) -> bool:
    """Return True if the item passes safety threshold (#81)."""
    if item.safety_score is None:
        return True  # No score = not yet checked, allow through
    return item.safety_score >= SAFETY_THRESHOLD


def _session_to_library_item(session, is_favorited: bool = False) -> LibraryItem:
    """Convert a SessionData to a LibraryItem."""
    # Get first segment text as preview
    preview = ""
    if session.segments:
        preview = session.segments[0].get("text", "")[:150]

    total = session.total_segments or 1
    progress = int((session.current_segment / total) * 100)
    progress = max(0, min(100, progress))

    # Enrich interactive cards with metadata similar to art stories
    full_text = " ".join(
        segment.get("text", "") for segment in session.segments if segment.get("text")
    ).strip()
    word_count = count_words(full_text) if full_text else None
    themes = [session.theme] if session.theme else []

    return LibraryItem(
        id=session.session_id,
        type=LibraryItemType.INTERACTIVE,
        title=session.story_title,
        preview=preview,
        image_url=None,
        audio_url=None,
        created_at=session.created_at,
        is_favorited=is_favorited,
        word_count=word_count,
        themes=themes,
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


async def _resolve_thumbnail(story_id: str) -> Optional[str]:
    """Try to get a cover artifact URL for a story, return None on failure."""
    try:
        link_repo = StoryArtifactLinkRepository(db_manager)
        artifact = await link_repo.get_canonical_artifact(story_id, "cover")
        if artifact and artifact.artifact_url:
            return artifact.artifact_url
    except Exception:
        pass
    return None


def _sort_items(items: List[LibraryItem], sort: LibrarySortOrder) -> None:
    """Sort items in-place according to the requested order (#83)."""
    if sort == LibrarySortOrder.OLDEST:
        items.sort(key=lambda x: x.created_at)
    elif sort == LibrarySortOrder.WORD_COUNT:
        items.sort(key=lambda x: x.word_count or 0, reverse=True)
    elif sort == LibrarySortOrder.FAVORITE_FIRST:
        # Keep newest-first ordering inside each favorite group
        items.sort(key=lambda x: x.created_at, reverse=True)
        items.sort(key=lambda x: x.is_favorited, reverse=True)
    else:  # NEWEST (default)
        items.sort(key=lambda x: x.created_at, reverse=True)


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
    sort: LibrarySortOrder = Query(LibrarySortOrder.NEWEST, description="Sort order"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Unified library endpoint. Aggregates stories, sessions, and news."""
    all_items: List[LibraryItem] = []

    # Fetch stories (includes both art-story and news types)
    if type is None or type in (LibraryItemType.ART_STORY, LibraryItemType.NEWS, LibraryItemType.MORNING_SHOW):
        stories = await story_repo.list_by_user(user.user_id, limit=200, offset=0)

        # Separate favorites lookups by resolved type
        art_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.ART_STORY]
        news_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.NEWS]
        morning_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.MORNING_SHOW]
        fav_art_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "art-story", art_ids
        ) if art_ids else set()
        fav_news_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "news", news_ids
        ) if news_ids else set()
        fav_morning_ids = await favorite_repo.get_favorited_ids(
            user.user_id, "morning-show", morning_ids
        ) if morning_ids else set()
        fav_story_ids = fav_art_ids | fav_news_ids | fav_morning_ids

        for s in stories:
            thumb = await _resolve_thumbnail(s["story_id"])
            item = _story_to_library_item(
                s, is_favorited=s["story_id"] in fav_story_ids, thumbnail_url=thumb
            )
            # Apply type filter
            if type is not None and item.type != type:
                continue
            # Apply safety filter (#81)
            if not _is_safe(item):
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

    # Sort (#83)
    _sort_items(all_items, sort)

    total = len(all_items)
    paginated = all_items[offset:offset + limit]

    return LibraryResponse(
        items=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# GET /api/v1/library/stats — Creation stats endpoint (#133)
# ============================================================================

@router.get(
    "/stats",
    response_model=LibraryStatsResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Get library creation stats",
    description="Returns creation counts grouped by week or month",
)
async def get_library_stats(
    group_by: LibraryStatsGroupBy = Query(
        LibraryStatsGroupBy.WEEK, description="Group by week or month"
    ),
    user: UserData = Depends(get_current_user),
):
    """Return aggregate creation counts per time period (#133).

    Queries both stories and sessions tables, groups by the requested
    period, and returns only aggregate counts — no personal data.
    """
    if group_by == LibraryStatsGroupBy.MONTH:
        # SQLite strftime: %Y-%m → "2026-03"
        fmt = "%Y-%m"
    else:
        # ISO week: %Y-W%W → "2026-W10"
        fmt = "%Y-W%W"

    query = f"""
        SELECT period, SUM(cnt) AS count FROM (
            SELECT strftime('{fmt}', created_at) AS period, COUNT(*) AS cnt
            FROM stories
            WHERE user_id = ?
            GROUP BY period
            UNION ALL
            SELECT strftime('{fmt}', created_at) AS period, COUNT(*) AS cnt
            FROM sessions
            WHERE user_id = ?
            GROUP BY period
        )
        GROUP BY period
        ORDER BY period
    """

    rows = await db_manager.fetchall(query, (user.user_id, user.user_id))

    periods = [
        LibraryStatsPeriod(period=row["period"], count=row["count"])
        for row in rows
        if row["period"] is not None
    ]

    return LibraryStatsResponse(periods=periods)


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
    sort: LibrarySortOrder = Query(LibrarySortOrder.NEWEST, description="Sort order"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Search across all library content using text matching."""
    all_items: List[LibraryItem] = []
    query_lower = q.lower()

    # Search stories (includes both art-story and news types)
    if type is None or type in (LibraryItemType.ART_STORY, LibraryItemType.NEWS, LibraryItemType.MORNING_SHOW):
        stories = await story_repo.list_by_user(user.user_id, limit=200, offset=0)

        art_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.ART_STORY]
        news_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.NEWS]
        morning_ids = [s["story_id"] for s in stories if _resolve_story_type(s) == LibraryItemType.MORNING_SHOW]
        fav_art = await favorite_repo.get_favorited_ids(
            user.user_id, "art-story", art_ids
        ) if art_ids else set()
        fav_news = await favorite_repo.get_favorited_ids(
            user.user_id, "news", news_ids
        ) if news_ids else set()
        fav_morning = await favorite_repo.get_favorited_ids(
            user.user_id, "morning-show", morning_ids
        ) if morning_ids else set()
        fav_ids = fav_art | fav_news | fav_morning

        for s in stories:
            thumb = await _resolve_thumbnail(s["story_id"])
            item = _story_to_library_item(
                s, is_favorited=s["story_id"] in fav_ids, thumbnail_url=thumb
            )
            # Apply type filter
            if type is not None and item.type != type:
                continue
            # Apply safety filter (#81)
            if not _is_safe(item):
                continue

            text = s.get("story", {}).get("text", "")
            themes = json.dumps(s.get("educational_value", {}).get("themes", []))
            characters = json.dumps(s.get("characters", []))
            analysis = json.dumps(s.get("analysis", {}), ensure_ascii=False)
            searchable = f"{text} {themes} {characters} {analysis}".lower()

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

    # Sort (#83)
    _sort_items(all_items, sort)

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
