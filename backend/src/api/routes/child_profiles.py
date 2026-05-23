"""Child profile management API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..models import (
    ChildProfileCreateRequest,
    ChildProfileListResponse,
    ChildProfileResponse,
    ChildProfileUpdateRequest,
)
from ...services.database import ChildProfileData, child_profile_repo
from ...services.user_service import UserData


router = APIRouter(prefix="/api/v1/child-profiles", tags=["Child Profiles"])


def _require_parent(user: UserData) -> None:
    if getattr(user, "role", "child") != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PARENT_ROLE_REQUIRED"},
        )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "CHILD_PROFILE_NOT_FOUND"},
    )


def _parse_dt(value: str | None):
    return datetime.fromisoformat(value) if value else None


def _to_response(profile: ChildProfileData) -> ChildProfileResponse:
    return ChildProfileResponse(
        child_id=profile.child_id,
        user_id=profile.user_id,
        name=profile.name,
        age_group=profile.age_group,
        interests=profile.interests,
        avatar=profile.avatar,
        is_default=profile.is_default,
        archived_at=_parse_dt(profile.archived_at),
        created_at=datetime.fromisoformat(profile.created_at),
        updated_at=datetime.fromisoformat(profile.updated_at),
    )


@router.get("", response_model=ChildProfileListResponse)
async def list_child_profiles(
    user: UserData = Depends(get_current_user),
):
    profiles = await child_profile_repo.list_for_user(user.user_id)
    return ChildProfileListResponse(items=[_to_response(item) for item in profiles])


@router.post(
    "",
    response_model=ChildProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_child_profile(
    request: ChildProfileCreateRequest,
    user: UserData = Depends(get_current_user),
):
    _require_parent(user)
    try:
        profile = await child_profile_repo.create(
            user_id=user.user_id,
            child_id=request.child_id,
            name=request.name,
            age_group=request.age_group.value,
            interests=request.interests,
            avatar=request.avatar,
            is_default=request.is_default,
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper() or "DUPLICATE" in str(exc).upper():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CHILD_PROFILE_EXISTS"},
            ) from exc
        raise
    return _to_response(profile)


@router.patch("/{child_id}", response_model=ChildProfileResponse)
async def update_child_profile(
    child_id: str,
    request: ChildProfileUpdateRequest,
    user: UserData = Depends(get_current_user),
):
    _require_parent(user)
    profile = await child_profile_repo.update(
        user_id=user.user_id,
        child_id=child_id,
        name=request.name,
        age_group=request.age_group.value if request.age_group else None,
        interests=request.interests,
        avatar=request.avatar,
    )
    if profile is None:
        raise _not_found()
    return _to_response(profile)


@router.post("/{child_id}/default", response_model=ChildProfileResponse)
async def set_default_child_profile(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    _require_parent(user)
    profile = await child_profile_repo.set_default(
        user_id=user.user_id,
        child_id=child_id,
    )
    if profile is None:
        raise _not_found()
    return _to_response(profile)


@router.post("/{child_id}/archive", response_model=ChildProfileResponse)
async def archive_child_profile(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    _require_parent(user)
    profile = await child_profile_repo.archive(
        user_id=user.user_id,
        child_id=child_id,
    )
    if profile is None:
        raise _not_found()
    return _to_response(profile)
