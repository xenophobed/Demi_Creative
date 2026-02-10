"""
Video API Routes

视频生成 API 端点
支持从儿童画作生成动画视频
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ..models import (
    VideoJobRequest,
    VideoJobResponse,
    VideoJobStatusResponse,
    VideoStyle,
    VideoStatus
)
from ...mcp_servers import generate_painting_video, check_video_status, combine_video_audio
from ...services.database import story_repo


router = APIRouter(
    prefix="/api/v1/video",
    tags=["视频生成"]
)


# ============================================================================
# 配置
# ============================================================================
from ...paths import VIDEO_DIR, VIDEO_JOBS_DIR, DATA_DIR


def load_job_from_file(job_id: str) -> Optional[dict]:
    """从文件加载任务状态"""
    job_file = VIDEO_JOBS_DIR / f"{job_id}.json"
    if job_file.exists():
        with open(job_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@router.post(
    "/generate",
    response_model=VideoJobResponse,
    summary="生成视频",
    description="为画作故事生成动画视频",
    status_code=status.HTTP_202_ACCEPTED
)
async def generate_video(request: VideoJobRequest):
    """
    生成画作动画视频

    **工作流程**:
    1. 验证故事存在
    2. 获取故事关联的画作图片
    3. 调用视频生成服务
    4. 返回任务ID供查询进度

    **示例请求**:
    ```json
    {
      "story_id": "xxx-xxx-xxx",
      "style": "gentle_animation",
      "include_audio": true,
      "duration_seconds": 10
    }
    ```
    """
    # 1. 获取故事
    story = await story_repo.get_by_id(request.story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"故事不存在: {request.story_id}"
        )

    # 2. 获取画作图片路径
    image_path = story.get("image_path")
    if not image_path:
        # 尝试从 image_url 推断路径
        image_url = story.get("image_url", "")
        if image_url.startswith("/data/"):
            image_path = str(DATA_DIR / image_url.removeprefix("/data/"))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="故事缺少画作图片"
            )

    if not Path(image_path).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"画作图片文件不存在: {image_path}"
        )

    # 3. 调用视频生成工具
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
                detail=result_data.get("error", "视频生成失败")
            )

        job_id = result_data["job_id"]
        job_status = result_data.get("status", "pending")

        # 计算预计完成时间
        estimated_completion = None
        if job_status == "pending":
            estimated_completion = datetime.now() + timedelta(minutes=5)
        elif result_data.get("estimated_completion"):
            estimated_completion = datetime.fromisoformat(
                result_data["estimated_completion"]
            )

        # 4. 如果请求包含音频，且视频已完成，合并音频
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
                        # 更新任务状态文件
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
            detail="视频生成失败，请稍后重试"
        )


@router.get(
    "/status/{job_id}",
    response_model=VideoJobStatusResponse,
    summary="查询视频生成状态",
    description="根据任务ID查询视频生成进度"
)
async def get_video_status(job_id: str):
    """
    查询视频生成任务状态

    **参数**:
    - job_id: 视频生成任务ID

    **返回**:
    - 任务状态、进度和视频URL（完成时）

    **示例请求**:
    ```bash
    curl "http://localhost:8000/api/v1/video/status/{job_id}"
    ```
    """
    try:
        result = await check_video_status({"job_id": job_id})
        result_data = json.loads(result["content"][0]["text"])

        if not result_data.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result_data.get("error", f"任务不存在: {job_id}")
            )

        # 加载任务详情以获取合并后的视频URL
        job_data = load_job_from_file(job_id)
        video_url = result_data.get("video_url")

        # 优先使用合并后的视频
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
            detail="查询状态失败"
        )


@router.get(
    "/{video_id}",
    summary="获取视频信息",
    description="根据视频ID获取视频元数据",
    responses={
        200: {"description": "成功获取视频信息"},
        404: {"description": "视频不存在"}
    }
)
async def get_video_info(video_id: str):
    """
    获取视频元数据

    **参数**:
    - video_id: 视频ID（也是任务ID）

    **返回**:
    - 视频元数据，包括URL、大小、时长等

    **示例请求**:
    ```bash
    curl "http://localhost:8000/api/v1/video/{video_id}"
    ```
    """
    # 加载任务状态获取视频信息
    job_data = load_job_from_file(video_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"视频不存在: {video_id}"
        )

    if job_data.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"视频尚未生成完成，当前状态: {job_data.get('status')}"
        )

    # 获取视频文件信息
    video_path = job_data.get("video_path")
    combined_path = job_data.get("combined_video_path")

    # 优先使用合并后的视频
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
    summary="获取故事的所有视频",
    description="获取指定故事关联的所有视频"
)
async def get_videos_by_story(story_id: str):
    """
    获取故事关联的视频列表

    **参数**:
    - story_id: 故事ID

    **返回**:
    - 该故事的所有视频列表
    """
    # 验证故事存在
    story = await story_repo.get_by_id(story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"故事不存在: {story_id}"
        )

    # 扫描任务目录查找相关视频
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

    # 按创建时间排序
    videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return JSONResponse(content={
        "story_id": story_id,
        "total": len(videos),
        "videos": videos
    })
