"""
Audio API Routes

Audio generation API endpoints
Supports on-demand audio generation (for the 10-12 age group)
and voice preview with disk caching (#333).
"""

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.requests import Request

from ..deps import get_current_user, get_session_for_owner, get_story_for_owner
from ..models import AgeGroup, EmotionType, TTSProviderEnum
from ...services.database import session_repo, story_repo
from ...services.user_service import UserData
from ...services.tts_service import generate_story_audio_file
from ...services.storage_adapter import storage
from ...mcp_servers.tts_generator_server import (
    OPENAI_VOICES,
    MINIMAX_VOICES,
    ELEVENLABS_VOICES,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio"]
)


# ---------------------------------------------------------------------------
# Voice catalog models (#244)
# ---------------------------------------------------------------------------


class VoiceEntry(BaseModel):
    """A single voice in the catalog."""
    voice_id: str = Field(..., description="Voice identifier")
    provider: str = Field(..., description="TTS provider (openai, replicate, elevenlabs)")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Voice description")
    recommended_for: str = Field(..., description="Age group / use case recommendation")


class VoiceCatalogResponse(BaseModel):
    """Voice catalog response."""
    voices: list[VoiceEntry] = Field(..., description="Available voices")
    total: int = Field(..., description="Total number of voices")


# Age group → recommended_for keyword mapping for filtering
_AGE_KEYWORDS = {
    "3-5": ["3-5", "3-6", "All", "bedtime"],
    "6-8": ["6-8", "6-9", "All", "fairy tales", "playful", "adventure", "educational"],
    "9-12": ["9-12", "All", "narration", "educational", "adventure", "action"],
}


@router.get(
    "/voices",
    response_model=VoiceCatalogResponse,
    summary="List available TTS voices",
    description="Returns the merged voice catalog from all TTS providers, with optional filtering",
)
async def list_voices(
    age_group: Optional[str] = None,
    provider: Optional[str] = None,
):
    """
    List available TTS voices (public — no auth required). (#244)
    """
    voices: list[dict] = []

    catalogs = [
        ("openai", OPENAI_VOICES),
        ("replicate", MINIMAX_VOICES),
        ("elevenlabs", ELEVENLABS_VOICES),
    ]

    for prov, catalog in catalogs:
        if provider and prov != provider:
            continue
        for voice_id, meta in catalog.items():
            entry = {
                "voice_id": voice_id,
                "provider": prov,
                "display_name": meta["display_name"],
                "description": meta["description"],
                "recommended_for": meta["recommended_for"],
            }

            # Apply age_group filter
            if age_group and age_group in _AGE_KEYWORDS:
                keywords = _AGE_KEYWORDS[age_group]
                rec = meta["recommended_for"].lower()
                if not any(kw.lower() in rec for kw in keywords):
                    continue

            voices.append(entry)

    return VoiceCatalogResponse(voices=voices, total=len(voices))


# ---------------------------------------------------------------------------
# Voice preview (#333) — rate limiter + endpoint
# ---------------------------------------------------------------------------

PREVIEW_TEXT = (
    "Once upon a time, in a magical land far away, "
    "a curious little adventurer set off on a journey."
)

# Simple in-memory rate limiter: IP -> list of request timestamps
_preview_rate: dict[str, list[float]] = defaultdict(list)
_PREVIEW_RATE_LIMIT = 10  # requests per minute
_PREVIEW_RATE_WINDOW = 60.0  # seconds


def _check_preview_rate(client_ip: str) -> None:
    """Raise 429 if *client_ip* exceeds the preview rate limit."""
    now = time.monotonic()
    timestamps = _preview_rate[client_ip]
    # Prune old entries
    _preview_rate[client_ip] = [t for t in timestamps if now - t < _PREVIEW_RATE_WINDOW]
    if len(_preview_rate[client_ip]) >= _PREVIEW_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many preview requests. Please wait a moment.",
        )
    _preview_rate[client_ip].append(now)


class VoicePreviewResponse(BaseModel):
    """Voice preview response."""
    voice_id: str = Field(..., description="Voice identifier")
    provider: str = Field(..., description="TTS provider")
    audio_url: str = Field(..., description="URL to the preview audio file")
    cached: bool = Field(..., description="Whether the result was served from cache")


_VALID_PROVIDERS = {"openai", "replicate", "elevenlabs"}


@router.get(
    "/preview",
    response_model=VoicePreviewResponse,
    summary="Preview a TTS voice",
    description="Generate a short audio sample for a voice. Cached to disk after first generation.",
)
async def preview_voice(
    request: Request,
    voice_id: str,
    provider: str = "openai",
):
    """
    Generate or return a cached 2-4 second voice preview (public — no auth). (#333)
    """
    # Validate provider
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider '{provider}'. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}",
        )

    # Rate limit
    client_ip = request.client.host if request.client else "unknown"
    _check_preview_rate(client_ip)

    # Check cache — try storage adapter first (works for both local and Supabase)
    cache_filename = f"previews/{provider}_{voice_id}.mp3"
    preview_dir = Path("./data/audio/previews")
    preview_dir.mkdir(parents=True, exist_ok=True)
    local_cache_path = preview_dir / f"{provider}_{voice_id}.mp3"

    if local_cache_path.exists() and local_cache_path.stat().st_size > 0:
        audio_url = await storage.get_url("audio", cache_filename)
        return VoicePreviewResponse(
            voice_id=voice_id,
            provider=provider,
            audio_url=audio_url,
            cached=True,
        )

    # Generate preview audio
    try:
        result = await generate_story_audio_file(
            text=PREVIEW_TEXT,
            voice=voice_id,
            speed=1.0,
            provider=provider,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Preview generation failed: {result.get('error', 'unknown error')}",
            )

        # Move generated file to local cache
        generated_path = Path(result["audio_path"])
        generated_path.rename(local_cache_path)

        # Upload to storage backend (Supabase in prod, no-op for local)
        audio_url = await storage.upload(
            "audio", cache_filename, local_cache_path.read_bytes(), "audio/mpeg"
        )

        return VoicePreviewResponse(
            voice_id=voice_id,
            provider=provider,
            audio_url=audio_url,
            cached=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Voice preview generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Preview generation failed. Please try again later.",
        )


class AudioGenerateRequest(BaseModel):
    """On-demand audio generation request"""
    session_id: str = Field(..., description="Session ID")
    segment_id: int = Field(..., description="Segment ID")
    voice: str = Field(default="alloy", description="Voice type")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    # Expressive TTS params (#149) — all optional, backward compatible
    emotion: Optional[EmotionType] = Field(default=None, description="TTS emotion")
    pitch: Optional[int] = Field(default=None, ge=-12, le=12, description="Pitch adjustment (-12 to 12)")
    volume: Optional[float] = Field(default=None, ge=0, le=10, description="Volume (0-10)")
    language_boost: Optional[str] = Field(default=None, description="Language boost (e.g. English, Chinese)")
    provider: Optional[TTSProviderEnum] = Field(default=None, description="TTS provider")
    age_group: Optional[AgeGroup] = Field(default=None, description="Age group for emotion filtering")


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
            audio_url=existing_url,
            duration=None,
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
        result = await generate_story_audio_file(
            text=text,
            voice=request.voice,
            speed=request.speed,
            child_age=None,
            emotion=request.emotion,
            pitch=request.pitch,
            volume=request.volume,
            language_boost=request.language_boost,
            provider=request.provider,
            age_group=request.age_group,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Audio generation failed")
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
    # Expressive TTS params (#149)
    emotion: Optional[EmotionType] = Field(default=None, description="TTS emotion")
    pitch: Optional[int] = Field(default=None, ge=-12, le=12, description="Pitch adjustment")
    volume: Optional[float] = Field(default=None, ge=0, le=10, description="Volume")
    language_boost: Optional[str] = Field(default=None, description="Language boost")
    provider: Optional[TTSProviderEnum] = Field(default=None, description="TTS provider")
    age_group: Optional[AgeGroup] = Field(default=None, description="Age group for emotion filtering")


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
            audio_url=existing_audio,
            duration=None,
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
        result = await generate_story_audio_file(
            text=text,
            voice=request.voice,
            speed=request.speed,
            child_age=None,
            emotion=request.emotion,
            pitch=request.pitch,
            volume=request.volume,
            language_boost=request.language_boost,
            provider=request.provider,
            age_group=request.age_group,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Audio generation failed")
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
