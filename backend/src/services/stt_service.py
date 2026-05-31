"""
Speech-to-text service layer (#583).

Provides a pluggable STT API for the voice-input surfaces in epic #579
(PRD §3.15). OpenAI Whisper is the default provider; a deterministic
mock provider runs when ``STT_MOCK=1`` or ``OPENAI_API_KEY`` is unset
(test/CI environments).

Hard contract from PRD §3.15:
  - Audio bytes never reach disk — only the moderated transcript leaves
    the service. The contract test
    ``test_transcribe_never_writes_audio_to_disk`` enforces this.
  - The transcript is run through ``check_content_safety`` AFTER
    transcribe; safety failure returns ``safety_passed=False`` with
    ``text=""`` but still ``success=True`` (the request itself didn't
    fail — the content was rejected).
  - Safety MCP failures fail closed (``safety_passed=False``).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

from ..mcp_servers.safety_check_server import check_content_safety


# ---------------------------------------------------------------------------
# Public constants (PRD §3.15.4 acceptance criteria)
# ---------------------------------------------------------------------------

MAX_AUDIO_BYTES: int = 2 * 1024 * 1024  # 2 MB
MAX_DURATION_MS: int = 30_000  # 30 s
ALLOWED_MIME: set[str] = {"audio/webm", "audio/mp4", "audio/mpeg"}
SAFETY_THRESHOLD: float = 0.85


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class STTProvider(Protocol):
    """Pluggable speech-to-text backend.

    Implementations MUST treat ``audio_bytes`` as in-memory only — no
    disk writes.
    """

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language_hint: Optional[str] = None,
    ) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------------
# OpenAI Whisper provider
# ---------------------------------------------------------------------------

class OpenAISTTProvider:
    """OpenAI Whisper provider.

    Sends the in-memory ``audio_bytes`` to ``audio.transcriptions.create``
    via a ``BytesIO`` file handle. Nothing touches disk on this path.
    """

    MODEL = "whisper-1"

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "error": "OPENAI_API_KEY not configured"}
        if OpenAI is None:  # pragma: no cover - openai is in requirements
            return {"success": False, "error": "openai SDK not installed"}

        def _sync_call() -> Dict[str, Any]:
            client = OpenAI(api_key=api_key)
            # The OpenAI SDK requires a name attribute on the file-like
            # object to infer the extension. Whisper uses extension as a
            # format hint when the SDK can't sniff the container.
            buffer = io.BytesIO(audio_bytes)
            buffer.name = _extension_for(mime_type)
            kwargs: Dict[str, Any] = {
                "model": self.MODEL,
                "file": buffer,
                "response_format": "verbose_json",
            }
            if language_hint:
                kwargs["language"] = language_hint
            response = client.audio.transcriptions.create(**kwargs)
            # `response` is a VerboseTranscription object exposing .text,
            # .language, .duration (seconds).
            duration_seconds = float(getattr(response, "duration", 0.0) or 0.0)
            return {
                "success": True,
                "text": getattr(response, "text", "") or "",
                "language": getattr(response, "language", language_hint or "en"),
                "duration_ms": int(round(duration_seconds * 1000)),
            }

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, _sync_call)
        except Exception as exc:  # pragma: no cover - exercised via mocked provider
            logger.warning("OpenAI Whisper transcribe failed: %s", exc)
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Mock provider (test/CI fallback)
# ---------------------------------------------------------------------------

class MockSTTProvider:
    """Deterministic mock STT provider for test environments."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "text": "hello from the mock transcriber",
            "language": language_hint or "en",
            "duration_ms": 1200,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIME_EXT_MAP: Dict[str, str] = {
    "audio/webm": "audio.webm",
    "audio/mp4": "audio.mp4",
    "audio/mpeg": "audio.mp3",
}


def _extension_for(mime_type: str) -> str:
    base = mime_type.split(";", 1)[0].strip().lower()
    return _MIME_EXT_MAP.get(base, "audio.bin")


def _normalize_mime(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def validate_audio_file(mime_type: str, size_bytes: int) -> Optional[str]:
    """Return an error string if the upload is invalid, else ``None``."""
    normalized = _normalize_mime(mime_type)
    if normalized not in ALLOWED_MIME:
        return f"Unsupported audio mime type: {mime_type}"
    if size_bytes > MAX_AUDIO_BYTES:
        return "Audio exceeds 2 MB upload limit"
    if size_bytes <= 0:
        return "Empty audio payload"
    return None


def _select_provider(provider: Optional[STTProvider]) -> STTProvider:
    if provider is not None:
        return provider
    if os.getenv("STT_MOCK") == "1" or not os.getenv("OPENAI_API_KEY"):
        return MockSTTProvider()
    return OpenAISTTProvider()


def _unwrap_tool_payload(result: Any) -> Dict[str, Any]:
    """Unwrap SdkMcpTool ``{"content": [{"text": "<json>"}]}`` envelopes."""
    if isinstance(result, dict) and "content" in result:
        try:
            text = result["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return {}
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def _safety_check_text(text: str, target_age: int) -> Dict[str, Any]:
    """Invoke the safety MCP tool and return the parsed envelope.

    Exposed as a module-level function so tests can patch it cleanly.
    """
    raw = await check_content_safety.handler({
        "content_text": text,
        "content_type": "voice_input",
        "target_age": target_age,
    })
    return _unwrap_tool_payload(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def transcribe_audio_bytes(
    audio_bytes: bytes,
    mime_type: str,
    target_age: int,
    *,
    language_hint: Optional[str] = None,
    provider: Optional[STTProvider] = None,
) -> Dict[str, Any]:
    """Transcribe in-memory audio and moderate the result.

    Returns an envelope:
        {
            "success": bool,           # transport-level success
            "text": str,               # empty string if safety failed
            "language": str,           # detected or hinted
            "duration_ms": int,
            "safety_passed": bool,     # False when score < threshold or
                                       # the safety MCP throws
            "error": Optional[str],    # only on success=False
            "provider": Optional[str],
        }

    DO NOT PERSIST ``audio_bytes`` to disk anywhere in this code path.
    """
    chosen = _select_provider(provider)
    provider_name = type(chosen).__name__

    raw = await chosen.transcribe(audio_bytes, mime_type, language_hint)
    if not raw.get("success"):
        return {
            "success": False,
            "text": "",
            "language": language_hint or "en",
            "duration_ms": 0,
            "safety_passed": False,
            "error": raw.get("error", "Transcription failed"),
            "provider": provider_name,
        }

    text = (raw.get("text") or "").strip()
    language = raw.get("language") or language_hint or "en"
    duration_ms = int(raw.get("duration_ms") or 0)

    # Empty transcripts skip the safety call (nothing to moderate) but
    # still surface as safety_passed=False so the UI shows the "didn't
    # catch that" message instead of an empty insertion.
    if not text:
        return {
            "success": True,
            "text": "",
            "language": language,
            "duration_ms": duration_ms,
            "safety_passed": False,
            "error": None,
            "provider": provider_name,
        }

    try:
        safety = await _safety_check_text(text, target_age)
        score = float(safety.get("safety_score", 0.0))
    except Exception as exc:
        # Fail-closed: a flaky safety MCP must never let unmoderated
        # speech reach a kid-facing input.
        logger.warning("Safety check failed for transcript; failing closed: %s", exc)
        return {
            "success": True,
            "text": "",
            "language": language,
            "duration_ms": duration_ms,
            "safety_passed": False,
            "error": None,
            "provider": provider_name,
        }

    safety_passed = score >= SAFETY_THRESHOLD
    return {
        "success": True,
        "text": text if safety_passed else "",
        "language": language,
        "duration_ms": duration_ms,
        "safety_passed": safety_passed,
        "error": None,
        "provider": provider_name,
    }
