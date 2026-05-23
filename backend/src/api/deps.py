"""
Shared Auth Dependencies

Consolidated authentication and ownership verification for all protected routes.
"""

import hmac
import os
from typing import Optional, Sequence

from fastapi import Depends, Header, HTTPException, status

from ..services.database import (
    db_manager,
    referral_repo,
    session_repo,
    story_repo,
    usage_repo,
    user_repo,
    child_profile_repo,
)
from ..services.database.session_repository import SessionData
from ..services.database.sql_compat import insert_or_ignore
from ..services.supabase_auth import decode_supabase_token
from ..services.user_service import UserData, user_service

_DEFAULT_DAILY_QUOTA = 6
_TIER_QUOTA = {"free": 3, "plus": 9}


async def has_visible_hub_post(
    *,
    source_id: str,
    source_types: Sequence[str],
    user_id: str,
) -> bool:
    """
    Return true when a source artifact is readable through Content Hub.

    Library/detail endpoints are normally owner-only. A Hub post is the
    intentional sharing boundary: public groups are readable by any signed-in
    user, while private groups require membership on the account.
    """
    if not source_types:
        return False

    placeholders = ",".join("?" for _ in source_types)
    row = await db_manager.fetchone(
        f"""
        SELECT 1
        FROM hub_posts p
        JOIN hub_groups g ON g.group_id = p.group_id
        LEFT JOIN hub_group_memberships m
          ON m.group_id = p.group_id AND m.user_id = ?
        WHERE p.source_id = ?
          AND p.source_artifact_type IN ({placeholders})
          AND p.removed_at IS NULL
          AND (g.visibility = 'public' OR m.group_id IS NOT NULL)
        LIMIT 1
        """,
        (user_id, source_id, *source_types),
    )
    return row is not None


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


async def require_owned_child_profile(
    user: UserData,
    child_id: str,
    *,
    include_archived: bool = False,
) -> None:
    """Validate that a child_id belongs to the authenticated account.

    Parent-owned Phase 3 flows use child_profiles as the canonical ownership
    source. Child-started legacy accounts can still operate on their own
    default_child_id when they do not yet have a parent-owned profile row.
    """
    if not child_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CHILD_PROFILE_REQUIRED"},
        )

    profile = await child_profile_repo.get_for_user(
        user.user_id,
        child_id,
        include_archived=include_archived,
    )
    if profile is not None:
        return

    if (
        getattr(user, "role", "child") == "child"
        and getattr(user, "default_child_id", None) == child_id
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "CHILD_PROFILE_NOT_FOUND"},
    )


async def _get_or_create_supabase_user(claims) -> Optional[UserData]:
    """Look up local user by Supabase UID, or auto-create one."""
    import secrets
    import string
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

    # Generate a unique referral code (same logic as user_repo._generate_referral_code)
    alphabet = string.ascii_lowercase + string.digits
    referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))
    role = claims.role if claims.role in {"parent", "child"} else "parent"
    consent_status = "not_required" if role == "parent" else "pending_parent_consent"

    now = datetime.now().isoformat()
    await db_manager.execute(
        insert_or_ignore(
            "users",
            ["user_id", "username", "email", "password_hash", "display_name",
             "is_active", "is_verified", "role",
             "parent_email", "consent_status",
             "membership_tier", "referral_code", "default_child_id",
             "created_at", "updated_at"],
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
            role,
            claims.parent_email,
            consent_status,
            "free",
            referral_code,
            claims.child_id if role == "parent" else None,
            now,
            now,
        ),
    )
    await db_manager.commit()

    # Handle referral if a referral_code was passed during registration (#424)
    if getattr(claims, "referral_code", None):
        try:
            referrer = await user_repo.get_by_referral_code(claims.referral_code)
            if referrer and referrer.user_id != claims.sub:
                await referral_repo.create_referral(
                    referrer_user_id=referrer.user_id,
                    referred_user_id=claims.sub,
                    referral_code=claims.referral_code,
                )
                # Update referred_by on the new user
                await db_manager.execute(
                    "UPDATE users SET referred_by = ? WHERE user_id = ?",
                    (claims.referral_code, claims.sub),
                )
                await db_manager.commit()

                # Qualify immediately if email is confirmed (#425)
                if claims.email_confirmed:
                    await referral_repo.qualify_referral(claims.sub)
                    from ..services.user_service import user_service
                    await user_service.qualify_and_maybe_upgrade(referrer.user_id)
        except Exception:
            pass  # Referral is non-critical — don't block user creation

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


async def get_story_for_owner(
    story_id: str,
    user_id: str,
    *,
    allow_hub_shared: bool = False,
) -> dict:
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
        is_shared = await has_visible_hub_post(
            source_id=story_id,
            source_types=("art_story", "kids_daily"),
            user_id=user_id,
        ) if allow_hub_shared else False
        if not is_shared:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this story",
            )

    return story


async def get_session_for_owner(
    session_id: str,
    user_id: str,
    *,
    allow_hub_shared: bool = False,
) -> SessionData:
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
        is_shared = await has_visible_hub_post(
            source_id=session_id,
            source_types=("interactive_story",),
            user_id=user_id,
        ) if allow_hub_shared else False
        if not is_shared:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this session",
            )

    return session
