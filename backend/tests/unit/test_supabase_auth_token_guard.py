"""Regression tests for the Supabase token structural guard (#740).

Legacy accounts authenticate with opaque `secrets.token_urlsafe(32)` tokens
that are NOT JWTs. `decode_supabase_token` must skip these cheaply and
silently — no `jwt.decode`, no WARNING log spam — while still validating and
warning on genuine (3-segment) JWTs.
"""

import logging
import secrets

import jwt
import pytest

from backend.src.services import supabase_auth
from backend.src.services.supabase_auth import decode_supabase_token


@pytest.fixture
def hs256_secret(monkeypatch):
    secret = "test-supabase-jwt-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    # Ensure the JWKS path is a no-op so we exercise the HS256 branch.
    monkeypatch.setattr(supabase_auth, "_jwks_keys", [])
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    return secret


def test_legacy_opaque_token_is_skipped_without_warning(hs256_secret, caplog):
    """A non-JWT legacy token returns None and emits no warning."""
    legacy_token = secrets.token_urlsafe(32)  # no dots -> not a JWT
    assert "." not in legacy_token or legacy_token.count(".") != 2

    with caplog.at_level(logging.WARNING, logger="backend.src.services.supabase_auth"):
        result = decode_supabase_token(legacy_token)

    assert result is None
    assert "Not enough segments" not in caplog.text
    assert "Invalid Supabase token" not in caplog.text


def test_malformed_jwt_still_warns(hs256_secret, caplog):
    """A structurally-valid (3-segment) but bogus JWT still logs a warning."""
    bogus_jwt = "aaaa.bbbb.cccc"  # 3 segments, undecodable signature

    with caplog.at_level(logging.WARNING, logger="backend.src.services.supabase_auth"):
        result = decode_supabase_token(bogus_jwt)

    assert result is None
    assert "Invalid Supabase token" in caplog.text


def test_valid_hs256_jwt_decodes(hs256_secret):
    """A correctly signed Supabase HS256 JWT still decodes to claims."""
    token = jwt.encode(
        {
            "sub": "user-uuid-123",
            "email": "kid@example.com",
            "aud": "authenticated",
            "email_confirmed_at": "2026-01-01T00:00:00Z",
        },
        hs256_secret,
        algorithm="HS256",
    )

    claims = decode_supabase_token(token)

    assert claims is not None
    assert claims.sub == "user-uuid-123"
    assert claims.email == "kid@example.com"
