"""
Image to Story Agent

使用 Claude Agent SDK 将儿童画作转化为个性化故事。
支持流式响应以减少超时和改善用户体验。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, AsyncIterator, AsyncGenerator, Optional, List

from pydantic import BaseModel
try:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        ClaudeSDKClient,
        AssistantMessage,
        ToolUseBlock,
        ToolResultBlock,
    )
except Exception:  # pragma: no cover - import fallback for test env
    ClaudeAgentOptions = None
    ResultMessage = object
    ClaudeSDKClient = None
    AssistantMessage = object
    ToolUseBlock = object
    ToolResultBlock = object


def _should_use_mock() -> bool:
    """Return True when running inside pytest or when the SDK is unavailable."""
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


from ..mcp_servers import (
    vision_server,
    vector_server,
    safety_server,
    tts_server
)


def _should_use_mock() -> bool:
    """Return True when running inside pytest or when the SDK is unavailable."""
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
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

def _get_age_group_from_age(age: int) -> str:
    """Convert age to age group string."""
    if age <= 5:
        return "3-5"
    elif age <= 9:
        return "6-9"
    else:
        return "10-12"


def _get_audio_config(age_group: str) -> dict:
    """Get audio configuration for age group."""
    configs = {
        "3-5": {"audio_mode": "audio_first", "voice": "nova", "speed": 0.9},
        "6-9": {"audio_mode": "simultaneous", "voice": "shimmer", "speed": 1.0},
        "10-12": {"audio_mode": "text_first", "voice": "alloy", "speed": 1.1}
    }
    return configs.get(age_group, configs["6-9"])


async def image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None,
    enable_audio: bool = True,
    voice: str = None
) -> Dict[str, Any]:
    """
    将儿童画作转化为个性化故事

    Args:
        image_path: 画作图片路径
        child_id: 儿童ID
        child_age: 儿童年龄（3-12岁）
        interests: 儿童兴趣标签列表
        enable_audio: 是否生成语音
        voice: 语音类型（可选，默认根据年龄组选择）

    Returns:
        包含故事、音频等信息的字典
    """
    if _should_use_mock():
        raise RuntimeError("claude_agent_sdk is unavailable in current environment")
    # 验证输入
    if not Path(image_path).exists():
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    if not 3 <= child_age <= 12:
        raise ValueError("儿童年龄必须在 3-12 岁之间")

    interests_str = "、".join(interests) if interests else "未指定"

    # Get age-based audio config
    age_group = _get_age_group_from_age(child_age)
    audio_config = _get_audio_config(age_group)
    audio_mode = audio_config["audio_mode"]
    should_generate_audio = enable_audio and audio_mode in ["audio_first", "simultaneous"]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    # 构建提示词
    prompt = f"""请为这幅儿童画作创作一个适合{child_age}岁儿童的故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

**要求**：
1. 首先使用 `mcp__vision-analysis__analyze_children_drawing` 工具分析画作
2. 使用 `mcp__vector-search__search_similar_drawings` 工具搜索该儿童之前的相似画作，以保持角色和故事的连续性
3. 根据分析结果创作一个温馨、有教育意义的故事
4. 故事长度约 200-400 字
5. 语言要适合 {child_age} 岁儿童
6. **重要**：故事创作完成后，使用 `mcp__vector-search__store_drawing_embedding` 工具将画作存储到向量数据库，参数如下：
   - drawing_description: 画作的文字描述（从分析结果中获取）
   - child_id: {child_id}
   - drawing_analysis: 画作分析结果（包含 objects, scene, mood, colors, recurring_characters）
   - story_text: 生成的故事文本
   - image_path: {image_path}

请根据画作内容创作故事，并提取主题、概念和寓意。
"""

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt += f"""
**语音生成**：
故事创作完成后，请使用 `mcp__tts-generation__generate_story_audio` 工具为故事文本生成语音。
- 语音类型: {actual_voice}
- 语速: {audio_speed}
- 儿童ID: {child_id}
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
        max_turns=15,  # 增加 turns 以适应更多工具调用
        # 使用 Structured Output
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema()
        }
    )

    # 使用 ClaudeSDKClient 调用 Agent
    result_data = {}
    audio_path = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            # Check for TTS tool results in assistant messages
            if isinstance(message, AssistantMessage):
                content = getattr(message, 'content', None)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            # Try to extract audio path from TTS result
                            result_content = getattr(block, 'content', None)
                            if result_content and isinstance(result_content, str):
                                try:
                                    result_json = json.loads(result_content)
                                    if 'audio_path' in result_json:
                                        audio_path = result_json['audio_path']
                                except (json.JSONDecodeError, TypeError):
                                    pass

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

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    return result_data


async def stream_image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None,
    enable_audio: bool = True,
    voice: str = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式返回故事生成过程

    Args:
        image_path: 画作图片路径
        child_id: 儿童ID
        child_age: 儿童年龄
        interests: 兴趣标签列表
        enable_audio: 是否生成语音
        voice: 语音类型（可选）

    Yields:
        流式事件字典，包含 type 和 data 字段
    """
    if _should_use_mock():
        yield {
            "type": "error",
            "data": {
                "error": "RuntimeError",
                "message": "claude_agent_sdk is unavailable in current environment",
            },
        }
        return
    # 验证输入
    if not Path(image_path).exists():
        yield {
            "type": "error",
            "data": {
                "error": "FileNotFoundError",
                "message": f"图片文件不存在: {image_path}"
            }
        }
        return

    if not 3 <= child_age <= 12:
        yield {
            "type": "error",
            "data": {
                "error": "ValueError",
                "message": "儿童年龄必须在 3-12 岁之间"
            }
        }
        return

    interests_str = "、".join(interests) if interests else "未指定"

    # Get age-based audio config
    age_group = _get_age_group_from_age(child_age)
    audio_config = _get_audio_config(age_group)
    audio_mode = audio_config["audio_mode"]
    should_generate_audio = enable_audio and audio_mode in ["audio_first", "simultaneous"]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    # 发送开始事件
    yield {
        "type": "status",
        "data": {
            "status": "started",
            "message": "正在分析画作..."
        }
    }

    prompt = f"""请为这幅儿童画作创作一个适合{child_age}岁儿童的故事。

**任务信息**：
- 画作路径: {image_path}
- 儿童ID: {child_id}
- 儿童年龄: {child_age}岁
- 兴趣爱好: {interests_str}

**要求**：
1. 首先使用 `mcp__vision-analysis__analyze_children_drawing` 工具分析画作
2. 使用 `mcp__vector-search__search_similar_drawings` 工具搜索该儿童之前的相似画作，以保持角色和故事的连续性
3. 根据分析结果创作一个温馨、有教育意义的故事
4. 故事长度约 200-400 字
5. 语言要适合 {child_age} 岁儿童
6. **重要**：故事创作完成后，使用 `mcp__vector-search__store_drawing_embedding` 工具将画作存储到向量数据库，参数如下：
   - drawing_description: 画作的文字描述（从分析结果中获取）
   - child_id: {child_id}
   - drawing_analysis: 画作分析结果（包含 objects, scene, mood, colors, recurring_characters）
   - story_text: 生成的故事文本
   - image_path: {image_path}

请根据画作内容创作故事，并提取主题、概念和寓意。
"""

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt += f"""
**语音生成**：
故事创作完成后，请使用 `mcp__tts-generation__generate_story_audio` 工具为故事文本生成语音。
- 语音类型: {actual_voice}
- 语速: {audio_speed}
- 儿童ID: {child_id}
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
        max_turns=15,  # 增加 turns 以适应更多工具调用
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema()
        }
    )

    result_data = {}
    turn_count = 0
    audio_path = None

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                # 处理助手消息（思考过程和工具使用）
                if isinstance(message, AssistantMessage):
                    turn_count += 1

                    content = getattr(message, 'content', None)

                    if isinstance(content, str) and content:
                        yield {
                            "type": "thinking",
                            "data": {
                                "content": content[:200] + "..." if len(content) > 200 else content,
                                "turn": turn_count
                            }
                        }
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, ToolUseBlock):
                                tool_name = getattr(block, 'name', 'unknown')
                                # 友好的工具名称映射
                                tool_messages = {
                                    "mcp__vision-analysis__analyze_children_drawing": "正在分析画作...",
                                    "mcp__vector-search__search_similar_drawings": "正在搜索相似画作...",
                                    "mcp__vector-search__store_drawing_embedding": "正在保存画作到记忆库...",
                                    "mcp__safety-check__check_content_safety": "正在检查内容安全...",
                                    "mcp__tts-generation__generate_story_audio": "正在生成语音...",
                                }
                                yield {
                                    "type": "tool_use",
                                    "data": {
                                        "tool": tool_name,
                                        "message": tool_messages.get(tool_name, f"正在使用 {tool_name}...")
                                    }
                                }
                            elif isinstance(block, ToolResultBlock):
                                # Try to extract audio path from TTS result
                                result_content = getattr(block, 'content', None)
                                if result_content and isinstance(result_content, str):
                                    try:
                                        result_json = json.loads(result_content)
                                        if 'audio_path' in result_json:
                                            audio_path = result_json['audio_path']
                                            yield {
                                                "type": "audio_generated",
                                                "data": {
                                                    "audio_path": audio_path,
                                                    "message": "语音生成完成"
                                                }
                                            }
                                    except (json.JSONDecodeError, TypeError):
                                        pass

                                yield {
                                    "type": "tool_result",
                                    "data": {
                                        "status": "completed"
                                    }
                                }
                            elif hasattr(block, 'text'):
                                text = block.text
                                if text:
                                    yield {
                                        "type": "thinking",
                                        "data": {
                                            "content": text[:200] + "..." if len(text) > 200 else text,
                                            "turn": turn_count
                                        }
                                    }

                # 处理最终结果
                elif isinstance(message, ResultMessage):
                    if hasattr(message, 'structured_output') and message.structured_output:
                        result_data = message.structured_output
                    elif message.result:
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

    except Exception as e:
        yield {
            "type": "error",
            "data": {
                "error": str(type(e).__name__),
                "message": f"生成故事时发生错误: {str(e)}"
            }
        }
        return

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # 发送最终结果
    yield {
        "type": "result",
        "data": result_data
    }

    yield {
        "type": "complete",
        "data": {
            "status": "completed",
            "message": "故事创作完成！"
        }
    }


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
