"""
Image to Story Agent

使用 Claude Agent SDK 将儿童画作转化为个性化故事。
"""

import os
from pathlib import Path
from typing import Dict, Any, AsyncIterator, Optional, List

from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, ClaudeSDKClient
from ..mcp_servers import (
    vision_server,
    vector_server,
    safety_server,
    tts_server
)


# ============================================================================
# Pydantic 模型定义（用于 Structured Output）
# ============================================================================

class Character(BaseModel):
    """故事中的角色"""
    name: str
    description: str
    appearances: int = 1


class StoryOutput(BaseModel):
    """故事生成的结构化输出"""
    story: str
    themes: List[str] = []
    concepts: List[str] = []
    moral: Optional[str] = None
    characters: List[Character] = []
    analysis: Dict[str, Any] = {}
    safety_score: float = 0.9
    audio_url: Optional[str] = None


# ============================================================================
# Agent 函数
# ============================================================================

async def image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None
) -> Dict[str, Any]:
    """
    将儿童画作转化为个性化故事

    Args:
        image_path: 画作图片路径
        child_id: 儿童ID
        child_age: 儿童年龄（3-12岁）
        interests: 儿童兴趣标签列表

    Returns:
        包含故事、音频等信息的字典
    """
    # 验证输入
    if not Path(image_path).exists():
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    if not 3 <= child_age <= 12:
        raise ValueError("儿童年龄必须在 3-12 岁之间")

    interests_str = "、".join(interests) if interests else "未指定"

    # 构建提示词
    prompt = f"""请为这幅儿童画作创作一个适合{child_age}岁儿童的故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

**要求**：
1. 首先使用 `mcp__vision-analysis__analyze_children_drawing` 工具分析画作
2. 根据分析结果创作一个温馨、有教育意义的故事
3. 故事长度约 200-400 字
4. 语言要适合 {child_age} 岁儿童

请根据画作内容创作故事，并提取主题、概念和寓意。
"""

    # 配置 Agent 选项（使用 Structured Output）
    options = ClaudeAgentOptions(
        mcp_servers={
            "vision-analysis": vision_server,
            "vector-search": vector_server,
            "safety-check": safety_server,
            "tts-generation": tts_server
        },
        allowed_tools=[
            # Vision Analysis Tools
            "mcp__vision-analysis__analyze_children_drawing",
            # Vector Search Tools
            "mcp__vector-search__search_similar_drawings",
            "mcp__vector-search__store_drawing_embedding",
            # Safety Check Tools
            "mcp__safety-check__check_content_safety",
            "mcp__safety-check__suggest_content_improvements",
            # TTS Tools
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=10,
        # 使用 Structured Output
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema()
        }
    )

    # 使用 ClaudeSDKClient 调用 Agent
    result_data = {}
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                # 使用 structured_output 获取结构化结果
                if hasattr(message, 'structured_output') and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    # 回退：如果没有 structured_output，尝试解析 result
                    if isinstance(message.result, dict):
                        result_data = message.result
                    else:
                        result_data = {
                            "story": str(message.result),
                            "themes": [],
                            "concepts": [],
                            "moral": None,
                            "characters": [],
                            "analysis": {},
                            "safety_score": 0.9
                        }
                break

    return result_data


async def stream_image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None
) -> AsyncIterator[str]:
    """
    流式返回故事生成过程

    Args:
        image_path: 画作图片路径
        child_id: 儿童ID
        child_age: 儿童年龄
        interests: 兴趣标签列表

    Yields:
        生成过程中的消息
    """
    interests_str = "、".join(interests) if interests else "未指定"

    prompt = f"""请为这幅儿童画作创作故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

请分析画作并创作故事，在每一步完成后告知进展。
"""

    options = ClaudeAgentOptions(
        mcp_servers={
            "vision-analysis": vision_server,
            "vector-search": vector_server,
            "safety-check": safety_server,
            "tts-generation": tts_server
        },
        allowed_tools=[
            "mcp__vision-analysis__analyze_children_drawing",
            "mcp__vector-search__search_similar_drawings",
            "mcp__vector-search__store_drawing_embedding",
            "mcp__safety-check__check_content_safety",
            "mcp__safety-check__suggest_content_improvements",
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=10,
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema()
        }
    )

    async for message in query(prompt=prompt, options=options):
        # 流式返回消息
        yield str(message)


if __name__ == "__main__":
    """测试 Agent"""
    import asyncio

    async def test():
        print("=== 测试 Image to Story Agent ===\n")

        # 创建测试图片
        from PIL import Image
        test_image_path = "./test_drawing.png"
        img = Image.new('RGB', (400, 300), color='lightblue')
        img.save(test_image_path)

        try:
            result = await image_to_story(
                image_path=test_image_path,
                child_id="test_child_001",
                child_age=7,
                interests=["动物", "冒险"]
            )

            print("✅ 故事生成成功！")
            print("\n结果：")
            print(result)

        except Exception as e:
            print(f"❌ 错误: {e}")

        finally:
            # 清理测试文件
            if Path(test_image_path).exists():
                Path(test_image_path).unlink()

    asyncio.run(test())
