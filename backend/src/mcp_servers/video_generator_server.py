"""
Video Generation MCP Server

Provides tools for generating animated videos from children's paintings.

Cheapest-everywhere policy: video uses a low-cost Replicate image-to-video
model (default ``wan-video/wan-2.2-i2v-fast``) instead of OpenAI Sora. The
model is overridable via the ``VIDEO_MODEL`` env var with no code change.
"""

import os
import json
import base64
import subprocess
from typing import Any, Dict, Optional
from pathlib import Path
import uuid
from datetime import datetime, timedelta

from ..paths import VIDEO_DIR, VIDEO_JOBS_DIR

try:
    import replicate as _replicate
except Exception:  # pragma: no cover - import fallback for test env
    _replicate = None

try:
    import httpx as _httpx
except Exception:  # pragma: no cover - import fallback for test env
    _httpx = None

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
    "storybook": "Transform this children's painting into a storybook-style animation. Add gentle page-turning effects and bring elements to life as if the drawing is coming alive from a magical book.",
}


# Cheapest-everywhere policy: a low-cost, maintained, prompt-capable Replicate
# image-to-video model. Overridable via env without a redeploy of code.
DEFAULT_VIDEO_MODEL = "wan-video/wan-2.2-i2v-fast"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LEGACY_VIDEO_JOBS_DIR = _REPO_ROOT / "data" / "video_jobs"


def get_video_model() -> str:
    return os.getenv("VIDEO_MODEL", DEFAULT_VIDEO_MODEL)


def get_video_resolution() -> str:
    # 480p is the cheaper tier; bump to 720p via env only if needed.
    return os.getenv("VIDEO_RESOLUTION", "480p")


def get_video_render_timeout() -> float:
    """Max seconds to wait for a render. i2v jobs routinely take 1-2+ min
    (plus cold start), well beyond replicate.run()'s ~60s default wait."""
    try:
        return float(os.getenv("VIDEO_RENDER_TIMEOUT_S", "300"))
    except (TypeError, ValueError):
        return 300.0


def get_video_output_path():
    """Get video output directory"""
    video_dir = os.getenv("VIDEO_OUTPUT_PATH", str(VIDEO_DIR))
    Path(video_dir).mkdir(parents=True, exist_ok=True)
    return video_dir


def get_video_jobs_path():
    """Get video jobs directory"""
    jobs_dir = str(VIDEO_JOBS_DIR)
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
        ".gif": "image/gif",
    }
    return mime_types.get(ext, "image/png")


def normalize_duration_seconds(duration_seconds) -> int:
    """Coerce a requested clip length to a small, cost-friendly integer.

    The Replicate i2v model renders a short clip from its own frame defaults;
    we only record the requested duration in the job metadata. Clamp to a
    cheap 4-8s window so a stray large request can't drive up cost.
    """
    try:
        requested = int(duration_seconds)
    except (TypeError, ValueError):
        requested = 5
    return max(4, min(8, requested))


def save_job_status(job_id: str, job_data: Dict[str, Any]) -> None:
    """Save job status to file"""
    jobs_dir = get_video_jobs_path()
    job_file = Path(jobs_dir) / f"{job_id}.json"
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2, default=str)


def load_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Load job status"""
    primary = Path(get_video_jobs_path()) / f"{job_id}.json"
    legacy = _LEGACY_VIDEO_JOBS_DIR / f"{job_id}.json"
    for job_file in (primary, legacy):
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
    {"image_path": str, "style": str, "duration_seconds": int, "story_id": str},
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
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": f"Image file not found: {image_path}",
                            "job_id": None,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    # Check Replicate availability + token (cheapest-everywhere video provider).
    if _replicate is None or _httpx is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": "replicate/httpx SDK not installed",
                            "job_id": None,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    api_key = os.getenv("REPLICATE_API_TOKEN")
    if not api_key:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": "REPLICATE_API_TOKEN environment variable not configured",
                            "job_id": None,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # Get style prompt + cost-clamped clip length
        style_prompt = VIDEO_STYLE_PROMPTS.get(
            style, VIDEO_STYLE_PROMPTS["gentle_animation"]
        )
        clip_seconds = normalize_duration_seconds(duration_seconds)
        model = get_video_model()

        # Generate the animation via a Replicate image-to-video model. The
        # painting is the conditioning frame and the per-style prompt drives
        # the motion. ``resolution``/``go_fast`` keep the render on the cheap
        # tier (valid for the default WAN model). A generous client timeout is
        # required: i2v renders routinely exceed run()'s ~60s default wait and
        # would otherwise raise "read operation timed out".
        client = _replicate.Client(
            api_token=api_key,
            timeout=_httpx.Timeout(get_video_render_timeout(), connect=15.0),
        )
        with open(image_path, "rb") as image_file:
            output = client.run(
                model,
                input={
                    "prompt": style_prompt,
                    "image": image_file,
                    "resolution": get_video_resolution(),
                    "go_fast": True,
                },
                use_file_output=False,
            )

        # Replicate returns a single video URL (str / FileOutput) or a list.
        video_ref = output[0] if isinstance(output, (list, tuple)) else output
        if video_ref is None:
            raise Exception(f"{model} returned no video output")

        # Download the rendered video locally.
        video_dir = get_video_output_path()
        video_filename = f"video_{job_id}.mp4"
        video_path = Path(video_dir) / video_filename
        if hasattr(video_ref, "read"):
            data = video_ref.read()
        else:
            data = _httpx.get(str(video_ref), timeout=180).content
        with open(video_path, "wb") as f:
            f.write(data)

        # Save job status
        job_data = {
            "job_id": job_id,
            "story_id": story_id,
            "status": "completed",
            "progress_percent": 100,
            "video_path": str(video_path),
            "video_filename": video_filename,
            "style": style,
            "duration_seconds": clip_seconds,
            "model": model,
            "created_at": timestamp.isoformat(),
            "completed_at": datetime.now().isoformat(),
        }
        save_job_status(job_id, job_data)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": True,
                            "job_id": job_id,
                            "status": "completed",
                            "video_path": str(video_path),
                            "video_filename": video_filename,
                            "video_url": f"/data/videos/{video_filename}",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            ]
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
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "job_id": job_id,
                            "status": "failed",
                            "error": f"Video generation failed: {error_message}",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            ]
        }


@tool(
    "check_video_status",
    """Check the status of a video generation job.

    Returns the current status, progress percentage, and video URL if completed.""",
    {"job_id": str},
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
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"success": False, "error": f"Job not found: {job_id}"},
                        ensure_ascii=False,
                    ),
                }
            ]
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
        "estimated_completion": job_data.get("estimated_completion"),
    }

    if status == "completed":
        video_filename = job_data.get("video_filename")
        if video_filename:
            response["video_url"] = f"/data/videos/{video_filename}"
            response["video_path"] = job_data.get("video_path")

    if status == "failed":
        response["error_message"] = job_data.get("error")

    return {
        "content": [
            {"type": "text", "text": json.dumps(response, ensure_ascii=False, indent=2)}
        ]
    }


@tool(
    "combine_video_audio",
    """Combine a generated video with audio narration.

    Uses ffmpeg to merge video and audio files into a single video with narration.""",
    {"video_path": str, "audio_path": str, "output_filename": str},
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
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": f"Video file not found: {video_path}",
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    if not Path(audio_path).exists():
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": f"Audio file not found: {audio_path}",
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
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
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120  # 2-minute timeout
        )

        if result.returncode != 0:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "success": False,
                                "error": f"ffmpeg merge failed: {result.stderr}",
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }

        # Get file size
        file_size = output_path.stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": True,
                            "output_path": str(output_path),
                            "output_filename": output_filename,
                            "video_url": f"/data/videos/{output_filename}",
                            "file_size_mb": file_size_mb,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            ]
        }

    except subprocess.TimeoutExpired:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"success": False, "error": "ffmpeg processing timed out"},
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    except FileNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": "ffmpeg not installed, please install ffmpeg first",
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"success": False, "error": f"Merge failed: {str(e)}"},
                        ensure_ascii=False,
                    ),
                }
            ]
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
    ],
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
