"""Supabase JWT token validation.

Validates access tokens issued by Supabase Auth. Extracts the user's
Supabase UID and email from the JWT claims so the backend can look up
or auto-create a matching local user row.

Issue: #318 | Parent Epic: #313
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

import jwt

logger = logging.getLogger(__name__)


@dataclass
class SupabaseClaims:
    """Decoded Supabase JWT claims relevant to user identification."""
    sub: str          # Supabase user ID (UUID)
    email: str
    email_confirmed: bool


def get_jwt_secret() -> Optional[str]:
    """Return the Supabase JWT secret from env, or None if not configured."""
    return os.getenv("SUPABASE_JWT_SECRET")


def decode_supabase_token(token: str) -> Optional[SupabaseClaims]:
    """Decode and validate a Supabase access token.

    Returns SupabaseClaims on success, None if the token is invalid or
    SUPABASE_JWT_SECRET is not configured (allows graceful fallback to
    legacy auth).
    """
    secret = get_jwt_secret()
    if not secret:
        return None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        sub = payload.get("sub")
        email = payload.get("email", "")
        # Supabase puts email confirmation in app_metadata or user_metadata
        user_meta = payload.get("user_metadata", {})
        email_confirmed = payload.get("email_confirmed_at") is not None or \
            user_meta.get("email_verified", False)

        if not sub:
            return None

        return SupabaseClaims(
            sub=sub,
            email=email,
            email_confirmed=email_confirmed,
        )
    except jwt.ExpiredSignatureError:
        logger.debug("Supabase token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid Supabase token: %s", e)
        return None
