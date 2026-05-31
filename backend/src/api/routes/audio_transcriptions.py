"""
Audio Transcriptions API (#583)

Speech-to-text endpoint for the voice-input surfaces in epic #579
(PRD §3.15). Accepts a small audio clip from the browser, transcribes
it via the STT service, and returns the safety-moderated transcript.

Hard rules from PRD §3.15:
  - Audio bytes are processed in memory and never persisted to disk.
  - The transcript is moderated by ``check_content_safety`` before it is
    returned; failures return ``safety_passed=False, text=""``.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..deps import get_current_user
from ...services.stt_service import (
    MAX_AUDIO_BYTES,
    MAX_DURATION_MS,
    transcribe_audio_bytes,
    validate_audio_file,
)
from ...services.user_service import UserData

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio Transcriptions"],
)


class TranscriptionResponse(BaseModel):
    """Response envelope for POST /audio/transcriptions."""
    text: str
    language: str
    duration_ms: int
    safety_passed: bool


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    summary="Transcribe a short audio clip from a child voice-input surface",
)
async def transcribe_audio(
    audio: UploadFile = File(...),
    target_age: int = Form(7),
    language_hint: Optional[str] = Form(None),
    user: UserData = Depends(get_current_user),
) -> TranscriptionResponse:
    audio_bytes = await audio.read()
    mime_type = audio.content_type or "application/octet-stream"

    validation_error = validate_audio_file(mime_type, len(audio_bytes))
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AUDIO", "message": validation_error},
        )

    result = await transcribe_audio_bytes(
        audio_bytes,
        mime_type,
        target_age=target_age,
        language_hint=language_hint,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "TRANSCRIPTION_FAILED",
                "message": result.get("error", "Provider error"),
            },
        )

    if result["duration_ms"] > MAX_DURATION_MS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "AUDIO_TOO_LONG",
                "message": f"Audio exceeds {MAX_DURATION_MS // 1000}s limit",
            },
        )

    return TranscriptionResponse(
        text=result["text"],
        language=result["language"],
        duration_ms=result["duration_ms"],
        safety_passed=result["safety_passed"],
    )
