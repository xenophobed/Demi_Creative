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
Real network calls land in #614.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional, Protocol
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


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Same threshold as stt_service.SAFETY_THRESHOLD — kept here so providers
# don't need to import the STT module just to know the safety floor.
SAFETY_THRESHOLD: float = 0.85

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
# OpenAI Realtime provider — scaffold (#644)
# ---------------------------------------------------------------------------

# Reused message string so the #645 (E2) reviewer can grep for every
# call-site the broker integration must replace.
_E2_NOT_IMPLEMENTED: str = "E2 — broker integration"


class OpenAIRealtimeProvider:
    """OpenAI Realtime API provider — scaffold only.

    This story (#644) gives the provider class a Protocol-conformant
    shape and a working ``start_session`` that mints an ephemeral client
    secret via ``POST /v1/realtime/client_secrets``. Audio forwarding,
    tool-call translation, and synthesis stream from the upstream WS
    land in **E2 (#645)** — those methods explicitly raise
    ``NotImplementedError(_E2_NOT_IMPLEMENTED)`` here so a reviewer can
    grep the codebase and verify every site got wired.

    Graceful degradation:
      - Missing ``OPENAI_API_KEY`` → ``start_session`` returns a degraded
        handle with ``provider_state["provider_unavailable"] = True``.
        Mirrors the Hybrid provider's pattern: the broker translates
        this into ``VoiceWSErrorEvent(code="provider_unavailable")``
        instead of every caller wrapping ``start_session`` in try/except.
      - Missing ``httpx`` (test env without dep) → same degraded handle.

    Audio-on-disk invariant:
      - The provider never touches disk. The client secret + model
        metadata live in ``handle.provider_state`` (memory-only).
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

    async def start_session(
        self,
        *,
        user_id: str,
        child_id: str,
        target_age: int,
        persona: str = "buddy_default",
    ) -> SessionHandle:
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
                    "model": self.model,
                },
            )

        api_key = os.getenv("OPENAI_API_KEY")
        # Body shape per OpenAI Realtime docs: a "session" object with
        # type + model. Voice config is owned by the broker (E2) so we
        # keep the body minimal here — just enough to mint the secret.
        body: Dict[str, Any] = {
            "session": {
                "type": "realtime",
                "model": self.model,
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
                    "model": self.model,
                    "mint_error": str(exc),
                },
            )

        return SessionHandle(
            session_id=f"voice_openai_{uuid4().hex[:12]}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={
                "openai_client_secret": client_secret,
                "model": self.model,
                "expires_at": expires_at,
            },
        )

    async def push_audio(
        self,
        handle: SessionHandle,
        audio_bytes: bytes,
    ) -> None:
        # Audio forwarding to the upstream OpenAI Realtime WS lands in
        # #645. Reviewer: grep for ``_E2_NOT_IMPLEMENTED`` and wire each
        # call-site to the real WS forward.
        raise NotImplementedError(_E2_NOT_IMPLEMENTED)

    async def finalize_utterance(
        self,
        handle: SessionHandle,
    ) -> FinalTranscript:
        raise NotImplementedError(_E2_NOT_IMPLEMENTED)

    async def synthesize_speech(
        self,
        handle: SessionHandle,
        text: str,
    ) -> AsyncIterator[bytes]:
        # Matches the Protocol shape — the existing Mock/Hybrid impls
        # also ``async def`` this method and return an async iterator.
        # In E2 this will yield audio frames forwarded from the OpenAI
        # Realtime WS ``response.output_audio.delta`` events.
        raise NotImplementedError(_E2_NOT_IMPLEMENTED)

    async def close(self, handle: SessionHandle) -> None:
        # No persistent upstream connection in the scaffold — the broker
        # holds nothing for us to release. Closing the upstream WS is
        # E2 territory; keep this a benign no-op so the broker's
        # session-cleanup path doesn't fail under the scaffold.
        handle.provider_state["closed"] = True


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
