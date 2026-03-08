"""
TTS service layer.

Provides a plain callable API for story audio generation with pluggable
provider support (#149).  OpenAI is the default; Replicate minimax/speech-02-turbo
is available as an expressive alternative with emotion/pitch/volume controls.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set

import httpx

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

try:
    import replicate as _replicate_module
except Exception:  # pragma: no cover - import fallback for test env
    _replicate_module = None


# ---------------------------------------------------------------------------
# Age-based emotion filtering (#149)
# ---------------------------------------------------------------------------

AGE_EMOTION_MAP: Dict[str, Set[str]] = {
    "3-5": {"happy", "neutral"},
    "6-8": {"happy", "sad", "surprised", "neutral"},
    "9-12": {"happy", "sad", "surprised", "disgusted", "neutral"},
}


def filter_emotion_for_age(emotion: Optional[str], age_group: Optional[str]) -> Optional[str]:
    """Return *emotion* if allowed for *age_group*, else fall back to 'neutral'.

    Returns ``None`` unchanged so callers that omit emotion are unaffected.
    """
    if emotion is None:
        return None
    allowed = AGE_EMOTION_MAP.get(age_group or "6-8", AGE_EMOTION_MAP["6-8"])
    return emotion if emotion in allowed else "neutral"


# ---------------------------------------------------------------------------
# TTSProvider protocol (#149)
# ---------------------------------------------------------------------------

class TTSProvider(Protocol):
    """Pluggable TTS backend."""

    async def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        audio_path: str,
        emotion: Optional[str] = None,
        pitch: Optional[int] = None,
        volume: Optional[float] = None,
        language_boost: Optional[str] = None,
    ) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------------
# OpenAI provider (existing baseline, refactored)
# ---------------------------------------------------------------------------

class OpenAITTSProvider:
    """OpenAI tts-1 provider."""

    async def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        audio_path: str,
        emotion: Optional[str] = None,
        pitch: Optional[int] = None,
        volume: Optional[float] = None,
        language_boost: Optional[str] = None,
    ) -> Dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "error": "OPENAI_API_KEY not configured"}

        if OpenAI is not None:
            def _sync_tts() -> None:
                client = OpenAI(api_key=api_key)
                resp = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                    speed=speed,
                )
                resp.stream_to_file(audio_path)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _sync_tts)
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "tts-1",
                "voice": voice,
                "input": text,
                "speed": speed,
                "format": "mp3",
            }
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                Path(audio_path).write_bytes(response.content)

        return {"success": True, "provider": "openai"}


# ---------------------------------------------------------------------------
# Replicate minimax/speech-02-turbo provider (#149)
# ---------------------------------------------------------------------------

class ReplicateTTSProvider:
    """Replicate minimax/speech-02-turbo provider with expressive controls."""

    MODEL = "minimax/speech-02-turbo"

    async def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        audio_path: str,
        emotion: Optional[str] = None,
        pitch: Optional[int] = None,
        volume: Optional[float] = None,
        language_boost: Optional[str] = None,
    ) -> Dict[str, Any]:
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            return {"success": False, "error": "REPLICATE_API_TOKEN not configured"}

        if _replicate_module is None:
            return {"success": False, "error": "replicate SDK not installed"}

        input_params: Dict[str, Any] = {
            "text": text,
            "voice_id": voice,
            "speed": speed,
            "audio_format": "mp3",
        }
        if emotion is not None:
            input_params["emotion"] = emotion
        if pitch is not None:
            input_params["pitch"] = pitch
        if volume is not None:
            input_params["volume"] = volume
        if language_boost is not None:
            input_params["language_boost"] = language_boost

        def _sync_replicate() -> bytes:
            output = _replicate_module.run(self.MODEL, input=input_params)
            # output is a FileOutput; read bytes from it
            return output.read()

        try:
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, _sync_replicate)
            Path(audio_path).write_bytes(audio_bytes)
            return {"success": True, "provider": "replicate"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_openai_provider = OpenAITTSProvider()
_replicate_provider = ReplicateTTSProvider()


def _select_provider(provider: Optional[str]) -> TTSProvider:
    if provider == "replicate":
        return _replicate_provider
    return _openai_provider


# ---------------------------------------------------------------------------
# Public API (backward-compatible)
# ---------------------------------------------------------------------------

def get_audio_output_path() -> str:
    """Get the audio output directory."""
    audio_dir = os.getenv("AUDIO_OUTPUT_PATH", "./data/audio")
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    return audio_dir


def _resolve_speed(speed: Optional[float], child_age: Optional[int]) -> float:
    """Resolve speaking speed from explicit input or age defaults."""
    if speed is not None:
        return speed

    if child_age is None:
        return 1.0

    if child_age <= 5:
        return 0.9
    if child_age <= 8:
        return 1.0
    return 1.1


async def generate_story_audio_file(
    text: str,
    voice: str = "nova",
    speed: Optional[float] = None,
    child_age: Optional[int] = None,
    *,
    emotion: Optional[str] = None,
    pitch: Optional[int] = None,
    volume: Optional[float] = None,
    language_boost: Optional[str] = None,
    provider: Optional[str] = None,
    age_group: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate story audio file and return a normalized result payload.

    New optional params (#149): emotion, pitch, volume, language_boost,
    provider ('openai' | 'replicate'), age_group (for emotion filtering).
    All are keyword-only so existing positional callers are unaffected.
    """
    if not text:
        return {
            "success": False,
            "error": "story text is empty",
            "audio_path": None,
        }

    # Apply age-based emotion filtering
    filtered_emotion = filter_emotion_for_age(emotion, age_group)

    resolved_speed = _resolve_speed(speed, child_age)

    try:
        timestamp = datetime.now().isoformat()
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"story_{text_hash}_{timestamp.replace(':', '-')}.mp3"

        audio_dir = get_audio_output_path()
        audio_path = os.path.join(audio_dir, filename)

        chosen_provider = _select_provider(provider)
        fallback_used = False
        original_provider = provider or "openai"
        actual_provider = original_provider

        t0 = time.monotonic()

        result = await chosen_provider.generate(
            text=text,
            voice=voice,
            speed=resolved_speed,
            audio_path=audio_path,
            emotion=filtered_emotion,
            pitch=pitch,
            volume=volume,
            language_boost=language_boost,
        )

        # Fallback: if Replicate failed, retry once then fall back to OpenAI
        if not result.get("success") and provider == "replicate":
            logger.warning("Replicate TTS failed (%s), retrying once...", result.get("error"))
            result = await _replicate_provider.generate(
                text=text,
                voice=voice,
                speed=resolved_speed,
                audio_path=audio_path,
                emotion=filtered_emotion,
                pitch=pitch,
                volume=volume,
                language_boost=language_boost,
            )
            if not result.get("success"):
                logger.warning("Replicate retry failed, falling back to OpenAI")
                result = await _openai_provider.generate(
                    text=text,
                    voice=voice,
                    speed=resolved_speed,
                    audio_path=audio_path,
                )
                if result.get("success"):
                    fallback_used = True
                    actual_provider = "openai"

        elapsed_ms = round((time.monotonic() - t0) * 1000)

        if not result.get("success"):
            # Check if it's an API key issue — return the old-style error
            error_msg = result.get("error", "TTS generation failed")
            if "OPENAI_API_KEY" in error_msg:
                return {
                    "success": False,
                    "error": "OPENAI_API_KEY environment variable is not configured",
                    "audio_path": None,
                }
            return {
                "success": False,
                "error": f"TTS generation failed: {error_msg}",
                "audio_path": None,
            }

        file_size = os.path.getsize(audio_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        estimated_duration = round(len(text) / 150 * 60 / resolved_speed, 1)

        logger.info(
            "TTS generated: provider=%s fallback=%s latency_ms=%d size_mb=%.2f",
            actual_provider, fallback_used, elapsed_ms, file_size_mb,
        )

        return {
            "success": True,
            "audio_path": audio_path,
            "filename": filename,
            "voice": voice,
            "speed": resolved_speed,
            "file_size_mb": file_size_mb,
            "estimated_duration_seconds": estimated_duration,
            "duration": estimated_duration,
            "text_length": len(text),
            "provider": actual_provider,
            "fallback_used": fallback_used,
            "latency_ms": elapsed_ms,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"TTS generation failed: {str(e)}",
            "audio_path": None,
        }


# ---------------------------------------------------------------------------
# Multi-speaker helpers (unchanged, used by Morning Show)
# ---------------------------------------------------------------------------

def _audio_url_from_path(audio_path: Optional[str]) -> Optional[str]:
    if not audio_path:
        return None
    filename = Path(audio_path).name
    return f"/data/audio/{filename}"


def _voice_assignment_for_age(age_group: str) -> Dict[str, Dict[str, float | str]]:
    table = {
        "3-5": {
            "curious_kid": {"voice": "nova", "speed": 0.9},
            "fun_expert": {"voice": "shimmer", "speed": 0.9},
            "guest": {"voice": "alloy", "speed": 0.9},
        },
        "6-8": {
            "curious_kid": {"voice": "shimmer", "speed": 1.0},
            "fun_expert": {"voice": "fable", "speed": 1.0},
            "guest": {"voice": "alloy", "speed": 1.0},
        },
        "9-12": {
            "curious_kid": {"voice": "echo", "speed": 1.1},
            "fun_expert": {"voice": "fable", "speed": 1.1},
            "guest": {"voice": "alloy", "speed": 1.1},
        },
    }
    return table.get(age_group, table["6-8"])


def _extract_lines(dialogue_script: Any) -> List[Dict[str, Any]]:
    if isinstance(dialogue_script, dict):
        return dialogue_script.get("lines", []) or []
    lines = getattr(dialogue_script, "lines", [])
    out: List[Dict[str, Any]] = []
    for line in lines:
        if hasattr(line, "model_dump"):
            out.append(line.model_dump())
        elif isinstance(line, dict):
            out.append(line)
        else:
            out.append(
                {
                    "role": getattr(line, "role", "guest"),
                    "text": getattr(line, "text", ""),
                    "timestamp_start": getattr(line, "timestamp_start", 0.0),
                    "timestamp_end": getattr(line, "timestamp_end", 1.0),
                }
            )
    return out


async def generate_multi_speaker_audio(dialogue_script: Any, age_group: str) -> Dict[str, str]:
    """
    Generate per-line multi-speaker audio for Morning Show dialogue (#92).

    Returns:
        Dict[str, str]: mapping of line_index -> audio_url
    """
    lines = _extract_lines(dialogue_script)
    if not lines:
        return {}

    voices = _voice_assignment_for_age(age_group)
    audio_urls: Dict[str, str] = {}

    # Try MCP batch generation first per role to reduce repeated API calls.
    try:
        from ..mcp_servers import generate_audio_batch

        if generate_audio_batch is not None:
            role_to_batch: Dict[str, List[Dict[str, Any]]] = {"curious_kid": [], "fun_expert": [], "guest": []}
            for index, line in enumerate(lines):
                role = str(line.get("role", "guest"))
                role_to_batch.setdefault(role, []).append({"segment_id": index, "text": line.get("text", "")})

            for role, segments in role_to_batch.items():
                if not segments:
                    continue
                voice_cfg = voices.get(role, {"voice": "alloy", "speed": 1.0})
                raw = await generate_audio_batch(
                    {
                        "story_segments": segments,
                        "voice": voice_cfg["voice"],
                        "speed": voice_cfg["speed"],
                    }
                )
                content = raw.get("content", []) if isinstance(raw, dict) else []
                if not content:
                    continue
                text = content[0].get("text", "{}") if isinstance(content[0], dict) else "{}"
                payload = json.loads(text)
                for item in payload.get("results", []) or []:
                    segment_id = item.get("segment_id")
                    url = _audio_url_from_path(item.get("audio_path"))
                    if segment_id is not None and url:
                        audio_urls[str(segment_id)] = url
    except Exception:
        # Fall through to per-line generation
        pass

    # Fill missing lines with direct TTS generation (or deterministic placeholders).
    for index, line in enumerate(lines):
        key = str(index)
        if key in audio_urls:
            continue

        role = str(line.get("role", "guest"))
        voice_cfg = voices.get(role, {"voice": "alloy", "speed": 1.0})
        text = str(line.get("text", "")).strip()

        if not text:
            continue

        generated = await generate_story_audio_file(
            text=text,
            voice=str(voice_cfg["voice"]),
            speed=float(voice_cfg["speed"]),
        )
        url = _audio_url_from_path(generated.get("audio_path"))
        if url:
            audio_urls[key] = url

    return audio_urls
