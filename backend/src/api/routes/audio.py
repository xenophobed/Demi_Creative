"""
Audio API Routes

语音生成 API 端点
支持按需生成音频（用于 10-12 岁年龄组）
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ...services.database import session_repo
from ...mcp_servers import generate_story_audio


router = APIRouter(
    prefix="/api/v1/audio",
    tags=["语音"]
)


class AudioGenerateRequest(BaseModel):
    """按需生成音频请求"""
    session_id: str = Field(..., description="会话ID")
    segment_id: int = Field(..., description="段落ID")
    voice: str = Field(default="alloy", description="语音类型")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速")


class AudioGenerateResponse(BaseModel):
    """音频生成响应"""
    session_id: str = Field(..., description="会话ID")
    segment_id: int = Field(..., description="段落ID")
    audio_url: str = Field(..., description="音频URL")
    duration: Optional[float] = Field(None, description="音频时长（秒）")


@router.post(
    "/generate",
    response_model=AudioGenerateResponse,
    summary="按需生成音频",
    description="为指定会话的段落生成音频（主要用于 10-12 岁年龄组的按需播放功能）",
    status_code=status.HTTP_201_CREATED
)
async def generate_audio_on_demand(request: AudioGenerateRequest):
    """
    按需生成音频

    用于 10-12 岁年龄组，用户点击"播放语音"按钮时调用。

    **工作流程**:
    1. 验证会话存在且有效
    2. 获取指定段落的文本
    3. 调用 TTS 服务生成音频
    4. 返回音频 URL

    **示例请求**:
    ```json
    {
      "session_id": "xxx-xxx-xxx",
      "segment_id": 0,
      "voice": "alloy",
      "speed": 1.1
    }
    ```
    """
    # 1. 获取会话
    session = await session_repo.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 2. 检查是否已有该段落的音频
    audio_urls = getattr(session, 'audio_urls', None) or {}
    if request.segment_id in audio_urls:
        existing_url = audio_urls[request.segment_id]
        return AudioGenerateResponse(
            session_id=request.session_id,
            segment_id=request.segment_id,
            audio_url=existing_url
        )

    # 3. 获取段落文本
    if request.segment_id >= len(session.segments):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"段落 {request.segment_id} 不存在"
        )

    segment = session.segments[request.segment_id]
    text = segment.get("text", "")

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="段落文本为空，无法生成音频"
        )

    # 4. 调用 TTS 服务生成音频
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
                detail="音频生成失败"
            )

        # 5. 构建音频 URL
        audio_filename = Path(audio_path).name
        audio_url = f"/data/audio/{audio_filename}"

        # 6. 更新会话，保存音频 URL
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
            detail="音频生成失败，请稍后重试"
        )


@router.get(
    "/session/{session_id}",
    summary="获取会话的所有音频",
    description="获取指定会话的所有已生成音频 URL"
)
async def get_session_audio(session_id: str):
    """
    获取会话的所有音频 URL

    **返回**:
    - audio_urls: 段落ID到音频URL的映射
    """
    session = await session_repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    audio_urls = getattr(session, 'audio_urls', None) or {}
    return {
        "session_id": session_id,
        "audio_urls": audio_urls
    }
