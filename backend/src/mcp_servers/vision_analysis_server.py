"""
Vision Analysis MCP Server

Provides tools for analyzing children's drawings using Claude Vision API.
"""

import os
import json
import base64
from typing import Any, Dict
from pathlib import Path

import anyio
from anthropic import AsyncAnthropic
from claude_agent_sdk import tool, create_sdk_mcp_server


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
    {"image_path": str, "child_age": int}
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
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"图片文件不存在: {image_path}"
                }, ensure_ascii=False)
            }]
        }

    # 读取图片并转换为 base64（非阻塞）
    raw_bytes = await anyio.Path(image_path).read_bytes()
    image_data = base64.standard_b64encode(raw_bytes).decode("utf-8")

    # 确定图片格式
    file_extension = Path(image_path).suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }
    media_type = media_type_map.get(file_extension, "image/jpeg")

    # 调用 Claude Vision API
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # 根据年龄调整分析提示
    age_context = ""
    if child_age <= 5:
        age_context = "这是一个3-5岁学龄前儿童的画作，注重识别简单的形状和鲜艳的颜色。"
    elif child_age <= 8:
        age_context = "这是一个6-8岁小学低年级儿童的画作，会有更多细节和故事性。"
    else:
        age_context = "这是一个9-12岁小学高年级儿童的画作，可能包含复杂的情节和抽象概念。"

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
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
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
                    result[field] = [] if field == "objects" else "未知" if field != "confidence_score" else 0.5

            # 确保 recurring_characters 存在
            if "recurring_characters" not in result:
                result["recurring_characters"] = []

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                }]
            }

        except json.JSONDecodeError:
            # 如果无法解析为 JSON，返回原始文本并标记错误
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "无法解析 Vision API 响应",
                        "raw_response": response_text,
                        "objects": [],
                        "scene": "未知",
                        "mood": "未知",
                        "confidence_score": 0.0
                    }, ensure_ascii=False)
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Vision API 调用失败: {str(e)}",
                    "objects": [],
                    "scene": "未知",
                    "mood": "未知",
                    "confidence_score": 0.0
                }, ensure_ascii=False)
            }]
        }


# 创建 MCP Server
vision_server = create_sdk_mcp_server(
    name="vision-analysis",
    version="1.0.0",
    tools=[analyze_children_drawing]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        # 测试示例
        result = await analyze_children_drawing({
            "image_path": "test_image.jpg",
            "child_age": 7
        })
        print(json.dumps(json.loads(result["content"][0]["text"]), indent=2, ensure_ascii=False))

    asyncio.run(test())
