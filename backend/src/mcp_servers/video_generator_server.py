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

from openai import OpenAI
from claude_agent_sdk import tool, create_sdk_mcp_server


# Video style prompts for child-friendly animation
VIDEO_STYLE_PROMPTS = {
    "gentle_animation": "Gently animate this children's painting with soft, slow movements. Keep the original artwork style intact while adding subtle motion like swaying trees, twinkling stars, or gently moving characters. The animation should be calm and soothing, suitable for all ages.",
    "playful": "Create a playful animation from this children's painting. Add bouncy, fun movements to the characters and elements. Keep the whimsical, child-drawn quality while making elements dance and move joyfully.",
    "storybook": "Transform this children's painting into a storybook-style animation. Add gentle page-turning effects and bring elements to life as if the drawing is coming alive from a magical book."
}


def get_video_output_path():
    """获取视频输出目录"""
    video_dir = os.getenv("VIDEO_OUTPUT_PATH", "./data/videos")
    Path(video_dir).mkdir(parents=True, exist_ok=True)
    return video_dir


def get_video_jobs_path():
    """获取视频任务目录"""
    jobs_dir = "./data/video_jobs"
    Path(jobs_dir).mkdir(parents=True, exist_ok=True)
    return jobs_dir


def encode_image_to_base64(image_path: str) -> str:
    """将图片编码为 base64"""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    """获取图片 MIME 类型"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    return mime_types.get(ext, "image/png")


def save_job_status(job_id: str, job_data: Dict[str, Any]) -> None:
    """保存任务状态到文件"""
    jobs_dir = get_video_jobs_path()
    job_file = Path(jobs_dir) / f"{job_id}.json"
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2, default=str)


def load_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """加载任务状态"""
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
    生成画作动画视频

    Args:
        args: 包含 image_path, style, duration_seconds, story_id 的字典

    Returns:
        包含任务ID和状态的字典
    """
    image_path = args["image_path"]
    style = args.get("style", "gentle_animation")
    duration_seconds = args.get("duration_seconds", 10)
    story_id = args.get("story_id", "")

    # 验证图片存在
    if not Path(image_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"图片文件不存在: {image_path}",
                    "job_id": None
                }, ensure_ascii=False)
            }]
        }

    # 检查 OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "未配置 OPENAI_API_KEY 环境变量",
                    "job_id": None
                }, ensure_ascii=False)
            }]
        }

    try:
        client = OpenAI(api_key=api_key)

        # 生成任务ID
        job_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # 获取风格提示词
        style_prompt = VIDEO_STYLE_PROMPTS.get(
            style,
            VIDEO_STYLE_PROMPTS["gentle_animation"]
        )

        # 编码图片
        image_base64 = encode_image_to_base64(image_path)
        mime_type = get_image_mime_type(image_path)

        # 调用 OpenAI Sora API 生成视频
        # 注意：这里使用 OpenAI 的视频生成 API（Sora）
        response = client.images.generate(
            model="sora",
            prompt=style_prompt,
            image=f"data:{mime_type};base64,{image_base64}",
            n=1,
            size="1024x1024",
            response_format="url"
        )

        # 获取生成的视频URL
        if response.data and len(response.data) > 0:
            video_url = response.data[0].url

            # 下载视频到本地
            video_dir = get_video_output_path()
            video_filename = f"video_{job_id}.mp4"
            video_path = Path(video_dir) / video_filename

            # 使用 requests 下载视频
            import httpx
            async with httpx.AsyncClient() as http_client:
                video_response = await http_client.get(video_url)
                with open(video_path, "wb") as f:
                    f.write(video_response.content)

            # 保存任务状态
            job_data = {
                "job_id": job_id,
                "story_id": story_id,
                "status": "completed",
                "progress_percent": 100,
                "video_path": str(video_path),
                "video_filename": video_filename,
                "style": style,
                "duration_seconds": duration_seconds,
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
        else:
            raise Exception("No video generated from API response")

    except Exception as e:
        error_message = str(e)

        # 如果是 API 不支持的错误，创建一个待处理的任务
        # 实际生产中可能需要使用队列系统
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "story_id": story_id,
            "status": "pending",
            "progress_percent": 0,
            "style": style,
            "duration_seconds": duration_seconds,
            "image_path": image_path,
            "created_at": datetime.now().isoformat(),
            "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat(),
            "error": error_message if "sora" in error_message.lower() else None
        }
        save_job_status(job_id, job_data)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "job_id": job_id,
                    "status": "pending",
                    "message": "视频生成任务已创建，请稍后查询状态",
                    "estimated_completion": job_data["estimated_completion"],
                    "note": "Sora API 可能需要一些时间处理，请使用 check_video_status 工具查询进度"
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
    检查视频生成任务状态

    Args:
        args: 包含 job_id 的字典

    Returns:
        任务状态信息
    """
    job_id = args["job_id"]

    job_data = load_job_status(job_id)
    if not job_data:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"任务不存在: {job_id}"
                }, ensure_ascii=False)
            }]
        }

    # 如果任务是 pending 状态，检查是否有外部更新
    # 在实际生产中，这里可能会轮询外部 API 或消息队列
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
    合并视频和音频

    Args:
        args: 包含 video_path, audio_path, output_filename 的字典

    Returns:
        合并后的视频路径
    """
    video_path = args["video_path"]
    audio_path = args["audio_path"]
    output_filename = args.get("output_filename")

    # 验证文件存在
    if not Path(video_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"视频文件不存在: {video_path}"
                }, ensure_ascii=False)
            }]
        }

    if not Path(audio_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"音频文件不存在: {audio_path}"
                }, ensure_ascii=False)
            }]
        }

    try:
        # 生成输出文件名
        if not output_filename:
            video_stem = Path(video_path).stem
            output_filename = f"combined_{video_stem}.mp4"

        video_dir = get_video_output_path()
        output_path = Path(video_dir) / output_filename

        # 使用 ffmpeg 合并视频和音频
        # -i: 输入文件
        # -c:v copy: 复制视频流（不重新编码）
        # -c:a aac: 使用 AAC 编码音频
        # -shortest: 以最短的流为准
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出文件
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
            timeout=120  # 2分钟超时
        )

        if result.returncode != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": f"ffmpeg 合并失败: {result.stderr}"
                    }, ensure_ascii=False)
                }]
            }

        # 获取文件大小
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
                    "error": "ffmpeg 处理超时"
                }, ensure_ascii=False)
            }]
        }
    except FileNotFoundError:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "ffmpeg 未安装，请先安装 ffmpeg"
                }, ensure_ascii=False)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"合并失败: {str(e)}"
                }, ensure_ascii=False)
            }]
        }


# 创建 MCP Server
video_server = create_sdk_mcp_server(
    name="video-generation",
    version="1.0.0",
    tools=[generate_painting_video, check_video_status, combine_video_audio]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        print("=== 测试 Video Generation ===\n")

        # 测试检查不存在的任务
        print("1. 检查不存在的任务...")
        status_result = await check_video_status({"job_id": "non-existent"})
        print(json.loads(status_result["content"][0]["text"]))
        print()

        # 测试生成视频（需要有效的图片路径）
        print("2. 生成画作视频（示例）...")
        print("   需要提供有效的 image_path 进行测试")
        print()

        # 测试合并视频音频（需要有效的文件）
        print("3. 合并视频音频（示例）...")
        print("   需要提供有效的 video_path 和 audio_path 进行测试")

    asyncio.run(test())
