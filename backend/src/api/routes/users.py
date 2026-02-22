"""
User API Routes

User authentication and management API endpoints
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status

from ..models import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    UserWithStatsResponse,
    TokenResponse,
    AuthResponse,
    ChangePasswordRequest,
    UpdateProfileRequest,
    ErrorResponse,
)
from ..deps import get_current_user
from ...services.user_service import user_service, UserData


router = APIRouter(
    prefix="/api/v1/users",
    tags=["User Authentication"]
)


def _user_to_response(user: UserData) -> UserResponse:
    """Convert UserData to UserResponse"""
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=datetime.fromisoformat(user.created_at),
        last_login_at=datetime.fromisoformat(user.last_login_at) if user.last_login_at else None
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        409: {"model": ErrorResponse, "description": "User already exists"}
    },
    summary="User registration",
    description="Create a new user account and return an access token"
)
async def register(request: UserRegisterRequest):
    """
    User registration

    Registration flow:
    1. Validate username and email format
    2. Check if username and email already exist
    3. Create user and generate access token
    """
    result = await user_service.register(
        username=request.username,
        email=request.email,
        password=request.password,
        display_name=request.display_name
    )

    if not result.success:
        # Determine whether it is a parameter error or a conflict error
        if "already exists" in result.error or "already registered" in result.error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.error
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return AuthResponse(
        user=_user_to_response(result.user),
        token=TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
            expires_in=result.token.expires_in
        )
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication failed"}
    },
    summary="User login",
    description="Log in with username/email and password"
)
async def login(request: UserLoginRequest):
    """
    User login

    Login flow:
    1. Find user by username or email
    2. Verify password
    3. Generate and return access token
    """
    result = await user_service.login(
        username_or_email=request.username_or_email,
        password=request.password
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error
        )

    return AuthResponse(
        user=_user_to_response(result.user),
        token=TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
            expires_in=result.token.expires_in
        )
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User logout",
    description="Invalidate the current access token"
)
async def logout(authorization: Optional[str] = Header(None)):
    """
    User logout

    Invalidate the current token
    """
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            await user_service.logout(parts[1])


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    },
    summary="Get current user info",
    description="Get information about the currently logged-in user"
)
async def get_me(user: UserData = Depends(get_current_user)):
    """Get current user info"""
    return _user_to_response(user)


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"}
    },
    summary="Update current user profile",
    description="Update the display name and avatar of the currently logged-in user"
)
async def update_me(
    request: UpdateProfileRequest,
    user: UserData = Depends(get_current_user),
):
    """Update user profile"""

    result = await user_service.update_profile(
        user_id=user.user_id,
        display_name=request.display_name,
        avatar_url=request.avatar_url
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return _user_to_response(result.user)


@router.post(
    "/me/change-password",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized or incorrect old password"},
        400: {"model": ErrorResponse, "description": "New password does not meet requirements"}
    },
    summary="Change password",
    description="Change the password of the currently logged-in user"
)
async def change_password(
    request: ChangePasswordRequest,
    user: UserData = Depends(get_current_user),
):
    """Change password"""

    result = await user_service.change_password(
        user_id=user.user_id,
        old_password=request.old_password,
        new_password=request.new_password
    )

    if not result.success:
        if "old password" in result.error.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.error
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return _user_to_response(result.user)


@router.get(
    "/me/stats",
    response_model=UserWithStatsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    },
    summary="Get current user stats",
    description="Get current user info with story and session counts"
)
async def get_me_stats(user: UserData = Depends(get_current_user)):
    """Get current user info with content statistics"""

    from ...services.database import user_repo
    user_with_stats = await user_repo.get_with_stats(user.user_id)

    if not user_with_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserWithStatsResponse(
        user_id=user_with_stats.user_id,
        username=user_with_stats.username,
        email=user_with_stats.email,
        display_name=user_with_stats.display_name,
        avatar_url=user_with_stats.avatar_url,
        is_active=user_with_stats.is_active,
        is_verified=user_with_stats.is_verified,
        created_at=datetime.fromisoformat(user_with_stats.created_at),
        last_login_at=datetime.fromisoformat(user_with_stats.last_login_at) if user_with_stats.last_login_at else None,
        story_count=user_with_stats.story_count,
        session_count=user_with_stats.session_count,
    )


@router.get(
    "/me/stories",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    },
    summary="Get current user's stories",
    description="Get paginated list of stories created by the current user"
)
async def get_me_stories(
    limit: int = 20,
    offset: int = 0,
    user: UserData = Depends(get_current_user),
):
    """Get current user's stories with pagination"""

    from ...services.database import user_repo
    result = await user_repo.get_user_stories(user.user_id, limit=limit, offset=offset)
    return result


@router.get(
    "/me/sessions",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    },
    summary="Get current user's sessions",
    description="Get paginated list of interactive story sessions for the current user"
)
async def get_me_sessions(
    status: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status_filter"),
    limit: int = 20,
    offset: int = 0,
    user: UserData = Depends(get_current_user),
):
    """Get current user's interactive story sessions with pagination"""

    effective_status = status if status is not None else status_filter

    from ...services.database import user_repo
    result = await user_repo.get_user_sessions(
        user.user_id, status=effective_status, limit=limit, offset=offset
    )
    return result


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        404: {"model": ErrorResponse, "description": "User not found"}
    },
    summary="Get user info",
    description="Get public user information by user ID"
)
async def get_user(user_id: str):
    """
    Get public information for a specified user
    """
    from ...services.database import user_repo

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return _user_to_response(user)
