"""
STT Service Contract Tests (#583)

Locks the service-layer contract for speech-to-text:
  - Provider protocol shape (OpenAI + Mock).
  - Validation of mime type and size BEFORE provider call.
  - check_content_safety runs on the transcript AFTER transcribe; failures
    return safety_passed=False with text="" (still success=True).
  - Audio bytes are NEVER written to disk — only the transcript leaves the
    service.

The disk-persistence guard is a hard product rule from PRD §3.15 (COPPA-
adjacent surface). If a future provider/refactor starts writing audio
bytes to /tmp, this test fails immediately.
"""

import builtins
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.src.services import stt_service
from backend.src.services.stt_service import (
    MAX_AUDIO_BYTES,
    ALLOWED_MIME,
    MockSTTProvider,
    OpenAISTTProvider,
    SAFETY_THRESHOLD,
    transcribe_audio_bytes,
    validate_audio_file,
)


# -------------------- Validation contract --------------------

class TestValidation:
    def test_accepts_supported_mime_types(self):
        for mime in ("audio/webm", "audio/mp4", "audio/mpeg"):
            assert validate_audio_file(mime, 1024) is None, mime

    def test_strips_codec_parameters_from_mime(self):
        # Browsers send "audio/webm;codecs=opus" — must not be rejected.
        assert validate_audio_file("audio/webm;codecs=opus", 1024) is None

    def test_rejects_unsupported_mime(self):
        msg = validate_audio_file("audio/wav", 1024)
        assert msg is not None and "mime" in msg.lower() or "audio" in msg.lower()

    def test_rejects_oversized_audio(self):
        msg = validate_audio_file("audio/webm", MAX_AUDIO_BYTES + 1)
        assert msg is not None and "2" in msg

    def test_allowed_mime_set_matches_prd_spec(self):
        # PRD §3.15.4 explicitly enumerates these three.
        assert ALLOWED_MIME == {"audio/webm", "audio/mp4", "audio/mpeg"}


# -------------------- Provider protocol contract --------------------

class TestProviderProtocol:
    @pytest.mark.asyncio
    async def test_mock_provider_returns_canonical_envelope(self):
        result = await MockSTTProvider().transcribe(b"x" * 100, "audio/webm")
        assert result["success"] is True
        assert isinstance(result["text"], str)
        assert isinstance(result["language"], str)
        assert isinstance(result["duration_ms"], int)

    @pytest.mark.asyncio
    async def test_openai_provider_returns_error_envelope_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = await OpenAISTTProvider().transcribe(b"x" * 100, "audio/webm")
        assert result["success"] is False
        assert "OPENAI_API_KEY" in result.get("error", "")


# -------------------- Safety integration contract --------------------

class TestSafetyIntegration:
    @pytest.mark.asyncio
    async def test_safety_pass_returns_text(self, monkeypatch):
        monkeypatch.setenv("STT_MOCK", "1")

        safe_envelope = {"safety_score": 0.95, "issues": []}
        with patch.object(
            stt_service,
            "_safety_check_text",
            new=AsyncMock(return_value=safe_envelope),
        ):
            result = await transcribe_audio_bytes(
                b"x" * 100, "audio/webm", target_age=7
            )

        assert result["success"] is True
        assert result["safety_passed"] is True
        assert result["text"]  # mock provider returns non-empty
        assert result["language"] == "en"

    @pytest.mark.asyncio
    async def test_safety_fail_returns_empty_text(self, monkeypatch):
        monkeypatch.setenv("STT_MOCK", "1")

        unsafe_envelope = {"safety_score": 0.3, "issues": ["violence"]}
        with patch.object(
            stt_service,
            "_safety_check_text",
            new=AsyncMock(return_value=unsafe_envelope),
        ):
            result = await transcribe_audio_bytes(
                b"x" * 100, "audio/webm", target_age=7
            )

        assert result["success"] is True
        assert result["safety_passed"] is False
        assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_safety_mcp_failure_fails_closed(self, monkeypatch):
        monkeypatch.setenv("STT_MOCK", "1")

        with patch.object(
            stt_service,
            "_safety_check_text",
            new=AsyncMock(side_effect=RuntimeError("safety unavailable")),
        ):
            result = await transcribe_audio_bytes(
                b"x" * 100, "audio/webm", target_age=7
            )

        assert result["success"] is True
        assert result["safety_passed"] is False
        assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_provider_error_propagates_as_failure(self, monkeypatch):
        failing_provider = AsyncMock()
        failing_provider.transcribe = AsyncMock(
            return_value={"success": False, "error": "upstream timeout"}
        )

        result = await transcribe_audio_bytes(
            b"x" * 100,
            "audio/webm",
            target_age=7,
            provider=failing_provider,
        )

        assert result["success"] is False
        assert result["safety_passed"] is False
        assert "timeout" in result.get("error", "").lower()

    def test_safety_threshold_matches_prd(self):
        # PRD §3.15.4 acceptance criterion fixes the threshold.
        assert SAFETY_THRESHOLD == 0.85


# -------------------- Retention contract (the load-bearing one) --------------------

class TestNoDiskPersistence:
    @pytest.mark.asyncio
    async def test_transcribe_never_writes_audio_to_disk(self, monkeypatch):
        """COPPA-adjacent: audio bytes must never reach disk.

        Patches every common file-write entrypoint and asserts none fire
        during a transcription call.
        """
        monkeypatch.setenv("STT_MOCK", "1")

        write_bytes_calls: list = []
        named_temp_calls: list = []

        original_write_bytes = Path.write_bytes
        original_namedtempfile = tempfile.NamedTemporaryFile

        def spy_write_bytes(self, *args, **kwargs):
            write_bytes_calls.append(str(self))
            return original_write_bytes(self, *args, **kwargs)

        def spy_named_temp(*args, **kwargs):
            named_temp_calls.append((args, kwargs))
            return original_namedtempfile(*args, **kwargs)

        monkeypatch.setattr(Path, "write_bytes", spy_write_bytes)
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy_named_temp)

        # Also guard against open(..., 'wb')-style writes inside the service.
        open_write_calls: list = []
        original_open = builtins.open

        def spy_open(file, mode="r", *args, **kwargs):
            if "w" in mode or "a" in mode or "x" in mode:
                open_write_calls.append((str(file), mode))
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", spy_open)

        safe_envelope = {"safety_score": 0.95, "issues": []}
        with patch.object(
            stt_service,
            "_safety_check_text",
            new=AsyncMock(return_value=safe_envelope),
        ):
            await transcribe_audio_bytes(
                b"x" * 200, "audio/webm", target_age=7
            )

        # The STT service itself must not write audio anywhere.
        # We allow non-audio writes only if the file path obviously isn't
        # under our audio handling — but for a pure mock-provider call,
        # ZERO writes is the right assertion.
        assert write_bytes_calls == [], (
            f"stt_service wrote to disk: {write_bytes_calls}"
        )
        assert named_temp_calls == [], (
            f"stt_service created a temp file: {named_temp_calls}"
        )
        assert open_write_calls == [], (
            f"stt_service opened a file for writing: {open_write_calls}"
        )
