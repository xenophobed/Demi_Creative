"""Achievement badge API routes (#536)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ...services.achievement_service import (
    UnknownAchievementError,
    achievement_service,
)
from ...services.user_service import UserData
from ..deps import get_current_user


router = APIRouter(prefix="/api/v1/achievements", tags=["Achievements"])


class AwardAchievementRequest(BaseModel):
    child_id: str = Field(..., min_length=1, max_length=100)
    achievement_id: str = Field(..., min_length=1, max_length=100)


@router.post("/award", summary="Award a server-owned achievement badge")
async def award_achievement(
    request: AwardAchievementRequest,
    response: Response,
    user: UserData = Depends(get_current_user),
):
    try:
        result = await achievement_service.award(
            user_id=user.user_id,
            child_id=request.child_id,
            achievement_id=request.achievement_id,
        )
    except UnknownAchievementError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown achievement",
        )

    response.status_code = (
        status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
    )
    return result


@router.get("/{child_id}", summary="List achievement badges for a child")
async def list_achievements(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    return await achievement_service.list_for_child(user.user_id, child_id)
