"""
Hub Group Routes (#448) — list, create, join, get.

Endpoints
  GET  /api/v1/hub/groups               -> list (public + caller's private)
  POST /api/v1/hub/groups               -> create (public or private)
  GET  /api/v1/hub/groups/{group_id}    -> detail
  POST /api/v1/hub/groups/{group_id}/join -> join, optional ?invite=token

Behaviour
  - Public groups: open join (any onboarded user).
  - Private groups: invite_token must match the row at create time.
  - Private invite_token is exposed ONCE in the create response so the
    inviter can copy/paste a link. List/get responses NEVER expose the
    invite_token to anyone other than members. (Safety belt: the
    response model omits the field for non-members.)

Onboarding gate
  Posting requires onboarding (#440) — but joining/listing does not.
  The narrow check is: any user with a valid auth token can browse
  public groups; only onboarded users can join. We enforce join's
  onboarding requirement so we never end up with members who can't
  actually post anything to the group.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...deps import get_current_user
from ...models import (
    CreateGroupRequest,
    GroupResponse,
    JoinGroupResponse,
    ListGroupsResponse,
)
from ....services.database import group_repo
from ....services.user_service import UserData


router = APIRouter(prefix="/api/v1/hub/groups", tags=["Content Hub"])


def _to_response(group, *, include_invite_token: bool = False) -> GroupResponse:
    """Convert GroupData to GroupResponse.

    Privacy: invite_token is included ONLY when include_invite_token=True
    (e.g. on create-response or for an owner viewing their own group).
    """
    return GroupResponse(
        group_id=group.group_id,
        slug=group.slug,
        name=group.name,
        description=group.description,
        theme=group.theme,
        visibility=group.visibility,
        invite_token=group.invite_token if include_invite_token else None,
        created_at=group.created_at,
        member_count=group.member_count,
    )


def _require_onboarded(user: UserData) -> None:
    """Common helper: a user must have onboarded_at set to act on groups."""
    if user.onboarded_at is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "ONBOARDING_REQUIRED"},
        )


@router.get(
    "",
    response_model=ListGroupsResponse,
    summary="List groups (public + caller's private)",
)
async def list_groups(
    user: UserData = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    public = await group_repo.list_public(limit=limit, offset=offset)
    if user.default_child_id:
        joined = await group_repo.list_for_member(
            user_id=user.user_id, child_id=user.default_child_id
        )
    else:
        joined = []

    seen_ids = {g.group_id for g in public}
    # Include any private groups the caller is a member of, deduped.
    extras = [g for g in joined if g.group_id not in seen_ids]
    items = [_to_response(g) for g in public] + [
        _to_response(g, include_invite_token=False) for g in extras
    ]
    return ListGroupsResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a group (public or private)",
)
async def create_group(
    body: CreateGroupRequest,
    user: UserData = Depends(get_current_user),
):
    _require_onboarded(user)
    if user.default_child_id is None:
        # Unusual — onboarding completion sets default_child_id on the
        # first PUT /me/agent (#455). If we somehow get here with no
        # child profile bound, the create can't satisfy the membership
        # FK invariant downstream.
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "CHILD_PROFILE_REQUIRED"},
        )
    if body.visibility not in ("public", "private"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_VISIBILITY"},
        )

    group = await group_repo.create_group(
        name=body.name,
        visibility=body.visibility,
        created_by_user_id=user.user_id,
        owner_child_id=user.default_child_id,
        description=body.description,
        theme=body.theme,
    )
    # Expose the invite_token exactly once — at create time — so the
    # owner can copy/paste it. List/get responses scrub the field.
    return _to_response(group, include_invite_token=True)


@router.get(
    "/{ident}",
    response_model=GroupResponse,
    summary="Get a group by id or slug",
)
async def get_group(
    ident: str,
    user: UserData = Depends(get_current_user),
):
    """Look up a group by either its UUID hex id OR its kebab-case slug.

    The frontend GroupPage routes by slug (/content-hub/:slug), so the
    by-slug path is what matters in practice. The id path is kept so
    consumers that already have the id (e.g. server-side tests or the
    create-response payload) can use it directly without an extra hop.
    """
    group = await group_repo.get_by_id(ident)
    if group is None:
        # Fall through: maybe the caller passed a slug.
        group = await group_repo.get_by_slug(ident)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GROUP_NOT_FOUND"},
        )
    # Owner sees the invite_token; everyone else does not.
    is_owner = group.created_by_user_id == user.user_id
    return _to_response(group, include_invite_token=is_owner)


@router.post(
    "/{group_id}/join",
    response_model=JoinGroupResponse,
    summary="Join a group (open for public, invite-token for private)",
)
async def join_group(
    group_id: str,
    user: UserData = Depends(get_current_user),
    invite: Optional[str] = Query(None, alias="invite"),
):
    _require_onboarded(user)
    if user.default_child_id is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "CHILD_PROFILE_REQUIRED"},
        )
    try:
        membership = await group_repo.join_group(
            group_id=group_id,
            user_id=user.user_id,
            child_id=user.default_child_id,
            invite_token=invite,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GROUP_NOT_FOUND"},
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INVALID_INVITE_TOKEN"},
        )
    return JoinGroupResponse(
        group_id=membership.group_id,
        role=membership.role,
        joined_at=membership.joined_at,
    )
