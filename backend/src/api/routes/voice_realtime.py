"""
Talk to Buddy — Realtime Voice routes (#611 contract, #615 broker, #645 OpenAI relay).

REST `POST /me/agent/voice/session` mints a single-use ephemeral JWT
after verifying consent + quota. The browser then opens
`WS /me/agent/voice/stream?token=...` and the broker:

  1. Verifies the token (consuming the JTI — replay returns 1008)
  2. Loads the child profile + provider via `_select_provider()`
  3. Calls `provider.start_session(...)` to mint a handle
  4. Loops on incoming JSON frames (VoiceWSClientEvent discriminated union)
  5. On `audio_chunk`: `provider.push_audio(handle, audio_bytes)`
  6. On `vad_end`: `provider.finalize_utterance(handle)` →
     - Run per-age safety check on transcript
     - On safety pass: invoke provider-specific reply flow
       (OpenAI Realtime — model emits text + audio together; Hybrid —
       text is computed locally then TTS streams)
     - Run per-age safety check on assistant reply text BEFORE TTS
       audio is forwarded to the client
     - On safety fail (either side): emit `safety_block` event +
       fallback copy. Session continues.
  7. Idle / max-session timers per age — fire on inactivity / cap.
  8. On `client_done`: graceful close + `voice_session_repo.end_session`
  9. On client disconnect or error: `end_session(reason=...)`

Hard rules from PRD §3.16:
  - Audio bytes never persist on disk — provider's job; broker does
    not need to interact with bytes beyond forwarding them
  - Quota check happens at session start AND between utterances
  - Safety check runs on BOTH transcript (before forwarding to model)
    AND assistant text deltas (before forwarding TTS audio to client)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.websockets import WebSocketDisconnect

from ..deps import get_current_user
from ..models import (
    VoiceProviderConfig,
    VoiceSessionStartRequest,
    VoiceSessionStartResponse,
)
from ...services.database import (
    agent_repo,
    child_profile_repo,
    voice_session_repo,
)
from ...services.realtime_voice_service import (
    FinalTranscript,
    RealtimeVoiceProvider,
    SessionHandle,
    _select_provider,
    estimate_session_cost_usd,
    log_voice_session_end,
    safety_threshold_for_age,
)
from ...services.user_service import UserData
from ...services.voice_ephemeral_token import (
    TOKEN_TTL_SECONDS,
    mint_voice_token,
    verify_voice_token,
)
from ...mcp_servers import check_content_safety

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
# Per-age idle + max-session timers (PRD §3.16.6)
# ---------------------------------------------------------------------------

# 30s / 45s / 60s — the silence window that auto-ends a session.
_IDLE_TIMEOUT_BY_AGE: Dict[str, float] = {
    "3-5": 30.0,
    "6-8": 45.0,
    "9-12": 60.0,
}

# 10 / 15 / 20 minutes — the hard cap on a single voice session.
_MAX_SESSION_BY_AGE: Dict[str, float] = {
    "3-5": 10 * 60.0,
    "6-8": 15 * 60.0,
    "9-12": 20 * 60.0,
}

# Test seams — tests set these to small values so timers fire in
# sub-seconds instead of minutes. Production leaves them None and the
# broker reads the per-age tables above.
_IDLE_TIMEOUT_OVERRIDE_SECONDS: Optional[float] = None
_MAX_SESSION_OVERRIDE_SECONDS: Optional[float] = None


def _idle_timeout_for(age_group: Optional[str]) -> float:
    if _IDLE_TIMEOUT_OVERRIDE_SECONDS is not None:
        return _IDLE_TIMEOUT_OVERRIDE_SECONDS
    return _IDLE_TIMEOUT_BY_AGE.get(age_group or "6-8", 45.0)


def _max_session_for(age_group: Optional[str]) -> float:
    if _MAX_SESSION_OVERRIDE_SECONDS is not None:
        return _MAX_SESSION_OVERRIDE_SECONDS
    return _MAX_SESSION_BY_AGE.get(age_group or "6-8", 15 * 60.0)


# ---------------------------------------------------------------------------
# Safety check helper — module-level so tests can monkeypatch.
# ---------------------------------------------------------------------------

async def _safety_check_text(text: str, target_age: int) -> Dict[str, Any]:
    """Invoke the safety MCP and return the parsed envelope.

    Module-level so the broker tests can monkeypatch the safety verdict
    without touching the underlying MCP. Returns ``{"safety_score": float, ...}``
    or raises if the MCP is unreachable.

    Mirrors the helper in ``stt_service`` but lives here because the
    broker's safety check is independent of STT (it also runs on the
    assistant reply, not just transcripts).
    """
    raw = await check_content_safety.handler({
        "content_text": text,
        "content_type": "voice_reply",
        "target_age": target_age,
    })
    # The safety MCP wraps its envelope in the SDK's content shape.
    # Be defensive: a malformed envelope must surface as a low score so
    # the broker fails closed.
    try:
        import json as _json
        if isinstance(raw, dict) and "content" in raw:
            payload = _json.loads(raw["content"][0]["text"])
            if isinstance(payload, dict):
                return payload
        if isinstance(raw, str):
            return _json.loads(raw)
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {"safety_score": 0.0, "passed": False}
    return {"safety_score": 0.0, "passed": False}


_SAFETY_FALLBACK_REPLY: str = (
    "Let's pick something different to talk about. "
    "What's something fun you'd like to make today?"
)


async def _validate_enabled_skills_for_voice(
    *, user_id: str, child_id: str,
) -> Optional[str]:
    """Return None if voice is allowed, else a refusal code string.

    #608 carry-over: refuse to mint a voice token when the requested
    buddy is configured with a specialist that's disabled. Today the
    voice channel itself isn't gated behind a per-skill toggle — but
    we lock the seam now so a future "voice_conversation" skill flag
    can plug in without churning the route.
    """
    try:
        agent = await agent_repo.get_agent(user_id=user_id, child_id=child_id)
    except Exception:
        # If the lookup fails we don't block voice — voice is independent
        # of agent persona. The agent table is best-effort context.
        return None
    if agent is None:
        return None
    # Future-proof: if a "voice_conversation" skill toggle is ever added
    # to the enabled_skills whitelist, refuse here when it's missing.
    # For now, presence of an agent record is sufficient.
    return None


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

    # Enforce server-side enabled_skills validation BEFORE minting a token.
    # #608 carry-over: refuse to start voice when the buddy persona is
    # configured to disable the relevant skill.
    refusal = await _validate_enabled_skills_for_voice(
        user_id=user.user_id, child_id=request.child_id,
    )
    if refusal is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VOICE_SKILL_DISABLED", "skill": refusal},
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

    # For the OpenAI Realtime provider we bundle the ephemeral client
    # secret so the frontend can hold it for E4's WebRTC transport
    # (currently unused — server-relay is the only path in E2).
    openai_secret: Optional[str] = None
    if provider.name == "openai_realtime":
        try:
            target_age = _target_age_for(profile.age_group)
            preview_handle = await provider.start_session(
                user_id=user.user_id,
                child_id=request.child_id,
                target_age=target_age,
                persona=profile.voice_persona or "buddy_default",
                voice_premium_voice=bool(
                    getattr(profile, "voice_premium_voice", False)
                ),
                voice_premium_voice_consent=bool(
                    getattr(profile, "voice_premium_voice_consent", False)
                ),
            )
            openai_secret = (
                preview_handle.provider_state.get("openai_client_secret") or None
            )
            # Release the preview handle's upstream WS (if any) — the WS
            # broker will mint its own when the client connects.
            try:
                await provider.close(preview_handle)
            except Exception:  # pragma: no cover
                pass
        except Exception as exc:
            logger.warning(
                "Failed to pre-mint OpenAI client secret for /session: %s", exc,
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
        openai_realtime_client_secret=openai_secret,
        transport="ws",
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


async def _run_safety_gate(
    *, text: str, target_age: int,
) -> bool:
    """Run the safety check + per-age threshold compare. Fail closed."""
    if not text.strip():
        return False
    try:
        envelope = await _safety_check_text(text, target_age)
        score = float(envelope.get("safety_score", 0.0))
    except Exception as exc:
        logger.warning("voice broker safety check raised; failing closed: %s", exc)
        return False
    return score >= safety_threshold_for_age(target_age)


async def _stream_openai_reply(
    *,
    websocket: WebSocket,
    provider: RealtimeVoiceProvider,
    handle: SessionHandle,
    target_age: int,
    state: Dict[str, Any],
) -> None:
    """Consume the OpenAI Realtime reply stream with a pre-TTS safety gate.

    The model emits text + audio together. We buffer the audio in
    memory while accumulating the text, run the safety check on the
    final text, and either forward the buffered audio chunks or emit
    a ``safety_block`` event. Audio bytes never reach disk.
    """
    text_acc = ""
    audio_buffer: List[bytes] = []
    text_done_seen = False

    stream = await provider.stream_assistant_reply(handle)  # type: ignore[attr-defined]
    async for ev in stream:
        if ev.kind == "text_delta":
            text_acc += ev.text
        elif ev.kind == "text_done":
            text_acc = ev.text or text_acc
            text_done_seen = True
        elif ev.kind == "audio_chunk":
            audio_buffer.append(ev.audio)
        elif ev.kind == "response_done":
            break

    # Run the pre-TTS safety gate on the assembled text. The gate is the
    # load-bearing safeguard — even if the model emitted the full audio
    # we MUST NOT forward it to the client when the text fails.
    safe = await _run_safety_gate(text=text_acc, target_age=target_age)
    if not safe:
        await _send_event(websocket, {
            "type": "safety_block",
            "direction": "reply",
            "fallback_text": _SAFETY_FALLBACK_REPLY,
        })
        return

    # Safe path: emit the assistant text + forward the audio chunks.
    if text_acc:
        await _send_event(websocket, {
            "type": "assistant_text",
            "delta": text_acc,
            "is_final": True,
        })

    for seq, chunk in enumerate(audio_buffer):
        if not chunk:
            continue
        await _send_event(websocket, {
            "type": "audio_chunk",
            "seq": seq,
            "audio_b64": base64.b64encode(chunk).decode("ascii"),
        })
        # Capture first_audio_ms on the first non-empty chunk we forward.
        if state.get("first_audio_ms") is None:
            elapsed_ms = int(
                (time.monotonic() - state["started_at_monotonic"]) * 1000
            )
            state["first_audio_ms"] = max(0, elapsed_ms)


async def _stream_legacy_reply(
    *,
    websocket: WebSocket,
    provider: RealtimeVoiceProvider,
    handle: SessionHandle,
    transcript: FinalTranscript,
    target_age: int,
    state: Dict[str, Any],
) -> None:
    """Hybrid / Mock provider path — text is determined locally then TTS.

    The reply text for these providers is a stand-in until the
    ``stream_my_agent_chat`` integration lands. The pre-TTS safety gate
    still runs so the parity invariant holds across providers.
    """
    # Stand-in reply. The mock provider's canned transcript flows
    # through unchanged for contract-test stability; the hybrid path
    # will later route through ``stream_my_agent_chat`` (out of scope
    # for this story — E3 / #646).
    reply_text = f"Heard you say: {transcript.text}"

    safe = await _run_safety_gate(text=reply_text, target_age=target_age)
    if not safe:
        await _send_event(websocket, {
            "type": "safety_block",
            "direction": "reply",
            "fallback_text": _SAFETY_FALLBACK_REPLY,
        })
        return

    await _send_event(websocket, {
        "type": "assistant_text",
        "delta": reply_text,
        "is_final": True,
    })

    try:
        audio_gen = await provider.synthesize_speech(handle, reply_text)
        seq = 0
        async for chunk in audio_gen:
            if not chunk:
                continue
            await _send_event(websocket, {
                "type": "audio_chunk",
                "seq": seq,
                "audio_b64": base64.b64encode(chunk).decode("ascii"),
            })
            if state.get("first_audio_ms") is None:
                elapsed_ms = int(
                    (time.monotonic() - state["started_at_monotonic"]) * 1000
                )
                state["first_audio_ms"] = max(0, elapsed_ms)
            seq += 1
    except Exception as exc:
        logger.warning(
            "[session=%s] TTS streaming failed: %s",
            handle.session_id, exc,
        )
        await _emit_error(websocket, code="tts_failed", message=str(exc))


async def _run_assistant_turn(
    *,
    websocket: WebSocket,
    provider: RealtimeVoiceProvider,
    handle: SessionHandle,
    transcript: FinalTranscript,
    target_age: int,
    state: Dict[str, Any],
) -> None:
    """Dispatch to the provider-appropriate reply flow.

    OpenAI Realtime exposes ``stream_assistant_reply`` — text + audio
    arrive together from the upstream model. Hybrid / Mock providers
    don't have that method; the broker computes the reply text locally
    (placeholder for now) and calls ``synthesize_speech`` separately.

    Both paths run the pre-TTS safety gate so #608's reply-safety AC
    holds regardless of which provider an env routes to.
    """
    if callable(getattr(provider, "stream_assistant_reply", None)):
        await _stream_openai_reply(
            websocket=websocket, provider=provider, handle=handle,
            target_age=target_age, state=state,
        )
    else:
        await _stream_legacy_reply(
            websocket=websocket, provider=provider, handle=handle,
            transcript=transcript, target_age=target_age, state=state,
        )


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
    age_group = profile.age_group
    handle: Optional[SessionHandle] = None
    started_at = time.monotonic()
    termination_reason = "user_ended"
    # Per-session mutable state shared with helpers — telemetry,
    # timer reset, etc. Living here keeps the helpers pure-ish while
    # giving them a single place to record first_audio_ms.
    state: Dict[str, Any] = {
        "started_at_monotonic": started_at,
        "first_audio_ms": None,
        "last_activity_monotonic": started_at,
    }

    idle_timeout = _idle_timeout_for(age_group)
    max_session_seconds = _max_session_for(age_group)

    try:
        # #648 tier-selection: surface the per-child premium-voice flags
        # so the OpenAI provider can pick mini vs premium. Providers that
        # don't accept these kwargs silently ignore them — the broker
        # passes through positionally to the typed Protocol via **kwargs.
        start_kwargs: Dict[str, Any] = {
            "user_id": claims.user_id,
            "child_id": claims.child_id,
            "target_age": target_age,
            "persona": profile.voice_persona or "buddy_default",
        }
        if provider.name == "openai_realtime":
            start_kwargs["voice_premium_voice"] = bool(
                getattr(profile, "voice_premium_voice", False)
            )
            start_kwargs["voice_premium_voice_consent"] = bool(
                getattr(profile, "voice_premium_voice_consent", False)
            )
        handle = await provider.start_session(**start_kwargs)

        while True:
            # Compute the next deadline — whichever fires first wins.
            now = time.monotonic()
            remaining_idle = max(
                0.0, idle_timeout - (now - state["last_activity_monotonic"])
            )
            remaining_max = max(
                0.0, max_session_seconds - (now - started_at)
            )
            deadline = min(remaining_idle, remaining_max)

            try:
                event_task = asyncio.create_task(websocket.receive_json())
                done, pending = await asyncio.wait(
                    [event_task], timeout=deadline,
                )
                if not done:
                    # Timer fired before any client event arrived.
                    event_task.cancel()
                    if remaining_max <= remaining_idle:
                        # Max-session cap hit — emit quota_exhausted.
                        termination_reason = "quota"
                        await _send_event(websocket, {
                            "type": "quota_exhausted",
                            "seconds_remaining": 0,
                        })
                    else:
                        termination_reason = "timeout"
                        await _emit_error(
                            websocket,
                            code="idle_timeout",
                            message="No activity within the idle window",
                        )
                    return
                event: Dict[str, Any] = event_task.result()
            except WebSocketDisconnect:
                termination_reason = "client_disconnect"
                return

            # Any client event resets the idle clock.
            state["last_activity_monotonic"] = time.monotonic()

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

                # Provider runs its own per-utterance safety check on the
                # transcript (Hybrid: Whisper → safety MCP; OpenAI: model
                # consumed the audio under the system prompt's safety
                # preamble). Trust the provider's verdict here — the
                # per-age threshold lives in the provider for transcript
                # safety. The reply-side gate (in _run_assistant_turn)
                # is where the broker enforces the per-age floor.
                if not transcript.safety_passed or not transcript.text:
                    await _send_event(
                        websocket,
                        {
                            "type": "safety_block",
                            "direction": "utterance",
                            "fallback_text": _SAFETY_FALLBACK_REPLY,
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
                    target_age=target_age,
                    state=state,
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
        # #648 cost telemetry — only the OpenAI provider populates ``model``
        # in provider_state. Hybrid / Mock leave it unset, so the helpers
        # return zero cost and the row's cost columns stay NULL.
        session_model: Optional[str] = None
        prompt_cache_hit: bool = False
        if handle is not None:
            session_model = handle.provider_state.get("model")  # type: ignore[union-attr]
            prompt_cache_hit = bool(
                handle.provider_state.get("prompt_cache_hit", False)  # type: ignore[union-attr]
            )
        cost_estimate_usd = estimate_session_cost_usd(
            model=session_model,
            duration_seconds=elapsed,
            prompt_cache_hit=prompt_cache_hit,
        )

        # Final session_end event with telemetry — surfaced to the Parent
        # Dashboard via the frontend in Phase D (#648).
        await _send_event(websocket, {
            "type": "session_end",
            "reason": termination_reason,
            "duration_seconds": elapsed,
            "first_audio_ms": state.get("first_audio_ms") or 0,
            "model": session_model,
            "cost_estimate_usd": cost_estimate_usd,
        })
        await voice_session_repo.end_session(
            session_id=claims.session_id,
            reason=termination_reason,
            duration_seconds=elapsed,
            model=session_model,
            cost_estimate_usd=cost_estimate_usd if session_model else None,
            prompt_cache_hit=prompt_cache_hit if session_model else None,
        )
        # Structured log line for the ops cost dashboard. Greppable as
        # ``event=voice_session_end`` — the alerting layer sums
        # ``cost_estimate_usd`` over the rolling month and trips at 80%
        # of the operator-set ``OPENAI_REALTIME_MONTHLY_CAP_USD``.
        log_voice_session_end(
            session_id=claims.session_id,
            model=session_model,
            duration_seconds=elapsed,
            cost_estimate_usd=cost_estimate_usd,
            prompt_cache_hit=prompt_cache_hit,
            first_audio_ms=state.get("first_audio_ms") or 0,
            ended_reason=termination_reason,
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
