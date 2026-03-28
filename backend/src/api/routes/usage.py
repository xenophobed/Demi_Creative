"""Usage / quota API routes.

Exposes the current user's daily generation quota status so the
frontend can display "X of 3 used today".

Issue: #314 | Parent Epic: #313
"""

from fastapi import APIRouter, Depends

from ..deps import get_current_user, _get_daily_quota
from ...services.user_service import UserData
from ...services.database import usage_repo

router = APIRouter(
    prefix="/api/v1/usage",
    tags=["Usage"],
)


@router.get(
    "/today",
    summary="Get today's generation quota status",
)
async def get_usage_today(
    user: UserData = Depends(get_current_user),
):
    """Return the current user's daily generation usage and remaining quota."""
    quota = _get_daily_quota()
    return await usage_repo.get_quota_status(user.user_id, limit=quota)
