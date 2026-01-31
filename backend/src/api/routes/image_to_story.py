"""
Image to Story API Routes

画作转故事 API 端点
"""

import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from ..models import (
    ImageToStoryResponse,
    StoryContent,
    EducationalValue,
    CharacterMemory,
    AgeGroup
)
from ...agents.image_to_story_agent import image_to_story


router = APIRouter(
    prefix="/api/v1",
    tags=["画作转故事"]
)


# ============================================================================
# 故事存储（内存存储，生产环境应使用数据库）
# ============================================================================
story_storage: Dict[str, Dict[str, Any]] = {}


def save_story(story_id: str, response_data: Dict[str, Any]) -> None:
    """保存故事到存储"""
    story_storage[story_id] = {
        **response_data,
        "stored_at": datetime.now().isoformat()
    }


def get_story(story_id: str) -> Optional[Dict[str, Any]]:
    """从存储中获取故事"""
    return story_storage.get(story_id)


# ============================================================================
# 配置
# ============================================================================
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_file(file: UploadFile) -> None:
    """
    验证上传的图片文件

    Args:
        file: 上传的文件

    Raises:
        HTTPException: 如果文件不符合要求
    """
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式。允许的格式: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 检查 MIME 类型
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件必须是图片类型"
        )


async def save_upload_file(file: UploadFile, child_id: str) -> Path:
    """
    保存上传的文件

    Args:
        file: 上传的文件
        child_id: 儿童ID

    Returns:
        Path: 保存的文件路径

    Raises:
        HTTPException: 如果文件太大
    """
    # 创建儿童专属目录
    child_dir = UPLOAD_DIR / child_id
    child_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = child_dir / unique_filename

    # 保存文件并检查大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE / 1024 / 1024}MB）"
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return file_path


def parse_age_group(age_group: str) -> int:
    """
    将年龄组转换为具体年龄（取中间值）

    Args:
        age_group: 年龄组（如 "3-5"）

    Returns:
        int: 年龄
    """
    age_map = {
        "3-5": 4,
        "6-8": 7,
        "9-12": 10
    }
    return age_map.get(age_group, 7)


@router.post(
    "/image-to-story",
    response_model=ImageToStoryResponse,
    summary="画作转故事",
    description="上传儿童画作，AI 生成个性化故事",
    status_code=status.HTTP_201_CREATED
)
async def create_story_from_image(
    image: UploadFile = File(..., description="儿童画作图片（PNG/JPG，最大10MB）"),
    child_id: str = Form(..., description="儿童唯一标识符"),
    age_group: AgeGroup = Form(..., description="年龄组：3-5, 6-8, 9-12"),
    interests: Optional[str] = Form(None, description="兴趣标签，用逗号分隔（最多5个）"),
    voice: str = Form("nova", description="语音类型"),
    enable_audio: bool = Form(True, description="是否生成语音")
):
    """
    画作转故事 API

    **工作流程**:
    1. 验证并保存上传的图片
    2. 调用 image_to_story_agent
    3. 返回故事、音频和教育价值

    **示例请求**:
    ```bash
    curl -X POST "http://localhost:8000/api/v1/image-to-story" \\
      -F "image=@drawing.png" \\
      -F "child_id=child_001" \\
      -F "age_group=6-8" \\
      -F "interests=动物,冒险,太空" \\
      -F "voice=nova" \\
      -F "enable_audio=true"
    ```
    """
    try:
        # 1. 验证图片
        validate_image_file(image)

        # 2. 保存图片
        image_path = await save_upload_file(image, child_id)

        # 3. 解析参数
        child_age = parse_age_group(age_group.value)
        interests_list = None
        if interests:
            interests_list = [i.strip() for i in interests.split(",") if i.strip()]
            if len(interests_list) > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="兴趣标签最多5个"
                )

        # 4. 调用 Agent 生成故事
        result = await image_to_story(
            image_path=str(image_path),
            child_id=child_id,
            child_age=child_age,
            interests=interests_list
        )

        # 5. 解析结果并构建响应
        # 注意：这里假设 agent 返回的结果包含所需字段
        # 实际使用时需要根据 agent 的返回格式调整

        story_id = str(uuid.uuid4())

        # 提取故事文本
        story_text = result.get("story", "")
        word_count = len(story_text)

        # 提取教育价值
        educational_value = EducationalValue(
            themes=result.get("themes", []),
            concepts=result.get("concepts", []),
            moral=result.get("moral")
        )

        # 提取角色记忆
        characters = []
        for char_data in result.get("characters", []):
            characters.append(CharacterMemory(
                character_name=char_data.get("name", ""),
                description=char_data.get("description", ""),
                appearances=char_data.get("appearances", 1)
            ))

        # 构建响应
        created_at = datetime.now()
        response = ImageToStoryResponse(
            story_id=story_id,
            story=StoryContent(
                text=story_text,
                word_count=word_count,
                age_adapted=True
            ),
            audio_url=result.get("audio_url"),
            educational_value=educational_value,
            characters=characters,
            analysis=result.get("analysis", {}),
            safety_score=result.get("safety_score", 0.9),
            created_at=created_at
        )

        # 保存故事到存储
        save_story(story_id, {
            "story_id": story_id,
            "story": {
                "text": story_text,
                "word_count": word_count,
                "age_adapted": True
            },
            "audio_url": result.get("audio_url"),
            "educational_value": {
                "themes": result.get("themes", []),
                "concepts": result.get("concepts", []),
                "moral": result.get("moral")
            },
            "characters": [
                {
                    "character_name": c.character_name,
                    "description": c.description,
                    "appearances": c.appearances
                }
                for c in characters
            ],
            "analysis": result.get("analysis", {}),
            "safety_score": result.get("safety_score", 0.9),
            "created_at": created_at.isoformat(),
            "child_id": child_id,
            "age_group": age_group.value,
            "image_path": str(image_path)
        })

        return response

    except HTTPException:
        # 重新抛出 HTTP 异常
        raise

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # 记录错误
        print(f"❌ Error in image-to-story: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="故事生成失败，请稍后重试"
        )

    finally:
        # 可选：清理临时文件（如果不需要保存）
        # if image_path and image_path.exists():
        #     image_path.unlink()
        pass


@router.get(
    "/stories/{story_id}",
    summary="获取故事",
    description="根据故事ID获取已生成的故事详情",
    responses={
        200: {"description": "成功获取故事"},
        404: {"description": "故事不存在"}
    }
)
async def get_story_by_id(story_id: str):
    """
    获取故事详情

    **参数**:
    - story_id: 故事唯一标识符

    **返回**:
    - 故事完整数据，包括文本、音频URL、教育价值等

    **示例请求**:
    ```bash
    curl "http://localhost:8000/api/v1/stories/{story_id}"
    ```
    """
    story = get_story(story_id)

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"故事不存在: {story_id}"
        )

    return JSONResponse(content=story)


@router.get(
    "/stories",
    summary="列出所有故事",
    description="获取所有已生成故事的列表（用于调试）"
)
async def list_stories(
    child_id: Optional[str] = None,
    limit: int = 20
):
    """
    列出故事

    **参数**:
    - child_id: 可选，按儿童ID筛选
    - limit: 返回数量限制

    **返回**:
    - 故事列表摘要
    """
    stories = []

    for sid, data in story_storage.items():
        # 如果指定了 child_id，进行筛选
        if child_id and data.get("child_id") != child_id:
            continue

        stories.append({
            "story_id": sid,
            "child_id": data.get("child_id"),
            "created_at": data.get("created_at"),
            "word_count": data.get("story", {}).get("word_count", 0),
            "has_audio": bool(data.get("audio_url"))
        })

        if len(stories) >= limit:
            break

    return JSONResponse(content={
        "total": len(stories),
        "stories": stories
    })
