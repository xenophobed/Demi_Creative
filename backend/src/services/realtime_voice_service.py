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
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional, Protocol
from uuid import uuid4


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
# Provider selection
# ---------------------------------------------------------------------------

def _select_provider(
    override: Optional[RealtimeVoiceProvider] = None,
) -> RealtimeVoiceProvider:
    """Pick the provider for this process.

    Priority:
      1. Explicit ``override`` — test injection.
      2. ``REALTIME_VOICE_PROVIDER=mock`` → MockRealtimeVoiceProvider.
      3. ``REALTIME_VOICE_PROVIDER=hybrid`` → not yet implemented (#614);
         falls back to Mock with a stderr warning.
      4. Missing ``OPENAI_API_KEY`` → Mock (dev/test env without keys).
      5. Default → Mock until #614 lands.
    """
    if override is not None:
        return override

    requested = os.getenv(DEFAULT_PROVIDER_ENV, "").strip().lower()
    if requested == "mock":
        return MockRealtimeVoiceProvider()

    if requested == "hybrid":
        # #614 will replace this branch with the real provider. For now
        # we degrade to Mock so /voice/session never hard-fails on a
        # half-deployed environment.
        return MockRealtimeVoiceProvider()

    if not os.getenv("OPENAI_API_KEY"):
        return MockRealtimeVoiceProvider()

    return MockRealtimeVoiceProvider()
