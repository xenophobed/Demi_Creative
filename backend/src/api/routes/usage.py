"""Usage / quota API routes.

Exposes the current user's daily generation quota status for UI display.

Issue: #314 | Parent Epic: #313
"""

from fastapi import APIRouter, Depends

from ...services.database import usage_repo
from ...services.user_service import UserData
from ..deps import _get_daily_quota, _is_development_env, get_current_user

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
    if _is_development_env():
        used = await usage_repo.get_usage_today(user.user_id)
        return {
            "used": used,
            "limit": -1,
            "remaining": -1,
            "resets_at": None,
            "unlimited": True,
        }

    quota = _get_daily_quota()
    return await usage_repo.get_quota_status(user.user_id, limit=quota)
