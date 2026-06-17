"""
Ephemeral JWT for Talk-to-Buddy realtime voice handshake (#614).

The REST `/voice/session` endpoint mints one of these for the client.
The client passes it in the WebSocket query string (`?token=...`); the
WS broker (#615) calls ``verify_voice_token`` once at handshake time.

Hard rules from PRD §3.16:
  - Single-use — verifying consumes the ``jti``. A replay returns None.
  - Short-lived — 60s TTL. Clients must reconnect via REST if the WS
    drops; there is no refresh.
  - Purpose-scoped — the ``purpose`` claim distinguishes voice tokens
    from any other JWT the codebase mints (parent-approval, Supabase
    session, etc.) so the secret can't be cross-used.

In-memory nonce storage is fine for v1 single-process deploy. A
``TODO(scale)`` notes the Redis migration path for multi-worker prod.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

import jwt

logger = logging.getLogger(__name__)

# Hard constants from PRD §3.16.4.
TOKEN_TTL_SECONDS: int = 60
TOKEN_ALGORITHM: str = "HS256"
TOKEN_PURPOSE: str = "voice_realtime"

# In-memory nonce set. Maps jti → expiration timestamp (float seconds).
# Lazy sweep on every verify call keeps the set bounded — entries TTL
# out in ≤60s so the set can never grow past TOKEN_TTL_SECONDS × mint
# rate. Bytes-wise this is O(KB) even at 100 req/s.
#
# TODO(scale): in-process nonce set is only correct with exactly one
# process/replica — see assert_single_process_or_warn() + #684. Future
# fix = DB-backed nonce on the voice_sessions row (or Redis) so the
# replay guard holds across multiple uvicorn workers.
_USED_JTIS: Dict[str, float] = {}


def assert_single_process_or_warn() -> None:
    """Warn loudly if multiple workers are configured while the nonce
    store is in-process. The in-memory _USED_JTIS replay guard is only
    correct with exactly one process/replica. See #684 for the
    DB-backed nonce migration path."""
    for var in ("WEB_CONCURRENCY", "UVICORN_WORKERS"):
        raw = os.getenv(var)
        if not raw:
            continue
        try:
            workers = int(raw)
        except (TypeError, ValueError):
            continue
        if workers > 1:
            logger.warning(
                "%s=%s configured but the voice token replay guard "
                "(_USED_JTIS) is an in-process nonce store — single-use "
                "voice tokens are NOT safe across multiple workers/replicas. "
                "See #684: migrate to a DB-backed nonce on the voice_sessions "
                "row before scaling out.",
                var,
                workers,
            )


def _signing_secret() -> str:
    """Resolve the signing key with the same fallback chain as parent-approval JWT.

    Priority:
      1. VOICE_REALTIME_TOKEN_SECRET — dedicated env var
      2. SECRET_KEY — general app secret
      3. dev fallback (logs WARNING once)
    """
    secret = os.getenv("VOICE_REALTIME_TOKEN_SECRET") or os.getenv("SECRET_KEY")
    if secret:
        return secret
    if not getattr(_signing_secret, "_warned", False):
        logger.warning(
            "voice_ephemeral_token using insecure dev fallback secret — "
            "set VOICE_REALTIME_TOKEN_SECRET or SECRET_KEY for production"
        )
        _signing_secret._warned = True  # type: ignore[attr-defined]
    return "dev-voice-realtime-secret"


@dataclass(frozen=True)
class VoiceTokenClaims:
    """Decoded payload — exposed to the broker for downstream auth checks."""
    session_id: str
    user_id: str
    child_id: str
    purpose: str
    jti: str
    iat: int
    exp: int


def mint_voice_token(
    *,
    session_id: str,
    user_id: str,
    child_id: str,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    """Create a single-use HS256 token for a fresh voice session.

    The caller (REST `/voice/session` route in #615) should always pair
    a mint with a `voice_session_repo.create_session(...)` write so the
    audit row exists when the WS handshake completes.
    """
    now = int(time.time())
    ttl = max(0, int(ttl_seconds))
    payload: Dict[str, Any] = {
        "sub": user_id,
        "session_id": session_id,
        "child_id": child_id,
        "purpose": TOKEN_PURPOSE,
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(payload, _signing_secret(), algorithm=TOKEN_ALGORITHM)
    # PyJWT ≥2.0 returns str; ≤1.x returned bytes. Be defensive.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def _sweep_expired_jtis(now: float) -> None:
    """Drop nonce entries whose token expiration has passed."""
    expired = [jti for jti, exp in _USED_JTIS.items() if exp < now]
    for jti in expired:
        _USED_JTIS.pop(jti, None)


def verify_voice_token(token: str) -> Optional[VoiceTokenClaims]:
    """Validate signature + expiration + purpose + nonce.

    Consumes the ``jti`` on success — a second call with the same token
    returns ``None`` (replay protection). Returns ``None`` on any failure:
    bad signature, expired, wrong purpose, replay, malformed payload.
    """
    # Sweep BEFORE decode so even malformed inputs (or the broker
    # spamming us with auth_failed retries) keep the nonce store from
    # holding on to expired entries forever.
    _sweep_expired_jtis(time.time())

    try:
        payload = jwt.decode(
            token,
            _signing_secret(),
            algorithms=[TOKEN_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    purpose = payload.get("purpose")
    if purpose != TOKEN_PURPOSE:
        return None

    jti = payload.get("jti")
    if not jti or not isinstance(jti, str):
        return None

    if jti in _USED_JTIS:
        # Replay — refuse and do not extend the nonce TTL.
        return None

    # Required fields — surface any missing ones as a failure rather
    # than letting them flow into the broker as silent defaults.
    session_id = payload.get("session_id")
    child_id = payload.get("child_id")
    if not session_id or not child_id:
        return None

    # Consume the nonce — even if the broker subsequently rejects the
    # session for consent/quota reasons, the token itself is spent.
    _USED_JTIS[jti] = float(payload["exp"])

    return VoiceTokenClaims(
        session_id=session_id,
        user_id=payload["sub"],
        child_id=child_id,
        purpose=purpose,
        jti=jti,
        iat=int(payload["iat"]),
        exp=int(payload["exp"]),
    )


def _reset_nonce_store_for_tests() -> None:
    """Test-only helper. Clears the in-memory nonce set between tests."""
    _USED_JTIS.clear()
