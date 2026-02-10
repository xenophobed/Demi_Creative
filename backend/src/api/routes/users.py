"""
User API Routes

用户认证和管理 API 端点
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, status

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
from ...services.user_service import user_service, UserData


router = APIRouter(
    prefix="/api/v1/users",
    tags=["用户认证"]
)


def _user_to_response(user: UserData) -> UserResponse:
    """将UserData转换为UserResponse"""
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


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserData:
    """
    从请求头获取当前用户

    Args:
        authorization: Authorization header

    Returns:
        UserData: 当前用户

    Raises:
        HTTPException: 未授权或令牌无效
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌"
        )

    # 解析 Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌格式错误"
        )

    token = parts[1]
    user = await user_service.validate_token(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌无效或已过期"
        )

    return user


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        409: {"model": ErrorResponse, "description": "用户已存在"}
    },
    summary="用户注册",
    description="创建新用户账户并返回访问令牌"
)
async def register(request: UserRegisterRequest):
    """
    用户注册

    注册流程:
    1. 验证用户名和邮箱格式
    2. 检查用户名和邮箱是否已存在
    3. 创建用户并生成访问令牌
    """
    result = await user_service.register(
        username=request.username,
        email=request.email,
        password=request.password,
        display_name=request.display_name
    )

    if not result.success:
        # 判断是参数错误还是冲突错误
        if "已存在" in result.error or "已被注册" in result.error:
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
        401: {"model": ErrorResponse, "description": "认证失败"}
    },
    summary="用户登录",
    description="使用用户名/邮箱和密码登录"
)
async def login(request: UserLoginRequest):
    """
    用户登录

    登录流程:
    1. 通过用户名或邮箱查找用户
    2. 验证密码
    3. 生成并返回访问令牌
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
    summary="用户登出",
    description="使当前访问令牌失效"
)
async def logout(authorization: Optional[str] = Header(None)):
    """
    用户登出

    使当前令牌失效
    """
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            await user_service.logout(parts[1])


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授权"}
    },
    summary="获取当前用户信息",
    description="获取当前登录用户的信息"
)
async def get_me(authorization: Optional[str] = Header(None)):
    """
    获取当前用户信息

    需要在请求头中提供有效的访问令牌
    """
    user = await get_current_user(authorization)
    return _user_to_response(user)


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授权"},
        400: {"model": ErrorResponse, "description": "请求参数错误"}
    },
    summary="更新当前用户资料",
    description="更新当前登录用户的显示名称和头像"
)
async def update_me(
    request: UpdateProfileRequest,
    authorization: Optional[str] = Header(None)
):
    """
    更新用户资料

    可更新的字段:
    - display_name: 显示名称
    - avatar_url: 头像URL
    """
    user = await get_current_user(authorization)

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
        401: {"model": ErrorResponse, "description": "未授权或旧密码错误"},
        400: {"model": ErrorResponse, "description": "新密码不符合要求"}
    },
    summary="修改密码",
    description="修改当前登录用户的密码"
)
async def change_password(
    request: ChangePasswordRequest,
    authorization: Optional[str] = Header(None)
):
    """
    修改密码

    需要提供旧密码进行验证
    """
    user = await get_current_user(authorization)

    result = await user_service.change_password(
        user_id=user.user_id,
        old_password=request.old_password,
        new_password=request.new_password
    )

    if not result.success:
        if "旧密码" in result.error:
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
async def get_me_stats(authorization: Optional[str] = Header(None)):
    """Get current user info with content statistics"""
    user = await get_current_user(authorization)

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
    authorization: Optional[str] = Header(None),
):
    """Get current user's stories with pagination"""
    user = await get_current_user(authorization)

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
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
):
    """Get current user's interactive story sessions with pagination"""
    user = await get_current_user(authorization)

    from ...services.database import user_repo
    result = await user_repo.get_user_sessions(
        user.user_id, status=status_filter, limit=limit, offset=offset
    )
    return result


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        404: {"model": ErrorResponse, "description": "用户不存在"}
    },
    summary="获取用户信息",
    description="根据用户ID获取公开的用户信息"
)
async def get_user(user_id: str):
    """
    获取指定用户的公开信息
    """
    from ...services.database import user_repo

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    return _user_to_response(user)
