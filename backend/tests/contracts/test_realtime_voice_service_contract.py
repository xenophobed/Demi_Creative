"""
Realtime voice service contract tests (#613).

Locks the provider Protocol surface + the Mock impl's deterministic
round-trip + the no-disk invariant. Real-provider tests live in #614.
"""

import builtins
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.src.services import realtime_voice_service as rtvs
from backend.src.services.realtime_voice_service import (
    MOCK_TRANSCRIPT,
    MockRealtimeVoiceProvider,
    SAFETY_THRESHOLD,
    SessionHandle,
    _select_provider,
)


# ----------------------------- Protocol shape ------------------------------

class TestProtocolShape:
    """The Mock satisfies the Protocol — every method exists and is async."""

    def test_mock_has_required_attributes(self):
        provider = MockRealtimeVoiceProvider()
        assert provider.name == "mock"
        for method in (
            "start_session", "push_audio", "finalize_utterance",
            "synthesize_speech", "close",
        ):
            assert hasattr(provider, method), f"missing {method}"

    def test_safety_threshold_matches_stt_module(self):
        # Public constants must agree across modules so the WS broker
        # doesn't pull a stale floor.
        from backend.src.services import stt_service
        assert SAFETY_THRESHOLD == stt_service.SAFETY_THRESHOLD


# --------------------------- Mock round-trip --------------------------------

class TestMockRoundTrip:
    @pytest.mark.asyncio
    async def test_start_session_returns_unique_handle(self):
        provider = MockRealtimeVoiceProvider()
        h1 = await provider.start_session(
            user_id="u1", child_id="c1", target_age=7,
        )
        h2 = await provider.start_session(
            user_id="u1", child_id="c1", target_age=7,
        )
        assert h1.session_id != h2.session_id
        assert h1.user_id == "u1"
        assert h1.target_age == 7
        assert h1.persona == "buddy_default"

    @pytest.mark.asyncio
    async def test_push_audio_accumulates_byte_count(self):
        provider = MockRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert h.provider_state["bytes_received"] == 0
        await provider.push_audio(h, b"\x00" * 100)
        assert h.provider_state["bytes_received"] == 100
        await provider.push_audio(h, b"\x00" * 50)
        assert h.provider_state["bytes_received"] == 150

    @pytest.mark.asyncio
    async def test_finalize_returns_deterministic_transcript(self):
        provider = MockRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await provider.push_audio(h, b"\x00" * 200)
        result = await provider.finalize_utterance(h)
        assert result.success is True
        assert result.safety_passed is True
        assert result.text == MOCK_TRANSCRIPT
        assert result.language == "en"
        assert result.duration_ms == 1200
        assert result.provider == "mock"
        # Buffer reset for the next utterance.
        assert h.provider_state["bytes_received"] == 0
        assert h.provider_state["utterances"] == 1

    @pytest.mark.asyncio
    async def test_synthesize_speech_yields_three_frames(self):
        provider = MockRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        chunks: list[bytes] = []
        gen = await provider.synthesize_speech(h, "the buddy says hello")
        async for chunk in gen:
            chunks.append(chunk)
        # Three deterministic frames so the broker can verify ordering.
        assert len(chunks) == 3
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            assert len(chunk) == 64

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        provider = MockRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Mock has nothing to release; assertion is "does not raise".
        await provider.close(h)


# ---------------------- Selection / fallback semantics ---------------------

class TestProviderSelection:
    def test_override_wins(self):
        sentinel = MockRealtimeVoiceProvider()
        sentinel.name = "sentinel"
        chosen = _select_provider(override=sentinel)
        assert chosen is sentinel

    def test_mock_env_returns_mock(self, monkeypatch):
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "mock")
        chosen = _select_provider()
        assert chosen.name == "mock"

    def test_hybrid_env_falls_back_to_mock_until_implemented(self, monkeypatch):
        # #614 will replace this with the real provider; until then,
        # never crash on a half-deployed env.
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "hybrid")
        chosen = _select_provider()
        assert chosen.name == "mock"

    def test_missing_openai_key_returns_mock(self, monkeypatch):
        monkeypatch.delenv("REALTIME_VOICE_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        chosen = _select_provider()
        assert chosen.name == "mock"


# ---------------------- The load-bearing contract --------------------------

class TestNoDiskPersistence:
    """Audio must never reach disk during a full round-trip."""

    @pytest.mark.asyncio
    async def test_mock_provider_never_writes_to_disk(self, monkeypatch):
        write_bytes_calls: list[str] = []
        named_temp_calls: list[tuple] = []
        open_write_calls: list[tuple[str, str]] = []

        original_write_bytes = Path.write_bytes
        original_named_temp = tempfile.NamedTemporaryFile
        original_open = builtins.open

        def spy_write_bytes(self, *args, **kwargs):
            write_bytes_calls.append(str(self))
            return original_write_bytes(self, *args, **kwargs)

        def spy_named_temp(*args, **kwargs):
            named_temp_calls.append((args, kwargs))
            return original_named_temp(*args, **kwargs)

        def spy_open(file, mode="r", *args, **kwargs):
            if any(c in mode for c in ("w", "a", "x")):
                open_write_calls.append((str(file), mode))
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "write_bytes", spy_write_bytes)
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy_named_temp)
        monkeypatch.setattr(builtins, "open", spy_open)

        provider = MockRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Realistic byte volume — a few hundred KB of "audio" pushed
        # in a few chunks, then finalized + synthesized.
        for _ in range(4):
            await provider.push_audio(h, b"\x00" * 65_536)
        await provider.finalize_utterance(h)
        gen = await provider.synthesize_speech(h, "buddy reply")
        async for _ in gen:
            pass
        await provider.close(h)

        assert write_bytes_calls == [], (
            f"realtime_voice_service wrote to disk: {write_bytes_calls}"
        )
        assert named_temp_calls == [], (
            f"realtime_voice_service created temp file: {named_temp_calls}"
        )
        assert open_write_calls == [], (
            f"realtime_voice_service opened a file for writing: {open_write_calls}"
        )


# ----------------------- Override + injection seam -------------------------

class TestProviderInjection:
    """The broker (#615) must be able to inject a stub provider for tests."""

    @pytest.mark.asyncio
    async def test_async_mock_provider_satisfies_protocol(self):
        # Build a stub that satisfies the Protocol without subclassing.
        stub = AsyncMock()
        stub.name = "stub"
        stub.start_session = AsyncMock(return_value=SessionHandle(
            session_id="voice_stub_1", user_id="u", child_id="c",
            target_age=7,
        ))
        stub.push_audio = AsyncMock(return_value=None)
        stub.finalize_utterance = AsyncMock(return_value=__import__(
            "backend.src.services.realtime_voice_service",
            fromlist=["FinalTranscript"],
        ).FinalTranscript(
            success=True, text="stub", language="en", duration_ms=500,
            safety_passed=True, provider="stub",
        ))
        stub.close = AsyncMock(return_value=None)

        chosen = _select_provider(override=stub)
        assert chosen is stub
        handle = await chosen.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert handle.session_id == "voice_stub_1"
