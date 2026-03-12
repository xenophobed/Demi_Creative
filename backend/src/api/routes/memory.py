"""Memory API routes — preferences and characters (#162).

Exposes read/delete endpoints for the memory system so the frontend can
display favorite themes, suggest topics, and show a character gallery.

Parent Epic: #42
"""

import re
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ...services.database import preference_repo, character_repo
from ...services.user_service import UserData

router = APIRouter(
    prefix="/api/v1/memory",
    tags=["Memory"],
)


def _validate_child_id(child_id: str) -> str:
    """Validate child_id format — alphanumeric, underscore, hyphen, 1-100 chars."""
    if not re.match(r"^[a-zA-Z0-9_-]{1,100}$", child_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid child_id format",
        )
    return child_id


@router.get(
    "/preferences/{child_id}",
    summary="Get child preference profile",
)
async def get_preferences(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Return the normalized preference profile for a child."""
    child_id = _validate_child_id(child_id)
    profile = await preference_repo.get_profile(child_id)
    return {"child_id": child_id, "profile": profile}


@router.delete(
    "/preferences/{child_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete child preference data",
)
async def delete_preferences(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Remove preference profile for a child (COPPA compliance)."""
    child_id = _validate_child_id(child_id)
    db = preference_repo._db
    await db.execute(
        "DELETE FROM child_preferences WHERE child_id = ?",
        (child_id,),
    )
    await db.commit()
    return {"child_id": child_id, "deleted": True}


@router.get(
    "/characters/{child_id}",
    summary="Get child's character gallery",
)
async def get_characters(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Return all characters for a child, sorted by appearance count."""
    child_id = _validate_child_id(child_id)
    characters = await character_repo.get_characters(child_id)
    return {"child_id": child_id, "characters": characters}
