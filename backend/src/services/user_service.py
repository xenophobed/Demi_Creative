"""
User Service

用户认证和管理服务
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass

from .database import user_repo, UserData


@dataclass
class TokenData:
    """令牌数据"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # 秒
    user_id: str = ""


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    user: Optional[UserData] = None
    token: Optional[TokenData] = None
    error: Optional[str] = None


class UserService:
    """用户服务类"""

    def __init__(self):
        self._repo = user_repo
        # 简单的内存令牌存储 (生产环境应使用Redis)
        self._tokens: dict[str, Tuple[str, datetime]] = {}
        self._token_expiry_hours = 24

    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        哈希密码

        Args:
            password: 明文密码
            salt: 盐值（可选）

        Returns:
            Tuple[str, str]: (哈希值, 盐值)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        # 使用PBKDF2-like方式
        salted = f"{salt}:{password}"
        hash_value = hashlib.sha256(salted.encode()).hexdigest()
        return f"{salt}:{hash_value}", salt

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """
        验证密码

        Args:
            password: 明文密码
            stored_hash: 存储的哈希值

        Returns:
            bool: 密码是否正确
        """
        try:
            salt, _ = stored_hash.split(":", 1)
            computed_hash, _ = self._hash_password(password, salt)
            return secrets.compare_digest(computed_hash, stored_hash)
        except ValueError:
            return False

    def _generate_token(self, user_id: str) -> TokenData:
        """
        生成访问令牌

        Args:
            user_id: 用户ID

        Returns:
            TokenData: 令牌数据
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=self._token_expiry_hours)
        self._tokens[token] = (user_id, expires_at)

        return TokenData(
            access_token=token,
            token_type="bearer",
            expires_in=self._token_expiry_hours * 3600,
            user_id=user_id
        )

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None
    ) -> AuthResult:
        """
        用户注册

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            display_name: 显示名称

        Returns:
            AuthResult: 注册结果
        """
        # 验证用户名
        if len(username) < 3 or len(username) > 50:
            return AuthResult(success=False, error="用户名长度必须在3-50个字符之间")

        # 验证邮箱格式
        if "@" not in email or "." not in email:
            return AuthResult(success=False, error="邮箱格式不正确")

        # 验证密码强度
        if len(password) < 6:
            return AuthResult(success=False, error="密码长度至少6个字符")

        # 检查用户名是否存在
        if await self._repo.check_username_exists(username):
            return AuthResult(success=False, error="用户名已存在")

        # 检查邮箱是否存在
        if await self._repo.check_email_exists(email):
            return AuthResult(success=False, error="邮箱已被注册")

        # 创建用户
        password_hash, _ = self._hash_password(password)
        user = await self._repo.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name
        )

        # 生成令牌
        token = self._generate_token(user.user_id)

        return AuthResult(
            success=True,
            user=user,
            token=token
        )

    async def login(
        self,
        username_or_email: str,
        password: str
    ) -> AuthResult:
        """
        用户登录

        Args:
            username_or_email: 用户名或邮箱
            password: 密码

        Returns:
            AuthResult: 登录结果
        """
        # 尝试用用户名或邮箱查找用户
        user = await self._repo.get_by_username(username_or_email)
        if not user:
            user = await self._repo.get_by_email(username_or_email)

        if not user:
            return AuthResult(success=False, error="用户不存在")

        if not user.is_active:
            return AuthResult(success=False, error="账户已被禁用")

        # 验证密码
        if not self._verify_password(password, user.password_hash):
            return AuthResult(success=False, error="密码错误")

        # 更新最后登录时间
        await self._repo.update_last_login(user.user_id)

        # 生成令牌
        token = self._generate_token(user.user_id)

        return AuthResult(
            success=True,
            user=user,
            token=token
        )

    async def logout(self, token: str) -> bool:
        """
        用户登出

        Args:
            token: 访问令牌

        Returns:
            bool: 是否成功
        """
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    async def validate_token(self, token: str) -> Optional[UserData]:
        """
        验证令牌

        Args:
            token: 访问令牌

        Returns:
            UserData 或 None
        """
        if token not in self._tokens:
            return None

        user_id, expires_at = self._tokens[token]

        # 检查是否过期
        if datetime.now() > expires_at:
            del self._tokens[token]
            return None

        return await self._repo.get_by_id(user_id)

    async def get_current_user(self, token: str) -> Optional[UserData]:
        """
        获取当前用户（validate_token的别名）

        Args:
            token: 访问令牌

        Returns:
            UserData 或 None
        """
        return await self.validate_token(token)

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> AuthResult:
        """
        修改密码

        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            AuthResult: 操作结果
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            return AuthResult(success=False, error="用户不存在")

        # 验证旧密码
        if not self._verify_password(old_password, user.password_hash):
            return AuthResult(success=False, error="旧密码错误")

        # 验证新密码
        if len(new_password) < 6:
            return AuthResult(success=False, error="新密码长度至少6个字符")

        # 更新密码
        new_hash, _ = self._hash_password(new_password)
        await self._repo.update_user(user_id, password_hash=new_hash)

        return AuthResult(success=True, user=user)

    async def update_profile(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> AuthResult:
        """
        更新用户资料

        Args:
            user_id: 用户ID
            display_name: 显示名称
            avatar_url: 头像URL

        Returns:
            AuthResult: 操作结果
        """
        success = await self._repo.update_user(
            user_id,
            display_name=display_name,
            avatar_url=avatar_url
        )

        if not success:
            return AuthResult(success=False, error="用户不存在")

        user = await self._repo.get_by_id(user_id)
        return AuthResult(success=True, user=user)

    def cleanup_expired_tokens(self) -> int:
        """
        清理过期令牌

        Returns:
            int: 清理的令牌数量
        """
        now = datetime.now()
        expired = [
            token for token, (_, expires_at) in self._tokens.items()
            if now > expires_at
        ]
        for token in expired:
            del self._tokens[token]
        return len(expired)


# 全局用户服务实例
user_service = UserService()
