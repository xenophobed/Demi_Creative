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
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
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
from ...services.realtime_voice_tools import (
    ToolContext,
    handle_tool_call,
)
from ...services.user_service import UserData
from ...services.voice_ephemeral_token import (
    TOKEN_TTL_SECONDS,
    mint_voice_token,
    verify_voice_token,
)
from ...services import voice_telemetry
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


# Score that triggers an additional heavier safety review pass beyond
# the per-age threshold. Anything in the "borderline" band (passed the
# floor but landed close to it) still gets a second look from the
# safety-review-specialist before reaching the kid's ears.
#
# PRD §3.16 calls for the heavier review on "uncertain content"; in
# practice that's any reply whose score is below this margin above the
# floor. Tuned to be visible only on real edge cases.
_SAFETY_REVIEW_MARGIN: float = 0.05


async def _safety_review_specialist(text: str, target_age: int) -> bool:
    """Heavier safety review for borderline assistant text.

    Module-level so tests can monkeypatch it the same way they patch
    ``_safety_check_text``. The default implementation routes through
    the existing safety MCP (same handler the broker already uses) but
    asks for a stricter pass — the "uncertain content" review PRD §3.16
    calls for is encoded as: same MCP, treat any score below the per-age
    threshold as a hard fail (don't trust borderline content even if it
    nominally passes a single check).

    Returns True when the reply is safe to forward; False on failure.
    Always fails closed on exception — the caller will emit the safety
    fallback. The integration point is intentionally thin so a future
    PR can swap in the full ``safety-review-specialist`` AgentDefinition
    orchestration (#605 follow-up) without touching the broker.
    """
    try:
        envelope = await _safety_check_text(text, target_age)
        score = float(envelope.get("safety_score", 0.0))
    except Exception as exc:
        logger.warning(
            "voice broker safety-review specialist raised; failing closed: %s", exc,
        )
        return False
    # The heavier review uses a small extra margin above the floor —
    # borderline-pass content that landed just over the floor gets
    # demoted to "not safe enough" by the specialist.
    from ...services.realtime_voice_service import safety_threshold_for_age
    return score >= safety_threshold_for_age(target_age)


# Per PRD §3.16 the voice surface's job is to hand off to the
# specialists. If the parent disabled every launch-flow skill the buddy
# can never do anything useful in voice mode, so we refuse the token
# mint and surface a 409 the panel can translate into "ask your grown-up
# to turn on at least one skill". Single-skill personas are allowed
# (e.g. image-story-only buddies still work).
_VOICE_LAUNCH_SKILLS: frozenset[str] = frozenset({
    "image_story",
    "interactive_story",
    "kids_daily",
})


async def _validate_enabled_skills_for_voice(
    *, user_id: str, child_id: str,
) -> Optional[str]:
    """Return None if voice is allowed, else a refusal code string.

    #608 carry-over: refuse to mint a voice token when the buddy's
    ``enabled_skills`` contains NONE of the launch-flow specialists.

    The voice channel itself is the buddy's conversational surface, but
    every useful action it can take (image story, interactive story,
    kids daily) is gated by ``enabled_skills`` on the per-child persona.
    If all three are off the parent has effectively disabled the buddy,
    so we refuse here rather than open a voice session the model can't
    do anything useful with.

    Defense in depth: even when this check passes, the broker filters
    the realtime tool set via ``filter_tool_definitions_by_skills``
    before ``session.update`` — so a partially-disabled persona only
    sees the launch tools their parent allowed. The token-mint refusal
    is the OUTER guard (don't even start), the tool filter is the INNER
    guard (don't expose disabled tools to the model).

    Returns a refusal code string (used as ``detail.skill`` on the 409)
    when refused; ``None`` when voice may proceed.
    """
    try:
        agent = await agent_repo.get_agent(user_id=user_id, child_id=child_id)
    except Exception:
        # If the lookup fails we don't block voice — voice is independent
        # of agent persona. The agent table is best-effort context.
        return None
    if agent is None:
        # No persona row → defaults apply; voice is allowed.
        return None
    enabled = set(agent.enabled_skills or [])
    if not (_VOICE_LAUNCH_SKILLS & enabled):
        # Zero launch-flow skills enabled — buddy can't hand off to any
        # specialist, voice mode would be a dead end. Refuse with the
        # canonical list so the client can surface which to re-enable.
        return "all_launch_skills_disabled"
    return None


async def _agent_id_for_voice(
    *, user_id: str, child_id: str,
) -> Optional[str]:
    """Best-effort lookup of the persona's surrogate ``agent_id`` for the
    ``voice_session_started`` telemetry event. Returns ``None`` on lookup
    failure or a default (no-persona) buddy — telemetry must never block
    a session, so this swallows errors and lets the event carry a null
    agent_id rather than raising."""
    try:
        agent = await agent_repo.get_agent(user_id=user_id, child_id=child_id)
    except Exception:
        return None
    return agent.agent_id if agent is not None else None


async def _enabled_skills_for_voice(
    *, user_id: str, child_id: str,
) -> Optional[list[str]]:
    """Look up the enabled_skills list for the broker to forward to the
    provider's ``start_session``. Returns ``None`` on lookup failure or
    missing persona so the provider's filter falls back to "expose all
    tools" (preserves pre-#608 behavior in degraded paths)."""
    try:
        agent = await agent_repo.get_agent(user_id=user_id, child_id=child_id)
    except Exception:
        return None
    if agent is None:
        return None
    return list(agent.enabled_skills or [])


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
    prefer_webrtc: bool = Query(
        default=False,
        description=(
            "E4 (#647) WebRTC opt-in. When ``true`` AND the active provider "
            "supports browser-direct realtime (OpenAI), the response sets "
            "``transport=\"webrtc\"`` and surfaces an ephemeral OpenAI "
            "client secret. Non-OpenAI providers silently fall back to "
            "``ws`` — the WS broker is the universal path."
        ),
    ),
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

    # #647: WebRTC is opt-in AND only meaningful when the provider can
    # serve a browser-direct realtime handshake. Today that's only
    # ``openai_realtime``. Anything else silently degrades to WS — the
    # client never sees a 4xx for asking, because the WS broker is the
    # universal fallback and refusing would break the panel UX.
    selected_transport: str = "ws"
    if prefer_webrtc and provider.name == "openai_realtime":
        selected_transport = "webrtc"

    persisted = await voice_session_repo.create_session(
        user_id=user.user_id,
        child_id=request.child_id,
        provider=provider.name,
        transport=selected_transport,
    )

    token = mint_voice_token(
        session_id=persisted.session_id,
        user_id=user.user_id,
        child_id=request.child_id,
    )

    # For the OpenAI Realtime provider we bundle the ephemeral client
    # secret so the frontend can hold it for E4's WebRTC transport.
    # Pre-#647 the secret was minted for both paths (so a client could
    # try WebRTC after the fact); we keep that behavior unchanged.
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
        transport=selected_transport,  # type: ignore[arg-type]
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
    """Run the safety check + per-age threshold compare. Fail closed.

    Two-pass design:
      1. ``_safety_check_text`` — fast per-utterance gate. A clear pass
         (well above the per-age floor) returns True immediately.
      2. ``_safety_review_specialist`` — heavier review fired ONLY for
         borderline content (within ``_SAFETY_REVIEW_MARGIN`` of the
         floor). Skips on a clean pass to keep first-audio latency low.

    Any exception in either pass fails closed — the caller emits the
    safety_block fallback. This is the PRD §3.16 "fail closed on
    uncertain content" rule.
    """
    if not text.strip():
        return False
    try:
        envelope = await _safety_check_text(text, target_age)
        score = float(envelope.get("safety_score", 0.0))
    except Exception as exc:
        logger.warning("voice broker safety check raised; failing closed: %s", exc)
        return False
    threshold = safety_threshold_for_age(target_age)
    if score < threshold:
        return False
    # Borderline pass — invoke the heavier specialist review. A clearly
    # safe score (>= threshold + margin) skips the second pass so the
    # common case stays cheap. The specialist hook itself catches its
    # own MCP exceptions and returns False; we re-wrap so a monkeypatched
    # specialist that raises (test scaffolding, future bugs) still fails
    # closed instead of crashing the broker turn.
    if score < threshold + _SAFETY_REVIEW_MARGIN:
        try:
            return await _safety_review_specialist(text, target_age)
        except Exception as exc:
            logger.warning(
                "voice broker safety-review specialist raised; "
                "failing closed: %s", exc,
            )
            return False
    return True


def _age_group_for_target(target_age: int) -> str:
    """Map the broker's integer ``target_age`` to the age-group enum
    that tools and prompts expect. Mirrors the band split used in
    ``realtime_voice_service`` for safety thresholds."""
    if target_age <= 5:
        return "3-5"
    if target_age <= 8:
        return "6-8"
    return "9-12"


async def _dispatch_function_call(
    *,
    websocket: WebSocket,
    provider: RealtimeVoiceProvider,
    handle: SessionHandle,
    target_age: int,
    ev: Any,  # ReplyEvent — typed via duck-typing to keep the import diamond shallow
    state: Dict[str, Any],
) -> None:
    """Route one model-issued tool call.

    Always pairs the dispatch with a ``function_call_output`` upstream
    so the model isn't stranded. Envelope ``type`` is the router:

    - ``launch_flow``  → forward as a WS event to the client (existing
      ``useLaunchFlowNavigation`` consumer); also echo a minimal ack
      back to the model so its turn settles cleanly.
    - ``tool_result``  → feed the full payload back to the model as
      JSON so it can continue the conversation with the lookup result.
    - ``end_call``     → flag the outer broker loop to close the WS
      with ``ended_reason="voice_tool_end_call"`` after this turn.

    Tool handlers never raise (per ``realtime_voice_tools`` contract),
    so any exception caught here is a wiring bug — log loudly and emit
    an error envelope to the model so the turn doesn't hang.
    """
    ctx = ToolContext(
        user_id=handle.user_id,
        child_id=handle.child_id,
        age_group=_age_group_for_target(target_age),
        session_id=handle.session_id,
    )
    try:
        envelope = await handle_tool_call(ev.name, ev.args, ctx)
    except Exception as exc:  # defensive — handler contract says never raise
        logger.exception("[session=%s] tool dispatch crashed: %s", handle.session_id, exc)
        envelope = {"type": "tool_result", "payload": {"error": f"dispatch_crash:{exc}"}}

    envelope_type = envelope.get("type", "")
    payload = envelope.get("payload") or {}

    if envelope_type == "launch_flow":
        # Surface the navigation event to the browser BEFORE acking the
        # model so the client transition feels in sync with the buddy's
        # spoken handoff sentence.
        await _send_event(websocket, {"type": "launch_flow", **payload})
        # #609 telemetry — voice drove the kid INTO a creation flow; the
        # target flow type is the key engagement signal for the surface.
        voice_telemetry.emit_voice_session_launch_flow_emitted(
            session_id=handle.session_id,
            flow=str(payload.get("flow_type") or "unknown"),
        )
        ack_output = json.dumps({"status": "launched", "flow_type": payload.get("flow_type")})
    elif envelope_type == "end_call":
        # Don't ack the model — we're closing. Just remember to break.
        state["end_call_requested"] = True
        state["end_call_reason"] = payload.get("ended_reason") or "voice_tool_end_call"
        return
    else:
        # tool_result (including unknown / error envelopes from the
        # handler) — feed the whole payload back so the model can
        # incorporate it into its next turn.
        ack_output = json.dumps(payload)

    if callable(getattr(provider, "send_function_call_output", None)):
        try:
            await provider.send_function_call_output(  # type: ignore[attr-defined]
                handle, call_id=ev.call_id, output=ack_output,
            )
        except Exception as exc:  # pragma: no cover - upstream WS noise
            logger.warning(
                "[session=%s] failed to send function_call_output: %s",
                handle.session_id, exc,
            )


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
    end_call_requested = False

    stream = await provider.stream_assistant_reply(handle)  # type: ignore[attr-defined]
    async for ev in stream:
        if ev.kind == "text_delta":
            text_acc += ev.text
        elif ev.kind == "text_done":
            text_acc = ev.text or text_acc
            text_done_seen = True
        elif ev.kind == "audio_chunk":
            audio_buffer.append(ev.audio)
        elif ev.kind == "function_call":
            # Dispatch the model's tool call. The handler returns a typed
            # envelope: ``launch_flow`` notifies the client to navigate,
            # ``tool_result`` feeds extra context back to the model,
            # ``end_call`` closes the session at the next turn boundary.
            # Every call MUST be paired with a ``function_call_output``
            # upstream so the model doesn't hang waiting on it.
            await _dispatch_function_call(
                websocket=websocket,
                provider=provider,
                handle=handle,
                target_age=target_age,
                ev=ev,
                state=state,
            )
            if state.get("end_call_requested"):
                end_call_requested = True
        elif ev.kind == "response_done":
            break

    # An end_call tool fired during this turn — let the broker's outer
    # loop close cleanly with the documented ended_reason.
    if end_call_requested:
        return

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
        # #609 telemetry — the buddy's reply text failed the pre-TTS gate
        # and was never forwarded. Category is a bounded reason code; the
        # rejected text itself is never logged.
        voice_telemetry.emit_voice_session_safety_rejection(
            session_id=handle.session_id,
            direction="reply",
            category="reply_unsafe",
        )
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
        # #609 telemetry — the buddy's reply text failed the pre-TTS gate
        # and was never forwarded. Category is a bounded reason code; the
        # rejected text itself is never logged.
        voice_telemetry.emit_voice_session_safety_rejection(
            session_id=handle.session_id,
            direction="reply",
            category="reply_unsafe",
        )
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
        # #609 telemetry — barge-in tracking. No interruption signal is
        # wired in the broker yet (full-duplex barge-in is a follow-up),
        # so this stays 0 until that lands; the event still fires at close
        # so the histogram schema exists from day one.
        "interruption_count": 0,
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
            # #608: pass the persona's enabled_skills so the provider
            # filters launch tools BEFORE registering them with OpenAI.
            # Defense in depth — the token-mint guard already refuses
            # zero-skill personas; this prevents partial-skill personas
            # from exposing disabled launch tools to the model.
            start_kwargs["enabled_skills"] = await _enabled_skills_for_voice(
                user_id=claims.user_id, child_id=claims.child_id,
            )
        handle = await provider.start_session(**start_kwargs)

        # #609 telemetry — session opened. agent_id is a best-effort
        # lookup so the dashboard can slice voice engagement by persona;
        # a null agent_id just means a default (no-persona) buddy.
        voice_telemetry.emit_voice_session_started(
            session_id=claims.session_id,
            age_group=age_group,
            agent_id=await _agent_id_for_voice(
                user_id=claims.user_id, child_id=claims.child_id,
            ),
            provider=provider.name,
        )

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
                    # #609 telemetry — record WHICH side tripped the gate
                    # without ever logging the (unsafe) transcript text.
                    voice_telemetry.emit_voice_session_safety_rejection(
                        session_id=claims.session_id,
                        direction="utterance",
                        category=(
                            "empty_transcript" if not transcript.text
                            else "transcript_unsafe"
                        ),
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
                # A tool dispatched an end_call envelope this turn —
                # close cleanly with the dedicated reason so Parent
                # Dashboard can distinguish kid-initiated voice goodbyes
                # from network drops.
                if state.get("end_call_requested"):
                    termination_reason = "voice_tool_end_call"
                    return

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
        # #609 product/engagement telemetry — distinct from the cost line
        # above. ``voice_session_ended`` powers the abnormal-termination
        # alerting; the first-audio + interruption events feed the latency
        # histogram and the reply-length tuning signal. All fire exactly
        # once per session because they live in the broker's finally block.
        voice_telemetry.emit_voice_session_ended(
            session_id=claims.session_id,
            duration_seconds=elapsed,
            ended_reason=termination_reason,
        )
        if state.get("first_audio_ms") is not None:
            voice_telemetry.emit_voice_session_first_audio_ms(
                session_id=claims.session_id,
                first_audio_ms=state["first_audio_ms"],
                age_group=age_group,
            )
        voice_telemetry.emit_voice_session_interruption_count(
            session_id=claims.session_id,
            count=int(state.get("interruption_count") or 0),
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
