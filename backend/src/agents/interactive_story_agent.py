"""
Interactive Story Agent

使用 Claude Agent SDK 生成多分支互动故事。
"""

import os
from typing import Dict, Any, List, Optional

from pydantic import BaseModel
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, ClaudeSDKClient
from ..mcp_servers import (
    safety_server,
    tts_server,
    vector_server
)


# ============================================================================
# Pydantic 模型定义（用于 Structured Output）
# ============================================================================

class StoryChoiceOutput(BaseModel):
    """故事选项"""
    choice_id: str
    text: str
    emoji: str


class StorySegmentOutput(BaseModel):
    """故事段落输出"""
    segment_id: int
    text: str
    choices: List[StoryChoiceOutput] = []
    is_ending: bool = False


class StoryOpeningOutput(BaseModel):
    """故事开场输出"""
    title: str
    segment: StorySegmentOutput


class NextSegmentOutput(BaseModel):
    """下一段落输出"""
    segment: StorySegmentOutput
    is_ending: bool = False
    educational_summary: Optional[Dict[str, Any]] = None


# ============================================================================
# 年龄适配配置
# ============================================================================

AGE_CONFIG = {
    "3-5": {
        "word_count": "50-100",
        "sentence_length": "5-10字",
        "complexity": "非常简单",
        "vocab_level": "基础日常词汇",
        "theme_depth": "简单、具体、与日常生活相关",
        "choices_style": "简单动作，配有大emoji",
        "total_segments": 3
    },
    "6-8": {
        "word_count": "100-200",
        "sentence_length": "10-15字",
        "complexity": "简单",
        "vocab_level": "小学低年级词汇",
        "theme_depth": "有趣的冒险，简单的道德选择",
        "choices_style": "有趣的选择，配有emoji",
        "total_segments": 4
    },
    "9-12": {
        "word_count": "150-300",
        "sentence_length": "15-25字",
        "complexity": "中等",
        "vocab_level": "小学高年级词汇",
        "theme_depth": "复杂情节，品德和智慧的考验",
        "choices_style": "有深度的选择，影响故事走向",
        "total_segments": 5
    }
}


# ============================================================================
# Agent 函数
# ============================================================================

async def generate_story_opening(
    child_id: str,
    age_group: str,
    interests: List[str],
    theme: str = None
) -> Dict[str, Any]:
    """
    生成互动故事开场

    Args:
        child_id: 儿童ID
        age_group: 年龄组 ("3-5", "6-8", "9-12")
        interests: 兴趣标签列表
        theme: 故事主题（可选）

    Returns:
        包含故事标题和开场段落的字典
    """
    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    interests_str = "、".join(interests) if interests else "冒险"
    theme_str = theme if theme else f"关于{interests[0]}的冒险" if interests else "神秘的冒险"

    prompt = f"""你是一位专业的儿童故事作家，擅长创作适合不同年龄段的互动故事。

请为一个{age_group}岁的儿童创作一个互动故事的**开场**。

**儿童信息**：
- 儿童ID: {child_id}
- 年龄组: {age_group}岁
- 兴趣爱好: {interests_str}
- 故事主题: {theme_str}

**写作要求**（年龄适配）：
- 每段字数: {config['word_count']}字
- 句子长度: {config['sentence_length']}
- 复杂度: {config['complexity']}
- 词汇水平: {config['vocab_level']}
- 主题深度: {config['theme_depth']}
- 选项风格: {config['choices_style']}

**重要规则**：
1. 故事必须温馨、积极、有教育意义
2. 所有分支最终都应该是"好结局"（不惩罚儿童的选择）
3. 自然融入 STEAM 或品德教育元素
4. 开场需要吸引儿童的注意力，设置悬念
5. 提供 2-3 个有趣的选项，每个选项配一个合适的 emoji
6. 选项应该是平等的，没有"正确答案"

**输出格式**：
请直接返回 JSON 格式的故事开场，包含：
- title: 故事标题（吸引人，与主题相关）
- segment: 开场段落
  - segment_id: 0
  - text: 故事开场文本
  - choices: 选项数组，每个选项包含 choice_id, text, emoji
  - is_ending: false

创作一个精彩的故事开场吧！
"""

    options = ClaudeAgentOptions(
        mcp_servers={
            "safety-check": safety_server,
            "vector-search": vector_server
        },
        allowed_tools=[
            "mcp__safety-check__check_content_safety",
            "mcp__vector-search__search_similar_drawings"
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=5,
        output_format={
            "type": "json_schema",
            "schema": StoryOpeningOutput.model_json_schema()
        }
    )

    result_data = {}
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                if hasattr(message, 'structured_output') and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    if isinstance(message.result, dict):
                        result_data = message.result
                    else:
                        # Fallback: create default structure
                        result_data = _create_default_opening(theme_str, interests, config)
                break

    # Validate and ensure required structure
    if not result_data or "title" not in result_data:
        result_data = _create_default_opening(theme_str, interests, config)

    # Ensure segment has proper choice IDs
    if "segment" in result_data and "choices" in result_data["segment"]:
        for i, choice in enumerate(result_data["segment"]["choices"]):
            if "choice_id" not in choice or not choice["choice_id"]:
                choice["choice_id"] = f"choice_0_{chr(97 + i)}"

    return result_data


async def generate_next_segment(
    session_id: str,
    choice_id: str,
    session_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根据选择生成下一个故事段落

    Args:
        session_id: 会话ID
        choice_id: 用户选择的选项ID
        session_data: 会话数据，包含之前的段落和选择历史

    Returns:
        包含下一段落的字典
    """
    segments = session_data.get("segments", [])
    choice_history = session_data.get("choice_history", [])
    age_group = session_data.get("age_group", "6-8")
    interests = session_data.get("interests", ["冒险"])
    theme = session_data.get("theme", "冒险故事")
    story_title = session_data.get("story_title", "神秘的冒险")

    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    segment_count = len(segments)
    total_segments = config["total_segments"]

    # Determine if this should be the ending
    is_final_segment = segment_count >= total_segments - 1

    # Build story context from previous segments
    story_context = "\n".join([
        f"段落 {s.get('segment_id', i)}: {s.get('text', '')}"
        for i, s in enumerate(segments)
    ])

    # Find what the last choice was
    last_segment = segments[-1] if segments else {}
    last_choices = last_segment.get("choices", [])
    chosen_option = None
    for c in last_choices:
        if c.get("choice_id") == choice_id:
            chosen_option = c.get("text", "")
            break

    prompt = f"""你是一位专业的儿童故事作家，正在继续一个互动故事。

**故事信息**：
- 故事标题: {story_title}
- 年龄组: {age_group}岁
- 兴趣爱好: {', '.join(interests)}
- 主题: {theme}
- 当前段落: 第 {segment_count + 1} 段（共 {total_segments} 段）
- 是否为结局: {'是' if is_final_segment else '否'}

**之前的故事内容**：
{story_context if story_context else "这是故事的开始"}

**用户的选择**：
选择ID: {choice_id}
选择内容: {chosen_option or "继续故事"}

**写作要求**（年龄适配）：
- 每段字数: {config['word_count']}字
- 句子长度: {config['sentence_length']}
- 复杂度: {config['complexity']}
- 词汇水平: {config['vocab_level']}
- 选项风格: {config['choices_style']}

**重要规则**：
1. 根据用户的选择自然延续故事
2. 保持故事的连贯性和吸引力
3. {'这是结局段落，请给出一个温馨、积极的结局，总结故事的教育意义' if is_final_segment else '继续发展情节，提供 2-3 个新选项'}
4. 所有内容必须适合儿童，积极向上
5. {'不需要提供选项' if is_final_segment else '每个选项配一个合适的 emoji'}

**输出格式**：
请直接返回 JSON 格式，包含：
- segment: 故事段落
  - segment_id: {segment_count}
  - text: 故事内容
  - choices: {'空数组 []' if is_final_segment else '选项数组'}
  - is_ending: {str(is_final_segment).lower()}
- is_ending: {str(is_final_segment).lower()}
{f'''- educational_summary: 教育总结（仅结局时提供）
  - themes: 主题数组（如：["勇气", "友谊"]）
  - concepts: 概念数组（如：["决策", "合作"]）
  - moral: 道德寓意（一句话总结）''' if is_final_segment else ''}

继续这个精彩的故事吧！
"""

    options = ClaudeAgentOptions(
        mcp_servers={
            "safety-check": safety_server
        },
        allowed_tools=[
            "mcp__safety-check__check_content_safety"
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=5,
        output_format={
            "type": "json_schema",
            "schema": NextSegmentOutput.model_json_schema()
        }
    )

    result_data = {}
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                if hasattr(message, 'structured_output') and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    if isinstance(message.result, dict):
                        result_data = message.result
                    else:
                        result_data = _create_default_segment(
                            segment_count, is_final_segment, chosen_option
                        )
                break

    # Validate and ensure required structure
    if not result_data or "segment" not in result_data:
        result_data = _create_default_segment(
            segment_count, is_final_segment, chosen_option
        )

    # Ensure proper structure
    result_data["is_ending"] = is_final_segment

    if "segment" in result_data:
        result_data["segment"]["segment_id"] = segment_count
        result_data["segment"]["is_ending"] = is_final_segment

        # Ensure choice IDs for non-ending segments
        if not is_final_segment and "choices" in result_data["segment"]:
            for i, choice in enumerate(result_data["segment"]["choices"]):
                if "choice_id" not in choice or not choice["choice_id"]:
                    choice["choice_id"] = f"choice_{segment_count}_{chr(97 + i)}"

    # Add educational summary for endings
    if is_final_segment and "educational_summary" not in result_data:
        result_data["educational_summary"] = {
            "themes": ["勇气", "友谊"],
            "concepts": ["决策", "探索"],
            "moral": "勇敢面对挑战，和朋友一起会更有力量"
        }

    return result_data


def _create_default_opening(theme: str, interests: List[str], config: Dict) -> Dict[str, Any]:
    """创建默认开场（当AI生成失败时使用）"""
    interest_item = interests[0] if interests else "宝箱"
    return {
        "title": f"{theme}之旅",
        "segment": {
            "segment_id": 0,
            "text": f"在一个阳光明媚的早晨，小主人公发现了一个神秘的{interest_item}。它闪闪发光，好像在邀请小主人公来探索...",
            "choices": [
                {"choice_id": "choice_0_a", "text": "立刻去探索", "emoji": "🔍"},
                {"choice_id": "choice_0_b", "text": "先找朋友一起", "emoji": "👫"},
                {"choice_id": "choice_0_c", "text": "仔细观察一下", "emoji": "👀"}
            ],
            "is_ending": False
        }
    }


def _create_default_segment(segment_id: int, is_ending: bool, choice_text: str = None) -> Dict[str, Any]:
    """创建默认段落（当AI生成失败时使用）"""
    if is_ending:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": "经过这次奇妙的冒险，小主人公学会了很多。不管遇到什么困难，只要勇敢面对，善待朋友，就一定能找到解决办法。这真是一次难忘的经历！",
                "choices": [],
                "is_ending": True
            },
            "is_ending": True,
            "educational_summary": {
                "themes": ["勇气", "友谊"],
                "concepts": ["决策", "探索"],
                "moral": "勇敢面对挑战，和朋友一起会更有力量"
            }
        }
    else:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": f"小主人公决定{choice_text or '继续探索'}。前方出现了一条分岔路，一边通向神秘的森林，一边通向闪闪发光的小溪...",
                "choices": [
                    {"choice_id": f"choice_{segment_id}_a", "text": "走向森林", "emoji": "🌲"},
                    {"choice_id": f"choice_{segment_id}_b", "text": "走向小溪", "emoji": "💧"}
                ],
                "is_ending": False
            },
            "is_ending": False
        }


if __name__ == "__main__":
    """测试 Agent"""
    import asyncio

    async def test():
        print("=== 测试 Interactive Story Agent ===\n")

        try:
            # 测试生成开场
            print("1. 测试生成故事开场...")
            opening = await generate_story_opening(
                child_id="test_child_001",
                age_group="6-8",
                interests=["恐龙", "冒险"],
                theme="恐龙世界探险"
            )
            print(f"标题: {opening.get('title')}")
            print(f"开场: {opening.get('segment', {}).get('text', '')[:100]}...")
            print(f"选项数: {len(opening.get('segment', {}).get('choices', []))}")
            print()

            # 测试生成下一段
            print("2. 测试生成下一段...")
            next_seg = await generate_next_segment(
                session_id="test_session",
                choice_id="choice_0_a",
                session_data={
                    "segments": [opening.get("segment", {})],
                    "choice_history": ["choice_0_a"],
                    "age_group": "6-8",
                    "interests": ["恐龙", "冒险"],
                    "theme": "恐龙世界探险",
                    "story_title": opening.get("title", "冒险故事")
                }
            )
            print(f"段落: {next_seg.get('segment', {}).get('text', '')[:100]}...")
            print(f"是否结局: {next_seg.get('is_ending')}")
            print()

            print("✅ 测试完成！")

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(test())
