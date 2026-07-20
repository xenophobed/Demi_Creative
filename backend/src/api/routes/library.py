"""
Library API Routes

Unified content library endpoints: browse, search, and favorite management.
Aggregates stories, interactive sessions, and news into a single API.

Implements: #58, #59, #60, #81, #83, #84
"""

import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...paths import AUDIO_DIR
from ...services.database import (
    child_profile_repo,
    favorite_repo,
    session_repo,
    story_repo,
)
from ...services.database.artifact_repository import StoryArtifactLinkRepository
from ...services.database.connection import db_manager
from ...services.database.sql_compat import date_format_sql, group_concat_sql
from ...services.user_service import UserData
from ...utils.text import count_words
from ..deps import get_current_user
from ..models import (
    ErrorResponse,
    FavoriteRequest,
    FavoriteResponse,
    LibraryItem,
    LibraryItemType,
    LibraryResponse,
    LibrarySortOrder,
    LibraryStatsGroupBy,
    LibraryStatsPeriod,
    LibraryStatsResponse,
    ParentDashboardRecentCreation,
    ParentDashboardTheme,
    RichStatsPeriod,
    RichStatsResponse,
)

# Content safety threshold — items below this score are hidden (#81)
SAFETY_THRESHOLD = 0.85

# Lifecycle states whose stories are visible in My Library + search.
# Per PRD §3.6 / §3.7, only published or candidate content is surfaced;
# intermediate (work-in-progress) and archived content must never appear.
# Legacy stories with NO primary artifact link have no lifecycle state and
# are treated as visible so we don't hide a user's existing library (#712/#713).
VISIBLE_LIFECYCLE_STATES = {"published", "candidate"}

router = APIRouter(prefix="/api/v1/library", tags=["Library"])


# ============================================================================
# Helpers
# ============================================================================


def _resolve_story_type(story: dict) -> LibraryItemType:
    """Map the story_type DB field to a LibraryItemType."""
    story_type = story.get("story_type", "image_to_story")
    if story_type in ("kids_daily", "morning_show", "news_to_kids"):
        return LibraryItemType.KIDS_DAILY
    if story_type == "interactive":
        return LibraryItemType.INTERACTIVE
    return LibraryItemType.ART_STORY


def _resolve_local_audio(audio_url: Optional[str]) -> Optional[str]:
    """Drop locally-served audio URLs whose backing file no longer exists.

    Remote URLs (anything not under /data/audio/) are returned unchanged.
    """
    if isinstance(audio_url, str) and audio_url.startswith("/data/audio/"):
        filename = audio_url[len("/data/audio/") :]
        file_path = AUDIO_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            return None
    return audio_url


def _ordered_audio_segments(raw_urls: object) -> Optional[List[str]]:
    """Build an ordered playlist from a {line_index -> url} audio map.

    Keys are stringified integers ("0", "1", ...). We sort numerically so the
    show plays in dialogue order, validate each clip the same way as the single
    audio_url, and skip any missing/blank entries. Returns None when there is no
    usable multi-clip audio.
    """
    if not isinstance(raw_urls, dict) or not raw_urls:
        return None

    def _index(key: object) -> int:
        try:
            return int(key)
        except (TypeError, ValueError):
            return 1 << 30  # push unparseable keys to the end, stable-ish

    segments: List[str] = []
    for key in sorted(raw_urls.keys(), key=_index):
        url = _resolve_local_audio(raw_urls[key])
        if isinstance(url, str) and url:
            segments.append(url)

    return segments or None


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
    category = (
        analysis.get("category") if item_type in (LibraryItemType.KIDS_DAILY,) else None
    )
    duration_seconds = (
        analysis.get("duration_seconds")
        if item_type == LibraryItemType.KIDS_DAILY
        else None
    )
    is_new = analysis.get("is_new") if item_type == LibraryItemType.KIDS_DAILY else None
    title = (
        analysis.get("kid_title")
        if item_type in (LibraryItemType.KIDS_DAILY,)
        else _extract_title(text)
    )

    audio_url = _resolve_local_audio(story.get("audio_url"))

    # Multi-segment episodes (Kids Daily) store one TTS clip per dialogue line in
    # analysis.audio_urls ({"0": url, "1": url, ...}). Surface the whole show as an
    # ordered playlist so the mini player plays every line, not just the first (#).
    audio_segments: Optional[List[str]] = None
    if item_type == LibraryItemType.KIDS_DAILY:
        audio_segments = _ordered_audio_segments(analysis.get("audio_urls"))
        # Fall back to the first segment if the legacy single audio_url is missing,
        # so the play button still appears for episodes with per-line audio only.
        if audio_segments and not audio_url:
            audio_url = audio_segments[0]

    return LibraryItem(
        id=story["story_id"],
        type=item_type,
        title=title or _extract_title(text),
        preview=text[:150] if text else "",
        image_url=story.get("image_url"),
        thumbnail_url=thumbnail_url or story.get("image_url"),
        audio_url=audio_url,
        audio_segments=audio_segments,
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


async def _get_visible_story_ids(story_ids: List[str]) -> set:
    """Resolve which story IDs are lifecycle-visible in the library (#712/#713).

    A story with primary artifacts is visible only when at least one primary
    artifact is in a visible lifecycle state (published or candidate).
    Legacy stories without a primary artifact link remain visible for
    backwards compatibility. Stories with linked primary artifacts that are
    all intermediate/archived are hidden.

    Returns the set of story_ids that should be shown. Batched to one query
    set (chunked) to avoid N+1 lookups.
    """
    if not story_ids:
        return set()

    link_repo = StoryArtifactLinkRepository(db_manager)
    try:
        states_by_story = await link_repo.get_primary_lifecycle_states(story_ids)
    except Exception:
        # Do not expose content when its lifecycle state cannot be verified.
        return set()

    visible: set = set()
    for sid in story_ids:
        states = states_by_story.get(sid)
        if not states:
            # Legacy / no primary artifact link → treat as visible.
            visible.add(sid)
        elif states & VISIBLE_LIFECYCLE_STATES:
            # At least one primary artifact is published or candidate.
            visible.add(sid)
        # Otherwise primary artifacts are all intermediate/archived → hide.
    return visible


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


def _extract_title(text: str, max_len: int = 24) -> str:
    """Extract a concise display title from story text."""
    if not text:
        return "Untitled Story"

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_line:
        first_line = text.strip()

    candidate = re.sub(r"^[《「『【〈\s]+|[》」』】〉\s]+$", "", first_line).strip()
    if not candidate:
        candidate = first_line

    for sep in [
        "\u3002",
        "\uff01",
        "\uff1f",
        ".",
        "!",
        "?",
        "\uff1b",
        ";",
        "\uff1a",
        ":",
        "\uff0c",
        ",",
    ]:
        idx = candidate.find(sep)
        if 0 < idx:
            candidate = candidate[:idx].strip()
            break

    if not candidate:
        return "Untitled Story"
    if len(candidate) <= max_len:
        return candidate
    return candidate[:max_len].rstrip() + "..."


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


async def _get_visible_library_counts(user_id: str) -> dict[str, int]:
    """Return counts using the same type and safety rules as library browsing."""
    stories = await story_repo.list_by_user(user_id, limit=10000, offset=0)
    art_story_count = 0
    news_count = 0

    for story in stories:
        item_type = _resolve_story_type(story)
        if item_type not in (LibraryItemType.ART_STORY, LibraryItemType.KIDS_DAILY):
            continue
        if (
            story.get("safety_score") is not None
            and story["safety_score"] < SAFETY_THRESHOLD
        ):
            continue
        if item_type == LibraryItemType.KIDS_DAILY:
            news_count += 1
        else:
            art_story_count += 1

    sessions = await session_repo.list_by_user(user_id, limit=10000, offset=0)
    interactive_count = len(sessions)

    return {
        "art_story_count": art_story_count,
        "interactive_count": interactive_count,
        "news_count": news_count,
        "total": art_story_count + interactive_count + news_count,
    }


async def _ensure_owned_child_scope(user: UserData, child_id: Optional[str]) -> None:
    """Ensure a requested child profile belongs to the current account."""
    if not child_id:
        return

    profile = await child_profile_repo.get_for_user(user.user_id, child_id)
    if profile is not None:
        return

    if getattr(user, "default_child_id", None) == child_id:
        return

    owned = await db_manager.fetchone(
        """
        SELECT 1 FROM stories WHERE user_id = ? AND child_id = ?
        UNION
        SELECT 1 FROM sessions WHERE user_id = ? AND child_id = ?
        LIMIT 1
        """,
        (user.user_id, child_id, user.user_id, child_id),
    )
    if owned:
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Child profile not found",
    )


def _parse_theme_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ]
        except (json.JSONDecodeError, ValueError, TypeError):
            return [part.strip() for part in value.split(",") if part.strip()]
    return []


async def _get_parent_dashboard_themes(
    user_id: str,
    child_id: Optional[str],
) -> list[ParentDashboardTheme]:
    child_filter = " AND child_id = ?" if child_id else ""
    rows = await db_manager.fetchall(
        f"""
        SELECT themes
        FROM stories
        WHERE user_id = ?
          AND (safety_score IS NULL OR safety_score >= ?)
          {child_filter}
        """,
        (user_id, SAFETY_THRESHOLD, child_id) if child_id else (user_id, SAFETY_THRESHOLD),
    )

    counts: dict[str, int] = {}
    for row in rows:
        for theme in _parse_theme_list(row.get("themes")):
            counts[theme] = counts.get(theme, 0) + 1

    return [
        ParentDashboardTheme(theme=theme, count=count)
        for theme, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]


async def _get_parent_dashboard_recent_creations(
    user_id: str,
    child_id: Optional[str],
) -> list[ParentDashboardRecentCreation]:
    child_filter = " AND child_id = ?" if child_id else ""
    story_params = (
        (user_id, SAFETY_THRESHOLD, child_id)
        if child_id
        else (user_id, SAFETY_THRESHOLD)
    )
    story_rows = await db_manager.fetchall(
        f"""
        SELECT story_id, story_text, story_type, image_url, created_at
        FROM stories
        WHERE user_id = ?
          AND (safety_score IS NULL OR safety_score >= ?)
          {child_filter}
        ORDER BY created_at DESC
        LIMIT 5
        """,
        story_params,
    )

    session_params = (user_id, child_id) if child_id else (user_id,)
    session_rows = await db_manager.fetchall(
        f"""
        SELECT session_id, story_title, created_at
        FROM sessions
        WHERE user_id = ?{child_filter}
        ORDER BY created_at DESC
        LIMIT 5
        """,
        session_params,
    )

    items: list[ParentDashboardRecentCreation] = []
    for row in story_rows:
        story_type = row.get("story_type") or "image_to_story"
        items.append(
            ParentDashboardRecentCreation(
                id=row["story_id"],
                type=_resolve_story_type({"story_type": story_type}).value,
                title=_extract_title(row.get("story_text") or ""),
                created_at=row["created_at"],
                thumbnail_url=row.get("image_url"),
            )
        )
    for row in session_rows:
        items.append(
            ParentDashboardRecentCreation(
                id=row["session_id"],
                type=LibraryItemType.INTERACTIVE.value,
                title=row.get("story_title") or "Interactive Story",
                created_at=row["created_at"],
                thumbnail_url=None,
            )
        )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:5]


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

    # Legacy type aliases all map to KIDS_DAILY
    _KIDS_DAILY_ALIASES = {
        LibraryItemType.NEWS,
        LibraryItemType.MORNING_SHOW,
        LibraryItemType.KIDS_NEWS,
        LibraryItemType.KIDS_DAILY,
    }
    effective_type = LibraryItemType.KIDS_DAILY if type in _KIDS_DAILY_ALIASES else type

    # Fetch stories (includes both art-story and kids-daily types)
    if effective_type is None or effective_type in (
        LibraryItemType.ART_STORY,
        LibraryItemType.KIDS_DAILY,
    ):
        stories = await story_repo.list_by_user(user.user_id, limit=10000, offset=0)

        # Separate favorites lookups by resolved type
        art_ids = [
            s["story_id"]
            for s in stories
            if _resolve_story_type(s) == LibraryItemType.ART_STORY
        ]
        kids_daily_ids = [
            s["story_id"]
            for s in stories
            if _resolve_story_type(s) == LibraryItemType.KIDS_DAILY
        ]
        fav_art_ids = (
            await favorite_repo.get_favorited_ids(user.user_id, "art-story", art_ids)
            if art_ids
            else set()
        )
        fav_kids_daily_ids = (
            await favorite_repo.get_favorited_ids(
                user.user_id, "kids-daily", kids_daily_ids
            )
            if kids_daily_ids
            else set()
        )
        fav_story_ids = fav_art_ids | fav_kids_daily_ids

        # Resolve lifecycle visibility in one batched lookup (#712)
        visible_story_ids = await _get_visible_story_ids(
            [s["story_id"] for s in stories]
        )

        for s in stories:
            thumb = await _resolve_thumbnail(s["story_id"])
            item = _story_to_library_item(
                s, is_favorited=s["story_id"] in fav_story_ids, thumbnail_url=thumb
            )
            # Apply type filter
            if effective_type is not None and item.type != effective_type:
                continue
            # Apply safety filter (#81)
            if not _is_safe(item):
                continue
            # Apply lifecycle filter — only published/candidate are visible (#712)
            if s["story_id"] not in visible_story_ids:
                continue
            all_items.append(item)

    # Fetch interactive sessions
    if type is None or type == LibraryItemType.INTERACTIVE:
        sessions = await session_repo.list_by_user(user.user_id, limit=10000, offset=0)
        session_ids = [s.session_id for s in sessions]
        fav_session_ids = (
            await favorite_repo.get_favorited_ids(
                user.user_id, "interactive", session_ids
            )
            if session_ids
            else set()
        )

        for s in sessions:
            all_items.append(
                _session_to_library_item(
                    s, is_favorited=s.session_id in fav_session_ids
                )
            )

    # Sort (#83)
    _sort_items(all_items, sort)

    total = len(all_items)
    paginated = all_items[offset : offset + limit]

    return LibraryResponse(
        items=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# GET /api/v1/library/counts — Profile stat counts (#524)
# ============================================================================


@router.get(
    "/counts",
    responses={401: {"model": ErrorResponse}},
    summary="Get library-visible counts",
    description="Returns profile stat counts using library type and safety rules",
)
async def get_library_counts(
    user: UserData = Depends(get_current_user),
):
    """Return counts for profile stat cards, kept in sync with My Library."""
    return await _get_visible_library_counts(user.user_id)


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
        fmt = "%Y-%m"
    else:
        fmt = "%Y-W%W"

    period_expr = date_format_sql("created_at", fmt, db_manager.dialect)

    query = f"""
        SELECT period, SUM(cnt) AS count FROM (
            SELECT {period_expr} AS period, COUNT(*) AS cnt
            FROM stories
            WHERE user_id = ?
            GROUP BY period
            UNION ALL
            SELECT {period_expr} AS period, COUNT(*) AS cnt
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
# GET /api/v1/library/stats-rich — Rich growth dashboard (#356)
# ============================================================================


@router.get(
    "/stats-rich",
    response_model=RichStatsResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Get rich growth dashboard stats",
    description="Returns multi-dimensional growth metrics per period: word count, theme diversity, completion rate, content mix, and streak",
)
async def get_rich_stats(
    group_by: LibraryStatsGroupBy = Query(
        LibraryStatsGroupBy.WEEK, description="Group by week or month"
    ),
    child_id: Optional[str] = Query(
        None, description="Optional child profile scope for parent dashboard views"
    ),
    parent_dashboard: bool = Query(
        False, description="Require parent role for parent-facing dashboard entrypoint"
    ),
    user: UserData = Depends(get_current_user),
):
    """Rich growth metrics aggregated per time period (#356).

    Uses existing DB data — no schema changes needed.
    """
    if parent_dashboard and getattr(user, "role", "child") != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent dashboard requires parent role",
        )

    await _ensure_owned_child_scope(user, child_id)

    fmt = "%Y-%m" if group_by == LibraryStatsGroupBy.MONTH else "%Y-W%W"
    period_expr = date_format_sql("created_at", fmt, db_manager.dialect)
    child_filter = " AND child_id = ?" if child_id else ""
    session_params = (user.user_id, child_id) if child_id else (user.user_id,)

    # 1) Stories: count, word_count sum, themes, story_type per period
    stories_query = f"""
        SELECT
            {period_expr} AS period,
            COUNT(*) AS cnt,
            COALESCE(SUM(word_count), 0) AS total_words,
            {group_concat_sql("themes", "||", db_manager.dialect)} AS all_themes,
            {group_concat_sql("story_type", "||", db_manager.dialect)} AS all_types
        FROM stories
        WHERE user_id = ?
          AND (safety_score IS NULL OR safety_score >= ?)
          {child_filter}
        GROUP BY period
        ORDER BY period
    """
    story_params = (
        (user.user_id, SAFETY_THRESHOLD, child_id)
        if child_id
        else (user.user_id, SAFETY_THRESHOLD)
    )
    story_rows = await db_manager.fetchall(stories_query, story_params)

    # 2) Sessions: count, completed count per period
    sessions_query = f"""
        SELECT
            {period_expr} AS period,
            COUNT(*) AS total_sessions,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions
        FROM sessions
        WHERE user_id = ?{child_filter}
        GROUP BY period
        ORDER BY period
    """
    session_rows = await db_manager.fetchall(sessions_query, session_params)

    # Build lookup from sessions
    session_map: dict = {}
    for row in session_rows:
        if row["period"]:
            session_map[row["period"]] = row

    # Collect all periods
    all_periods: dict[str, RichStatsPeriod] = {}

    for row in story_rows:
        p = row["period"]
        if not p:
            continue

        # Parse unique themes from concatenated JSON arrays
        unique_themes: set[str] = set()
        if row["all_themes"]:
            for chunk in row["all_themes"].split("||"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                try:
                    parsed = json.loads(chunk)
                    if isinstance(parsed, list):
                        unique_themes.update(str(t) for t in parsed)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Parse story type breakdown
        type_breakdown: dict[str, int] = {}
        if row["all_types"]:
            for t in row["all_types"].split("||"):
                t = t.strip()
                if t:
                    type_breakdown[t] = type_breakdown.get(t, 0) + 1

        # Merge with session data
        sess = session_map.pop(p, None)
        total_sess = sess["total_sessions"] if sess else 0
        completed_sess = sess["completed_sessions"] if sess else 0
        creation_count = row["cnt"] + total_sess
        completion_rate = (
            round(completed_sess / total_sess, 2)
            if total_sess > 0
            else 0.0
        )
        if total_sess > 0:
            type_breakdown["interactive"] = type_breakdown.get("interactive", 0) + total_sess

        all_periods[p] = RichStatsPeriod(
            period=p,
            creation_count=creation_count,
            total_words=row["total_words"],
            unique_themes=len(unique_themes),
            completion_rate=completion_rate,
            story_type_breakdown=type_breakdown,
        )

    # Add session-only periods (no stories that period)
    for p, sess in session_map.items():
        all_periods[p] = RichStatsPeriod(
            period=p,
            creation_count=sess["total_sessions"],
            total_words=0,
            unique_themes=0,
            completion_rate=(
                round(sess["completed_sessions"] / sess["total_sessions"], 2)
                if sess["total_sessions"] > 0
                else 0.0
            ),
            story_type_breakdown={"interactive": sess["total_sessions"]},
        )

    sorted_periods = sorted(all_periods.values(), key=lambda x: x.period)
    top_themes: list[ParentDashboardTheme] = []
    recent_creations: list[ParentDashboardRecentCreation] = []
    if parent_dashboard:
        top_themes = await _get_parent_dashboard_themes(user.user_id, child_id)
        recent_creations = await _get_parent_dashboard_recent_creations(
            user.user_id,
            child_id,
        )

    return RichStatsResponse(
        periods=sorted_periods,
        streak_days=0,
        top_themes=top_themes,
        recent_creations=recent_creations,
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
    sort: LibrarySortOrder = Query(LibrarySortOrder.NEWEST, description="Sort order"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Search across all library content using text matching."""
    all_items: List[LibraryItem] = []
    query_lower = q.lower()

    # Legacy type aliases all map to KIDS_DAILY
    _KIDS_DAILY_ALIASES = {
        LibraryItemType.NEWS,
        LibraryItemType.MORNING_SHOW,
        LibraryItemType.KIDS_NEWS,
        LibraryItemType.KIDS_DAILY,
    }
    effective_type = LibraryItemType.KIDS_DAILY if type in _KIDS_DAILY_ALIASES else type

    # Search stories (includes both art-story and kids-daily types)
    if effective_type is None or effective_type in (
        LibraryItemType.ART_STORY,
        LibraryItemType.KIDS_DAILY,
    ):
        stories = await story_repo.list_by_user(user.user_id, limit=10000, offset=0)

        art_ids = [
            s["story_id"]
            for s in stories
            if _resolve_story_type(s) == LibraryItemType.ART_STORY
        ]
        kids_daily_ids = [
            s["story_id"]
            for s in stories
            if _resolve_story_type(s) == LibraryItemType.KIDS_DAILY
        ]
        fav_art = (
            await favorite_repo.get_favorited_ids(user.user_id, "art-story", art_ids)
            if art_ids
            else set()
        )
        fav_kids_daily = (
            await favorite_repo.get_favorited_ids(
                user.user_id, "kids-daily", kids_daily_ids
            )
            if kids_daily_ids
            else set()
        )
        fav_ids = fav_art | fav_kids_daily

        # Resolve lifecycle visibility in one batched lookup (#713)
        visible_story_ids = await _get_visible_story_ids(
            [s["story_id"] for s in stories]
        )

        for s in stories:
            thumb = await _resolve_thumbnail(s["story_id"])
            item = _story_to_library_item(
                s, is_favorited=s["story_id"] in fav_ids, thumbnail_url=thumb
            )
            # Apply type filter
            if effective_type is not None and item.type != effective_type:
                continue
            # Apply safety filter (#81)
            if not _is_safe(item):
                continue
            # Apply lifecycle filter — only published/candidate are visible (#713)
            if s["story_id"] not in visible_story_ids:
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
        sessions = await session_repo.list_by_user(user.user_id, limit=10000, offset=0)
        session_ids = [s.session_id for s in sessions]
        fav_ids = (
            await favorite_repo.get_favorited_ids(
                user.user_id, "interactive", session_ids
            )
            if session_ids
            else set()
        )

        for s in sessions:
            searchable = f"{s.story_title} {s.theme or ''}".lower()
            if query_lower in searchable:
                all_items.append(
                    _session_to_library_item(s, is_favorited=s.session_id in fav_ids)
                )

    # Sort (#83)
    _sort_items(all_items, sort)

    total = len(all_items)
    paginated = all_items[offset : offset + limit]

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
