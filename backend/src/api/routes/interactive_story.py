"""
Interactive Story API Routes

互动故事 API 端点
"""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, status, Path as PathParam
from fastapi.responses import JSONResponse

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
from ...services import session_manager


router = APIRouter(
    prefix="/api/v1/story/interactive",
    tags=["互动故事"]
)


# TODO: 实现互动故事生成逻辑（当前为模拟实现）
async def generate_story_opening(
    child_id: str,
    age_group: str,
    interests: List[str],
    theme: str = None
) -> dict:
    """
    生成故事开场

    TODO: 调用 Interactive Story Skill
    """
    # 模拟故事开场
    return {
        "title": f"{'神秘的' if not theme else theme}冒险之旅",
        "segment": {
            "segment_id": 0,
            "text": f"在一个阳光明媚的早晨，小主人公发现了一个神秘的{interests[0] if interests else '宝箱'}...",
            "choices": [
                {"choice_id": "choice_0_a", "text": "立刻打开看看", "emoji": "🔓"},
                {"choice_id": "choice_0_b", "text": "先找朋友一起来", "emoji": "👫"}
            ]
        }
    }


async def generate_next_segment(
    session_id: str,
    choice_id: str,
    session_data: dict
) -> dict:
    """
    根据选择生成下一段落

    TODO: 调用 Interactive Story Skill
    """
    segment_count = len(session_data.get("segments", []))

    # 模拟生成下一段
    if segment_count < 3:
        # 继续故事
        return {
            "segment": {
                "segment_id": segment_count,
                "text": "故事继续发展...",
                "choices": [
                    {"choice_id": f"choice_{segment_count}_a", "text": "选项A", "emoji": "⭐"},
                    {"choice_id": f"choice_{segment_count}_b", "text": "选项B", "emoji": "🌟"}
                ]
            },
            "is_ending": False
        }
    else:
        # 结局
        return {
            "segment": {
                "segment_id": segment_count,
                "text": "经过重重冒险，小主人公终于达成了目标！这是一个美好的结局。",
                "choices": [],
                "is_ending": True
            },
            "is_ending": True,
            "educational_summary": {
                "themes": ["勇气", "友谊"],
                "concepts": ["决策", "合作"],
                "moral": "勇敢面对挑战，和朋友一起会更有力量"
            }
        }


@router.post(
    "/start",
    response_model=InteractiveStoryStartResponse,
    summary="开始互动故事",
    description="创建新的互动故事会话",
    status_code=status.HTTP_201_CREATED
)
async def start_interactive_story(
    request: InteractiveStoryStartRequest
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
        # 1. 生成故事开场
        opening_data = await generate_story_opening(
            child_id=request.child_id,
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme
        )

        # 2. 创建会话
        session = session_manager.create_session(
            child_id=request.child_id,
            story_title=opening_data["title"],
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme,
            voice=request.voice.value,
            enable_audio=request.enable_audio,
            total_segments=5  # 预计总段落数
        )

        # 3. 保存开场段落
        segment_data = opening_data["segment"]
        session_manager.update_session(
            session_id=session.session_id,
            segment=segment_data
        )

        # 4. 构建响应
        opening_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=None,  # TODO: 生成音频
            choices=[
                StoryChoice(**choice)
                for choice in segment_data["choices"]
            ],
            is_ending=False
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
        session = session_manager.get_session(session_id)
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

        # 3. 生成下一段
        next_data = await generate_next_segment(
            session_id=session_id,
            choice_id=request.choice_id,
            session_data={
                "segments": session.segments,
                "choice_history": session.choice_history
            }
        )

        # 4. 更新会话
        segment_data = next_data["segment"]
        is_ending = next_data.get("is_ending", False)

        session_manager.update_session(
            session_id=session_id,
            segment=segment_data,
            choice_id=request.choice_id,
            status="completed" if is_ending else "active",
            educational_summary=next_data.get("educational_summary")
        )

        # 5. 构建响应
        next_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=None,  # TODO: 生成音频
            choices=[
                StoryChoice(**choice)
                for choice in segment_data.get("choices", [])
            ],
            is_ending=segment_data.get("is_ending", False)
        )

        # 更新后的会话
        updated_session = session_manager.get_session(session_id)

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
        session = session_manager.get_session(session_id)
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
