"""
Image to Story Agent

使用 Claude Agent SDK 将儿童画作转化为个性化故事。
"""

import os
from pathlib import Path
from typing import Dict, Any, AsyncIterator

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from ..mcp_servers import (
    vision_server,
    vector_server,
    safety_server,
    tts_server
)


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
    prompt = f"""请使用 Story Generation Skill 为这幅儿童画作创作故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

**工作流程**：
1. 使用 `mcp__vision-analysis__analyze_children_drawing` 分析画作
2. 使用 `mcp__vector-search__search_similar_drawings` 查找历史记忆
3. 根据年龄和分析结果创作故事
4. 使用 `mcp__safety-check__check_content_safety` 检查安全性
5. 使用 `mcp__vector-search__store_drawing_embedding` 存储记忆
6. 使用 `mcp__tts-generation__generate_story_audio` 生成语音

请严格按照 Story Generation Skill 的工作流程执行。
"""

    # 配置 Agent 选项
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
            # Skills
            "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
    )

    # 调用 Agent
    result_data = {}
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_data = message.result
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

    prompt = f"""请使用 Story Generation Skill 为这幅儿童画作创作故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

请严格按照 Story Generation Skill 的工作流程执行，并在每一步完成后告知进展。
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
            "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
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
