"""
Hub Reaction Routes (#454) — toggle + counts on hub posts.

Endpoints
  POST /api/v1/hub/posts/{post_id}/reactions       -> toggle (idempotent)
  GET  /api/v1/hub/posts/{post_id}/reactions       -> counts + viewer's set

Three reaction types only — heart / star / wow — per PRD §3.12.5.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ...deps import get_current_user
from ...models import (
    HubReactionResponse,
    ReactionToggleRequest,
    ReactionToggleResponse,
)
from ....services.database import group_repo, hub_post_repo, hub_reaction_repo
from ....services.user_service import UserData


router = APIRouter(prefix="/api/v1/hub/posts", tags=["Content Hub"])


_VALID_REACTIONS = {"heart", "star", "wow"}


async def _ensure_post_visible(post_id: str, user: UserData):
    """Read access mirrors the feed: public groups open, private members-only.

    Returns the post (HubPostData) or raises HTTPException.
    """
    post = await hub_post_repo.get_by_id(post_id)
    if post is None or post.removed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POST_NOT_FOUND"},
        )
    group = await group_repo.get_by_id(post.group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GROUP_NOT_FOUND"},
        )
    if group.visibility == "private":
        if user.default_child_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "NOT_A_MEMBER"},
            )
        m = await group_repo.get_membership(
            group.group_id, user.user_id, user.default_child_id
        )
        if m is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "NOT_A_MEMBER"},
            )
    return post


@router.post(
    "/{post_id}/reactions",
    response_model=ReactionToggleResponse,
    summary="Toggle a reaction (idempotent: insert or remove)",
)
async def toggle_reaction(
    post_id: str,
    body: ReactionToggleRequest,
    user: UserData = Depends(get_current_user),
):
    if body.reaction_type not in _VALID_REACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REACTION_TYPE"},
        )
    await _ensure_post_visible(post_id, user)

    inserted = await hub_reaction_repo.toggle(
        post_id=post_id,
        user_id=user.user_id,
        reaction_type=body.reaction_type,
    )
    counts = await hub_reaction_repo.counts_for_post(post_id)
    viewer_reactions = await hub_reaction_repo.reactions_by_user(
        post_id, user.user_id
    )
    return ReactionToggleResponse(
        post_id=post_id,
        reaction_type=body.reaction_type,
        active=inserted,
        counts=counts,
        viewer_reactions=viewer_reactions,
    )


@router.get(
    "/{post_id}/reactions",
    response_model=HubReactionResponse,
    summary="Reaction counts + viewer's active set for a post",
)
async def get_reactions(
    post_id: str,
    user: UserData = Depends(get_current_user),
):
    await _ensure_post_visible(post_id, user)
    counts = await hub_reaction_repo.counts_for_post(post_id)
    viewer_reactions = await hub_reaction_repo.reactions_by_user(
        post_id, user.user_id
    )
    return HubReactionResponse(
        post_id=post_id,
        counts=counts,
        viewer_reactions=viewer_reactions,
    )
