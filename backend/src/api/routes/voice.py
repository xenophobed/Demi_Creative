"""
Voice Cloning API Routes (#150)

Endpoints for cloning, listing, and deleting custom TTS voices.
Parent Epic: #45
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel

from ..deps import get_current_user
from ...services.user_service import UserData
from ...services.voice_service import (
    clone_voice,
    list_cloned_voices,
    delete_cloned_voice,
    validate_voice_file,
)
from ...paths import UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/voices",
    tags=["Voice Cloning"],
)


# ── Response Models ────────────────────────────────────────────────────────

class ClonedVoiceResponse(BaseModel):
    voice_id: str
    display_name: str
    replicate_voice_id: str
    created_at: Optional[str] = None


class VoiceCloneResult(BaseModel):
    success: bool
    voice_id: Optional[str] = None
    display_name: Optional[str] = None
    error: Optional[str] = None


class VoiceListResponse(BaseModel):
    voices: List[ClonedVoiceResponse]
    total: int


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post(
    "/clone",
    response_model=VoiceCloneResult,
    summary="Clone a voice from audio sample",
    description="Upload a voice sample (MP3/WAV/M4A, 10s-5min, <20MB) to create a custom TTS voice. Requires parental auth.",
)
async def clone_voice_endpoint(
    voice_file: UploadFile = File(...),
    display_name: str = Form(...),
    child_id: str = Form(...),
    user: UserData = Depends(get_current_user),
):
    """Clone a voice from an uploaded audio sample."""
    # Validate file
    file_data = await voice_file.read()
    filename = voice_file.filename or "upload.mp3"

    error = validate_voice_file(filename, len(file_data))
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Save temp file for Replicate
    voice_dir = UPLOAD_DIR / "voice_samples"
    voice_dir.mkdir(parents=True, exist_ok=True)
    temp_path = voice_dir / filename
    temp_path.write_bytes(file_data)

    try:
        result = await clone_voice(
            voice_file_path=str(temp_path),
            voice_file_data=file_data,
            display_name=display_name,
            user_id=user.user_id,
            child_id=child_id,
        )
    finally:
        # Clean up temp file
        temp_path.unlink(missing_ok=True)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.get("error", "Voice cloning failed"),
        )

    return VoiceCloneResult(
        success=True,
        voice_id=result["voice_id"],
        display_name=result["display_name"],
    )


@router.get(
    "",
    response_model=VoiceListResponse,
    summary="List cloned voices",
    description="Get all custom cloned voices for the authenticated user.",
)
async def list_voices_endpoint(
    user: UserData = Depends(get_current_user),
):
    """List all active cloned voices for the current user."""
    voices = await list_cloned_voices(user.user_id)
    return VoiceListResponse(
        voices=[
            ClonedVoiceResponse(
                voice_id=v["voice_id"],
                display_name=v["display_name"],
                replicate_voice_id=v["replicate_voice_id"],
                created_at=v.get("created_at"),
            )
            for v in voices
        ],
        total=len(voices),
    )


@router.delete(
    "/{voice_id}",
    summary="Delete a cloned voice",
    description="Soft-delete a cloned voice. Must belong to the authenticated user.",
)
async def delete_voice_endpoint(
    voice_id: str,
    user: UserData = Depends(get_current_user),
):
    """Delete a cloned voice."""
    deleted = await delete_cloned_voice(voice_id, user.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice not found or does not belong to you",
        )
    return {"success": True, "voice_id": voice_id}
