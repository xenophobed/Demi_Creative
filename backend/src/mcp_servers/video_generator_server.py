"""
Video Generation MCP Server

Provides tools for generating animated videos from children's paintings using OpenAI Sora.
"""

import os
import json
import base64
import subprocess
from typing import Any, Dict, Optional
from pathlib import Path
import uuid
from datetime import datetime, timedelta

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except Exception:  # pragma: no cover - import fallback for test env
    def tool(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# Video style prompts for child-friendly animation
VIDEO_STYLE_PROMPTS = {
    "gentle_animation": "Gently animate this children's painting with soft, slow movements. Keep the original artwork style intact while adding subtle motion like swaying trees, twinkling stars, or gently moving characters. The animation should be calm and soothing, suitable for all ages.",
    "playful": "Create a playful animation from this children's painting. Add bouncy, fun movements to the characters and elements. Keep the whimsical, child-drawn quality while making elements dance and move joyfully.",
    "storybook": "Transform this children's painting into a storybook-style animation. Add gentle page-turning effects and bring elements to life as if the drawing is coming alive from a magical book."
}


def get_video_output_path():
    """Get video output directory"""
    video_dir = os.getenv("VIDEO_OUTPUT_PATH", "./data/videos")
    Path(video_dir).mkdir(parents=True, exist_ok=True)
    return video_dir


def get_video_jobs_path():
    """Get video jobs directory"""
    jobs_dir = "./data/video_jobs"
    Path(jobs_dir).mkdir(parents=True, exist_ok=True)
    return jobs_dir


def encode_image_to_base64(image_path: str) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    """Get image MIME type"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    return mime_types.get(ext, "image/png")


# Sora only renders fixed clip lengths; map any requested duration onto one.
SORA_SUPPORTED_DURATIONS = (4, 8, 12)


def nearest_supported_duration(duration_seconds: int) -> str:
    """Snap a requested duration to the nearest Sora-supported clip length.

    Sora's videos API only accepts 4, 8, or 12 second clips, so an arbitrary
    request (e.g. the legacy default of 10) must be coerced or the call fails.
    """
    try:
        requested = int(duration_seconds)
    except (TypeError, ValueError):
        requested = SORA_SUPPORTED_DURATIONS[0]
    closest = min(SORA_SUPPORTED_DURATIONS, key=lambda s: abs(s - requested))
    return str(closest)


def save_job_status(job_id: str, job_data: Dict[str, Any]) -> None:
    """Save job status to file"""
    jobs_dir = get_video_jobs_path()
    job_file = Path(jobs_dir) / f"{job_id}.json"
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2, default=str)


def load_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Load job status"""
    jobs_dir = get_video_jobs_path()
    job_file = Path(jobs_dir) / f"{job_id}.json"
    if job_file.exists():
        with open(job_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@tool(
    "generate_painting_video",
    """Generate an animated video from a children's painting using OpenAI Sora.

    This tool:
    1. Takes a children's painting image
    2. Generates a child-friendly animated video
    3. Returns a job ID for tracking the async generation

    The video will animate elements within the painting while preserving
    the original artistic style.""",
    {
        "image_path": str,
        "style": str,
        "duration_seconds": int,
        "story_id": str
    }
)
async def generate_painting_video(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate animated video from painting

    Args:
        args: Dictionary containing image_path, style, duration_seconds, story_id

    Returns:
        Dictionary containing job ID and status
    """
    image_path = args["image_path"]
    style = args.get("style", "gentle_animation")
    duration_seconds = args.get("duration_seconds", 10)
    story_id = args.get("story_id", "")

    # Verify image exists
    if not Path(image_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Image file not found: {image_path}",
                    "job_id": None
                }, ensure_ascii=False)
            }]
        }

    # Check OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "OPENAI_API_KEY environment variable not configured",
                    "job_id": None
                }, ensure_ascii=False)
            }]
        }

    try:
        client = OpenAI(api_key=api_key)

        # Generate job ID
        job_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # Get style prompt
        style_prompt = VIDEO_STYLE_PROMPTS.get(
            style,
            VIDEO_STYLE_PROMPTS["gentle_animation"]
        )

        # Generate the animation with OpenAI Sora. The painting is supplied as a
        # visual reference through the dedicated videos API.
        #
        # The previous implementation called client.images.generate(image=...),
        # which raises "unexpected keyword argument 'image'": images.generate()
        # accepts no image input and returns stills, not video. Sora is exposed
        # via client.videos.* instead.
        seconds = nearest_supported_duration(duration_seconds)

        with open(image_path, "rb") as image_file:
            video_job = client.videos.create_and_poll(
                model="sora-2",
                prompt=style_prompt,
                input_reference=image_file,
                seconds=seconds,
                size="1280x720",
            )

        if getattr(video_job, "status", None) != "completed":
            failure = getattr(video_job, "error", None)
            reason = getattr(failure, "message", None) or failure or "unknown error"
            raise Exception(
                f"Sora video job ended with status "
                f"'{getattr(video_job, 'status', 'unknown')}': {reason}"
            )

        # Download the rendered video locally.
        video_dir = get_video_output_path()
        video_filename = f"video_{job_id}.mp4"
        video_path = Path(video_dir) / video_filename
        client.videos.download_content(
            video_job.id, variant="video"
        ).write_to_file(str(video_path))

        # Save job status
        job_data = {
            "job_id": job_id,
            "story_id": story_id,
            "status": "completed",
            "progress_percent": 100,
            "video_path": str(video_path),
            "video_filename": video_filename,
            "style": style,
            "duration_seconds": int(seconds),
            "created_at": timestamp.isoformat(),
            "completed_at": datetime.now().isoformat()
        }
        save_job_status(job_id, job_data)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "job_id": job_id,
                    "status": "completed",
                    "video_path": str(video_path),
                    "video_filename": video_filename,
                    "video_url": f"/data/videos/{video_filename}"
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        error_message = str(e)

        # Fail fast (#182): no async worker exists to resolve pending jobs,
        # so report the failure immediately instead of creating a phantom job.
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "story_id": story_id,
            "status": "failed",
            "progress_percent": 0,
            "style": style,
            "duration_seconds": duration_seconds,
            "image_path": image_path,
            "created_at": datetime.now().isoformat(),
            "error": error_message,
        }
        save_job_status(job_id, job_data)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "job_id": job_id,
                    "status": "failed",
                    "error": f"Video generation failed: {error_message}",
                }, ensure_ascii=False, indent=2)
            }]
        }


@tool(
    "check_video_status",
    """Check the status of a video generation job.

    Returns the current status, progress percentage, and video URL if completed.""",
    {"job_id": str}
)
async def check_video_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check video generation job status

    Args:
        args: Dictionary containing job_id

    Returns:
        Job status information
    """
    job_id = args["job_id"]

    job_data = load_job_status(job_id)
    if not job_data:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Job not found: {job_id}"
                }, ensure_ascii=False)
            }]
        }

    # If job is in pending status, check for external updates
    # In production, this might poll an external API or message queue
    status = job_data.get("status", "pending")

    response = {
        "success": True,
        "job_id": job_id,
        "status": status,
        "progress_percent": job_data.get("progress_percent", 0),
        "created_at": job_data.get("created_at"),
        "completed_at": job_data.get("completed_at"),
        "estimated_completion": job_data.get("estimated_completion")
    }

    if status == "completed":
        video_filename = job_data.get("video_filename")
        if video_filename:
            response["video_url"] = f"/data/videos/{video_filename}"
            response["video_path"] = job_data.get("video_path")

    if status == "failed":
        response["error_message"] = job_data.get("error")

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "combine_video_audio",
    """Combine a generated video with audio narration.

    Uses ffmpeg to merge video and audio files into a single video with narration.""",
    {"video_path": str, "audio_path": str, "output_filename": str}
)
async def combine_video_audio(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine video and audio

    Args:
        args: Dictionary containing video_path, audio_path, output_filename

    Returns:
        Combined video path
    """
    video_path = args["video_path"]
    audio_path = args["audio_path"]
    output_filename = args.get("output_filename")

    # Verify files exist
    if not Path(video_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Video file not found: {video_path}"
                }, ensure_ascii=False)
            }]
        }

    if not Path(audio_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Audio file not found: {audio_path}"
                }, ensure_ascii=False)
            }]
        }

    try:
        # Generate output filename
        if not output_filename:
            video_stem = Path(video_path).stem
            output_filename = f"combined_{video_stem}.mp4"

        video_dir = get_video_output_path()
        output_path = Path(video_dir) / output_filename

        # Use ffmpeg to combine video and audio
        # -i: input file
        # -c:v copy: copy video stream (no re-encoding)
        # -c:a aac: encode audio with AAC
        # -shortest: use the shortest stream as reference
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2-minute timeout
        )

        if result.returncode != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": f"ffmpeg merge failed: {result.stderr}"
                    }, ensure_ascii=False)
                }]
            }

        # Get file size
        file_size = output_path.stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "output_path": str(output_path),
                    "output_filename": output_filename,
                    "video_url": f"/data/videos/{output_filename}",
                    "file_size_mb": file_size_mb
                }, ensure_ascii=False, indent=2)
            }]
        }

    except subprocess.TimeoutExpired:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "ffmpeg processing timed out"
                }, ensure_ascii=False)
            }]
        }
    except FileNotFoundError:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "ffmpeg not installed, please install ffmpeg first"
                }, ensure_ascii=False)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Merge failed: {str(e)}"
                }, ensure_ascii=False)
            }]
        }


# Expose directly callable async functions for in-process use while preserving
# the MCP tool objects for agent tool registration.
_generate_painting_video_tool = generate_painting_video
_check_video_status_tool = check_video_status
_combine_video_audio_tool = combine_video_audio

generate_painting_video = getattr(
    _generate_painting_video_tool, "handler", _generate_painting_video_tool
)
check_video_status = getattr(
    _check_video_status_tool, "handler", _check_video_status_tool
)
combine_video_audio = getattr(
    _combine_video_audio_tool, "handler", _combine_video_audio_tool
)


# Create MCP Server
video_server = create_sdk_mcp_server(
    name="video-generation",
    version="1.0.0",
    tools=[
        _generate_painting_video_tool,
        _check_video_status_tool,
        _combine_video_audio_tool,
    ]
)


if __name__ == "__main__":
    """Test tools"""
    import asyncio

    async def test():
        print("=== Test Video Generation ===\n")

        # Test checking a non-existent job
        print("1. Checking non-existent job...")
        status_result = await check_video_status({"job_id": "non-existent"})
        print(json.loads(status_result["content"][0]["text"]))
        print()

        # Test video generation (requires valid image path)
        print("2. Generate painting video (example)...")
        print("   Requires a valid image_path for testing")
        print()

        # Test combining video and audio (requires valid files)
        print("3. Combine video and audio (example)...")
        print("   Requires valid video_path and audio_path for testing")

    asyncio.run(test())
