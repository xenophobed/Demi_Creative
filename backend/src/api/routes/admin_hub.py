"""
Admin Hub Moderation Routes (#456) — soft-delete a hub post.

Minimal moderation surface for v1: an admin can mark a post as
removed, which strips it from group feeds while preserving the row
for audit. Full moderation queue UI is deferred to v2.

Endpoints
  POST /api/v1/admin/hub/posts/{post_id}/remove

Why a separate router (not extending admin_artifacts)
  admin_artifacts is scoped to the artifact-graph surface (#16).
  Hub posts are a distinct domain — keeping the router separate
  keeps the URL paths self-explanatory and avoids importing hub
  state into the artifact admin.

Provenance / audit log
  hub_posts.removed_at + removed_reason capture the soft-delete
  state. v2 can wire a ProvenanceTracker call here once that
  module's API stabilises.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_admin_user
from ..models import RemoveHubPostRequest, RemoveHubPostResponse
from ...services.database import hub_post_repo
from ...services.user_service import UserData


router = APIRouter(prefix="/api/v1/admin/hub", tags=["Admin / Content Hub"])


@router.post(
    "/posts/{post_id}/remove",
    response_model=RemoveHubPostResponse,
    summary="Soft-delete a hub post (admin only)",
)
async def remove_hub_post(
    post_id: str,
    body: RemoveHubPostRequest,
    admin: UserData = Depends(get_admin_user),
):
    post = await hub_post_repo.get_by_id(post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POST_NOT_FOUND"},
        )
    if post.removed_at is not None:
        # Idempotent: already removed -> echo current state, do not error.
        return RemoveHubPostResponse(
            post_id=post.post_id,
            removed_at=post.removed_at,
            removed_reason=post.removed_reason,
            already_removed=True,
        )

    await hub_post_repo.soft_delete(post_id, reason=body.reason)
    fresh = await hub_post_repo.get_by_id(post_id)
    return RemoveHubPostResponse(
        post_id=fresh.post_id,
        removed_at=fresh.removed_at,
        removed_reason=fresh.removed_reason,
        already_removed=False,
    )
