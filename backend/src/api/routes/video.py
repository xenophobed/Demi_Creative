"""
Video API Routes

Video generation API endpoints
Supports generating animated videos from children's artwork
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ..models import (
    VideoJobRequest,
    VideoJobResponse,
    VideoJobStatusResponse,
    VideoStyle,
    VideoStatus
)
from ..deps import get_current_user, get_story_for_owner
from ...mcp_servers import generate_painting_video, check_video_status, combine_video_audio
from ...services.database import story_repo
from ...services.user_service import UserData


router = APIRouter(
    prefix="/api/v1/video",
    tags=["Video Generation"]
)


# ============================================================================
# Configuration
# ============================================================================
from ...paths import VIDEO_DIR, VIDEO_JOBS_DIR, DATA_DIR


def load_job_from_file(job_id: str) -> Optional[dict]:
    """Load job status from file"""
    job_file = VIDEO_JOBS_DIR / f"{job_id}.json"
    if job_file.exists():
        with open(job_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@router.post(
    "/generate",
    response_model=VideoJobResponse,
    summary="Generate video",
    description="Generate an animated video for an artwork story",
    status_code=status.HTTP_202_ACCEPTED
)
async def generate_video(
    request: VideoJobRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Generate an artwork animation video (requires authentication + story ownership)
    """
    # 1. Get story and verify ownership
    story = await get_story_for_owner(request.story_id, user.user_id)

    # 2. Get artwork image path
    image_path = story.get("image_path")
    if not image_path:
        # Try to infer path from image_url
        image_url = story.get("image_url", "")
        if image_url.startswith("/data/"):
            image_path = str(DATA_DIR / image_url.removeprefix("/data/"))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Story is missing artwork image"
            )

    if not Path(image_path).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Artwork image file not found: {image_path}"
        )

    # 3. Call video generation tool
    try:
        result = await generate_painting_video({
            "image_path": image_path,
            "style": request.style.value,
            "duration_seconds": request.duration_seconds,
            "story_id": request.story_id
        })

        result_data = json.loads(result["content"][0]["text"])

        if not result_data.get("success") and not result_data.get("job_id"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result_data.get("error", "Video generation failed")
            )

        job_id = result_data["job_id"]
        job_status = result_data.get("status", "pending")

        # Calculate estimated completion time
        estimated_completion = None
        if job_status == "pending":
            estimated_completion = datetime.now() + timedelta(minutes=5)
        elif result_data.get("estimated_completion"):
            estimated_completion = datetime.fromisoformat(
                result_data["estimated_completion"]
            )

        # 4. If audio was requested and video is already completed, combine audio
        if request.include_audio and job_status == "completed":
            audio_url = story.get("audio_url")
            if audio_url:
                video_path = result_data.get("video_path")
                audio_path = str(DATA_DIR / audio_url.removeprefix("/data/"))

                if video_path and Path(audio_path).exists():
                    combine_result = await combine_video_audio({
                        "video_path": video_path,
                        "audio_path": audio_path,
                        "output_filename": f"combined_{job_id}.mp4"
                    })

                    combine_data = json.loads(combine_result["content"][0]["text"])
                    if combine_data.get("success"):
                        # Update job status file
                        job_file = VIDEO_JOBS_DIR / f"{job_id}.json"
                        if job_file.exists():
                            with open(job_file, "r", encoding="utf-8") as f:
                                job_data = json.load(f)
                            job_data["combined_video_url"] = combine_data["video_url"]
                            job_data["combined_video_path"] = combine_data["output_path"]
                            with open(job_file, "w", encoding="utf-8") as f:
                                json.dump(job_data, f, ensure_ascii=False, indent=2)

        return VideoJobResponse(
            job_id=job_id,
            story_id=request.story_id,
            status=VideoStatus(job_status),
            estimated_completion=estimated_completion,
            created_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video generation failed, please try again later"
        )


@router.get(
    "/status/{job_id}",
    response_model=VideoJobStatusResponse,
    summary="Check video generation status",
    description="Check video generation progress by job ID"
)
async def get_video_status(
    job_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Check video generation job status (requires authentication + story ownership)
    """
    try:
        # Verify ownership via the job's story_id
        job_data_check = load_job_from_file(job_id)
        if job_data_check and job_data_check.get("story_id"):
            await get_story_for_owner(job_data_check["story_id"], user.user_id)

        result = await check_video_status({"job_id": job_id})
        result_data = json.loads(result["content"][0]["text"])

        if not result_data.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result_data.get("error", f"Job not found: {job_id}")
            )

        # Load job details to get combined video URL
        job_data = load_job_from_file(job_id)
        video_url = result_data.get("video_url")

        # Prefer combined video
        if job_data and job_data.get("combined_video_url"):
            video_url = job_data["combined_video_url"]

        created_at = datetime.now()
        if result_data.get("created_at"):
            created_at = datetime.fromisoformat(result_data["created_at"])

        completed_at = None
        if result_data.get("completed_at"):
            completed_at = datetime.fromisoformat(result_data["completed_at"])

        return VideoJobStatusResponse(
            job_id=job_id,
            status=VideoStatus(result_data["status"]),
            progress_percent=result_data.get("progress_percent", 0),
            video_url=video_url,
            error_message=result_data.get("error_message"),
            created_at=created_at,
            completed_at=completed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking video status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check status"
        )


@router.get(
    "/{video_id}",
    summary="Get video info",
    description="Get video metadata by video ID",
    responses={
        200: {"description": "Successfully retrieved video info"},
        404: {"description": "Video not found"}
    }
)
async def get_video_info(
    video_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Get video metadata (requires authentication + story ownership)
    """
    job_data = load_job_from_file(video_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}"
        )

    # Verify ownership via the job's story_id
    if job_data.get("story_id"):
        await get_story_for_owner(job_data["story_id"], user.user_id)

    if job_data.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video generation not yet complete, current status: {job_data.get('status')}"
        )

    # Get video file info
    video_path = job_data.get("video_path")
    combined_path = job_data.get("combined_video_path")

    # Prefer combined video
    final_path = combined_path if combined_path else video_path
    final_url = job_data.get("combined_video_url") or f"/data/videos/{job_data.get('video_filename')}"

    file_size_mb = None
    if final_path and Path(final_path).exists():
        file_size = Path(final_path).stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)

    return JSONResponse(content={
        "video_id": video_id,
        "story_id": job_data.get("story_id"),
        "status": job_data.get("status"),
        "style": job_data.get("style"),
        "duration_seconds": job_data.get("duration_seconds"),
        "video_url": final_url,
        "has_audio": bool(combined_path),
        "file_size_mb": file_size_mb,
        "created_at": job_data.get("created_at"),
        "completed_at": job_data.get("completed_at")
    })


@router.get(
    "/story/{story_id}",
    summary="Get all videos for a story",
    description="Get all videos associated with a specific story"
)
async def get_videos_by_story(
    story_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Get list of videos associated with a story (requires authentication + story ownership)
    """
    await get_story_for_owner(story_id, user.user_id)

    # Scan job directory for related videos
    videos = []
    if VIDEO_JOBS_DIR.exists():
        for job_file in VIDEO_JOBS_DIR.glob("*.json"):
            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    job_data = json.load(f)

                if job_data.get("story_id") == story_id:
                    video_url = job_data.get("combined_video_url") or (
                        f"/data/videos/{job_data.get('video_filename')}"
                        if job_data.get("video_filename") else None
                    )

                    videos.append({
                        "video_id": job_data.get("job_id"),
                        "status": job_data.get("status"),
                        "style": job_data.get("style"),
                        "video_url": video_url if job_data.get("status") == "completed" else None,
                        "has_audio": bool(job_data.get("combined_video_url")),
                        "created_at": job_data.get("created_at")
                    })
            except (json.JSONDecodeError, IOError):
                continue

    # Sort by creation time
    videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return JSONResponse(content={
        "story_id": story_id,
        "total": len(videos),
        "videos": videos
    })
