"""
Hub Post Routes (#449) — list + create.

Endpoints
  GET  /api/v1/hub/groups/{group_id}/posts   -> recency feed (paginated)
  POST /api/v1/hub/groups/{group_id}/posts   -> create with persona snapshot

Privacy invariants (locked by the COPPA contract test #450)
  - Responses NEVER include user-table fields. We project from the
    persona snapshot columns on hub_posts only.
  - The post create response strips `author_user_id`, `author_child_id`,
    `author_agent_id`, and `safety_score` (all server-side bookkeeping).

Onboarding gate
  POST requires onboarded_at non-null + a user.default_child_id —
  otherwise the agent persona snapshot can't be assembled.

Caption safety
  Captions, when present, must pass check_content_safety with
  score >= 0.85. The pipeline is fail-closed: if the safety MCP raises
  or returns a malformed envelope, the request is rejected with HTTP
  503 SAFETY_UNAVAILABLE — never silently let unchecked text through.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...deps import get_current_user
from ...models import (
    CreatePostRequest,
    HubPostResponse,
    ListHubPostsResponse,
)
from ....mcp_servers import check_content_safety
from ....services.database import group_repo, hub_post_repo
from ....services.achievement_service import FIRST_SHARED_POST, achievement_service
from ....services.user_service import UserData


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/hub/groups", tags=["Content Hub"])

_AGENT_SAFETY_TARGET_AGE = 4
_SAFETY_THRESHOLD = 0.85


class _SafetyUnavailableError(RuntimeError):
    """Raised when the safety MCP cannot be reached. Triggers fail-closed."""


async def _run_caption_safety(text: str) -> float:
    """Mirrors the agent endpoint's fail-closed safety check.

    We treat the youngest tier as the target age so the strictest filter
    applies — captions are read by all child age groups.

    Note: ``check_content_safety`` is decorated with the SDK's ``@tool``
    which wraps it in an ``SdkMcpTool`` registration object that is NOT
    itself callable. The raw async handler lives at ``.handler``.
    """
    try:
        result = await check_content_safety.handler({
            "content_text": text,
            "content_type": "hub_caption",
            "target_age": _AGENT_SAFETY_TARGET_AGE,
        })
    except Exception as exc:  # noqa: BLE001 - fail closed on any error
        logger.warning("Safety MCP unavailable for hub caption", exc_info=True)
        raise _SafetyUnavailableError(str(exc)) from exc

    try:
        data = json.loads(result["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise _SafetyUnavailableError("malformed safety payload") from exc

    if "error" in data:
        raise _SafetyUnavailableError(str(data["error"]))

    score = data.get("safety_score")
    if score is None:
        raise _SafetyUnavailableError("safety_score missing from response")

    return float(score)


def _to_response(post) -> HubPostResponse:
    """Project a HubPostData onto the COPPA-safe response shape.

    Critically: this picks ONLY the persona snapshot fields plus the
    post's own metadata — never any users-table column. The contract
    test in #450 asserts this projection is structurally sound.
    """
    return HubPostResponse(
        post_id=post.post_id,
        group_id=post.group_id,
        agent_name=post.agent_name_snapshot,
        agent_avatar_id=post.agent_avatar_id_snapshot,
        agent_title=post.agent_title_snapshot,
        source_artifact_type=post.source_artifact_type,
        source_id=post.source_id,
        caption=post.caption,
        created_at=post.created_at,
    )


def _require_onboarded(user: UserData) -> None:
    if user.role == "child" and user.consent_status == "pending_parent_consent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PARENT_APPROVAL_REQUIRED"},
        )
    if user.onboarded_at is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "ONBOARDING_REQUIRED"},
        )


def _require_child(user: UserData) -> str:
    if user.default_child_id is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "CHILD_PROFILE_REQUIRED"},
        )
    return user.default_child_id


async def _ensure_member(group_id: str, user: UserData, child_id: str) -> None:
    membership = await group_repo.get_membership(group_id, user.user_id, child_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_A_MEMBER"},
        )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/{group_id}/posts",
    response_model=HubPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a story to a group with persona snapshot",
)
async def create_post(
    group_id: str,
    body: CreatePostRequest,
    user: UserData = Depends(get_current_user),
):
    _require_onboarded(user)
    child_id = _require_child(user)

    group = await group_repo.get_by_id(group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GROUP_NOT_FOUND"},
        )
    await _ensure_member(group_id, user, child_id)

    if body.source_artifact_type not in (
        "art_story",
        "interactive_story",
        "kids_daily",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SOURCE_TYPE"},
        )

    safety_score = 1.0
    caption = body.caption
    if caption:
        try:
            safety_score = await _run_caption_safety(caption)
        except _SafetyUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "SAFETY_UNAVAILABLE"},
            )
        if safety_score < _SAFETY_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNSAFE_CAPTION",
                    "reason": "Caption did not pass content safety check",
                    "score": safety_score,
                },
            )

    try:
        post = await hub_post_repo.create_post(
            group_id=group_id,
            user_id=user.user_id,
            child_id=child_id,
            source_artifact_type=body.source_artifact_type,
            source_id=body.source_id,
            caption=caption,
            safety_score=safety_score,
        )
    except LookupError as exc:
        # Repository raises LookupError("AGENT_REQUIRED") if no buddy
        # exists for (user_id, child_id). Map to 412 so the frontend
        # can route the user back to /my-agent.
        if "AGENT_REQUIRED" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail={"code": "AGENT_REQUIRED"},
            )
        raise

    await achievement_service.award_event_safely(
        user.user_id, child_id, FIRST_SHARED_POST
    )

    return _to_response(post)


# ---------------------------------------------------------------------------
# List (the COPPA-critical surface)
# ---------------------------------------------------------------------------


@router.get(
    "/{group_id}/posts",
    response_model=ListHubPostsResponse,
    summary="Recency feed for a group (COPPA-safe — no user fields)",
)
async def list_posts(
    group_id: str,
    user: UserData = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=50),
    cursor_created_at: Optional[str] = Query(None),
    cursor_post_id: Optional[str] = Query(None),
):
    group = await group_repo.get_by_id(group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GROUP_NOT_FOUND"},
        )
    # Private groups: only members may read posts.
    if group.visibility == "private":
        if user.default_child_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "NOT_A_MEMBER"},
            )
        await _ensure_member(group_id, user, user.default_child_id)

    before = None
    if cursor_created_at and cursor_post_id:
        before = (cursor_created_at, cursor_post_id)

    posts = await hub_post_repo.list_by_group(
        group_id, limit=limit, before=before
    )
    items = [_to_response(p) for p in posts]
    next_cursor: Optional[dict] = None
    if posts and len(posts) == limit:
        last = posts[-1]
        next_cursor = {
            "cursor_created_at": last.created_at,
            "cursor_post_id": last.post_id,
        }
    return ListHubPostsResponse(items=items, next_cursor=next_cursor)
