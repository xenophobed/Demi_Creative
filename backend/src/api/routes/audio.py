"""
Audio API Routes

Audio generation API endpoints
Supports on-demand audio generation (for the 10-12 age group)
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..deps import get_current_user, get_session_for_owner, get_story_for_owner
from ...services.database import session_repo, story_repo
from ...services.user_service import UserData
from ...mcp_servers import generate_story_audio


router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio"]
)


class AudioGenerateRequest(BaseModel):
    """On-demand audio generation request"""
    session_id: str = Field(..., description="Session ID")
    segment_id: int = Field(..., description="Segment ID")
    voice: str = Field(default="alloy", description="Voice type")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")


class AudioGenerateResponse(BaseModel):
    """Audio generation response"""
    session_id: str = Field(..., description="Session ID")
    segment_id: int = Field(..., description="Segment ID")
    audio_url: str = Field(..., description="Audio URL")
    duration: Optional[float] = Field(None, description="Audio duration (seconds)")


@router.post(
    "/generate",
    response_model=AudioGenerateResponse,
    summary="Generate audio on demand",
    description="Generate audio for a specific session segment (primarily for on-demand playback in the 10-12 age group)",
    status_code=status.HTTP_201_CREATED
)
async def generate_audio_on_demand(
    request: AudioGenerateRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Generate audio on demand (requires authentication + session ownership)
    """
    # 1. Get session and verify ownership
    session = await get_session_for_owner(request.session_id, user.user_id)

    # 2. Check if audio already exists for this segment
    audio_urls = getattr(session, 'audio_urls', None) or {}
    if request.segment_id in audio_urls:
        existing_url = audio_urls[request.segment_id]
        return AudioGenerateResponse(
            session_id=request.session_id,
            segment_id=request.segment_id,
            audio_url=existing_url
        )

    # 3. Get segment text
    if request.segment_id >= len(session.segments):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {request.segment_id} not found"
        )

    segment = session.segments[request.segment_id]
    text = segment.get("text", "")

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment text is empty, cannot generate audio"
        )

    # 4. Call TTS service to generate audio
    try:
        result = await generate_story_audio(
            text=text,
            voice=request.voice,
            speed=request.speed,
            child_id=session.child_id,
            session_id=request.session_id
        )

        audio_path = result.get("audio_path")
        if not audio_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audio generation failed"
            )

        # 5. Build audio URL
        audio_filename = Path(audio_path).name
        audio_url = f"/data/audio/{audio_filename}"

        # 6. Update session, save audio URL
        await session_repo.update_session(
            session_id=request.session_id,
            audio_url=audio_url,
            segment_id=request.segment_id
        )

        return AudioGenerateResponse(
            session_id=request.session_id,
            segment_id=request.segment_id,
            audio_url=audio_url,
            duration=result.get("duration")
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audio generation failed, please try again later"
        )


class StoryAudioGenerateRequest(BaseModel):
    """Generate audio for an image-to-story"""
    story_id: str = Field(..., description="Story ID")
    voice: str = Field(default="alloy", description="Voice type")
    speed: float = Field(default=1.1, ge=0.5, le=2.0, description="Speech speed")


class StoryAudioGenerateResponse(BaseModel):
    """Audio generation response for stories"""
    story_id: str = Field(..., description="Story ID")
    audio_url: str = Field(..., description="Audio URL")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")


@router.post(
    "/generate-for-story",
    response_model=StoryAudioGenerateResponse,
    summary="Generate audio for an image-to-story",
    description="Generate TTS audio for a story (for 10-12 age group on-demand playback)",
    status_code=status.HTTP_201_CREATED
)
async def generate_audio_for_story(
    request: StoryAudioGenerateRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Generate audio on-demand for an image-to-story. Requires authentication + story ownership.
    """
    # 1. Look up the story and verify ownership
    story = await get_story_for_owner(request.story_id, user.user_id)

    # 2. Return existing audio if already generated
    existing_audio = story.get("audio_url")
    if existing_audio:
        return StoryAudioGenerateResponse(
            story_id=request.story_id,
            audio_url=existing_audio
        )

    # 3. Get story text
    story_content = story.get("story", {})
    text = story_content.get("text", "")
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story text is empty, cannot generate audio"
        )

    # 4. Generate TTS audio
    try:
        result = await generate_story_audio(
            text=text,
            voice=request.voice,
            speed=request.speed,
            child_id=story.get("child_id", ""),
        )

        audio_path = result.get("audio_path")
        if not audio_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audio generation failed"
            )

        # 5. Build audio URL and update story record
        audio_filename = Path(audio_path).name
        audio_url = f"/data/audio/{audio_filename}"

        await story_repo._db.execute(
            "UPDATE stories SET audio_url = ? WHERE story_id = ?",
            (audio_url, request.story_id)
        )
        await story_repo._db.commit()

        return StoryAudioGenerateResponse(
            story_id=request.story_id,
            audio_url=audio_url,
            duration=result.get("duration")
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating audio for story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audio generation failed, please try again"
        )


@router.get(
    "/session/{session_id}",
    summary="Get all audio for a session",
    description="Get all generated audio URLs for a specified session"
)
async def get_session_audio(
    session_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Get all audio URLs for a session (requires authentication + session ownership)
    """
    session = await get_session_for_owner(session_id, user.user_id)
    audio_urls = getattr(session, 'audio_urls', None) or {}
    return {
        "session_id": session_id,
        "audio_urls": audio_urls
    }
