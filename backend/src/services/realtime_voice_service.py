"""
Realtime voice service — provider abstraction layer (#613).

Mirrors the STTProvider Protocol shape from ``stt_service.py``. This
module is the seam between the WS broker (#615) and the concrete
provider impls (Mock — here; Hybrid Whisper+ElevenLabs Flash — #614).

Hard rules (PRD §3.16):
  - Audio bytes never reach disk. The Mock provider creates none;
    real impls must keep them in ``io.BytesIO`` buffers only.
  - Safety integration lives in the provider impl, not the broker.
    The broker passes ``target_age`` through and trusts the envelope.
  - All providers expose the same envelope shape so the broker is
    provider-agnostic.

This sub-story (#613) ships the Protocol + a deterministic Mock only.
Real network calls land in #614. OpenAI Realtime broker integration
lands in #645 (this revision).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

try:
    from elevenlabs.client import AsyncElevenLabs as _elevenlabs_AsyncClient
    from elevenlabs import VoiceSettings as _elevenlabs_VoiceSettings
except Exception:  # pragma: no cover - import fallback for test env
    _elevenlabs_AsyncClient = None
    _elevenlabs_VoiceSettings = None

# httpx is a hard dep (see requirements.txt). Aliasing the class through
# the module gives tests a stable monkeypatch target — they can swap
# ``rtvs._httpx_AsyncClient`` for a fake without touching the global
# ``httpx`` namespace. Import is intentionally module-level (no network
# I/O), and the class is only *constructed* inside ``start_session``.
try:
    import httpx as _httpx
    _httpx_AsyncClient = _httpx.AsyncClient
except Exception:  # pragma: no cover - import fallback for test env
    _httpx = None
    _httpx_AsyncClient = None  # type: ignore[assignment]

# ``websockets`` is shipped transitively via FastAPI. Aliasing the connect
# helper here gives the OpenAIRealtimeProvider a stable monkeypatch seam:
# tests can swap ``rtvs._websockets_connect`` for a fake upstream without
# touching the global ``websockets`` namespace. Import is module-level
# (no I/O); the connect call is only made inside ``start_session``.
try:
    import websockets as _websockets
    _websockets_connect = _websockets.connect
except Exception:  # pragma: no cover - import fallback for test env
    _websockets = None
    _websockets_connect = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Same threshold as stt_service.SAFETY_THRESHOLD — kept here so providers
# don't need to import the STT module just to know the safety floor.
SAFETY_THRESHOLD: float = 0.85

# Per-age safety floor (PRD §3.16.6). 3-5 gets a stricter floor because
# the voice channel is the most intimate modality. The broker uses this
# table for BOTH the per-utterance transcript gate AND the per-reply text
# gate so a single tuning location applies to both safety checkpoints.
SAFETY_THRESHOLD_BY_AGE: Dict[str, float] = {
    "3-5": 0.90,
    "6-8": 0.85,
    "9-12": 0.85,
}


def safety_threshold_for_age(target_age: int) -> float:
    """Map a numeric ``target_age`` to its per-age safety threshold."""
    if target_age <= 5:
        return SAFETY_THRESHOLD_BY_AGE["3-5"]
    if target_age <= 8:
        return SAFETY_THRESHOLD_BY_AGE["6-8"]
    return SAFETY_THRESHOLD_BY_AGE["9-12"]

# How the WS broker tells us which provider to use. "mock" forces the
# deterministic in-memory provider; "hybrid" routes to the Whisper +
# ElevenLabs Flash impl in #614 (not implemented yet).
DEFAULT_PROVIDER_ENV: str = "REALTIME_VOICE_PROVIDER"

# OpenAI Realtime API constants (#644 scaffold; broker integration → #645).
# We mint ephemeral client secrets server-side via the documented endpoint
# so the browser never sees the long-lived OPENAI_API_KEY.
OPENAI_REALTIME_CLIENT_SECRETS_URL: str = (
    "https://api.openai.com/v1/realtime/client_secrets"
)
# Default model — the "mini" tier is the cost guardrail. Escalation to the
# full ``gpt-realtime-2`` tier is owned by #648 (E5 cost telemetry).
OPENAI_REALTIME_MODEL_DEFAULT: str = "gpt-realtime-mini"
OPENAI_REALTIME_MODEL_ESCALATED: str = "gpt-realtime-2"

# Per-model USD rates per minute (PRD §3.16.8 — E5 cost telemetry / #648).
#
# These are *blended* input+output rates derived from the OpenAI Realtime
# pricing table. Cached vs uncached refers to the prompt-cache hit state
# of the session — a cache hit dramatically reduces input cost since the
# system prompt + per-age preamble does not get re-billed.
#
# Tune ranges (±5% per the contract test in
# ``test_voice_cost_telemetry_contract``):
#   gpt-realtime-mini cached:   $0.05/min input + $0.10/min output → blend $0.075
#   gpt-realtime-mini uncached: $0.18/min input + $0.25/min output → blend $0.215
#   gpt-realtime-2 cached:      $0.10/min input + $0.30/min output → blend $0.20
#   gpt-realtime-2 uncached:    $0.40/min input + $0.46/min output → blend $0.43
#
# All figures are in USD. Multi-currency support is out of scope for v2.
# Update this table together with the PRD when the upstream rate card moves.
VOICE_MODEL_RATES_USD_PER_MIN: Dict[str, Dict[str, float]] = {
    OPENAI_REALTIME_MODEL_DEFAULT: {
        "cached": 0.075,
        "uncached": 0.215,
    },
    OPENAI_REALTIME_MODEL_ESCALATED: {
        "cached": 0.20,
        "uncached": 0.43,
    },
}

# Operator-set cap. Read by an external alerting tool — we surface the
# env var name here so reviewers can find it. Once monthly spend crosses
# 80% of the cap, the ops alert fires. Wiring lives in deploy infra; the
# backend just exposes the structured ``voice_session_end`` log so the
# alerting layer has a per-session signal to sum.
OPENAI_REALTIME_MONTHLY_CAP_USD_ENV: str = "OPENAI_REALTIME_MONTHLY_CAP_USD"


def estimate_session_cost_usd(
    *,
    model: Optional[str],
    duration_seconds: float,
    prompt_cache_hit: bool,
) -> float:
    """Per-session cost estimate in USD.

    Linear-in-duration: ``cost = duration_seconds * rate / 60`` where
    ``rate`` is picked from :data:`VOICE_MODEL_RATES_USD_PER_MIN`. Defaults
    to ``0.0`` for unknown / missing models so the broker can call this
    on Mock/Hybrid sessions without special-casing.

    ``prompt_cache_hit=True`` selects the cached rate; the broker derives
    this from the upstream session metadata (or, today, treats every
    session except the first one in a 5-min window as a cache hit).
    """
    if not model:
        return 0.0
    rates = VOICE_MODEL_RATES_USD_PER_MIN.get(model)
    if rates is None:
        return 0.0
    rate = rates["cached"] if prompt_cache_hit else rates["uncached"]
    if duration_seconds <= 0:
        return 0.0
    return float(duration_seconds) * rate / 60.0


def log_voice_session_end(
    *,
    session_id: str,
    model: Optional[str],
    duration_seconds: float,
    cost_estimate_usd: float,
    prompt_cache_hit: bool,
    first_audio_ms: int,
    ended_reason: str,
) -> None:
    """Emit the structured ``voice_session_end`` log line.

    The ops-side dashboard scrapes ``event=voice_session_end`` records
    and aggregates ``cost_estimate_usd`` by day to spot runaway spend.
    Fields are flat so a downstream JSON formatter (e.g. ``python-json-logger``)
    serialises them without nesting.

    We log at INFO — sessions are infrequent enough (one per child play)
    that this won't spam DEBUG-suppressed environments.
    """
    extra = {
        "event": "voice_session_end",
        "session_id": session_id,
        "model": model,
        "duration_s": int(round(duration_seconds)),
        "cost_estimate_usd": float(cost_estimate_usd),
        "prompt_cache_hit": bool(prompt_cache_hit),
        "first_audio_ms": int(first_audio_ms or 0),
        "ended_reason": ended_reason,
    }
    logger.info(
        "voice_session_end session=%s model=%s duration_s=%s cost_usd=%.4f "
        "cache_hit=%s first_audio_ms=%s reason=%s",
        session_id, model, extra["duration_s"], extra["cost_estimate_usd"],
        extra["prompt_cache_hit"], extra["first_audio_ms"], ended_reason,
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class SessionHandle:
    """Opaque session identifier returned by ``start_session``.

    The broker treats this as a black box and passes it back into every
    other provider method on the same session. Providers may attach
    arbitrary internal state via ``provider_state``.
    """
    session_id: str
    user_id: str
    child_id: str
    target_age: int
    persona: str = "buddy_default"
    sample_rate_hz: int = 16_000
    audio_format: str = "pcm16"
    # Provider-private state — the broker must never read this.
    provider_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinalTranscript:
    """Result of one finalized child utterance.

    ``success`` = True even when ``safety_passed`` = False, because the
    request itself didn't fail — the content was just rejected. The
    broker uses this envelope to decide whether to forward the text to
    Claude or emit a ``safety_block`` event instead.
    """
    success: bool
    text: str
    language: str
    duration_ms: int
    safety_passed: bool
    error: Optional[str] = None
    provider: str = ""


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class RealtimeVoiceProvider(Protocol):
    """Pluggable realtime voice backend.

    Lifecycle: ``start_session`` once → many cycles of
    ``push_audio``+``finalize_utterance`` → eventually ``close``. Audio
    output via ``synthesize_speech`` is independently callable any
    number of times during the session.
    """

    name: str

    async def start_session(
        self,
        *,
        user_id: str,
        child_id: str,
        target_age: int,
        persona: str = "buddy_default",
    ) -> SessionHandle: ...

    async def push_audio(
        self,
        handle: SessionHandle,
        audio_bytes: bytes,
    ) -> None: ...

    async def finalize_utterance(
        self,
        handle: SessionHandle,
    ) -> FinalTranscript: ...

    def synthesize_speech(
        self,
        handle: SessionHandle,
        text: str,
    ) -> AsyncIterator[bytes]: ...

    async def close(self, handle: SessionHandle) -> None: ...


# ---------------------------------------------------------------------------
# Mock provider (CI / dev / contract tests)
# ---------------------------------------------------------------------------

# Deterministic transcript the mock returns for every finalized utterance.
# Tests assert on this exact string so changes are noticed.
MOCK_TRANSCRIPT: str = "hello buddy this is a mock transcript"

# Deterministic audio frame. Three short PCM-shaped silent chunks so the
# broker's chunk-counting logic has something to chew on without making
# the byte stream large enough to slow tests.
_MOCK_FRAMES: tuple[bytes, ...] = (
    b"\x00" * 64,
    b"\x00" * 64,
    b"\x00" * 64,
)


class MockRealtimeVoiceProvider:
    """Deterministic provider for tests and offline development.

    Round-trip:
      - ``start_session`` returns a fresh handle with no I/O.
      - ``push_audio`` accumulates byte count in provider_state for
        contract-test inspection but never writes anywhere.
      - ``finalize_utterance`` returns ``MOCK_TRANSCRIPT`` with
        ``safety_passed=True`` and a 1200 ms canned duration.
      - ``synthesize_speech`` yields three small silent PCM frames.
      - ``close`` is a no-op.

    The provider is intentionally boring — its job is to exercise the
    broker's plumbing without depending on Whisper or ElevenLabs.
    """

    name: str = "mock"

    async def start_session(
        self,
        *,
        user_id: str,
        child_id: str,
        target_age: int,
        persona: str = "buddy_default",
    ) -> SessionHandle:
        return SessionHandle(
            session_id=f"voice_mock_{uuid4().hex[:12]}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={"bytes_received": 0, "utterances": 0},
        )

    async def push_audio(self, handle: SessionHandle, audio_bytes: bytes) -> None:
        handle.provider_state["bytes_received"] = (
            handle.provider_state.get("bytes_received", 0) + len(audio_bytes)
        )

    async def finalize_utterance(self, handle: SessionHandle) -> FinalTranscript:
        handle.provider_state["utterances"] = (
            handle.provider_state.get("utterances", 0) + 1
        )
        handle.provider_state["bytes_received"] = 0
        return FinalTranscript(
            success=True,
            text=MOCK_TRANSCRIPT,
            language="en",
            duration_ms=1200,
            safety_passed=True,
            provider=self.name,
        )

    async def synthesize_speech(
        self,
        handle: SessionHandle,
        text: str,
    ) -> AsyncIterator[bytes]:
        # We declare this async-generator-returning to match the Protocol.
        # The body uses an inner generator so static analyzers infer the
        # right return type without an explicit yield in this function.
        async def _gen() -> AsyncIterator[bytes]:
            for frame in _MOCK_FRAMES:
                # Yield control between frames so the broker can observe
                # the streaming protocol (not just a giant batch).
                await asyncio.sleep(0)
                yield frame
        return _gen()

    async def close(self, handle: SessionHandle) -> None:
        # No real resources to release in the mock.
        return None


# ---------------------------------------------------------------------------
# Hybrid provider — Whisper STT + ElevenLabs Flash TTS (#614)
# ---------------------------------------------------------------------------

MAX_UTTERANCE_BYTES: int = 2 * 1024 * 1024  # 2 MB
MAX_UTTERANCE_MS: int = 30_000  # 30 s

_MIME_EXT_MAP: Dict[str, str] = {
    "audio/webm": "audio.webm",
    "audio/mp4": "audio.mp4",
    "audio/mpeg": "audio.mp3",
    "audio/wav": "audio.wav",
    "audio/pcm": "audio.wav",
}


def _extension_for(mime_type: str) -> str:
    """Pick a filename suffix the OpenAI SDK can sniff for Whisper."""
    base = mime_type.split(";", 1)[0].strip().lower()
    return _MIME_EXT_MAP.get(base, "audio.bin")


# Per-age TTS overrides land in #608 (Phase C). For v1 the provider
# exposes a global default and the broker can override via constructor.
DEFAULT_TTS_MODEL: str = "eleven_flash_v2_5"
DEFAULT_TTS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel"


class HybridRealtimeVoiceProvider:
    """Whisper STT + ElevenLabs Flash TTS, brokered in-memory.

    Audio bytes live in ``handle.provider_state["buffer"]`` (bytearray)
    only — never flushed to disk. ``finalize_utterance`` calls Whisper
    via the existing OpenAI client pattern (``io.BytesIO`` + ``buffer.name``
    extension hint) and runs the same safety check as ``stt_service``.

    Graceful degradation:
      - Missing ``OPENAI_API_KEY`` → ``finalize_utterance`` returns
        ``success=False, error="provider_unavailable"``. The broker
        translates to ``VoiceWSErrorEvent(code="provider_unavailable")``.
      - Missing ``ELEVENLABS_API_KEY`` → ``synthesize_speech`` yields an
        empty async generator. Session continues; buddy is silent. The
        broker emits ``assistant_text(is_final=True)`` and skips
        ``audio_chunk`` events.
      - SDK import failure → handled the same way.

    Single-tenant — one handle per session. The broker must never share
    a handle across concurrent coroutines on the same session.
    """

    name: str = "hybrid"
    WHISPER_MODEL: str = "whisper-1"

    def __init__(
        self,
        *,
        tts_model: str = DEFAULT_TTS_MODEL,
        tts_voice_id: str = DEFAULT_TTS_VOICE_ID,
    ) -> None:
        self.tts_model = tts_model
        self.tts_voice_id = tts_voice_id

    @property
    def _stt_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None

    @property
    def _tts_available(self) -> bool:
        return (
            bool(os.getenv("ELEVENLABS_API_KEY"))
            and _elevenlabs_AsyncClient is not None
            and _elevenlabs_VoiceSettings is not None
        )

    async def start_session(
        self,
        *,
        user_id: str,
        child_id: str,
        target_age: int,
        persona: str = "buddy_default",
    ) -> SessionHandle:
        return SessionHandle(
            session_id=f"voice_hybrid_{uuid4().hex[:12]}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={
                "buffer": bytearray(),
                "bytes_received": 0,
                "mime_type": "audio/webm",
                "utterances": 0,
                "forced_flush": False,
            },
        )

    async def push_audio(self, handle: SessionHandle, audio_bytes: bytes) -> None:
        state = handle.provider_state
        buffer: bytearray = state["buffer"]
        buffer.extend(audio_bytes)
        state["bytes_received"] = len(buffer)
        if len(buffer) >= MAX_UTTERANCE_BYTES:
            # Soft signal — broker checks state["forced_flush"] between
            # pushes if it wants to pre-empt. We never raise.
            state["forced_flush"] = True

    async def finalize_utterance(self, handle: SessionHandle) -> FinalTranscript:
        state = handle.provider_state
        audio_bytes = bytes(state["buffer"])
        # Reset immediately so a concurrent push (broker bug) doesn't
        # pollute the next utterance with leftover bytes.
        state["buffer"] = bytearray()
        state["bytes_received"] = 0
        state["forced_flush"] = False
        state["utterances"] = state.get("utterances", 0) + 1

        if not audio_bytes:
            return FinalTranscript(
                success=True, text="", language="en", duration_ms=0,
                safety_passed=False, error="empty_utterance",
                provider=self.name,
            )

        if not self._stt_available:
            return FinalTranscript(
                success=False, text="", language="en", duration_ms=0,
                safety_passed=False, error="provider_unavailable",
                provider=self.name,
            )

        mime_type = state.get("mime_type", "audio/webm")
        api_key = os.getenv("OPENAI_API_KEY")

        def _sync_transcribe() -> Dict[str, Any]:
            client = OpenAI(api_key=api_key)  # type: ignore[misc]
            buf = io.BytesIO(audio_bytes)
            buf.name = _extension_for(mime_type)
            response = client.audio.transcriptions.create(  # type: ignore[union-attr]
                model=self.WHISPER_MODEL,
                file=buf,
                response_format="verbose_json",
            )
            duration_s = float(getattr(response, "duration", 0.0) or 0.0)
            return {
                "text": getattr(response, "text", "") or "",
                "language": getattr(response, "language", "en"),
                "duration_ms": int(round(duration_s * 1000)),
            }

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, _sync_transcribe)
        except Exception as exc:
            logger.warning(
                "[session=%s] Whisper transcribe failed: %s",
                handle.session_id, exc,
            )
            return FinalTranscript(
                success=False, text="", language="en", duration_ms=0,
                safety_passed=False, error=f"stt_failed: {exc}",
                provider=self.name,
            )

        text = (result.get("text") or "").strip()
        # Lazy import to avoid circular dependency on stt_service at load.
        from . import stt_service as _stt

        try:
            safety_envelope = await _stt._safety_check_text(text, handle.target_age)
            score = float(safety_envelope.get("safety_score", 0.0))
        except Exception as exc:
            logger.warning(
                "[session=%s] safety check raised; fail-closed: %s",
                handle.session_id, exc,
            )
            return FinalTranscript(
                success=True, text="", language=result["language"],
                duration_ms=result["duration_ms"],
                safety_passed=False, error="safety_check_failed",
                provider=self.name,
            )

        safety_passed = score >= SAFETY_THRESHOLD
        return FinalTranscript(
            success=True,
            text=text if safety_passed else "",
            language=result["language"],
            duration_ms=result["duration_ms"],
            safety_passed=safety_passed,
            provider=self.name,
        )

    async def synthesize_speech(
        self,
        handle: SessionHandle,
        text: str,
    ) -> AsyncIterator[bytes]:
        if not text.strip():
            async def _empty() -> AsyncIterator[bytes]:
                if False:  # pragma: no cover
                    yield b""
            return _empty()

        if not self._tts_available:
            logger.info(
                "[session=%s] TTS unavailable — yielding empty stream",
                handle.session_id,
            )
            async def _silent() -> AsyncIterator[bytes]:
                if False:  # pragma: no cover
                    yield b""
            return _silent()

        api_key = os.getenv("ELEVENLABS_API_KEY")
        voice_id = self.tts_voice_id
        model_id = self.tts_model

        async def _stream_chunks() -> AsyncIterator[bytes]:
            try:
                client = _elevenlabs_AsyncClient(api_key=api_key)  # type: ignore[misc]
                voice_settings = _elevenlabs_VoiceSettings(  # type: ignore[misc]
                    stability=0.5, similarity_boost=0.75, style=0.2,
                )
                audio_stream = await client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id=model_id,
                    voice_settings=voice_settings,
                    output_format="mp3_44100_128",
                )
                async for chunk in audio_stream:
                    if chunk:
                        yield chunk
            except Exception as exc:
                logger.warning(
                    "[session=%s] ElevenLabs TTS failed mid-stream: %s",
                    handle.session_id, exc,
                )
                return

        return _stream_chunks()

    async def close(self, handle: SessionHandle) -> None:
        # No persistent connections — Whisper is one-shot, ElevenLabs
        # stream closes when its iterator exhausts. Clear the buffer
        # so nothing leaks if a caller holds the handle past close.
        handle.provider_state.pop("buffer", None)
        handle.provider_state["closed"] = True


# ---------------------------------------------------------------------------
# OpenAI Realtime provider — broker-integrated (#645)
# ---------------------------------------------------------------------------

# Historical marker kept for documentation: the scaffold (#644) used this
# string in NotImplementedError so the #645 reviewer could grep call sites.
# All sites are now wired; the constant remains for one release as a hint
# to anyone tracing the migration history.
_E2_NOT_IMPLEMENTED: str = "E2 — broker integration"

# Per-OpenAI Realtime API spec — the upstream WS endpoint. The model
# query parameter is appended at connection time.
OPENAI_REALTIME_WS_URL: str = "wss://api.openai.com/v1/realtime"

# GA Realtime audio sample rate (Hz) for the nested ``audio.{input,output}
# .format`` objects. 24 kHz mono 16-bit little-endian PCM is OpenAI's
# recommended GA default.
OPENAI_REALTIME_AUDIO_RATE: int = 24000

# Per-age voice subset (PRD §3.16.6). 3-5 is parent-locked to the gentle
# ``alloy`` voice; older tiers get richer choices. The broker passes the
# chosen voice through ``persona`` → ``voice_session_config``.
VOICE_SUBSET_BY_AGE: Dict[str, List[str]] = {
    "3-5": ["alloy"],
    "6-8": ["alloy", "shimmer", "echo"],
    "9-12": ["alloy", "shimmer", "echo", "fable", "onyx", "nova", "ballad", "verse"],
}

# Per-age reply length cap (approx. tokens). 3-5 gets very short replies;
# 9-12 can handle longer reasoning. Enforced via the system prompt.
REPLY_LENGTH_CAP_BY_AGE: Dict[str, int] = {
    "3-5": 40,
    "6-8": 80,
    "9-12": 160,
}


@dataclass
class ReplyEvent:
    """One streaming event from the model during an assistant reply.

    ``kind`` is one of:
      - ``"text_delta"``     — a partial chunk of the model's text reply
      - ``"text_done"``      — final accumulated reply text (full string)
      - ``"audio_chunk"``    — a chunk of synthesized audio bytes
      - ``"function_call"``  — the model invoked a tool; the broker should
        dispatch via ``realtime_voice_tools.handle_tool_call`` and feed the
        result back via ``send_function_call_output``
      - ``"response_done"``  — the model finished the current response
    """
    kind: str
    text: str = ""
    audio: bytes = b""
    # Populated when ``kind == "function_call"``. ``call_id`` is the
    # opaque OpenAI-side identifier the broker echoes back in the
    # ``function_call_output`` event so the model can correlate.
    call_id: str = ""
    name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)


def _build_openai_system_prompt(*, target_age: int, persona: str) -> str:
    """Sectioned system prompt for the realtime model.

    Structured per OpenAI gpt-realtime guidance (Role / Tone / Language /
    Safety / Tools / Fallback). The child-safety preamble lives in the
    Safety section and is the highest-priority instruction.
    """
    age_band = (
        "3-5" if target_age <= 5
        else "6-8" if target_age <= 8
        else "9-12"
    )
    cap = REPLY_LENGTH_CAP_BY_AGE[age_band]
    return (
        "# Role\n"
        f"You are Buddy, a warm and curious AI friend for a child "
        f"in the {age_band} age band. Persona id: {persona}.\n\n"
        "# Tone\n"
        "Warm, playful, age-appropriate. Use short sentences for young "
        "children and richer language for older ones. Never sound clinical "
        "or condescending.\n\n"
        "# Language\n"
        "Always reply in English. Do not switch languages even if the "
        "child speaks another language — gently redirect to English.\n\n"
        "# Safety (highest priority)\n"
        "- Never produce content involving violence, sexuality, scary "
        "imagery, hate, self-harm, or unsafe instructions.\n"
        "- Never collect personally identifying information from the child.\n"
        "- If the child asks about an unsafe topic, gently redirect to "
        "something creative and age-appropriate.\n"
        "- Keep secrets only when safe — if a child mentions harm or "
        "danger, recommend talking to a trusted adult.\n\n"
        "# Reply Length\n"
        f"Aim for around {cap} tokens or less. Stop at natural sentence "
        "boundaries — never trail off mid-thought.\n\n"
        "# Tools\n"
        "You have a small set of tools available. Use them when the "
        "child asks for something a tool can do — do not announce that "
        "you are using a tool, just call it:\n"
        "- launch_image_story / launch_interactive_story / launch_kids_daily — "
        "open the matching activity. Say one short, age-friendly handoff "
        "sentence BEFORE calling the tool (e.g. 'Cool, let's do that!').\n"
        "- recall_memory — look up something the child told you before.\n"
        "- safety_review_reply — request explicit safety review of "
        "content you're unsure about; better safe than sorry.\n"
        "- end_call — politely end the chat when the child says goodbye.\n\n"
        "# Fallback\n"
        "If you are unsure how to respond safely, say: "
        "'Let's pick something different to talk about. What's something "
        "fun you want to make today?'\n"
    )


def _choose_voice_for_age(*, target_age: int, persona: str) -> str:
    """Pick a per-age voice id. ``persona`` may override if allowed."""
    age_band = (
        "3-5" if target_age <= 5
        else "6-8" if target_age <= 8
        else "9-12"
    )
    allowed = VOICE_SUBSET_BY_AGE[age_band]
    # If the persona maps to an allowed voice (after stripping the
    # ``buddy_`` prefix common in our config), honour it. Otherwise the
    # first allowed voice is the safe default.
    candidate = (persona or "").replace("buddy_", "").strip().lower()
    if candidate in allowed:
        return candidate
    return allowed[0]


class OpenAIRealtimeProvider:
    """OpenAI Realtime API provider — broker-integrated.

    Lifecycle:
      1. ``start_session`` mints an ephemeral client secret AND opens a
         server-side WebSocket to the OpenAI Realtime endpoint. The
         session is configured with sectioned system prompt, per-age
         voice + reply cap, and ``input_audio_buffer.append`` mode.
      2. ``push_audio`` forwards a base64 PCM chunk as an
         ``input_audio_buffer.append`` event.
      3. ``finalize_utterance`` sends ``input_audio_buffer.commit`` and
         ``response.create``, then waits for the
         ``conversation.item.input_audio_transcription.completed``
         event to extract the child's transcript. The broker safety-
         checks the transcript via ``_safety_check_text``.
      4. ``stream_assistant_reply`` yields a sequence of ``ReplyEvent``s
         — text deltas, the final text, and audio chunks. The broker
         buffers audio until the text passes safety; on pass, it
         forwards the buffered audio chunks to the client.
      5. ``close`` cancels the upstream reader task and closes the WS.

    Graceful degradation:
      - Missing ``OPENAI_API_KEY`` → degraded handle, no WS opened.
      - Upstream connect failure → degraded handle with ``mint_error``.
      - Provider never touches disk. Audio chunks live in an in-memory
        ``asyncio.Queue`` only.
    """

    name: str = "openai_realtime"

    def __init__(
        self,
        *,
        model: str = OPENAI_REALTIME_MODEL_DEFAULT,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def _is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY")) and _httpx_AsyncClient is not None

    @property
    def _ws_available(self) -> bool:
        return _websockets_connect is not None

    def _select_model(
        self,
        *,
        voice_premium_voice: bool,
        voice_premium_voice_consent: bool,
    ) -> str:
        """Tier-selection policy — mini default, escalate only on dual opt-in.

        Both flags must be True before we route to the premium
        ``gpt-realtime-2`` tier. Single-flag set falls back to mini so
        that, e.g., a parent's consent toggle going True does not
        silently upgrade a child whose per-child opt-in was never set.

        The constructor's ``self.model`` is ignored — selection is
        decided at session start so a long-lived provider instance
        can serve sessions for many children with different tiers.

        Cheapest-everywhere cost policy: premium realtime is disabled by
        default — every session uses the ``gpt-realtime-mini`` tier
        regardless of the per-child opt-in flags. To re-enable the
        dual-opt-in escalation to ``gpt-realtime-2`` later, set the env
        var ``VOICE_ALLOW_PREMIUM_REALTIME=1`` (no redeploy of code
        needed; the escalation logic below is preserved).
        """
        if os.getenv("VOICE_ALLOW_PREMIUM_REALTIME", "0") != "1":
            return OPENAI_REALTIME_MODEL_DEFAULT
        if voice_premium_voice and voice_premium_voice_consent:
            return OPENAI_REALTIME_MODEL_ESCALATED
        return OPENAI_REALTIME_MODEL_DEFAULT

    async def start_session(
        self,
        *,
        user_id: str,
        child_id: str,
        target_age: int,
        persona: str = "buddy_default",
        voice_premium_voice: bool = False,
        voice_premium_voice_consent: bool = False,
        enabled_skills: Optional[List[str]] = None,
    ) -> SessionHandle:
        # Tier-selection policy (#648): default ``gpt-realtime-mini`` and
        # only escalate when BOTH the per-child opt-in flag and the
        # parent-side consent flag are set. Fail closed if either is
        # missing — silent escalation would defeat the cost guardrail.
        chosen_model = self._select_model(
            voice_premium_voice=voice_premium_voice,
            voice_premium_voice_consent=voice_premium_voice_consent,
        )

        # Degraded path: no key (or httpx missing in test env). Return a
        # handle the broker can recognise without raising.
        if not self._is_available:
            logger.warning(
                "OpenAIRealtimeProvider unavailable — OPENAI_API_KEY missing "
                "or httpx not installed; returning degraded handle"
            )
            return SessionHandle(
                session_id=f"voice_openai_{uuid4().hex[:12]}",
                user_id=user_id,
                child_id=child_id,
                target_age=target_age,
                persona=persona,
                provider_state={
                    "openai_client_secret": "",
                    "provider_unavailable": True,
                    "model": chosen_model,
                    "prompt_cache_hit": False,
                },
            )

        api_key = os.getenv("OPENAI_API_KEY")
        # Body shape per OpenAI Realtime docs: a "session" object with
        # type + model. Voice config is owned by the broker (E2) so we
        # keep the body minimal here — just enough to mint the secret.
        body: Dict[str, Any] = {
            "session": {
                "type": "realtime",
                "model": chosen_model,
            }
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client_secret: str = ""
        expires_at: Optional[int] = None
        try:
            # Lazy: construct httpx client only when we actually mint.
            async with _httpx_AsyncClient(timeout=self.timeout_seconds) as client:  # type: ignore[misc]
                response = await client.post(
                    OPENAI_REALTIME_CLIENT_SECRETS_URL,
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                payload = response.json() or {}
                # OpenAI returns ``{"value": "ek_...", "expires_at": <epoch>}``
                # at the top level. Be defensive: also accept a nested
                # ``client_secret`` shape if the API ever shifts.
                client_secret = (
                    payload.get("value")
                    or payload.get("client_secret", {}).get("value", "")
                    or ""
                )
                expires_at = payload.get("expires_at")
        except Exception as exc:
            logger.warning(
                "OpenAI client_secrets mint failed: %s — returning degraded handle",
                exc,
            )
            return SessionHandle(
                session_id=f"voice_openai_{uuid4().hex[:12]}",
                user_id=user_id,
                child_id=child_id,
                target_age=target_age,
                persona=persona,
                provider_state={
                    "openai_client_secret": "",
                    "provider_unavailable": True,
                    "model": chosen_model,
                    "prompt_cache_hit": False,
                    "mint_error": str(exc),
                },
            )

        # Configure per-age voice + sectioned system prompt.
        voice = _choose_voice_for_age(target_age=target_age, persona=persona)
        system_prompt = _build_openai_system_prompt(
            target_age=target_age, persona=persona,
        )

        # Open the upstream WS so the broker can ``push_audio`` /
        # ``finalize_utterance`` immediately. Failure is non-fatal —
        # the secret is still useful (the frontend may bypass the
        # relay via WebRTC in E4), and the broker treats a missing
        # ``upstream_ws`` as ``provider_unavailable`` at first use.
        #
        # Gated by ``OPENAI_REALTIME_OPEN_UPSTREAM`` so the historical
        # scaffold contract tests (which only patched ``_httpx_AsyncClient``)
        # don't accidentally hit real network. Production deploy sets
        # this flag to "1" in env so the WS opens automatically.
        upstream_ws = None
        open_upstream = (
            os.getenv("OPENAI_REALTIME_OPEN_UPSTREAM", "0").lower()
            in ("1", "true", "yes")
        )
        if self._ws_available and open_upstream:
            try:
                ws_url = f"{OPENAI_REALTIME_WS_URL}?model={chosen_model}"
                # GA Realtime API (beta shape removed by OpenAI 2026-05):
                # the ``OpenAI-Beta: realtime=v1`` header MUST NOT be sent —
                # it triggers ``invalid_request_error.beta_api_shape_disabled``
                # and the upstream closes with WS code 4000. Authorization is
                # the only required header now. See #751.
                # Use the module alias so tests can monkeypatch a fake.
                cm_or_awaitable = _websockets_connect(  # type: ignore[misc]
                    ws_url,
                    additional_headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                # ``websockets.connect`` returns an object that's both
                # an async context manager AND directly awaitable. We
                # prefer the direct-await path so the connection stays
                # open across method calls.
                if hasattr(cm_or_awaitable, "__await__"):
                    upstream_ws = await cm_or_awaitable
                else:
                    # Older websockets API — fall back to __aenter__.
                    upstream_ws = await cm_or_awaitable.__aenter__()
                # Send the session.update event configuring voice + prompt.
                # Tools are registered here so the model can call into our
                # specialist surface (launch_flow / recall_memory / end_call)
                # without a separate WS round-trip. The model-facing schema
                # lives in `realtime_voice_tools.get_tool_definitions()`; the
                # broker dispatches each call back through `handle_tool_call`.
                # #608 defense in depth: filter tools by the persona's
                # enabled_skills BEFORE registering them so the model
                # literally can't call a disabled launch flow. Falls back
                # to the full list when no persona context was provided
                # (preserves pre-#608 behavior for the legacy code paths).
                from .realtime_voice_tools import (
                    filter_tool_definitions_by_skills,
                )
                # GA only accepts {type,name,description,parameters} on a
                # function tool. Our defs also carry an internal ``version``
                # (used for drift detection elsewhere) which GA rejects with
                # ``Unknown parameter: 'session.tools[N].version'`` — strip to
                # the allowed keys here rather than mutate the source defs.
                _GA_TOOL_KEYS = ("type", "name", "description", "parameters")
                tools_for_session = [
                    {k: t[k] for k in _GA_TOOL_KEYS if k in t}
                    for t in filter_tool_definitions_by_skills(enabled_skills)
                ]
                # GA session shape (#751): ``type: "realtime"`` is required;
                # ``modalities`` → ``output_modalities``; the flat
                # ``input/output_audio_format`` strings + ``voice`` +
                # ``input_audio_transcription`` now live under a nested
                # ``audio`` object, and formats are ``{type, rate}`` objects.
                # ``turn_detection: null`` keeps turn-taking MANUAL — the
                # broker drives ``input_audio_buffer.commit`` + ``response
                # .create`` from the frontend's VAD, so server-side VAD must
                # stay off or it would double-trigger responses.
                await upstream_ws.send(json.dumps({
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "model": chosen_model,
                        # GA accepts ["text"] OR ["audio"], never both. For a
                        # spoken buddy we request ["audio"]; the model still
                        # streams the spoken text as
                        # ``response.output_audio_transcript.*`` events, which
                        # feed the pre-delivery safety gate.
                        "output_modalities": ["audio"],
                        "instructions": system_prompt,
                        "audio": {
                            "input": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": OPENAI_REALTIME_AUDIO_RATE,
                                },
                                "turn_detection": None,
                                "transcription": {"model": "gpt-4o-transcribe"},
                            },
                            "output": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": OPENAI_REALTIME_AUDIO_RATE,
                                },
                                "voice": voice,
                            },
                        },
                        "tools": tools_for_session,
                        "tool_choice": "auto",
                    },
                }))
            except Exception as exc:
                logger.warning(
                    "OpenAI upstream WS open failed (continuing with relay-only mode): %s",
                    exc,
                )
                upstream_ws = None

        # #752: if we asked to open the WS-broker upstream but it failed,
        # mark the session unavailable so ``finalize_utterance`` returns a
        # clean ``provider_unavailable`` envelope. Without this, the relay
        # path later calls ``upstream_ws.recv()`` on ``None`` and surfaces a
        # raw ``AttributeError`` ("'NoneType' object has no attribute
        # 'recv'") to the child as a generic failure. When ``open_upstream``
        # is False (WebRTC-direct path) a ``None`` upstream is expected and
        # NOT a degraded state — the browser uses the client secret instead.
        relay_unavailable = open_upstream and upstream_ws is None

        return SessionHandle(
            session_id=f"voice_openai_{uuid4().hex[:12]}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={
                "openai_client_secret": client_secret,
                "model": chosen_model,
                "expires_at": expires_at,
                "voice": voice,
                "system_prompt": system_prompt,
                "upstream_ws": upstream_ws,
                "provider_unavailable": relay_unavailable,
                "pending_events": [],
                # ``prompt_cache_hit`` is set by the broker when it
                # detects the upstream returned a cached-prompt header.
                # For v2 we default to False — the cost telemetry layer
                # treats unknown cache state as uncached (the safer/
                # higher cost figure for budget planning).
                "prompt_cache_hit": False,
            },
        )

    # -----------------------------------------------------------------
    # Upstream WS helpers — small enough to keep inline so a reviewer
    # can follow the lifecycle without bouncing between files.
    # -----------------------------------------------------------------

    async def _send_event(self, handle: SessionHandle, event: Dict[str, Any]) -> None:
        ws = handle.provider_state.get("upstream_ws")
        if ws is None:
            # Degraded session — silently drop. The broker should have
            # noticed ``provider_unavailable`` and never gotten here, but
            # we refuse to raise mid-stream.
            return
        await ws.send(json.dumps(event))

    async def push_audio(
        self,
        handle: SessionHandle,
        audio_bytes: bytes,
    ) -> None:
        """Forward a chunk of child audio to the upstream model."""
        # Gate on the live resource, not a cached flag: if there's no
        # upstream WS there's nothing to forward (#752).
        if handle.provider_state.get("upstream_ws") is None:
            return
        # OpenAI expects base64-encoded PCM audio in input_audio_buffer.append.
        await self._send_event(handle, {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(audio_bytes).decode("ascii"),
        })

    async def finalize_utterance(
        self,
        handle: SessionHandle,
    ) -> FinalTranscript:
        """Commit the audio buffer, request a response, await transcript.

        The model's transcribed user input arrives as
        ``conversation.item.input_audio_transcription.completed``. We
        listen for that single event and return the transcript; the
        broker is responsible for running the per-age safety check on
        the result.
        """
        # #752: no upstream WS → degrade cleanly with a typed
        # ``provider_unavailable`` envelope instead of later calling
        # ``.recv()`` on ``None`` (which surfaced a raw AttributeError to
        # the child). Covers both the WS-open-failed case and the no-key /
        # mint-failed degraded handles (which carry no ``upstream_ws``).
        if handle.provider_state.get("upstream_ws") is None:
            return FinalTranscript(
                success=False, text="", language="en", duration_ms=0,
                safety_passed=False, error="provider_unavailable",
                provider=self.name,
            )

        # Tell the upstream we're done with this utterance and want a reply.
        await self._send_event(handle, {"type": "input_audio_buffer.commit"})
        await self._send_event(handle, {"type": "response.create"})

        # Read events until we see the transcription completed signal.
        transcript_text: str = ""
        language: str = "en"
        try:
            transcript_text, language = await self._await_user_transcript(handle)
        except Exception as exc:
            logger.warning(
                "[session=%s] upstream transcript wait failed: %s",
                handle.session_id, exc,
            )
            return FinalTranscript(
                success=False, text="", language="en", duration_ms=0,
                safety_passed=False, error=f"upstream_failed: {exc}",
                provider=self.name,
            )

        return FinalTranscript(
            success=True,
            text=transcript_text,
            language=language,
            duration_ms=0,  # OpenAI doesn't surface utterance duration here
            # Per-age safety check happens in the broker — providers report
            # the transcript as-is. ``safety_passed=True`` here means
            # "transport succeeded"; the broker overrides if the safety
            # MCP score is sub-threshold.
            safety_passed=True,
            provider=self.name,
        )

    async def _await_user_transcript(
        self, handle: SessionHandle,
    ) -> Tuple[str, str]:
        """Pull events off the upstream WS until we see the transcript.

        ``stream_assistant_reply`` consumes the remainder of the
        response stream (text + audio). The events here are buffered
        in ``handle.provider_state["pending_events"]`` so the next call
        can replay them.
        """
        ws = handle.provider_state.get("upstream_ws")
        if ws is None:
            # #752: never call ``.recv()`` on a missing upstream. Callers
            # gate on ``provider_unavailable`` before reaching here, but a
            # clean error beats a raw AttributeError if that ever slips.
            raise RuntimeError("provider_unavailable")
        pending: List[Dict[str, Any]] = handle.provider_state.setdefault(
            "pending_events", []
        )

        # First drain any events buffered by a previous call.
        for ev in list(pending):
            pending.remove(ev)
            if (
                ev.get("type")
                == "conversation.item.input_audio_transcription.completed"
            ):
                return (
                    ev.get("transcript", "") or "",
                    ev.get("language", "en") or "en",
                )

        # Then pull new events until we see the transcript signal or
        # the response stream completes (in which case no transcript
        # arrived — return empty).
        while True:
            raw = await ws.recv()
            try:
                ev = json.loads(raw) if isinstance(raw, str) else json.loads(
                    raw.decode("utf-8")
                )
            except Exception:
                continue
            ev_type = ev.get("type", "")
            if ev_type == "conversation.item.input_audio_transcription.completed":
                return (
                    ev.get("transcript", "") or "",
                    ev.get("language", "en") or "en",
                )
            if ev_type in ("error", "session.error"):
                raise RuntimeError(ev.get("error", {}).get("message", "upstream error"))
            # Buffer everything else for the reply stream.
            pending.append(ev)
            # If the response completes before we saw a transcript event,
            # bail with an empty transcript rather than blocking forever.
            if ev_type == "response.done":
                return ("", "en")

    async def stream_assistant_reply(
        self, handle: SessionHandle,
    ) -> AsyncIterator[ReplyEvent]:
        """Yield text + audio deltas from the in-flight model response.

        Custom to OpenAI Realtime (not in the Protocol). The broker
        detects this method by ``hasattr(provider, "stream_assistant_reply")``
        and consumes the events; for providers without it, the broker
        falls back to the legacy ``synthesize_speech(text)`` path.
        """
        ws = handle.provider_state.get("upstream_ws")
        pending: List[Dict[str, Any]] = handle.provider_state.get(
            "pending_events", []
        )

        async def _gen() -> AsyncIterator[ReplyEvent]:
            # Replay buffered events first.
            for ev in list(pending):
                pending.remove(ev)
                async for out in _ev_to_reply_events(ev):
                    yield out
                if ev.get("type") == "response.done":
                    return

            # Then pull live events until the response is complete.
            while True:
                raw = await ws.recv()
                try:
                    ev = json.loads(raw) if isinstance(raw, str) else json.loads(
                        raw.decode("utf-8")
                    )
                except Exception:
                    continue
                async for out in _ev_to_reply_events(ev):
                    yield out
                if ev.get("type") == "response.done":
                    return

        return _gen()

    async def synthesize_speech(
        self,
        handle: SessionHandle,
        text: str,
    ) -> AsyncIterator[bytes]:
        """Yield audio bytes from the in-flight upstream response.

        Semantics differ from Hybrid: the OpenAI Realtime model emits
        text + audio together, so this method *consumes the live audio
        deltas* rather than calling a separate TTS endpoint. The
        ``text`` argument is informational only — the broker has
        already accepted the model's reply text via safety check and
        we are now just relaying the corresponding audio chunks.
        """
        if handle.provider_state.get("upstream_ws") is None:
            async def _empty() -> AsyncIterator[bytes]:
                if False:  # pragma: no cover
                    yield b""
            return _empty()

        ws = handle.provider_state.get("upstream_ws")
        pending: List[Dict[str, Any]] = handle.provider_state.get(
            "pending_events", []
        )

        async def _gen() -> AsyncIterator[bytes]:
            # Replay any buffered audio events first.
            for ev in list(pending):
                pending.remove(ev)
                audio_chunk = _extract_audio_delta(ev)
                if audio_chunk:
                    yield audio_chunk
                if ev.get("type") == "response.done":
                    return
            if ws is None:
                return
            while True:
                try:
                    raw = await ws.recv()
                except Exception:
                    return
                try:
                    ev = json.loads(raw) if isinstance(raw, str) else json.loads(
                        raw.decode("utf-8")
                    )
                except Exception:
                    continue
                audio_chunk = _extract_audio_delta(ev)
                if audio_chunk:
                    yield audio_chunk
                if ev.get("type") == "response.done":
                    return

        return _gen()

    async def send_function_call_output(
        self,
        handle: SessionHandle,
        *,
        call_id: str,
        output: str,
    ) -> None:
        """Feed a tool result back to the upstream model.

        OpenAI Realtime requires every function call to be paired with a
        ``conversation.item.create`` of type ``function_call_output`` and
        then a ``response.create`` to trigger the model's continuation.
        Skipping either step leaves the model waiting indefinitely. The
        broker calls this after dispatching the tool via
        ``realtime_voice_tools.handle_tool_call``.
        """
        await self._send_event(handle, {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            },
        })
        await self._send_event(handle, {"type": "response.create"})

    async def close(self, handle: SessionHandle) -> None:
        """Tear down the upstream WS cleanly."""
        handle.provider_state["closed"] = True
        ws = handle.provider_state.pop("upstream_ws", None)
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # pragma: no cover - best effort
                pass


# ---------------------------------------------------------------------------
# Helpers for translating OpenAI Realtime events to ReplyEvent / bytes.
# ---------------------------------------------------------------------------

def _extract_audio_delta(ev: Dict[str, Any]) -> bytes:
    """Decode a single ``response.audio.delta`` event to raw bytes.

    The upstream encodes audio chunks as base64 inside ``delta``. Any
    other event type is silently ignored — the broker only needs the
    audio bytes here.
    """
    ev_type = ev.get("type", "")
    # OpenAI Realtime emits ``response.audio.delta`` for streamed audio
    # bytes. Newer variants use ``response.output_audio.delta`` — accept
    # both so a model upgrade doesn't break us silently.
    if ev_type in ("response.audio.delta", "response.output_audio.delta"):
        delta = ev.get("delta", "") or ""
        if not delta:
            return b""
        try:
            return base64.b64decode(delta)
        except Exception:
            return b""
    return b""


async def _ev_to_reply_events(ev: Dict[str, Any]) -> AsyncIterator[ReplyEvent]:
    """Map one upstream event to zero-or-more ReplyEvent records."""
    ev_type = ev.get("type", "")
    # GA renamed the streamed-text events. With ``output_modalities:
    # ["audio"]`` the spoken text arrives as
    # ``response.output_audio_transcript.*``; ``response.output_text.*`` is
    # the text-only mode. We accept the GA names AND the legacy beta names so
    # the pre-delivery safety gate keeps receiving reply text — a missed
    # rename here would be a silent fail-open (audio forwarded, text empty).
    if ev_type in (
        "response.output_audio_transcript.delta",
        "response.audio_transcript.delta",
        "response.output_text.delta",
        "response.text.delta",
    ):
        delta = ev.get("delta", "") or ""
        if delta:
            yield ReplyEvent(kind="text_delta", text=delta)
    elif ev_type in (
        "response.output_audio_transcript.done",
        "response.audio_transcript.done",
        "response.output_text.done",
        "response.text.done",
    ):
        # OpenAI emits the full transcript text in ``transcript`` or ``text``.
        text = (
            ev.get("transcript")
            or ev.get("text")
            or ""
        )
        yield ReplyEvent(kind="text_done", text=text)
    elif ev_type in ("response.audio.delta", "response.output_audio.delta"):
        chunk = _extract_audio_delta(ev)
        if chunk:
            yield ReplyEvent(kind="audio_chunk", audio=chunk)
    elif ev_type == "response.function_call_arguments.done":
        # The model decided to call one of our tools. Surface it as a
        # ReplyEvent so the broker can dispatch via the tools module and
        # echo back via send_function_call_output. Malformed args are
        # coerced to an empty dict so the dispatcher's error path can
        # respond rather than crashing the stream.
        raw_args = ev.get("arguments", "") or "{}"
        try:
            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except Exception:
            parsed_args = {}
        if not isinstance(parsed_args, dict):
            parsed_args = {}
        yield ReplyEvent(
            kind="function_call",
            call_id=ev.get("call_id", "") or "",
            name=ev.get("name", "") or "",
            args=parsed_args,
        )
    elif ev_type == "response.done":
        yield ReplyEvent(kind="response_done")


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _select_provider(
    override: Optional[RealtimeVoiceProvider] = None,
) -> RealtimeVoiceProvider:
    """Pick the provider for this process.

    Priority:
      1. Explicit ``override`` — test injection.
      2. ``REALTIME_VOICE_PROVIDER=mock`` → MockRealtimeVoiceProvider.
      3. ``REALTIME_VOICE_PROVIDER=hybrid`` → HybridRealtimeVoiceProvider
         (degrades internally when keys are missing).
      4. ``REALTIME_VOICE_PROVIDER=openai`` →
         a) OPENAI_API_KEY set → OpenAIRealtimeProvider
         b) OPENAI_API_KEY missing → Hybrid (next tier in the
            graceful-degradation chain; Hybrid further degrades to a
            ``provider_unavailable`` envelope if its own key is missing).
      5. Missing ``OPENAI_API_KEY`` → Mock (dev/test env without keys).
      6. Default → Mock until an operator opts into a real provider.
    """
    if override is not None:
        return override

    requested = os.getenv(DEFAULT_PROVIDER_ENV, "").strip().lower()
    if requested == "mock":
        return MockRealtimeVoiceProvider()

    if requested == "hybrid":
        return HybridRealtimeVoiceProvider()

    if requested == "openai":
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIRealtimeProvider()
        # Fallback chain: openai -> hybrid -> mock. Hybrid itself
        # degrades internally if ELEVENLABS / OPENAI keys go missing,
        # so half-deployed envs still don't crash.
        logger.warning(
            "REALTIME_VOICE_PROVIDER=openai but OPENAI_API_KEY missing "
            "— falling back to HybridRealtimeVoiceProvider"
        )
        return HybridRealtimeVoiceProvider()

    if not os.getenv("OPENAI_API_KEY"):
        return MockRealtimeVoiceProvider()

    return MockRealtimeVoiceProvider()
