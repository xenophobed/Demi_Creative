"""
User Service

User authentication and management service
"""

import hashlib
import base64
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass

from .database import user_repo, referral_repo, db_manager, UserData


@dataclass
class TokenData:
    """Token data"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # seconds
    user_id: str = ""


@dataclass
class AuthResult:
    """Authentication result"""
    success: bool
    user: Optional[UserData] = None
    token: Optional[TokenData] = None
    error: Optional[str] = None


class UserService:
    """User service class"""

    def __init__(self):
        self._repo = user_repo
        self._db = db_manager
        self._token_expiry_days = 30
        self._password_scheme = "pbkdf2_sha256"
        self._pbkdf2_iterations = 260000

    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a password

        Args:
            password: Plain-text password
            salt: Salt value (optional)

        Returns:
            Tuple[str, str]: (hash value, salt value)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            self._pbkdf2_iterations,
        )
        hash_value = base64.b64encode(derived_key).decode("ascii")
        return (
            f"{self._password_scheme}${self._pbkdf2_iterations}${salt}${hash_value}",
            salt,
        )

    def _hash_password_legacy(self, password: str, salt: str) -> str:
        """Legacy password hashing for backward compatibility."""
        salted = f"{salt}:{password}"
        hash_value = hashlib.sha256(salted.encode("utf-8")).hexdigest()
        return f"{salt}:{hash_value}"

    def _verify_password_with_rehash(self, password: str, stored_hash: str) -> Tuple[bool, bool]:
        """
        Verify password and indicate whether the hash should be upgraded.

        Returns:
            Tuple[bool, bool]: (is_valid, should_rehash)
        """
        if stored_hash.startswith(f"{self._password_scheme}$"):
            try:
                scheme, iterations_str, salt, expected_hash = stored_hash.split("$", 3)
                if scheme != self._password_scheme:
                    return False, False

                iterations = int(iterations_str)
                derived_key = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    iterations,
                )
                computed_hash = base64.b64encode(derived_key).decode("ascii")
                is_valid = secrets.compare_digest(computed_hash, expected_hash)
                should_rehash = is_valid and iterations < self._pbkdf2_iterations
                return is_valid, should_rehash
            except (ValueError, TypeError):
                return False, False

        # Legacy format: "salt:sha256"
        try:
            salt, _ = stored_hash.split(":", 1)
            computed_hash = self._hash_password_legacy(password, salt)
            is_valid = secrets.compare_digest(computed_hash, stored_hash)
            return is_valid, is_valid
        except ValueError:
            return False, False

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """
        Verify a password

        Args:
            password: Plain-text password
            stored_hash: Stored hash value

        Returns:
            bool: Whether the password is correct
        """
        is_valid, _ = self._verify_password_with_rehash(password, stored_hash)
        return is_valid

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a bearer token for storage using SHA-256."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def _revoke_all_tokens(self, user_id: str) -> None:
        """Delete all tokens for a user (e.g. after password change)."""
        await self._db.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,))
        await self._db.commit()

    async def _generate_token(self, user_id: str) -> TokenData:
        """
        Generate an access token and persist its hash to the database.

        The raw token is returned to the caller but only a SHA-256 hash
        is stored, so a database leak does not expose valid credentials.

        Args:
            user_id: User ID

        Returns:
            TokenData: Token data (contains the raw token for the client)
        """
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        now = datetime.now()
        expires_at = now + timedelta(days=self._token_expiry_days)

        await self._db.execute(
            "INSERT INTO tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, expires_at.isoformat(), now.isoformat())
        )
        await self._db.commit()

        return TokenData(
            access_token=token,
            token_type="bearer",
            expires_in=self._token_expiry_days * 86400,
            user_id=user_id
        )

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        referral_code: Optional[str] = None,
        role: str = "parent",
        parent_email: Optional[str] = None,
        child_id: Optional[str] = None,
        child_name: Optional[str] = None,
        child_age_group: Optional[str] = None,
        child_interests: Optional[list[str]] = None,
    ) -> AuthResult:
        """
        User registration

        Args:
            username: Username
            email: Email address
            password: Password
            display_name: Display name
            referral_code: Referral code from share link (optional)
            role: Account role. Parent is the primary supported setup path.
            parent_email: Required when role is child.
            child_id: Initial child profile id for parent-owned setup.
            child_name: Initial child profile nickname.
            child_age_group: Initial child profile age group.
            child_interests: Initial child profile interests.

        Returns:
            AuthResult: Registration result
        """
        # Validate username
        if len(username) < 3 or len(username) > 50:
            return AuthResult(success=False, error="Username must be between 3 and 50 characters")

        # Validate email format
        if "@" not in email or "." not in email:
            return AuthResult(success=False, error="Invalid email format")

        # Validate password strength
        if len(password) < 6:
            return AuthResult(success=False, error="Password must be at least 6 characters")

        if role not in {"parent", "child"}:
            return AuthResult(success=False, error="Role must be 'parent' or 'child'")

        if role == "child":
            if not parent_email:
                return AuthResult(
                    success=False,
                    error="Parent email is required for child sign-up",
                )
            if "@" not in parent_email or "." not in parent_email:
                return AuthResult(success=False, error="Invalid parent email format")

        # Check if username already exists
        if await self._repo.check_username_exists(username):
            return AuthResult(success=False, error="Username already exists")

        # Check if email already exists
        if await self._repo.check_email_exists(email):
            return AuthResult(success=False, error="Email already registered")

        # Look up referrer by code (silently ignore invalid codes)
        referred_by = None
        referrer_user_id = None
        if referral_code:
            referrer = await self._repo.get_by_referral_code(referral_code)
            if referrer:
                referred_by = referral_code
                referrer_user_id = referrer.user_id

        # Create user
        password_hash, _ = self._hash_password(password)
        user = await self._repo.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            parent_email=parent_email.lower() if parent_email else None,
            consent_status=(
                "not_required" if role == "parent" else "pending_parent_consent"
            ),
            referred_by=referred_by
        )

        if role == "parent" and child_id:
            await self._repo.update_onboarding_fields(
                user.user_id,
                default_child_id=child_id,
            )
            fresh_user = await self._repo.get_by_id(user.user_id)
            if fresh_user:
                user = fresh_user

        # Create referral record if valid referrer found
        if referrer_user_id:
            try:
                await referral_repo.create_referral(
                    referrer_user_id=referrer_user_id,
                    referred_user_id=user.user_id,
                    referral_code=referral_code
                )
            except Exception:
                pass  # Silently ignore (e.g. duplicate referral)

        # Generate token
        token = await self._generate_token(user.user_id)

        return AuthResult(
            success=True,
            user=user,
            token=token
        )

    def _approval_secret(self) -> bytes:
        secret = (
            os.getenv("PARENT_APPROVAL_SECRET")
            or os.getenv("SECRET_KEY")
            or "dev-parent-approval-secret"
        )
        return secret.encode("utf-8")

    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    @staticmethod
    def _b64decode(data: str) -> bytes:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii"))

    def create_parent_approval_token(
        self,
        user_id: str,
        parent_email: str,
        *,
        expires_in_seconds: int = 72 * 3600,
    ) -> str:
        """Create a signed, expiring token for parent approval."""
        payload = {
            "sub": user_id,
            "parent_email": parent_email.lower(),
            "exp": int(time.time()) + expires_in_seconds,
            "purpose": "parent_approval",
        }
        payload_bytes = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        body = self._b64encode(payload_bytes)
        signature = hmac.new(
            self._approval_secret(),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{body}.{self._b64encode(signature)}"

    def _decode_parent_approval_token(self, token: str) -> tuple[Optional[dict], Optional[str]]:
        try:
            body, signature = token.split(".", 1)
        except ValueError:
            return None, "Invalid approval token"

        expected = hmac.new(
            self._approval_secret(),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        try:
            provided = self._b64decode(signature)
        except Exception:
            return None, "Invalid approval token"

        if not hmac.compare_digest(expected, provided):
            return None, "Invalid approval token"

        try:
            payload = json.loads(self._b64decode(body).decode("utf-8"))
        except Exception:
            return None, "Invalid approval token"

        if payload.get("purpose") != "parent_approval":
            return None, "Invalid approval token"
        if int(payload.get("exp", 0)) < int(time.time()):
            return None, "Approval token has expired"

        return payload, None

    async def approve_parent_approval_token(self, token: str) -> AuthResult:
        """Approve a child-started account from a signed parent token."""
        payload, error = self._decode_parent_approval_token(token)
        if error:
            return AuthResult(success=False, error=error)

        user = await self._repo.get_by_id(payload["sub"])
        if not user:
            return AuthResult(success=False, error="User not found")
        if user.role != "child":
            return AuthResult(success=False, error="Only child-started accounts require approval")
        if not user.parent_email or user.parent_email.lower() != payload["parent_email"]:
            return AuthResult(success=False, error="Approval token does not match account")
        if user.consent_status != "pending_parent_consent":
            return AuthResult(success=False, error="Account is not pending parent approval")

        await self._repo.update_consent_status(user.user_id, "approved")
        approved_user = await self._repo.get_by_id(user.user_id)
        return AuthResult(success=True, user=approved_user or user)

    async def qualify_and_maybe_upgrade(self, referred_user_id: str) -> bool:
        """Qualify a referral and auto-upgrade the referrer if threshold reached.

        Called when a referred user verifies their email.

        Returns:
            True if the referrer was upgraded to Plus tier.
        """
        qualified = await referral_repo.qualify_referral(referred_user_id)
        if not qualified:
            return False

        ref = await referral_repo.get_referral_by_referred_user(referred_user_id)
        if not ref:
            return False

        referrer_id = ref["referrer_user_id"]
        referrer = await self._repo.get_by_id(referrer_id)
        if not referrer or referrer.membership_tier == "plus":
            return False

        if await referral_repo.check_upgrade_eligible(referrer_id):
            await self._repo.update_membership_tier(referrer_id, "plus")
            return True

        return False

    async def login(
        self,
        username_or_email: str,
        password: str
    ) -> AuthResult:
        """
        User login

        Args:
            username_or_email: Username or email
            password: Password

        Returns:
            AuthResult: Login result
        """
        # Try to find user by username or email
        user = await self._repo.get_by_username(username_or_email)
        if not user:
            user = await self._repo.get_by_email(username_or_email)

        if not user:
            return AuthResult(success=False, error="User not found")

        if not user.is_active:
            return AuthResult(success=False, error="Account has been disabled")

        # Verify password
        is_valid, should_rehash = self._verify_password_with_rehash(password, user.password_hash)
        if not is_valid:
            return AuthResult(success=False, error="Incorrect password")

        if should_rehash:
            upgraded_hash, _ = self._hash_password(password)
            await self._repo.update_user(user.user_id, password_hash=upgraded_hash)
            user.password_hash = upgraded_hash

        # Update last login time
        await self._repo.update_last_login(user.user_id)

        # Generate token
        token = await self._generate_token(user.user_id)

        return AuthResult(
            success=True,
            user=user,
            token=token
        )

    async def logout(self, token: str) -> bool:
        """
        User logout

        Args:
            token: Access token

        Returns:
            bool: Whether successful
        """
        token_hash = self._hash_token(token)
        row = await self._db.fetchone("SELECT id FROM tokens WHERE token = ?", (token_hash,))
        if row:
            await self._db.execute("DELETE FROM tokens WHERE token = ?", (token_hash,))
            await self._db.commit()
            return True
        return False

    async def validate_token(self, token: str) -> Optional[UserData]:
        """
        Validate a token

        Args:
            token: Access token

        Returns:
            UserData or None
        """
        token_hash = self._hash_token(token)
        row = await self._db.fetchone(
            "SELECT user_id, expires_at FROM tokens WHERE token = ?", (token_hash,)
        )
        if not row:
            return None

        # Check if expired
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            await self._db.execute("DELETE FROM tokens WHERE token = ?", (token_hash,))
            await self._db.commit()
            return None

        return await self._repo.get_by_id(row["user_id"])

    async def get_current_user(self, token: str) -> Optional[UserData]:
        """
        Get current user (alias for validate_token)

        Args:
            token: Access token

        Returns:
            UserData or None
        """
        return await self.validate_token(token)

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> AuthResult:
        """
        Change password

        Args:
            user_id: User ID
            old_password: Old password
            new_password: New password

        Returns:
            AuthResult: Operation result
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            return AuthResult(success=False, error="User not found")

        # Verify old password
        if not self._verify_password(old_password, user.password_hash):
            return AuthResult(success=False, error="Incorrect old password")

        # Validate new password
        if len(new_password) < 6:
            return AuthResult(success=False, error="New password must be at least 6 characters")

        # Update password
        new_hash, _ = self._hash_password(new_password)
        await self._repo.update_user(user_id, password_hash=new_hash)

        # Revoke all existing tokens so stolen tokens cannot survive a password change
        await self._revoke_all_tokens(user_id)

        return AuthResult(success=True, user=user)

    async def update_profile(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> AuthResult:
        """
        Update user profile

        Args:
            user_id: User ID
            display_name: Display name
            avatar_url: Avatar URL

        Returns:
            AuthResult: Operation result
        """
        success = await self._repo.update_user(
            user_id,
            display_name=display_name,
            avatar_url=avatar_url
        )

        if not success:
            return AuthResult(success=False, error="User not found")

        user = await self._repo.get_by_id(user_id)
        return AuthResult(success=True, user=user)

    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens

        Returns:
            int: Number of tokens cleaned up
        """
        now = datetime.now().isoformat()
        rows = await self._db.fetchall(
            "SELECT id FROM tokens WHERE expires_at < ?", (now,)
        )
        if rows:
            await self._db.execute("DELETE FROM tokens WHERE expires_at < ?", (now,))
            await self._db.commit()
        return len(rows)


# Global user service instance
user_service = UserService()
