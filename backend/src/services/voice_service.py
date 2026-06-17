"""Voice cloning service (#150).

Orchestrates voice cloning via Replicate's minimax/voice-cloning model
and manages cloned voice lifecycle through the voice repository.

Parent Epic: #45
"""

import hashlib
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import replicate as _replicate_module
except Exception:  # pragma: no cover
    _replicate_module = None

# Allowed audio formats and constraints
ALLOWED_FORMATS = {".mp3", ".wav", ".m4a"}
MIN_DURATION_SECONDS = 10
MAX_DURATION_SECONDS = 300  # 5 minutes
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

VOICE_CLONE_MODEL = "minimax/voice-cloning"


def validate_voice_file(file_path: str, file_size: int) -> Optional[str]:
    """Validate voice file format and size. Returns error string or None."""
    ext = Path(file_path).suffix.lower()
    if ext not in ALLOWED_FORMATS:
        return f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_FORMATS))}"
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return f"File too large ({file_size / (1024*1024):.1f} MB). Maximum: {max_mb:.0f} MB"
    if file_size == 0:
        return "File is empty"
    return None


def get_audio_duration_seconds(file_path: str) -> Optional[float]:
    """Best-effort audio duration. Tries mutagen (pure-python, available in
    every environment incl. the slim prod image) first, then ffprobe. Returns
    None when neither can determine it, so callers never hard-block on a probe
    failure — the provider stays the final gate."""
    # 1. mutagen — portable, no system binary required.
    try:
        from mutagen import File as _MutagenFile
        info = getattr(_MutagenFile(file_path), "info", None)
        length = getattr(info, "length", None)
        if length and length > 0:
            return float(length)
    except Exception:
        pass
    # 2. ffprobe fallback — present in local dev, may be absent in prod.
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        out = (result.stdout or "").strip()
        return float(out) if result.returncode == 0 and out else None
    except Exception:
        return None


def validate_voice_duration(file_path: str) -> Optional[str]:
    """Enforce minimax's 10s-5min clone window with a friendly message.

    Best-effort: if the duration can't be measured (no ffprobe), returns None
    and lets the provider remain the final gate — so we never block a valid
    upload just because probing failed.
    """
    duration = get_audio_duration_seconds(file_path)
    if duration is None:
        return None
    if duration < MIN_DURATION_SECONDS:
        return (
            f"Voice sample is too short ({duration:.0f}s). Please upload "
            f"{MIN_DURATION_SECONDS}-{MAX_DURATION_SECONDS}s of clear speech."
        )
    if duration > MAX_DURATION_SECONDS:
        return (
            f"Voice sample is too long ({duration:.0f}s). Maximum "
            f"{MAX_DURATION_SECONDS // 60} minutes."
        )
    return None


def _file_hash(data: bytes) -> str:
    """SHA-256 hash of file content for dedup."""
    return hashlib.sha256(data).hexdigest()


async def clone_voice(
    voice_file_path: str,
    voice_file_data: bytes,
    display_name: str,
    user_id: str,
    child_id: str,
) -> Dict[str, Any]:
    """Clone a voice using Replicate and persist to DB.

    Returns dict with voice_id, display_name, replicate_voice_id, status.
    """
    from .database import voice_repo

    if _replicate_module is None:
        return {"success": False, "error": "Replicate SDK not installed"}

    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        return {"success": False, "error": "REPLICATE_API_TOKEN not configured"}

    file_hash = _file_hash(voice_file_data)

    # Call Replicate voice cloning
    try:
        with open(voice_file_path, "rb") as voice_fh:
            output = _replicate_module.run(
                VOICE_CLONE_MODEL,
                input={
                    "model": "speech-02-turbo",
                    "accuracy": 0.7,
                    "voice_file": voice_fh,
                    "need_noise_reduction": False,
                    "need_volume_normalization": False,
                },
            )

        # Replicate returns the cloned voice_id in output
        replicate_voice_id = str(output) if output else None
        if not replicate_voice_id:
            return {"success": False, "error": "Replicate returned empty voice ID"}

    except Exception as exc:
        logger.error("Voice cloning failed: %s", exc)
        return {"success": False, "error": f"Voice cloning failed: {exc}"}

    # Persist to DB
    voice_id = str(uuid.uuid4())
    try:
        record = await voice_repo.create_voice(
            voice_id=voice_id,
            user_id=user_id,
            child_id=child_id,
            display_name=display_name,
            replicate_voice_id=replicate_voice_id,
            voice_file_hash=file_hash,
        )
        return {
            "success": True,
            "voice_id": voice_id,
            "display_name": display_name,
            "replicate_voice_id": replicate_voice_id,
            "created_at": record.get("created_at"),
        }
    except Exception as exc:
        logger.error("Failed to persist cloned voice: %s", exc)
        return {"success": False, "error": f"Failed to save voice: {exc}"}


async def list_cloned_voices(user_id: str) -> List[Dict[str, Any]]:
    """List all active cloned voices for a user."""
    from .database import voice_repo
    return await voice_repo.get_voices_for_user(user_id)


async def delete_cloned_voice(voice_id: str, user_id: str) -> bool:
    """Soft-delete a cloned voice. Returns True if deleted."""
    from .database import voice_repo
    return await voice_repo.deactivate_voice(voice_id, user_id)
