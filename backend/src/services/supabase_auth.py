"""Supabase JWT token validation (httpx JWKS).

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
from typing import Optional, Any

import jwt
import httpx

logger = logging.getLogger(__name__)

# Cache fetched JWKS keys to avoid HTTP calls on every request
_jwks_keys: Optional[list[dict[str, Any]]] = None


@dataclass
class SupabaseClaims:
    """Decoded Supabase JWT claims relevant to user identification."""
    sub: str          # Supabase user ID (UUID)
    email: str
    email_confirmed: bool
    referral_code: Optional[str] = None  # From signUp metadata (#424)
    role: str = "parent"
    parent_email: Optional[str] = None
    child_id: Optional[str] = None


def get_jwt_secret() -> Optional[str]:
    """Return the Supabase JWT secret from env, or None if not configured."""
    return os.getenv("SUPABASE_JWT_SECRET")


def _fetch_jwks_keys() -> Optional[list[dict[str, Any]]]:
    """Fetch and cache JWKS keys from the Supabase project."""
    global _jwks_keys
    if _jwks_keys is not None:
        return _jwks_keys

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        return None

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()
        _jwks_keys = response.json().get("keys", [])
        logger.info("Fetched %d JWKS keys from %s", len(_jwks_keys), jwks_url)
        return _jwks_keys
    except Exception as e:
        logger.warning("Failed to fetch JWKS from %s: %s", jwks_url, e)
        return None


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
    keys = _fetch_jwks_keys()
    if not keys:
        return None

    # Find the matching key by kid from the token header
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        return None

    kid = unverified_header.get("kid")
    matching_key = None
    for key_data in keys:
        if key_data.get("kid") == kid:
            matching_key = key_data
            break

    if not matching_key:
        logger.warning("No JWKS key found matching kid=%s", kid)
        return None

    try:
        from jwt.algorithms import ECAlgorithm
        public_key = ECAlgorithm.from_jwk(matching_key)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return _extract_claims(payload)
    except jwt.ExpiredSignatureError:
        logger.warning("Supabase token expired (JWKS)")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid Supabase token (JWKS): %s", e)
        return None
    except Exception as e:
        logger.warning("JWKS decode error: %s", e)
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
        logger.warning("Supabase token expired (HS256)")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid Supabase token (HS256): %s", e)
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

    referral_code = user_meta.get("referral_code")
    requested_role = user_meta.get("role") or "parent"
    role = requested_role if requested_role in {"parent", "child"} else "parent"
    parent_email = user_meta.get("parent_email")
    child_id = user_meta.get("child_id")

    return SupabaseClaims(
        sub=sub,
        email=email,
        email_confirmed=email_confirmed,
        referral_code=referral_code,
        role=role,
        parent_email=parent_email,
        child_id=child_id,
    )
