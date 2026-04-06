"""
Vision Analysis MCP Server

Provides tools for analyzing children's drawings using Claude Vision API.
Includes automatic image resizing to prevent base64 payload overflow.
"""

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from ..utils.model_config import get_vision_model

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None

logger = logging.getLogger(__name__)

import anyio

try:
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover - import fallback for test env
    AsyncAnthropic = None

try:
    from claude_agent_sdk import create_sdk_mcp_server, tool
except Exception:  # pragma: no cover - import fallback for test env

    def tool(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# ============================================================================
# Image size safety: auto-resize before base64 encoding
# ============================================================================

# Claude Vision API accepts at most ~5 MB of base64 image data.
# base64 inflates raw bytes by ~33%, so we cap raw bytes at 3.5 MB.
_MAX_RAW_BYTES = 3_500_000

# Progressive quality steps for JPEG re-encoding
_QUALITY_STEPS = [85, 75, 65, 55]
# Progressive scale factors when quality alone isn't enough
_SCALE_STEPS = [0.90, 0.80, 0.70, 0.60, 0.50]


def _ensure_image_fits(
    raw_bytes: bytes,
    media_type: str,
) -> Tuple[bytes, str, bool]:
    """Ensure *raw_bytes* will fit under the Claude Vision base64 limit.

    Returns (possibly_resized_bytes, media_type, was_resized).
    The returned media_type may change to image/jpeg after re-encoding.
    """
    if len(raw_bytes) <= _MAX_RAW_BYTES:
        return raw_bytes, media_type, False

    if PILImage is None:
        logger.warning(
            "Image is %.2f MB but Pillow is not installed; "
            "sending as-is (may exceed API limit)",
            len(raw_bytes) / 1_000_000,
        )
        return raw_bytes, media_type, False

    logger.info(
        "Image is %.2f MB (> %.2f MB limit), auto-resizing…",
        len(raw_bytes) / 1_000_000,
        _MAX_RAW_BYTES / 1_000_000,
    )

    img = PILImage.open(io.BytesIO(raw_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Phase 1: reduce JPEG quality at original dimensions
    for quality in _QUALITY_STEPS:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= _MAX_RAW_BYTES:
            logger.info(
                "Resized to %.2f MB at quality=%d (original dims)",
                buf.tell() / 1_000_000,
                quality,
            )
            return buf.getvalue(), "image/jpeg", True

    # Phase 2: progressively scale down dimensions
    orig_w, orig_h = img.size
    for scale in _SCALE_STEPS:
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = img.resize((new_w, new_h), PILImage.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=75, optimize=True)
        if buf.tell() <= _MAX_RAW_BYTES:
            logger.info(
                "Resized to %.2f MB at %dx%d (scale=%.0f%%)",
                buf.tell() / 1_000_000,
                new_w,
                new_h,
                scale * 100,
            )
            return buf.getvalue(), "image/jpeg", True

    # Last resort: return the smallest version we produced
    logger.warning(
        "Could not reduce image below %.2f MB; sending smallest attempt",
        buf.tell() / 1_000_000,
    )
    return buf.getvalue(), "image/jpeg", True


@tool(
    "analyze_children_drawing",
    """分析儿童画作，识别画面中的物体、场景、情绪和颜色。

    这个工具会：
    1. 识别画作中的物体（动物、人物、植物、物品等）
    2. 判断整体场景（室内/户外、具体地点）
    3. 分析情绪氛围（快乐、悲伤、平静等）
    4. 识别主要颜色
    5. 检测是否有重复出现的角色

    返回结构化的分析结果。""",
    {"image_path": str, "child_age": int},
)
async def analyze_children_drawing(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 Claude Vision API 分析儿童画作

    Args:
        args: 包含 image_path 和 child_age 的字典

    Returns:
        包含分析结果的字典
    """
    image_path = args["image_path"]
    child_age = args["child_age"]

    # 读取图片文件
    if not Path(image_path).exists():
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": f"图片文件不存在: {image_path}"}, ensure_ascii=False
                    ),
                }
            ]
        }

    # 读取图片并转换为 base64（非阻塞）
    raw_bytes = await anyio.Path(image_path).read_bytes()

    # 确定图片格式
    file_extension = Path(image_path).suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(file_extension, "image/jpeg")

    # Auto-resize if the image would exceed Claude Vision API limits
    raw_bytes, media_type, was_resized = _ensure_image_fits(raw_bytes, media_type)
    if was_resized:
        logger.info("Image auto-resized for Vision API: %s", image_path)

    image_data = base64.standard_b64encode(raw_bytes).decode("utf-8")

    # 调用 Claude Vision API
    if AsyncAnthropic is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": "Anthropic SDK is unavailable in current environment",
                            "objects": [],
                            "scene": "未知",
                            "mood": "未知",
                            "confidence_score": 0.0,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # 根据年龄调整分析提示
    age_context = ""
    if child_age <= 5:
        age_context = "这是一个3-5岁学龄前儿童的画作，注重识别简单的形状和鲜艳的颜色。"
    elif child_age <= 8:
        age_context = "这是一个6-8岁小学低年级儿童的画作，会有更多细节和故事性。"
    else:
        age_context = (
            "这是一个9-12岁小学高年级儿童的画作，可能包含复杂的情节和抽象概念。"
        )

    prompt = f"""请仔细分析这幅儿童画作。{age_context}

请按以下格式返回 JSON 结构的分析结果：

{{
  "objects": ["识别到的所有物体，如：小狗、树木、太阳、房子"],
  "scene": "场景描述，如：户外公园、室内房间、海边",
  "mood": "整体情绪氛围，如：快乐、宁静、兴奋、悲伤",
  "colors": ["主要颜色，如：红色、蓝色、黄色"],
  "recurring_characters": [
    {{
      "name": "角色名称（如果画作中有文字标注）",
      "description": "角色特征描述，如：穿蓝色衣服的小狗",
      "visual_features": ["关键视觉特征，如：尖耳朵、长尾巴、戴红色项圈"]
    }}
  ],
  "story_potential": "这幅画可能讲述的故事线索",
  "confidence_score": 0.95
}}

注意：
1. objects 应该尽可能详细列出所有识别到的元素
2. recurring_characters 用于识别可能重复出现的角色（如果有明显特征）
3. confidence_score 表示分析的置信度（0.0-1.0）
4. 保持儿童友好的语言风格"""

    try:
        response = await client.messages.create(
            model=get_vision_model(),
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        # 提取响应文本
        response_text = response.content[0].text

        # 尝试解析 JSON
        try:
            # 如果响应包含代码块，提取 JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # 验证必需字段
            required_fields = ["objects", "scene", "mood", "confidence_score"]
            for field in required_fields:
                if field not in result:
                    result[field] = (
                        []
                        if field == "objects"
                        else "未知"
                        if field != "confidence_score"
                        else 0.5
                    )

            # 确保 recurring_characters 存在
            if "recurring_characters" not in result:
                result["recurring_characters"] = []

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ]
            }

        except json.JSONDecodeError:
            # 如果无法解析为 JSON，返回原始文本并标记错误
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "error": "无法解析 Vision API 响应",
                                "raw_response": response_text,
                                "objects": [],
                                "scene": "未知",
                                "mood": "未知",
                                "confidence_score": 0.0,
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
                        {
                            "error": f"Vision API 调用失败: {str(e)}",
                            "objects": [],
                            "scene": "未知",
                            "mood": "未知",
                            "confidence_score": 0.0,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }


# 创建 MCP Server
vision_server = create_sdk_mcp_server(
    name="vision-analysis", version="1.0.0", tools=[analyze_children_drawing]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        # 测试示例
        result = await analyze_children_drawing(
            {"image_path": "test_image.jpg", "child_age": 7}
        )
        print(
            json.dumps(
                json.loads(result["content"][0]["text"]), indent=2, ensure_ascii=False
            )
        )

    asyncio.run(test())
