"""Supabase JWT token validation.

Validates access tokens issued by Supabase Auth. Extracts the user's
Supabase UID and email from the JWT claims so the backend can look up
or auto-create a matching local user row.

Supports both:
- ES256 (asymmetric, JWKS) — newer Supabase projects (default since 2025)
- HS256 (symmetric, JWT secret) — older Supabase projects

Issue: #318 | Parent Epic: #313
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Cache the JWKS client to avoid fetching keys on every request
_jwks_client: Optional[PyJWKClient] = None


@dataclass
class SupabaseClaims:
    """Decoded Supabase JWT claims relevant to user identification."""
    sub: str          # Supabase user ID (UUID)
    email: str
    email_confirmed: bool


def get_jwt_secret() -> Optional[str]:
    """Return the Supabase JWT secret from env, or None if not configured."""
    return os.getenv("SUPABASE_JWT_SECRET")


def _get_jwks_client() -> Optional[PyJWKClient]:
    """Return a cached JWKS client for the Supabase project, or None."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        return None

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def decode_supabase_token(token: str) -> Optional[SupabaseClaims]:
    """Decode and validate a Supabase access token.

    Tries JWKS (ES256) first, falls back to HS256 with SUPABASE_JWT_SECRET.
    Returns SupabaseClaims on success, None if the token is invalid or
    no Supabase auth is configured.
    """
    claims = _decode_with_jwks(token)
    if claims:
        return claims

    return _decode_with_secret(token)


def _decode_with_jwks(token: str) -> Optional[SupabaseClaims]:
    """Decode token using JWKS (ES256)."""
    client = _get_jwks_client()
    if not client:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return _extract_claims(payload)
    except jwt.ExpiredSignatureError:
        logger.debug("Supabase token expired (JWKS)")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid Supabase token (JWKS): %s", e)
        return None
    except Exception as e:
        logger.debug("JWKS decode error: %s", e)
        return None


def _decode_with_secret(token: str) -> Optional[SupabaseClaims]:
    """Decode token using HS256 with SUPABASE_JWT_SECRET (legacy)."""
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
        return _extract_claims(payload)
    except jwt.ExpiredSignatureError:
        logger.debug("Supabase token expired (HS256)")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid Supabase token (HS256): %s", e)
        return None


def _extract_claims(payload: dict) -> Optional[SupabaseClaims]:
    """Extract SupabaseClaims from a decoded JWT payload."""
    sub = payload.get("sub")
    if not sub:
        return None

    email = payload.get("email", "")
    user_meta = payload.get("user_metadata", {})
    email_confirmed = payload.get("email_confirmed_at") is not None or \
        user_meta.get("email_verified", False)

    return SupabaseClaims(
        sub=sub,
        email=email,
        email_confirmed=email_confirmed,
    )
