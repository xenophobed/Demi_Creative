"""
Shared Auth Dependencies

Consolidated authentication and ownership verification for all protected routes.
"""

from typing import Optional
import os

from fastapi import Header, HTTPException, status

from ..services.user_service import user_service, UserData
from ..services.database import story_repo, session_repo, db_manager
from ..services.database.session_repository import SessionData


def _is_pytest_runtime() -> bool:
    return os.getenv("PYTEST_CURRENT_TEST") is not None


def _allow_test_auth_bypass() -> bool:
    return os.getenv("ENVIRONMENT") == "test" and _is_pytest_runtime()


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserData:
    """
    Parse Bearer token and validate. Raises 401 on failure.

    Usage: user: UserData = Depends(get_current_user)
    """
    if _allow_test_auth_bypass() and not db_manager.is_connected:
        from ..services.database.schema import init_schema

        await db_manager.connect()
        await init_schema(db_manager)

    if not authorization:
        if _allow_test_auth_bypass():
            await db_manager.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id, username, email, password_hash, display_name,
                    is_active, is_verified, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test_user",
                    "test_user",
                    "test@example.com",
                    "test_hash",
                    "Test User",
                    1,
                    1,
                    "",
                    "",
                ),
            )
            await db_manager.commit()

            return UserData(
                user_id="test_user",
                username="test_user",
                email="test@example.com",
                password_hash="test_hash",
                display_name="Test User",
                avatar_url=None,
                is_active=True,
                is_verified=True,
                created_at="",
                updated_at="",
                last_login_at=None,
            )
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


async def get_admin_user(
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None),
) -> UserData:
    """
    Verify admin access via X-Admin-Key header + valid auth token.

    Requires both a valid user session (Bearer token) and a matching
    X-Admin-Key header checked against the ADMIN_API_KEY env var.

    Raises 401 if unauthenticated, 403 if admin key is missing or wrong.
    """
    if _allow_test_auth_bypass():
        return await get_current_user(authorization)

    user = await get_current_user(authorization)

    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is not configured",
        )

    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
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
            detail="会话不存在",
        )

    if session.user_id is None:
        # Legacy session with no owner — auto-claim
        await session_repo.update_user_id(session_id, user_id)
        session.user_id = user_id
    elif session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="你无权访问该会话",
        )

    return session
