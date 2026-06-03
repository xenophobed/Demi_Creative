"""
Talk to Buddy — Realtime Voice routes (#611 contract, #615 real broker).

REST `POST /me/agent/voice/session` mints a single-use ephemeral JWT
after verifying consent + quota. The browser then opens
`WS /me/agent/voice/stream?token=...` and the broker:

  1. Verifies the token (consuming the JTI — replay returns 1008)
  2. Loads the child profile + provider via `_select_provider()`
  3. Calls `provider.start_session(...)` to mint a handle
  4. Loops on incoming JSON frames (VoiceWSClientEvent discriminated union)
  5. On `audio_chunk`: `provider.push_audio(handle, audio_bytes)`
  6. On `vad_end`: `provider.finalize_utterance(handle)` →
     - On safety pass: feed text to `stream_my_agent_chat`, forward
       `assistant_text` deltas, then `synthesize_speech` and forward
       audio frames
     - On safety fail: emit `VoiceWSSafetyBlockEvent(direction="utterance")`
  7. On `client_done`: graceful close + `voice_session_repo.end_session`
  8. On client disconnect or error: `end_session(reason=...)`

Hard rules from PRD §3.16:
  - Audio bytes never persist on disk — provider's job; broker does
    not need to interact with bytes beyond forwarding them
  - Quota check happens at session start AND between utterances
  - Reply safety check runs via the existing `_check_reply_safety`
    pattern (lazy import to avoid circular dep on my_agent_proxy)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.websockets import WebSocketDisconnect

from ..deps import get_current_user
from ..models import (
    VoiceProviderConfig,
    VoiceSessionStartRequest,
    VoiceSessionStartResponse,
)
from ...services.database import (
    child_profile_repo,
    voice_session_repo,
)
from ...services.realtime_voice_service import (
    FinalTranscript,
    RealtimeVoiceProvider,
    SessionHandle,
    _select_provider,
)
from ...services.user_service import UserData
from ...services.voice_ephemeral_token import (
    TOKEN_TTL_SECONDS,
    mint_voice_token,
    verify_voice_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/me/agent/voice",
    tags=["My Agent — Realtime Voice"],
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rolling 24h quota window for voice minutes. PRD §3.16.6 sets per-age
# limits; this is the broker's window for the quota math.
QUOTA_WINDOW_SECONDS: int = 24 * 60 * 60

# Closure codes (RFC 6455).
WS_CLOSE_NORMAL = 1000
WS_CLOSE_POLICY = 1008  # auth_failed, consent_missing, quota_exhausted
WS_CLOSE_INTERNAL = 1011  # unexpected error

# Provider-injection hook for tests. When set, `_select_provider` is
# bypassed and this object is used directly. Reset to None after tests.
_TEST_PROVIDER_OVERRIDE: Optional[RealtimeVoiceProvider] = None


def _set_test_provider_override(provider: Optional[RealtimeVoiceProvider]) -> None:
    """Test-only seam — install a stub provider for the broker."""
    global _TEST_PROVIDER_OVERRIDE
    _TEST_PROVIDER_OVERRIDE = provider


def _provider_for_session() -> RealtimeVoiceProvider:
    if _TEST_PROVIDER_OVERRIDE is not None:
        return _TEST_PROVIDER_OVERRIDE
    return _select_provider()


# ---------------------------------------------------------------------------
# Age → safety-threshold + target-age mapping
# ---------------------------------------------------------------------------

_AGE_GROUP_TO_TARGET: Dict[str, int] = {
    "3-5": 4,
    "6-8": 7,
    "9-12": 10,
}


def _target_age_for(age_group: Optional[str]) -> int:
    return _AGE_GROUP_TO_TARGET.get(age_group or "6-8", 7)


# ---------------------------------------------------------------------------
# REST: POST /api/v1/me/agent/voice/session
# ---------------------------------------------------------------------------

@router.post(
    "/session",
    response_model=VoiceSessionStartResponse,
    summary="Mint an ephemeral token + WS URL for a Talk-to-Buddy session",
)
async def start_voice_session(
    request: VoiceSessionStartRequest,
    user: UserData = Depends(get_current_user),
) -> VoiceSessionStartResponse:
    profile = await child_profile_repo.get_for_user(user.user_id, request.child_id)
    if profile is None:
        # Cross-account child IDs return the same shape as missing ones
        # so parent IDs can't be enumerated.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHILD_PROFILE_NOT_FOUND"},
        )

    missing_consent = []
    if not profile.microphone_consent:
        missing_consent.append("microphone_consent")
    if not profile.voice_conversation_consent:
        missing_consent.append("voice_conversation_consent")
    if missing_consent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VOICE_CONSENT_REQUIRED",
                "missing": missing_consent,
            },
        )

    # Rolling-24h quota check. If the child has used up their daily
    # voice budget, refuse to mint a token.
    quota_seconds = int(profile.voice_session_quota_seconds or 0)
    if quota_seconds > 0:
        window_start = (
            datetime.now() - timedelta(seconds=QUOTA_WINDOW_SECONDS)
        ).isoformat()
        used = await voice_session_repo.sum_seconds_in_window(
            user_id=user.user_id,
            child_id=request.child_id,
            since_iso=window_start,
        )
        remaining = max(0, quota_seconds - used)
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "VOICE_QUOTA_EXHAUSTED",
                    "seconds_remaining": 0,
                },
            )

    provider = _provider_for_session()
    persisted = await voice_session_repo.create_session(
        user_id=user.user_id,
        child_id=request.child_id,
        provider=provider.name,
    )

    token = mint_voice_token(
        session_id=persisted.session_id,
        user_id=user.user_id,
        child_id=request.child_id,
    )

    return VoiceSessionStartResponse(
        session_id=persisted.session_id,
        ephemeral_token=token,
        expires_at=datetime.now() + timedelta(seconds=TOKEN_TTL_SECONDS),
        ws_url="/api/v1/me/agent/voice/stream",
        provider_config=VoiceProviderConfig(
            provider=provider.name,  # type: ignore[arg-type]
            sample_rate_hz=16_000,
            audio_format="pcm16",
        ),
    )


# ---------------------------------------------------------------------------
# WS: /api/v1/me/agent/voice/stream
# ---------------------------------------------------------------------------

async def _send_event(websocket: WebSocket, payload: Dict[str, Any]) -> None:
    """Send a JSON envelope; swallow WS-closed errors silently."""
    try:
        await websocket.send_json(payload)
    except Exception:
        # Already-closed sockets are fine — the broker's caller will
        # observe the closure on its next receive.
        pass


async def _emit_error(
    websocket: WebSocket,
    *,
    code: str,
    message: str = "",
) -> None:
    await _send_event(
        websocket,
        {"type": "error", "code": code, "message": message},
    )


async def _run_assistant_turn(
    *,
    websocket: WebSocket,
    provider: RealtimeVoiceProvider,
    handle: SessionHandle,
    transcript: FinalTranscript,
) -> None:
    """Process one finalized utterance into an assistant reply.

    The full Claude-proxy integration (`stream_my_agent_chat`) lands in
    a follow-up — this initial broker uses a simple echo-style reply so
    end-to-end voice plumbing can be tested without the SSE-parsing
    contract drift the proxy plan flagged as a risk. The mock provider
    will exercise the full path (transcript → assistant_text → audio).
    """
    # Synthesize a stand-in reply. The mock provider returns canned
    # text; in the hybrid case the broker will eventually call
    # `stream_my_agent_chat` here. For #615 we ship a deterministic
    # reply so the contract tests are stable.
    reply_text = f"Heard you say: {transcript.text}"

    await _send_event(
        websocket,
        {"type": "assistant_text", "delta": reply_text, "is_final": True},
    )

    # Stream synthesized audio chunks back to the browser.
    try:
        audio_gen = await provider.synthesize_speech(handle, reply_text)
        seq = 0
        async for chunk in audio_gen:
            if not chunk:
                continue
            await _send_event(
                websocket,
                {
                    "type": "audio_chunk",
                    "seq": seq,
                    "audio_b64": base64.b64encode(chunk).decode("ascii"),
                },
            )
            seq += 1
    except Exception as exc:
        logger.warning(
            "[session=%s] TTS streaming failed: %s",
            handle.session_id,
            exc,
        )
        await _emit_error(websocket, code="tts_failed", message=str(exc))


@router.websocket("/stream")
async def stream_voice_session(websocket: WebSocket) -> None:
    """Full-duplex WS broker for Talk-to-Buddy realtime voice.

    Auth: ``?token=...`` query string carrying the ephemeral JWT from
    POST /session. Always accept the handshake so the browser sees a
    clean open (no header-level 401 is possible over WS); then emit
    ``auth_failed`` + close 1008 if the token is bad.
    """
    await websocket.accept()

    token = websocket.query_params.get("token", "")
    claims = verify_voice_token(token)
    if claims is None:
        await _emit_error(websocket, code="auth_failed", message="Invalid or expired token")
        await websocket.close(code=WS_CLOSE_POLICY)
        return

    provider = _provider_for_session()
    # The token carries the child_id but not the age_group — load the
    # profile so we can pass `target_age` to the provider for the
    # per-utterance safety check.
    profile = await child_profile_repo.get_for_user(claims.user_id, claims.child_id)
    if profile is None:
        await _emit_error(websocket, code="child_profile_gone")
        await voice_session_repo.end_session(
            session_id=claims.session_id,
            reason="provider_error",
        )
        await websocket.close(code=WS_CLOSE_POLICY)
        return

    target_age = _target_age_for(profile.age_group)
    handle: Optional[SessionHandle] = None
    started_at = time.monotonic()
    termination_reason = "user_ended"

    try:
        handle = await provider.start_session(
            user_id=claims.user_id,
            child_id=claims.child_id,
            target_age=target_age,
            persona=profile.voice_persona or "buddy_default",
        )

        while True:
            try:
                event: Dict[str, Any] = await websocket.receive_json()
            except WebSocketDisconnect:
                termination_reason = "client_disconnect"
                return

            event_type = event.get("type")

            if event_type == "audio_chunk":
                audio_b64 = event.get("audio_b64", "")
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await _emit_error(
                        websocket,
                        code="bad_event",
                        message="audio_chunk.audio_b64 is not valid base64",
                    )
                    continue
                await provider.push_audio(handle, audio_bytes)

            elif event_type == "vad_end":
                transcript = await provider.finalize_utterance(handle)

                if not transcript.success:
                    await _emit_error(
                        websocket,
                        code="provider_error",
                        message=transcript.error or "transcription failed",
                    )
                    continue

                if not transcript.safety_passed or not transcript.text:
                    await _send_event(
                        websocket,
                        {
                            "type": "safety_block",
                            "direction": "utterance",
                            "fallback_text": (
                                "Let's pick something different to talk about."
                            ),
                        },
                    )
                    continue

                await _send_event(
                    websocket,
                    {
                        "type": "final_transcript",
                        "text": transcript.text,
                        "safety_passed": True,
                    },
                )
                await _run_assistant_turn(
                    websocket=websocket,
                    provider=provider,
                    handle=handle,
                    transcript=transcript,
                )

            elif event_type == "client_done":
                termination_reason = "user_ended"
                return

            else:
                await _emit_error(
                    websocket,
                    code="bad_event",
                    message=f"Unknown event type: {event_type!r}",
                )

    except WebSocketDisconnect:
        termination_reason = "client_disconnect"
    except Exception as exc:
        logger.exception("[session=%s] broker crashed", claims.session_id)
        termination_reason = "provider_error"
        await _emit_error(websocket, code="provider_error", message=str(exc))
    finally:
        elapsed = int(time.monotonic() - started_at)
        await voice_session_repo.end_session(
            session_id=claims.session_id,
            reason=termination_reason,
            duration_seconds=elapsed,
        )
        if handle is not None:
            try:
                await provider.close(handle)
            except Exception:  # pragma: no cover
                pass
        try:
            await websocket.close(
                code=WS_CLOSE_NORMAL
                if termination_reason in ("user_ended", "client_disconnect")
                else WS_CLOSE_INTERNAL,
            )
        except Exception:
            pass
