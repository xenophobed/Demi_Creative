"""
Interactive Story API Routes

互动故事 API 端点
支持流式响应（SSE）以提供更好的用户体验
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Header, status, Path as PathParam
from fastapi.responses import JSONResponse, StreamingResponse

from ..models import (
    InteractiveStoryStartRequest,
    InteractiveStoryStartResponse,
    ChoiceRequest,
    ChoiceResponse,
    SessionStatusResponse,
    StorySegment,
    StoryChoice,
    EducationalValue,
    SessionStatus as SessionStatusEnum
)
from ...services.database import session_repo
from ...agents.interactive_story_agent import (
    generate_story_opening,
    generate_story_opening_stream,
    generate_next_segment,
    generate_next_segment_stream,
    AGE_CONFIG
)
from ...utils.audio_strategy import get_audio_strategy


router = APIRouter(
    prefix="/api/v1/story/interactive",
    tags=["互动故事"]
)


async def _optional_user_id(authorization: Optional[str]) -> Optional[str]:
    """Extract user_id from Bearer token if present, return None otherwise."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        from ...services.user_service import user_service
        user = await user_service.validate_token(parts[1])
        return user.user_id if user else None
    except Exception:
        return None


@router.post(
    "/start",
    response_model=InteractiveStoryStartResponse,
    summary="开始互动故事",
    description="创建新的互动故事会话",
    status_code=status.HTTP_201_CREATED
)
async def start_interactive_story(
    request: InteractiveStoryStartRequest,
    authorization: Optional[str] = Header(None),
):
    """
    开始互动故事

    **工作流程**:
    1. 验证请求参数
    2. 创建新会话
    3. 生成故事开场
    4. 返回会话ID和第一段

    **示例请求**:
    ```json
    {
      "child_id": "child_001",
      "age_group": "6-8",
      "interests": ["动物", "冒险"],
      "theme": "森林探险",
      "voice": "fable",
      "enable_audio": true
    }
    ```
    """
    try:
        # Optionally extract user_id from auth token
        user_id = await _optional_user_id(authorization)

        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(request.age_group.value)

        # 1. 生成故事开场
        opening_data = await generate_story_opening(
            child_id=request.child_id,
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme,
            enable_audio=request.enable_audio,
            voice=request.voice.value
        )

        # 2. 创建会话（根据年龄组确定总段落数）
        age_config = AGE_CONFIG.get(request.age_group.value, AGE_CONFIG["6-9"])
        total_segments = age_config["total_segments"]

        create_kwargs = dict(
            child_id=request.child_id,
            story_title=opening_data["title"],
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme,
            voice=request.voice.value,
            enable_audio=request.enable_audio,
            total_segments=total_segments,
        )
        if user_id:
            create_kwargs["user_id"] = user_id
        session = await session_repo.create_session(**create_kwargs)

        # 3. 保存开场段落
        segment_data = opening_data["segment"]

        # Handle audio URL from agent result
        audio_url = None
        if opening_data.get("audio_path"):
            audio_filename = Path(opening_data["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        await session_repo.update_session(
            session_id=session.session_id,
            segment=segment_data,
            audio_url=audio_url,
            segment_id=segment_data["segment_id"]
        )

        # 4. 构建响应 with age-based display settings
        opening_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=audio_url,
            choices=[
                StoryChoice(**choice)
                for choice in segment_data["choices"]
            ],
            is_ending=False,
            primary_mode=audio_strategy.primary_mode,
            optional_content_available=audio_strategy.optional_content_available,
            optional_content_type=audio_strategy.optional_content_type
        )

        response = InteractiveStoryStartResponse(
            session_id=session.session_id,
            story_title=opening_data["title"],
            opening=opening_segment,
            created_at=datetime.now()
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        print(f"❌ Error starting interactive story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="故事创建失败，请稍后重试"
        )


@router.post(
    "/start/stream",
    summary="开始互动故事（流式）",
    description="创建新的互动故事会话，使用 Server-Sent Events 流式返回进度",
    status_code=status.HTTP_200_OK
)
async def start_interactive_story_stream(
    request: InteractiveStoryStartRequest,
    authorization: Optional[str] = Header(None),
):
    """
    流式开始互动故事

    使用 Server-Sent Events (SSE) 流式返回故事生成进度。

    **事件类型**:
    - `status`: 状态更新 (started, processing)
    - `thinking`: AI 思考过程
    - `tool_use`: 工具使用通知
    - `tool_result`: 工具结果
    - `session`: 会话创建完成
    - `result`: 故事内容
    - `complete`: 生成完成
    - `error`: 错误信息

    **示例事件流**:
    ```
    event: status
    data: {"status": "started", "message": "正在创作故事..."}

    event: thinking
    data: {"content": "让我想想...", "turn": 1}

    event: session
    data: {"session_id": "xxx", "story_title": "冒险之旅"}

    event: result
    data: {"title": "...", "segment": {...}}

    event: complete
    data: {"status": "completed"}
    ```
    """
    # Optionally extract user_id from auth token
    user_id = await _optional_user_id(authorization)

    async def event_generator() -> AsyncGenerator[str, None]:
        session = None
        opening_data = None

        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(request.age_group.value)

        try:
            # 流式生成故事开场
            async for event in generate_story_opening_stream(
                child_id=request.child_id,
                age_group=request.age_group.value,
                interests=request.interests,
                theme=request.theme,
                enable_audio=request.enable_audio,
                voice=request.voice.value
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                # 当收到结果时，创建会话
                if event_type == "result":
                    opening_data = event_data

                    # 创建会话
                    age_config = AGE_CONFIG.get(request.age_group.value, AGE_CONFIG["6-9"])
                    total_segments = age_config["total_segments"]

                    stream_create_kwargs = dict(
                        child_id=request.child_id,
                        story_title=opening_data.get("title", "未命名故事"),
                        age_group=request.age_group.value,
                        interests=request.interests,
                        theme=request.theme,
                        voice=request.voice.value,
                        enable_audio=request.enable_audio,
                        total_segments=total_segments,
                    )
                    if user_id:
                        stream_create_kwargs["user_id"] = user_id
                    session = await session_repo.create_session(**stream_create_kwargs)

                    # 保存开场段落
                    segment_data = opening_data.get("segment", {})

                    # Handle audio URL from agent result
                    audio_url = None
                    if opening_data.get("audio_path"):
                        audio_filename = Path(opening_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    await session_repo.update_session(
                        session_id=session.session_id,
                        segment=segment_data,
                        audio_url=audio_url,
                        segment_id=segment_data.get("segment_id", 0)
                    )

                    # 发送会话信息
                    yield f"event: session\ndata: {json.dumps({'session_id': session.session_id, 'story_title': opening_data.get('title', '')}, ensure_ascii=False)}\n\n"

                    # 构建完整响应数据 with age-based display settings
                    response_data = {
                        "session_id": session.session_id,
                        "story_title": opening_data.get("title", ""),
                        "opening": {
                            "segment_id": segment_data.get("segment_id", 0),
                            "text": segment_data.get("text", ""),
                            "audio_url": audio_url,
                            "choices": segment_data.get("choices", []),
                            "is_ending": False,
                            "primary_mode": audio_strategy.primary_mode,
                            "optional_content_available": audio_strategy.optional_content_available,
                            "optional_content_type": audio_strategy.optional_content_type
                        },
                        "created_at": datetime.now().isoformat()
                    }
                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    # 转发其他事件
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_data = {"error": str(e), "message": "故事创建失败"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post(
    "/{session_id}/choose/stream",
    summary="选择故事分支（流式）",
    description="在互动故事中做出选择，使用 SSE 流式返回下一段"
)
async def choose_story_branch_stream(
    session_id: str = PathParam(..., description="会话ID"),
    request: ChoiceRequest = ...
):
    """
    流式选择故事分支

    使用 Server-Sent Events 流式返回下一段故事。
    """
    # 验证会话
    session = await session_repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"会话已{session.status}，无法继续"
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(session.age_group)

        try:
            # 流式生成下一段
            async for event in generate_next_segment_stream(
                session_id=session_id,
                choice_id=request.choice_id,
                session_data={
                    "segments": session.segments,
                    "choice_history": session.choice_history,
                    "age_group": session.age_group,
                    "interests": session.interests,
                    "theme": session.theme,
                    "story_title": session.story_title
                },
                enable_audio=session.enable_audio,
                voice=session.voice
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    next_data = event_data
                    segment_data = next_data.get("segment", {})
                    is_ending = next_data.get("is_ending", False)

                    # Handle audio URL from agent result
                    audio_url = None
                    if next_data.get("audio_path"):
                        audio_filename = Path(next_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    # 更新会话
                    await session_repo.update_session(
                        session_id=session_id,
                        segment=segment_data,
                        choice_id=request.choice_id,
                        status="completed" if is_ending else "active",
                        educational_summary=next_data.get("educational_summary"),
                        audio_url=audio_url,
                        segment_id=segment_data.get("segment_id", 0)
                    )

                    # 获取更新后的会话
                    updated_session = await session_repo.get_session(session_id)

                    # 构建响应 with age-based display settings
                    response_data = {
                        "session_id": session_id,
                        "next_segment": {
                            "segment_id": segment_data.get("segment_id", 0),
                            "text": segment_data.get("text", ""),
                            "audio_url": audio_url,
                            "choices": segment_data.get("choices", []),
                            "is_ending": segment_data.get("is_ending", False),
                            "primary_mode": audio_strategy.primary_mode,
                            "optional_content_available": audio_strategy.optional_content_available,
                            "optional_content_type": audio_strategy.optional_content_type
                        },
                        "choice_history": updated_session.choice_history,
                        "progress": updated_session.current_segment / updated_session.total_segments,
                        "educational_summary": next_data.get("educational_summary")
                    }
                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_data = {"error": str(e), "message": "故事分支生成失败"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post(
    "/{session_id}/choose",
    response_model=ChoiceResponse,
    summary="选择故事分支",
    description="在互动故事中做出选择，获取下一段"
)
async def choose_story_branch(
    session_id: str = PathParam(..., description="会话ID"),
    request: ChoiceRequest = ...
):
    """
    选择故事分支

    **工作流程**:
    1. 验证会话存在且有效
    2. 记录选择
    3. 生成下一段
    4. 更新会话状态
    5. 返回下一段内容

    **示例请求**:
    ```json
    {
      "choice_id": "choice_0_a"
    }
    ```
    """
    try:
        # 1. 获取会话
        session = await session_repo.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 2. 检查会话状态
        if session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"会话已{session.status}，无法继续"
            )

        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(session.age_group)

        # 3. 生成下一段（传递完整的会话上下文）
        next_data = await generate_next_segment(
            session_id=session_id,
            choice_id=request.choice_id,
            session_data={
                "segments": session.segments,
                "choice_history": session.choice_history,
                "age_group": session.age_group,
                "interests": session.interests,
                "theme": session.theme,
                "story_title": session.story_title
            },
            enable_audio=session.enable_audio,
            voice=session.voice
        )

        # 4. 更新会话
        segment_data = next_data["segment"]
        is_ending = next_data.get("is_ending", False)

        # Handle audio URL from agent result
        audio_url = None
        if next_data.get("audio_path"):
            audio_filename = Path(next_data["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        await session_repo.update_session(
            session_id=session_id,
            segment=segment_data,
            choice_id=request.choice_id,
            status="completed" if is_ending else "active",
            educational_summary=next_data.get("educational_summary"),
            audio_url=audio_url,
            segment_id=segment_data["segment_id"]
        )

        # 5. 构建响应 with age-based display settings
        next_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=audio_url,
            choices=[
                StoryChoice(**choice)
                for choice in segment_data.get("choices", [])
            ],
            is_ending=segment_data.get("is_ending", False),
            primary_mode=audio_strategy.primary_mode,
            optional_content_available=audio_strategy.optional_content_available,
            optional_content_type=audio_strategy.optional_content_type
        )

        # 更新后的会话
        updated_session = await session_repo.get_session(session_id)

        response = ChoiceResponse(
            session_id=session_id,
            next_segment=next_segment,
            choice_history=updated_session.choice_history,
            progress=updated_session.current_segment / updated_session.total_segments
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error choosing story branch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="故事分支生成失败，请稍后重试"
        )


@router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="获取会话状态",
    description="查询互动故事会话的当前状态"
)
async def get_session_status(
    session_id: str = PathParam(..., description="会话ID")
):
    """
    获取会话状态

    **返回信息**:
    - 会话基本信息
    - 当前进度
    - 选择历史
    - 教育总结（如果已完成）

    **示例响应**:
    ```json
    {
      "session_id": "xxx",
      "status": "active",
      "child_id": "child_001",
      "story_title": "神秘的冒险之旅",
      "current_segment": 2,
      "total_segments": 5,
      "choice_history": ["choice_0_a", "choice_1_b"],
      "created_at": "2024-01-26T10:00:00",
      "updated_at": "2024-01-26T10:05:00",
      "expires_at": "2024-01-27T10:00:00"
    }
    ```
    """
    try:
        # 获取会话
        session = await session_repo.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 构建响应
        educational_summary = None
        if session.educational_summary:
            educational_summary = EducationalValue(**session.educational_summary)

        response = SessionStatusResponse(
            session_id=session.session_id,
            status=SessionStatusEnum(session.status),
            child_id=session.child_id,
            story_title=session.story_title,
            current_segment=session.current_segment,
            total_segments=session.total_segments,
            choice_history=session.choice_history,
            educational_summary=educational_summary,
            created_at=datetime.fromisoformat(session.created_at),
            updated_at=datetime.fromisoformat(session.updated_at),
            expires_at=datetime.fromisoformat(session.expires_at)
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error getting session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话状态失败"
        )
