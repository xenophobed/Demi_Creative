"""
Contract tests for HybridRealtimeVoiceProvider (#614).

The provider talks to live Whisper + ElevenLabs in production, but
these tests run hermetically — every external call is monkeypatched.
The point of the suite is to lock the in-memory invariants:

  - Audio bytes are NEVER written to disk
  - Buffer is reset after every finalize_utterance
  - Hard byte cap raises the forced_flush signal
  - Missing OPENAI_API_KEY → provider_unavailable envelope
  - Missing ELEVENLABS_API_KEY → empty TTS stream (no audio_chunk events)
  - Whisper raise → stt_failed envelope
  - Safety MCP raise → fail-closed (safety_passed=False, text="")
  - Provider satisfies the RealtimeVoiceProvider Protocol
"""

import builtins
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.src.services import realtime_voice_service as rtvs
from backend.src.services.realtime_voice_service import (
    HybridRealtimeVoiceProvider,
    MAX_UTTERANCE_BYTES,
    SAFETY_THRESHOLD,
    SessionHandle,
    _extension_for,
    _select_provider,
)


# ---------------------- Protocol shape -------------------------------------

class TestProtocolShape:
    def test_hybrid_has_required_methods(self):
        provider = HybridRealtimeVoiceProvider()
        assert provider.name == "hybrid"
        for method in (
            "start_session", "push_audio", "finalize_utterance",
            "synthesize_speech", "close",
        ):
            assert hasattr(provider, method), f"missing {method}"


# ---------------------- Mime extension mapping -----------------------------

class TestExtensionFor:
    def test_webm_with_codec(self):
        assert _extension_for("audio/webm;codecs=opus") == "audio.webm"

    def test_mp4(self):
        assert _extension_for("audio/mp4") == "audio.mp4"

    def test_mpeg(self):
        assert _extension_for("audio/mpeg") == "audio.mp3"

    def test_pcm_and_wav(self):
        assert _extension_for("audio/wav") == "audio.wav"
        assert _extension_for("audio/pcm") == "audio.wav"

    def test_unknown_mime_falls_back(self):
        assert _extension_for("application/octet-stream") == "audio.bin"


# ---------------------- start_session shape --------------------------------

class TestStartSession:
    @pytest.mark.asyncio
    async def test_start_session_unique_id_and_empty_buffer(self):
        p = HybridRealtimeVoiceProvider()
        h1 = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        h2 = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert h1.session_id != h2.session_id
        assert h1.session_id.startswith("voice_hybrid_")
        assert h1.provider_state["buffer"] == bytearray()
        assert h1.provider_state["bytes_received"] == 0
        assert h1.provider_state["utterances"] == 0
        assert h1.provider_state["forced_flush"] is False


# ---------------------- Buffer + forced_flush ------------------------------

class TestBuffering:
    @pytest.mark.asyncio
    async def test_push_audio_accumulates(self):
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 100)
        await p.push_audio(h, b"\x00" * 50)
        assert h.provider_state["bytes_received"] == 150
        assert len(h.provider_state["buffer"]) == 150
        assert h.provider_state["forced_flush"] is False

    @pytest.mark.asyncio
    async def test_buffer_cap_raises_forced_flush(self):
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Push enough to cross the 2 MB threshold in one chunk.
        await p.push_audio(h, b"\x00" * (MAX_UTTERANCE_BYTES + 1))
        assert h.provider_state["forced_flush"] is True

    @pytest.mark.asyncio
    async def test_finalize_resets_buffer(self, monkeypatch):
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Skip the network — patch the path that would call Whisper.
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-stt-available-check")
        from openai import OpenAI as _OpenAI  # noqa: F401  ensure attr exists
        monkeypatch.setattr(
            rtvs, "OpenAI", lambda **_kw: MagicMock(),
        )
        # Force the inner _sync_transcribe path by injecting a fake
        # response shape directly. Easier: patch run_in_executor.
        import asyncio as _aio
        async def fake_exec(_pool, fn, *args, **kwargs):
            return {"text": "hello", "language": "en", "duration_ms": 1234}
        original_get_loop = _aio.get_running_loop
        class _FakeLoop:
            def run_in_executor(self, pool, fn):
                async def _runner():
                    return fn()
                return _runner()
        # Easier path: monkeypatch _safety_check_text + the executor's
        # inner sync call by replacing client.audio.transcriptions.create.
        # We do the simplest thing: patch run_in_executor on the running loop.
        monkeypatch.setattr(
            _aio, "get_running_loop",
            lambda: _FakeLoopWithReturn({"text": "hello world", "language": "en", "duration_ms": 1000}),
        )
        # Stub the safety helper before finalize runs.
        from backend.src.services import stt_service as _stt
        monkeypatch.setattr(
            _stt, "_safety_check_text",
            AsyncMock(return_value={"safety_score": 0.95}),
        )

        await p.push_audio(h, b"\x00" * 200)
        result = await p.finalize_utterance(h)
        assert result.success is True
        assert result.text == "hello world"
        assert result.safety_passed is True
        # Buffer must be empty after finalize.
        assert h.provider_state["buffer"] == bytearray()
        assert h.provider_state["bytes_received"] == 0
        assert h.provider_state["utterances"] == 1


class _FakeLoopWithReturn:
    """Helper: a fake event-loop whose run_in_executor returns a canned dict."""
    def __init__(self, canned_return):
        self._canned = canned_return

    def run_in_executor(self, pool, fn):
        async def _runner():
            # The real impl calls the sync function; for tests we ignore
            # it and return our canned shape so the test doesn't depend
            # on the OpenAI SDK being installed/reachable.
            return self._canned
        return _runner()


# ---------------------- Empty utterance ------------------------------------

class TestEmptyUtterance:
    @pytest.mark.asyncio
    async def test_finalize_with_empty_buffer_returns_empty_envelope(self):
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        result = await p.finalize_utterance(h)
        assert result.success is True
        assert result.text == ""
        assert result.safety_passed is False
        assert result.error == "empty_utterance"
        assert result.duration_ms == 0


# ---------------------- Graceful degradation -------------------------------

class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_missing_openai_key_returns_provider_unavailable(
        self, monkeypatch,
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 200)
        result = await p.finalize_utterance(h)
        assert result.success is False
        assert result.error == "provider_unavailable"
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_missing_elevenlabs_key_yields_empty_tts_stream(
        self, monkeypatch,
    ):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        gen = await p.synthesize_speech(h, "hello buddy")
        chunks = [chunk async for chunk in gen]
        # No audio frames — broker emits assistant_text(is_final=True) and
        # skips audio_chunk events.
        assert chunks == []

    @pytest.mark.asyncio
    async def test_empty_text_yields_empty_stream(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "stub-not-called")
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        gen = await p.synthesize_speech(h, "   ")
        chunks = [chunk async for chunk in gen]
        assert chunks == []


# ---------------------- Failure envelopes ----------------------------------

class TestFailureEnvelopes:
    @pytest.mark.asyncio
    async def test_whisper_exception_returns_stt_failed(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "stub")
        import asyncio as _aio

        class _RaisingLoop:
            def run_in_executor(self, pool, fn):
                async def _runner():
                    raise RuntimeError("upstream Whisper 500")
                return _runner()

        monkeypatch.setattr(_aio, "get_running_loop", lambda: _RaisingLoop())

        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 100)
        result = await p.finalize_utterance(h)
        assert result.success is False
        assert result.error is not None
        assert result.error.startswith("stt_failed:")
        assert "Whisper 500" in result.error

    @pytest.mark.asyncio
    async def test_safety_mcp_raises_fails_closed(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "stub")
        import asyncio as _aio
        monkeypatch.setattr(
            _aio, "get_running_loop",
            lambda: _FakeLoopWithReturn(
                {"text": "totally fine", "language": "en", "duration_ms": 500},
            ),
        )
        from backend.src.services import stt_service as _stt
        monkeypatch.setattr(
            _stt, "_safety_check_text",
            AsyncMock(side_effect=RuntimeError("safety MCP down")),
        )

        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 100)
        result = await p.finalize_utterance(h)
        # Fail-closed: success=True (transport ok) but text empty + flag false.
        assert result.success is True
        assert result.text == ""
        assert result.safety_passed is False
        assert result.error == "safety_check_failed"

    @pytest.mark.asyncio
    async def test_safety_score_below_threshold_blocks_text(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "stub")
        import asyncio as _aio
        monkeypatch.setattr(
            _aio, "get_running_loop",
            lambda: _FakeLoopWithReturn(
                {"text": "bad stuff", "language": "en", "duration_ms": 500},
            ),
        )
        from backend.src.services import stt_service as _stt
        monkeypatch.setattr(
            _stt, "_safety_check_text",
            AsyncMock(return_value={"safety_score": SAFETY_THRESHOLD - 0.1}),
        )

        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 100)
        result = await p.finalize_utterance(h)
        assert result.success is True
        assert result.text == ""
        assert result.safety_passed is False


# ---------------------- The load-bearing invariant -------------------------

class TestNoDiskPersistence:
    """No audio bytes reach disk during any provider operation."""

    @pytest.mark.asyncio
    async def test_full_round_trip_never_writes_to_disk(self, monkeypatch):
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

        # Stub the network paths.
        monkeypatch.setenv("OPENAI_API_KEY", "stub")
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)  # silent TTS
        import asyncio as _aio
        monkeypatch.setattr(
            _aio, "get_running_loop",
            lambda: _FakeLoopWithReturn(
                {"text": "hello", "language": "en", "duration_ms": 1000},
            ),
        )
        from backend.src.services import stt_service as _stt
        monkeypatch.setattr(
            _stt, "_safety_check_text",
            AsyncMock(return_value={"safety_score": 0.99}),
        )

        provider = HybridRealtimeVoiceProvider()
        h = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # Realistic mic capture — push a few hundred KB, finalize, attempt
        # synthesis (silent because no ElevenLabs key), close.
        for _ in range(4):
            await provider.push_audio(h, b"\x00" * 65_536)
        await provider.finalize_utterance(h)
        gen = await provider.synthesize_speech(h, "buddy reply")
        async for _ in gen:
            pass
        await provider.close(h)

        assert write_bytes_calls == [], (
            f"hybrid provider wrote to disk: {write_bytes_calls}"
        )
        assert named_temp_calls == [], (
            f"hybrid provider created temp file: {named_temp_calls}"
        )
        assert open_write_calls == [], (
            f"hybrid provider opened a file for writing: {open_write_calls}"
        )


# ---------------------- Provider selection ---------------------------------

class TestProviderSelectionWiresHybrid:
    def test_hybrid_env_returns_hybrid_provider(self, monkeypatch):
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "hybrid")
        chosen = _select_provider()
        assert chosen.name == "hybrid"
        assert isinstance(chosen, HybridRealtimeVoiceProvider)


# ---------------------- Cleanup --------------------------------------------

class TestClose:
    @pytest.mark.asyncio
    async def test_close_clears_buffer(self):
        p = HybridRealtimeVoiceProvider()
        h = await p.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await p.push_audio(h, b"\x00" * 100)
        await p.close(h)
        assert "buffer" not in h.provider_state
        assert h.provider_state["closed"] is True
