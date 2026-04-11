"""
Shared Auth Dependencies

Consolidated authentication and ownership verification for all protected routes.
"""

import hmac
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from ..services.database import (
    db_manager,
    session_repo,
    story_repo,
    usage_repo,
    user_repo,
)
from ..services.database.session_repository import SessionData
from ..services.database.sql_compat import insert_or_ignore
from ..services.supabase_auth import decode_supabase_token
from ..services.user_service import UserData, user_service

_DEFAULT_DAILY_QUOTA = 6
_TIER_QUOTA = {"free": 3, "plus": 9}


def _is_development_env() -> bool:
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    return env in {"development", "dev", "local"}


def _get_daily_quota(membership_tier: str = "free") -> int:
    """Return daily quota based on membership tier.

    Priority: env var override > tier-based default > global default.
    """
    env_quota = os.getenv("DAILY_GENERATION_QUOTA")
    if env_quota:
        try:
            quota = int(env_quota)
            return quota if quota > 0 else _DEFAULT_DAILY_QUOTA
        except (ValueError, TypeError):
            pass
    return _TIER_QUOTA.get(membership_tier, _DEFAULT_DAILY_QUOTA)


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
                insert_or_ignore(
                    "users",
                    ["user_id", "username", "email", "password_hash", "display_name",
                     "is_active", "is_verified", "created_at", "updated_at"],
                    db_manager.dialect,
                ),
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
                role="child",
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

    token = parts[1]

    # Try Supabase JWT first (if SUPABASE_JWT_SECRET is configured)
    claims = decode_supabase_token(token)
    if claims:
        user = await _get_or_create_supabase_user(claims)
        if user:
            return user

    # Fall back to legacy custom token validation
    user = await user_service.validate_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    return user


async def _get_or_create_supabase_user(claims) -> Optional[UserData]:
    """Look up local user by Supabase UID, or auto-create one."""
    from datetime import datetime

    user = await user_repo.get_by_id(claims.sub)
    if user:
        return user

    # Auto-create local user from Supabase claims
    now = datetime.now().isoformat()
    username = claims.email.split("@")[0][:50] if claims.email else claims.sub[:50]

    # Ensure unique username
    existing = await user_repo.get_by_username(username)
    if existing:
        username = f"{username}_{claims.sub[:8]}"

    now = datetime.now().isoformat()
    await db_manager.execute(
        insert_or_ignore(
            "users",
            ["user_id", "username", "email", "password_hash", "display_name",
             "is_active", "is_verified", "role", "created_at", "updated_at"],
            db_manager.dialect,
        ),
        (
            claims.sub,
            username,
            claims.email,
            "supabase_managed",
            username,
            1,
            1 if claims.email_confirmed else 0,
            "child",
            now,
            now,
        ),
    )
    await db_manager.commit()
    return await user_repo.get_by_id(claims.sub)


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

    if not x_admin_key or not hmac.compare_digest(x_admin_key, admin_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return user


async def check_generation_quota(
    user: UserData = Depends(get_current_user),
) -> UserData:
    """Raise HTTP 429 if the user has hit their daily generation quota.

    Usage: user: UserData = Depends(check_generation_quota)
    The caller receives the same UserData as get_current_user so no extra
    dep is needed.
    """
    if _allow_test_auth_bypass() or _is_development_env():
        return user

    tier = getattr(user, 'membership_tier', 'free') or 'free'
    quota = _get_daily_quota(tier)
    used = await usage_repo.get_usage_today(user.user_id)
    if used >= quota:
        resets_at = (await usage_repo.get_quota_status(user.user_id, quota))[
            "resets_at"
        ]
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "quota_remaining": 0,
                "resets_at": resets_at,
            },
        )
    return user


async def get_story_for_owner(story_id: str, user_id: str) -> dict:
    """
    Fetch story by ID, verify ownership.

    Raises:
        HTTPException 404: Story not found
        HTTPException 403: User does not own this story or story has no owner
    """
    story = await story_repo.get_by_id(story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story not found: {story_id}",
        )

    owner = story.get("user_id")
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This resource is not accessible",
        )
    elif owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this story",
        )

    return story


async def get_session_for_owner(session_id: str, user_id: str) -> SessionData:
    """
    Fetch session by ID, verify ownership.

    Raises:
        HTTPException 404: Session not found
        HTTPException 403: User does not own this session or session has no owner
    """
    session = await session_repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This resource is not accessible",
        )
    elif session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session",
        )

    return session
