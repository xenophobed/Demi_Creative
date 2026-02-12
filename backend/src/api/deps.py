"""
Shared Auth Dependencies

Consolidated authentication and ownership verification for all protected routes.
"""

from typing import Optional

from fastapi import Header, HTTPException, status

from ..services.user_service import user_service, UserData
from ..services.database import story_repo, session_repo
from ..services.database.session_repository import SessionData


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserData:
    """
    Parse Bearer token and validate. Raises 401 on failure.

    Usage: user: UserData = Depends(get_current_user)
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token format",
        )

    user = await user_service.validate_token(parts[1])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    return user


async def get_story_for_owner(story_id: str, user_id: str) -> dict:
    """
    Fetch story by ID, verify ownership. Auto-claims legacy stories (user_id=NULL).

    Raises:
        HTTPException 404: Story not found
        HTTPException 403: User does not own this story
    """
    story = await story_repo.get_by_id(story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story not found: {story_id}",
        )

    owner = story.get("user_id")
    if owner is None:
        # Legacy story with no owner — auto-claim for requesting user
        await story_repo.update_user_id(story_id, user_id)
        story["user_id"] = user_id
    elif owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this story",
        )

    return story


async def get_session_for_owner(session_id: str, user_id: str) -> SessionData:
    """
    Fetch session by ID, verify ownership. Auto-claims legacy sessions (user_id=NULL).

    Raises:
        HTTPException 404: Session not found
        HTTPException 403: User does not own this session
    """
    session = await session_repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id is None:
        # Legacy session with no owner — auto-claim
        await session_repo.update_user_id(session_id, user_id)
        session.user_id = user_id
    elif session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    return session
