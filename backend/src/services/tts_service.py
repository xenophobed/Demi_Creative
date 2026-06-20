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
import re
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

try:
    from elevenlabs.client import AsyncElevenLabs as _elevenlabs_AsyncClient
    from elevenlabs import VoiceSettings as _elevenlabs_VoiceSettings
except Exception:  # pragma: no cover - import fallback for test env
    _elevenlabs_AsyncClient = None
    _elevenlabs_VoiceSettings = None


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

            loop = asyncio.get_running_loop()
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
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(None, _sync_replicate)
            Path(audio_path).write_bytes(audio_bytes)
            return {"success": True, "provider": "replicate"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# ElevenLabs provider (#243)
# ---------------------------------------------------------------------------

# Emotion → ElevenLabs voice settings mapping
_EMOTION_VOICE_SETTINGS: Dict[str, Dict[str, float]] = {
    "happy": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.4},
    "sad": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.3},
    "neutral": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.0},
    "surprised": {"stability": 0.25, "similarity_boost": 0.70, "style": 0.5},
    "disgusted": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.2},
}


class ElevenLabsTTSProvider:
    """ElevenLabs TTS provider with expressive voice settings (#243)."""

    DEFAULT_MODEL = "eleven_flash_v2_5"

    def _emotion_to_voice_settings(self, emotion: Optional[str]) -> Dict[str, float]:
        """Map emotion string to ElevenLabs voice settings."""
        if emotion and emotion in _EMOTION_VOICE_SETTINGS:
            return dict(_EMOTION_VOICE_SETTINGS[emotion])
        return dict(_EMOTION_VOICE_SETTINGS["neutral"])

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
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            return {"success": False, "error": "ELEVENLABS_API_KEY not configured"}

        if _elevenlabs_AsyncClient is None or _elevenlabs_VoiceSettings is None:
            return {"success": False, "error": "elevenlabs SDK not installed"}

        try:
            settings = self._emotion_to_voice_settings(emotion)
            voice_settings = _elevenlabs_VoiceSettings(
                stability=settings["stability"],
                similarity_boost=settings["similarity_boost"],
                style=settings["style"],
            )

            client = _elevenlabs_AsyncClient(api_key=api_key)

            convert_kwargs: Dict[str, Any] = {
                "voice_id": voice,
                "text": text,
                "model_id": self.DEFAULT_MODEL,
                "voice_settings": voice_settings,
                "output_format": "mp3_44100_128",
            }
            # ElevenLabs supports speed on Flash v2.5 (0.7-1.2 range)
            if speed != 1.0:
                convert_kwargs["speed"] = max(0.7, min(1.2, speed))

            audio_stream = await client.text_to_speech.convert(**convert_kwargs)

            # Collect audio bytes from async iterator
            chunks = []
            async for chunk in audio_stream:
                chunks.append(chunk)
            audio_bytes = b"".join(chunks)

            Path(audio_path).write_bytes(audio_bytes)
            return {"success": True, "provider": "elevenlabs"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Scene profile presets (#245)
# ---------------------------------------------------------------------------

SCENE_PROFILES: Dict[str, Dict[str, float]] = {
    "bedtime": {"speed": 0.85, "stability": 0.7, "style": 0.1},
    "adventure": {"speed": 1.1, "stability": 0.3, "style": 0.5},
    "spooky": {"speed": 0.95, "stability": 0.4, "style": 0.3},
    "educational": {"speed": 1.0, "stability": 0.65, "style": 0.0},
}


def resolve_scene_profile(
    profile: str, *, age_group: Optional[str] = None
) -> Optional[Dict[str, float]]:
    """Resolve a scene profile name to voice settings.

    Returns None for unknown profiles. Restricts 'spooky' to 9-12 age group,
    falling back to 'adventure' for younger children.
    """
    if profile not in SCENE_PROFILES:
        return None

    if profile == "spooky" and age_group in ("3-5", "6-8"):
        return dict(SCENE_PROFILES["adventure"])

    return dict(SCENE_PROFILES[profile])


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_openai_provider = OpenAITTSProvider()
_replicate_provider = ReplicateTTSProvider()
_elevenlabs_provider = ElevenLabsTTSProvider()
_OPENAI_VOICE_IDS = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}


def _select_provider(provider: Optional[str]) -> TTSProvider:
    if provider == "replicate":
        return _replicate_provider
    if provider == "elevenlabs":
        return _elevenlabs_provider
    return _openai_provider


# ---------------------------------------------------------------------------
# Public API (backward-compatible)
# ---------------------------------------------------------------------------

def get_audio_output_path() -> str:
    """Get the audio output directory."""
    from ..paths import AUDIO_DIR
    audio_dir = os.getenv("AUDIO_OUTPUT_PATH", str(AUDIO_DIR))
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
        actual_provider = provider or "openai"

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

        # Fallback: if non-OpenAI provider failed, retry once then fall back to OpenAI
        if not result.get("success") and provider in ("replicate", "elevenlabs"):
            error_msg = result.get("error", "")
            # Skip retry for deterministic failures (missing token/key, SDK not installed)
            deterministic_markers = (
                "REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "SDK not installed",
            )
            is_deterministic = any(s in error_msg for s in deterministic_markers)

            if not is_deterministic:
                logger.warning("%s TTS failed (%s), retrying once...", provider, error_msg)
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

            if not result.get("success"):
                logger.warning("%s failed (%s), falling back to OpenAI", provider, error_msg)
                # Map non-OpenAI voice IDs to a safe OpenAI default
                fallback_voice = voice if voice in _OPENAI_VOICE_IDS else "nova"
                result = await _openai_provider.generate(
                    text=text,
                    voice=fallback_voice,
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


def _strip_self_name_prefix(text: str, speaker_name: Optional[str]) -> str:
    """Strip a leading ``"Name:"`` / ``"Name says:"`` self-introduction.

    Only the line's *own* speaker name is removed (case-insensitive), so real
    content like ``"Today: we learned..."`` is never touched. Mirrors the
    agent-side guard in ``kids_daily_agent`` for defense-in-depth.
    """
    if not text or not speaker_name:
        return text
    name = re.escape(str(speaker_name).strip())
    if not name:
        return text
    pattern = rf"^\s*{name}\s*(?:says|said)?\s*[:\-—]\s*"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).lstrip()


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

    # Defense-in-depth: never let a speaker's own name leak into synthesized
    # audio. Generators keep ``text`` name-free, but if a stale/cached script
    # still carries a "Name: ..." prefix we strip it here using the line's own
    # display_name so the child never hears "Duo, great question."
    for line in lines:
        if isinstance(line, dict):
            line["text"] = _strip_self_name_prefix(
                str(line.get("text", "")), line.get("display_name")
            )

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

            async def _role_batch(role: str, segments: List[Dict[str, Any]]):
                voice_cfg = voices.get(role, {"voice": "alloy", "speed": 1.0})
                return await generate_audio_batch(
                    {
                        "story_segments": segments,
                        "voice": voice_cfg["voice"],
                        "speed": voice_cfg["speed"],
                    }
                )

            # Generate each role's batch concurrently instead of role-by-role.
            active_roles = [(r, s) for r, s in role_to_batch.items() if s]
            raws = await asyncio.gather(
                *[_role_batch(r, s) for r, s in active_roles],
                return_exceptions=True,
            )
            for raw in raws:
                if isinstance(raw, Exception):
                    continue
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

    # Fill any lines the batch path missed with direct TTS — concurrently.
    missing: List[tuple] = []
    for index, line in enumerate(lines):
        key = str(index)
        if key in audio_urls:
            continue
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        role = str(line.get("role", "guest"))
        voice_cfg = voices.get(role, {"voice": "alloy", "speed": 1.0})
        missing.append((key, text, voice_cfg))

    if missing:
        async def _one_line(text: str, voice_cfg: Dict[str, Any]):
            return await generate_story_audio_file(
                text=text,
                voice=str(voice_cfg["voice"]),
                speed=float(voice_cfg["speed"]),
            )

        gens = await asyncio.gather(
            *[_one_line(t, vc) for _, t, vc in missing],
            return_exceptions=True,
        )
        for (key, _text, _vc), gen in zip(missing, gens):
            if isinstance(gen, Exception) or not isinstance(gen, dict):
                continue
            url = _audio_url_from_path(gen.get("audio_path"))
            if url:
                audio_urls[key] = url

    return audio_urls
