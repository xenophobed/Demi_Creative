"""
TTS service layer.

Provides a plain callable API for story audio generation.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None


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
) -> Dict[str, Any]:
    """Generate story audio file and return a normalized result payload."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not configured",
            "audio_path": None,
        }

    if not text:
        return {
            "success": False,
            "error": "story text is empty",
            "audio_path": None,
        }

    resolved_speed = _resolve_speed(speed, child_age)

    try:
        if OpenAI is None:
            return {
                "success": False,
                "error": "OpenAI SDK is unavailable in current environment",
                "audio_path": None,
            }

        client = OpenAI(api_key=api_key)

        timestamp = datetime.now().isoformat()
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"story_{text_hash}_{timestamp.replace(':', '-')}.mp3"

        audio_dir = get_audio_output_path()
        audio_path = os.path.join(audio_dir, filename)

        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            speed=resolved_speed,
        )
        response.stream_to_file(audio_path)

        file_size = os.path.getsize(audio_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        estimated_duration = round(len(text) / 150 * 60 / resolved_speed, 1)

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
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"TTS generation failed: {str(e)}",
            "audio_path": None,
        }
