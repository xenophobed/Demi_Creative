"""
Interactive Story Agent

使用 Claude Agent SDK 生成多分支互动故事。
支持流式响应以减少超时和改善用户体验。
"""

import json
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        ToolResultBlock,
        ToolUseBlock,
    )
except Exception:  # pragma: no cover - import fallback for test env
    ClaudeAgentOptions = None
    ResultMessage = object
    ClaudeSDKClient = None
    AssistantMessage = object
    ToolUseBlock = object
    ToolResultBlock = object


from ..mcp_servers import (
    safety_server,
    search_similar_stories,
    tts_server,
    vector_server,
)
from ..services.database import preference_repo
from ..services.story_memory import get_story_memory_prompt
from ..utils.model_config import get_claude_agent_model


async def _search_story_dedup(
    child_id: str, description: str, threshold: float = 0.9
) -> str:
    """Search for similar past stories and return a variation nudge if duplicates found.

    Best-effort: returns empty string on any failure. (#290)
    """
    if not child_id or not description:
        return ""
    try:
        result = await search_similar_stories(
            {
                "child_id": child_id,
                "story_description": description,
                "top_k": 3,
            }
        )
        import json as _json

        data = _json.loads(result["content"][0]["text"])
        similar = data.get("similar_stories", [])
        high_sim = [s for s in similar if s.get("similarity_score", 0) >= threshold]
        if not high_sim:
            return ""
        summaries = "\n".join(
            f"- {s.get('story_text_preview', 'N/A')}" for s in high_sim[:3]
        )
        return f"""
**Story Freshness — Variation Required** (#290):
The child has heard similar stories before:
{summaries}
Please create a FRESH, DIFFERENT story with a new angle, different plot structure, and different character dynamics.
"""
    except Exception:
        return ""


def _should_use_mock() -> bool:
    """Return True when running inside pytest or when the SDK is unavailable."""
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


# ============================================================================
# 流式事件类型
# ============================================================================


class StreamEvent:
    """流式事件基类"""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.type = event_type
        self.data = data

    def to_sse(self) -> str:
        """转换为 Server-Sent Event 格式"""
        return (
            f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"
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
        "total_segments": 3,
        # Audio settings
        "audio_mode": "audio_first",
        "voice": "nova",
        "speed": 0.9,
    },
    "6-8": {
        "word_count": "100-200",
        "sentence_length": "10-15字",
        "complexity": "简单",
        "vocab_level": "小学低年级词汇",
        "theme_depth": "有趣的冒险，简单的道德选择",
        "choices_style": "有趣的选择，配有emoji",
        "total_segments": 4,
        # Audio settings
        "audio_mode": "simultaneous",
        "voice": "shimmer",
        "speed": 1.0,
    },
    "9-12": {
        "word_count": "150-300",
        "sentence_length": "15-25字",
        "complexity": "中等",
        "vocab_level": "小学高年级词汇",
        "theme_depth": "复杂情节，品德和智慧的考验",
        "choices_style": "有深度的选择，影响故事走向",
        "total_segments": 5,
        # Audio settings
        "audio_mode": "text_first",
        "voice": "alloy",
        "speed": 1.1,
    },
}


# ============================================================================
# Prompt Construction Helpers (#72, #73)
# ============================================================================


async def _fetch_preference_context(child_id: str) -> str:
    """
    Fetch child preference profile and format as prompt context.

    Returns formatted string for injection into opening prompt,
    or empty string if no meaningful preferences exist.
    """
    try:
        profile = await preference_repo.get_profile(child_id)
    except Exception:
        return ""

    sections = []

    # Top 3 themes by frequency
    themes = profile.get("themes", {})
    if themes:
        top_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:3]
        sections.append(f"- 喜欢的主题: {', '.join(t[0] for t in top_themes)}")

    # Top 3 interests
    interests = profile.get("interests", {})
    if interests:
        top_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:3]
        sections.append(f"- 兴趣偏好: {', '.join(t[0] for t in top_interests)}")

    # Last 3 recent choices
    recent = profile.get("recent_choices", [])
    if recent:
        last_3 = recent[-3:]
        sections.append(f"- 最近选择: {', '.join(last_3)}")

    if not sections:
        return ""

    return "**儿童偏好记忆**：\n" + "\n".join(sections) + "\n"


def _build_opening_prompt(
    child_id: str,
    age_group: str,
    interests_str: str,
    theme_str: str,
    config: Dict[str, Any],
    preference_context: str = "",
    story_memory_section: str = "",
    dedup_nudge: str = "",
) -> str:
    """
    Build the full prompt for interactive story opening generation.

    Includes preference context (#72) and character continuity instructions (#73).
    """
    prompt = f"""你是一位专业的儿童故事作家，擅长创作适合不同年龄段的互动故事。

请为一个{age_group}岁的儿童创作一个互动故事的**开场**。

**儿童信息**：
- 儿童ID: {child_id}
- 年龄组: {age_group}岁
- 兴趣爱好: {interests_str}
- 故事主题: {theme_str}

**写作要求**（年龄适配）：
- 每段字数: {config["word_count"]}字
- 句子长度: {config["sentence_length"]}
- 复杂度: {config["complexity"]}
- 词汇水平: {config["vocab_level"]}
- 主题深度: {config["theme_depth"]}
- 选项风格: {config["choices_style"]}
"""

    # Inject preference context (#72)
    if preference_context:
        prompt += f"\n{preference_context}\n请根据上述儿童偏好，自然地融入他们喜欢的主题和元素。\n"

    # Inject cross-story memory (#165)
    if story_memory_section:
        prompt += f"\n{story_memory_section}\n"

    # Inject dedup variation nudge (#290)
    if dedup_nudge:
        prompt += f"\n{dedup_nudge}\n"

    # Character continuity (#73)
    prompt += f"""
**角色连续性**：
在创作故事前，请先使用 `mcp__vector-search__search_similar_drawings` 工具搜索该儿童之前的创作，查找是否有反复出现的角色。
- 搜索参数: child_id="{child_id}", query="{interests_str}"
- 如果发现 recurring_characters，自然地将这些角色融入新故事（不要强制，而是让角色自然出现）
- 如果没有历史角色，正常创作全新故事

**内容存储**：
故事创作完成后，请使用 `mcp__vector-search__store_drawing_embedding` 工具存储本次创作的角色信息，以便未来的故事可以延续角色。

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
    return prompt


def _build_next_segment_prompt(
    story_title: str,
    age_group: str,
    interests: List[str],
    theme: str,
    segment_count: int,
    total_segments: int,
    is_final_segment: bool,
    story_context: str,
    choice_id: str,
    chosen_option: str,
    config: Dict[str, Any],
    choice_history_context: str = "",
    opening_hook: str = "",
) -> str:
    """Build prompt for generating the next story segment."""
    return f"""你是一位专业的儿童故事作家，正在继续一个互动故事。

**故事信息**：
- 故事标题: {story_title}
- 年龄组: {age_group}岁
- 兴趣爱好: {", ".join(interests)}
- 主题: {theme}
- 当前段落: 第 {segment_count + 1} 段（共 {total_segments} 段）
- 是否为结局: {"是" if is_final_segment else "否"}

**之前的故事内容**：
{story_context if story_context else "这是故事的开始"}

**用户决策轨迹（按时间顺序）**：
{choice_history_context if choice_history_context else "（暂无历史选择）"}

**开场关键线索（结局必须回扣）**：
{opening_hook if opening_hook else "（无）"}

**用户的选择**：
选择ID: {choice_id}
选择内容: {chosen_option or "继续故事"}

**写作要求**（年龄适配）：
- 每段字数: {config["word_count"]}字
- 句子长度: {config["sentence_length"]}
- 复杂度: {config["complexity"]}
- 词汇水平: {config["vocab_level"]}
- 选项风格: {config["choices_style"]}

**重要规则**：
1. 根据用户的选择自然延续故事
2. 保持故事的连贯性和吸引力
3. {
        "这是结局段落，请给出一个温馨、积极、完整的结局：必须明确回应开场线索，并回扣至少两个关键选择，让结尾和前文形成闭环"
        if is_final_segment
        else "继续发展情节，提供 2-3 个新选项"
    }
4. 所有内容必须适合儿童，积极向上
5. {"不需要提供选项" if is_final_segment else "每个选项配一个合适的 emoji"}
6. {
        "结局不要再引入新的大冲突，重点是解决之前的问题并给出成长收获"
        if is_final_segment
        else "确保新选项真实影响后续发展，避免重复表述"
    }

**输出格式**：
请直接返回 JSON 格式，包含：
- segment: 故事段落
  - segment_id: {segment_count}
  - text: 故事内容
  - choices: {"空数组 []" if is_final_segment else "选项数组"}
  - is_ending: {str(is_final_segment).lower()}
- is_ending: {str(is_final_segment).lower()}
{
        f'''- educational_summary: 教育总结（仅结局时提供）
  - themes: 主题数组（如：["勇气", "友谊"]）
  - concepts: 概念数组（如：["决策", "合作"]）
  - moral: 道德寓意（一句话总结）'''
        if is_final_segment
        else ""
    }

继续这个精彩的故事吧！
"""


def _append_tts_instructions(
    prompt: str,
    voice: str,
    speed: float,
    id_label: str,
    id_value: str,
) -> str:
    """Append TTS generation instructions to a prompt."""
    return (
        prompt
        + f"""

**语音生成**：
故事创作完成后，请使用 `mcp__tts-generation__generate_story_audio` 工具为故事文本生成语音。
- 语音类型: {voice}
- 语速: {speed}
- {id_label}: {id_value}
"""
    )


# ============================================================================
# Story Coherence Helpers
# ============================================================================


def _build_fallback_choices(segment_id: int, age_group: str) -> List[Dict[str, str]]:
    """Fallback choices to keep interactive flow complete when model output is sparse."""
    if age_group == "3-5":
        templates = [("和伙伴一起前进", "🤝"), ("先观察再行动", "👀")]
    elif age_group == "9-12":
        templates = [("根据线索制定计划", "🧭"), ("先帮助伙伴再推进任务", "💡")]
    else:
        templates = [("顺着线索继续前进", "🔍"), ("和伙伴商量新计划", "🤝")]

    return [
        {
            "choice_id": f"choice_{segment_id}_{chr(97 + i)}",
            "text": text,
            "emoji": emoji,
        }
        for i, (text, emoji) in enumerate(templates)
    ]


def _normalize_choices(
    raw_choices: Any,
    segment_id: int,
    is_final_segment: bool,
    age_group: str,
) -> List[Dict[str, str]]:
    """Guarantee non-ending segments always have 2-3 valid choices."""
    if is_final_segment:
        return []

    normalized: List[Dict[str, str]] = []
    seen_texts: set[str] = set()
    emoji_defaults = ["✨", "🧭", "🤝"]

    if isinstance(raw_choices, list):
        for idx, choice in enumerate(raw_choices):
            if len(normalized) >= 3:
                break
            if not isinstance(choice, dict):
                continue
            text = str(choice.get("text", "")).strip()
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)
            emoji = (
                str(choice.get("emoji", "")).strip()
                or emoji_defaults[idx % len(emoji_defaults)]
            )
            normalized.append({"choice_id": "", "text": text, "emoji": emoji})

    if len(normalized) < 2:
        for fb in _build_fallback_choices(segment_id, age_group):
            if fb["text"] in seen_texts:
                continue
            seen_texts.add(fb["text"])
            normalized.append(
                {"choice_id": "", "text": fb["text"], "emoji": fb["emoji"]}
            )
            if len(normalized) >= 2:
                break

    # Rewrite IDs in stable order for the current segment
    for i, choice in enumerate(normalized[:3]):
        choice["choice_id"] = f"choice_{segment_id}_{chr(97 + i)}"

    return normalized[:3]


def _build_choice_history_context(
    segments: List[Dict[str, Any]], choice_history: List[str]
) -> str:
    """Build readable path history so the next segment can stay consistent."""
    if not choice_history:
        return "（暂无历史选择）"

    lines: List[str] = []
    for idx, choice_id in enumerate(choice_history):
        choice_text = str(choice_id)
        if idx < len(segments):
            seg_choices = segments[idx].get("choices", [])
            if isinstance(seg_choices, list):
                for choice in seg_choices:
                    if not isinstance(choice, dict):
                        continue
                    if choice.get("choice_id") == choice_id:
                        choice_text = str(choice.get("text", choice_id))
                        break
        lines.append(f"{idx + 1}. {choice_text}")

    return "\n".join(lines)


def _extract_opening_hook(segments: List[Dict[str, Any]]) -> str:
    """Extract first sentence from opening to enforce ending callback."""
    if not segments:
        return ""
    opening_text = str(segments[0].get("text", "")).strip()
    if not opening_text:
        return ""
    parts = re.split(r"[。！？!?]", opening_text)
    hook = parts[0].strip() if parts else opening_text
    return hook[:36]


def _ensure_ending_coherence(
    ending_text: str,
    opening_hook: str,
    chosen_option: Optional[str],
    choice_history_context: str,
) -> str:
    """Ensure final segment explicitly connects to opening and recent choices."""
    text = str(ending_text or "").strip()
    if not text:
        text = "这次冒险终于迎来了温暖的结局。"

    additions: List[str] = []
    if opening_hook and opening_hook not in text:
        additions.append(
            f"回想起故事开始时“{opening_hook}”，大家终于把这段冒险走到了温暖的结局。"
        )

    if chosen_option:
        chosen_option = str(chosen_option).strip()
        if chosen_option and chosen_option not in text:
            additions.append(
                f"也正因为最后选择了“{chosen_option}”，故事才迎来了现在的结果。"
            )

    if not any(k in text for k in ["最后", "终于", "结局", "回到", "学会", "从此"]):
        additions.append("最后，大家带着新的勇气与智慧回到日常生活，故事也圆满结束。")

    history_lines = [
        line.strip()
        for line in choice_history_context.splitlines()
        if line.strip() and line.strip()[0].isdigit()
    ]
    if history_lines:
        last_steps = []
        for line in history_lines[-2:]:
            if ". " in line:
                last_steps.append(line.split(". ", 1)[1])
            else:
                last_steps.append(line)
        summary = "；".join(last_steps)
        if summary and summary not in text:
            additions.append(f"一路上的关键选择（{summary}）在这一刻都得到了回应。")

    if additions:
        text = f"{text} {' '.join(additions)}"

    return text


# ============================================================================
# Agent 函数
# ============================================================================


def _mock_opening(interests: List[str]) -> Dict[str, Any]:
    topic = interests[0] if interests else "冒险"
    return {
        "title": f"{topic}小队大冒险",
        "segment": {
            "segment_id": 0,
            "text": f"在一个阳光明媚的早晨，小伙伴们决定开始一次关于{topic}的探索。",
            "choices": [
                {"choice_id": "choice_0_a", "text": "马上出发", "emoji": "🚀"},
                {"choice_id": "choice_0_b", "text": "先做准备", "emoji": "🎒"},
            ],
            "is_ending": False,
        },
    }


def _mock_next_segment(segment_count: int, is_final_segment: bool) -> Dict[str, Any]:
    segment = {
        "segment_id": segment_count,
        "text": "小伙伴们继续前进，发现了新的线索，并学会了互相帮助。",
        "choices": []
        if is_final_segment
        else [
            {
                "choice_id": f"choice_{segment_count}_a",
                "text": "勇敢尝试",
                "emoji": "✨",
            },
            {
                "choice_id": f"choice_{segment_count}_b",
                "text": "团队讨论",
                "emoji": "🤝",
            },
        ],
        "is_ending": is_final_segment,
    }
    result = {"segment": segment, "is_ending": is_final_segment}
    if is_final_segment:
        result["educational_summary"] = {
            "themes": ["勇气", "合作"],
            "concepts": ["选择", "探索"],
            "moral": "勇敢尝试并与伙伴合作，问题就会有答案。",
        }
    return result


async def generate_story_opening(
    child_id: str,
    age_group: str,
    interests: List[str],
    theme: str = None,
    enable_audio: bool = True,
    voice: str = None,
    user_id: str = "",
) -> Dict[str, Any]:
    """
    生成互动故事开场

    Args:
        child_id: 儿童ID
        age_group: 年龄组 ("3-5", "6-8", "9-12")
        interests: 兴趣标签列表
        theme: 故事主题（可选）
        enable_audio: 是否生成语音
        voice: 语音类型（可选，默认根据年龄组选择）

    Returns:
        包含故事标题和开场段落的字典
    """
    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    if _should_use_mock():
        return _mock_opening(interests)
    interests_str = "、".join(interests) if interests else "冒险"
    theme_str = (
        theme if theme else f"关于{interests[0]}的冒险" if interests else "神秘的冒险"
    )

    # Fetch preference context (#72)
    preference_context = await _fetch_preference_context(child_id)

    # Build story memory section for cross-story references (#165)
    story_memory_section = ""
    try:
        story_memory_section = await get_story_memory_prompt(child_id, user_id=user_id)
    except Exception:
        pass  # Non-critical

    # Story dedup check (#290)
    dedup_nudge = ""
    try:
        dedup_nudge = await _search_story_dedup(child_id, interests_str)
    except Exception:
        pass  # Best-effort

    # Build prompt with preference + character continuity (#72, #73)
    prompt = _build_opening_prompt(
        child_id=child_id,
        age_group=age_group,
        interests_str=interests_str,
        theme_str=theme_str,
        config=config,
        preference_context=preference_context,
        story_memory_section=story_memory_section,
        dedup_nudge=dedup_nudge,
    )

    # Determine if we should generate audio based on age_group audio_mode
    audio_mode = config.get("audio_mode", "simultaneous")
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or config.get("voice", "nova")
    audio_speed = config.get("speed", 1.0)

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt = _append_tts_instructions(
            prompt, actual_voice, audio_speed, "儿童ID", child_id
        )

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers={
            "safety-check": safety_server,
            "vector-search": vector_server,
            "tts-generation": tts_server,
        },
        allowed_tools=[
            "mcp__safety-check__check_content_safety",
            "mcp__vector-search__search_similar_drawings",
            "mcp__vector-search__store_drawing_embedding",
            "mcp__vector-search__search_similar_stories",
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=12,  # Increased: search + store + TTS add extra turns
        output_format={
            "type": "json_schema",
            "schema": StoryOpeningOutput.model_json_schema(),
        },
    )

    result_data = {}
    audio_path = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            # Check for TTS tool results in assistant messages
            if isinstance(message, AssistantMessage):
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            # Try to extract audio path from TTS result
                            result_content = getattr(block, "content", None)
                            if result_content and isinstance(result_content, str):
                                try:
                                    result_json = json.loads(result_content)
                                    if "audio_path" in result_json:
                                        audio_path = result_json["audio_path"]
                                except (json.JSONDecodeError, TypeError):
                                    pass

            if isinstance(message, ResultMessage):
                if hasattr(message, "structured_output") and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    if isinstance(message.result, dict):
                        result_data = message.result
                    else:
                        # Fallback: create default structure
                        result_data = _create_default_opening(
                            theme_str, interests, config
                        )
                break

    # Validate and ensure required structure
    if not result_data or "title" not in result_data:
        result_data = _create_default_opening(theme_str, interests, config)

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Ensure opening has valid interactive choices
    if "segment" in result_data and "choices" in result_data["segment"]:
        result_data["segment"]["choices"] = _normalize_choices(
            result_data["segment"]["choices"],
            segment_id=0,
            is_final_segment=False,
            age_group=age_group,
        )

    return result_data


async def generate_story_opening_stream(
    child_id: str,
    age_group: str,
    interests: List[str],
    theme: str = None,
    enable_audio: bool = True,
    voice: str = None,
    user_id: str = "",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式生成互动故事开场

    Args:
        child_id: 儿童ID
        age_group: 年龄组 ("3-5", "6-8", "9-12")
        interests: 兴趣标签列表
        theme: 故事主题（可选）
        enable_audio: 是否生成语音
        voice: 语音类型（可选）

    Yields:
        流式事件字典，包含 type 和 data 字段
    """
    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    if _should_use_mock():
        yield {
            "type": "status",
            "data": {"status": "started", "message": "正在生成故事开场..."},
        }
        yield {"type": "result", "data": _mock_opening(interests)}
        yield {
            "type": "complete",
            "data": {"status": "completed", "message": "故事开场生成完成"},
        }
        return
    interests_str = "、".join(interests) if interests else "冒险"
    theme_str = (
        theme if theme else f"关于{interests[0]}的冒险" if interests else "神秘的冒险"
    )

    # 发送开始事件
    yield {
        "type": "status",
        "data": {"status": "started", "message": "正在创作故事..."},
    }

    # Fetch preference context (#72)
    preference_context = await _fetch_preference_context(child_id)

    # Build story memory section for cross-story references (#165)
    story_memory_section = ""
    try:
        story_memory_section = await get_story_memory_prompt(child_id, user_id=user_id)
    except Exception:
        pass  # Non-critical

    # Build prompt with preference + character continuity (#72, #73)
    prompt = _build_opening_prompt(
        child_id=child_id,
        age_group=age_group,
        interests_str=interests_str,
        theme_str=theme_str,
        config=config,
        preference_context=preference_context,
        story_memory_section=story_memory_section,
    )

    # Determine if we should generate audio based on age_group audio_mode
    audio_mode = config.get("audio_mode", "simultaneous")
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or config.get("voice", "nova")
    audio_speed = config.get("speed", 1.0)

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt = _append_tts_instructions(
            prompt, actual_voice, audio_speed, "儿童ID", child_id
        )

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers={
            "safety-check": safety_server,
            "vector-search": vector_server,
            "tts-generation": tts_server,
        },
        allowed_tools=[
            "mcp__safety-check__check_content_safety",
            "mcp__vector-search__search_similar_drawings",
            "mcp__vector-search__store_drawing_embedding",
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=12,  # Increased: search + store + TTS add extra turns
        output_format={
            "type": "json_schema",
            "schema": StoryOpeningOutput.model_json_schema(),
        },
    )

    result_data = {}
    thinking_text = ""
    turn_count = 0
    audio_path = None

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                # 处理助手消息（思考过程和工具使用）
                if isinstance(message, AssistantMessage):
                    turn_count += 1

                    # 获取消息内容
                    content = getattr(message, "content", None)

                    # content 可能是字符串或内容块列表
                    if isinstance(content, str) and content:
                        thinking_text += content
                        yield {
                            "type": "thinking",
                            "data": {
                                "content": content[:200] + "..."
                                if len(content) > 200
                                else content,
                                "turn": turn_count,
                            },
                        }
                    elif isinstance(content, list):
                        # 遍历内容块
                        for block in content:
                            # 检查工具使用块
                            if isinstance(block, ToolUseBlock):
                                tool_name = getattr(block, "name", "unknown")
                                # Friendly tool name mapping
                                tool_messages = {
                                    "mcp__safety-check__check_content_safety": "正在检查内容安全...",
                                    "mcp__vector-search__search_similar_drawings": "正在搜索历史角色...",
                                    "mcp__vector-search__store_drawing_embedding": "正在存储角色记忆...",
                                    "mcp__tts-generation__generate_story_audio": "正在生成语音...",
                                }
                                yield {
                                    "type": "tool_use",
                                    "data": {
                                        "tool": tool_name,
                                        "message": tool_messages.get(
                                            tool_name, f"正在使用 {tool_name}..."
                                        ),
                                    },
                                }
                            # 检查工具结果块
                            elif isinstance(block, ToolResultBlock):
                                # Try to extract audio path from TTS result
                                result_content = getattr(block, "content", None)
                                if result_content and isinstance(result_content, str):
                                    try:
                                        result_json = json.loads(result_content)
                                        if "audio_path" in result_json:
                                            audio_path = result_json["audio_path"]
                                            yield {
                                                "type": "audio_generated",
                                                "data": {
                                                    "audio_path": audio_path,
                                                    "message": "语音生成完成",
                                                },
                                            }
                                    except (json.JSONDecodeError, TypeError):
                                        pass

                                yield {
                                    "type": "tool_result",
                                    "data": {
                                        "status": "completed",
                                        "message": "工具执行完成",
                                    },
                                }
                            # 处理文本块
                            elif hasattr(block, "text"):
                                text = block.text
                                if text:
                                    thinking_text += text
                                    yield {
                                        "type": "thinking",
                                        "data": {
                                            "content": text[:200] + "..."
                                            if len(text) > 200
                                            else text,
                                            "turn": turn_count,
                                        },
                                    }

                # 处理最终结果
                elif isinstance(message, ResultMessage):
                    if (
                        hasattr(message, "structured_output")
                        and message.structured_output
                    ):
                        result_data = message.structured_output
                    elif message.result:
                        if isinstance(message.result, dict):
                            result_data = message.result
                        else:
                            result_data = _create_default_opening(
                                theme_str, interests, config
                            )
                    break

    except Exception as e:
        yield {
            "type": "error",
            "data": {"error": str(e), "message": "生成故事时发生错误"},
        }
        # 使用默认开场
        result_data = _create_default_opening(theme_str, interests, config)

    # 验证并确保必需的结构
    if not result_data or "title" not in result_data:
        result_data = _create_default_opening(theme_str, interests, config)

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # 确保开场总是有有效选项，避免故事中途卡住
    if "segment" in result_data and "choices" in result_data["segment"]:
        result_data["segment"]["choices"] = _normalize_choices(
            result_data["segment"]["choices"],
            segment_id=0,
            is_final_segment=False,
            age_group=age_group,
        )

    # 发送最终结果
    yield {"type": "result", "data": result_data}

    yield {
        "type": "complete",
        "data": {"status": "completed", "message": "故事创作完成！"},
    }


async def generate_next_segment_stream(
    session_id: str,
    choice_id: str,
    session_data: Dict[str, Any],
    enable_audio: bool = True,
    voice: str = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式生成下一个故事段落

    Args:
        session_id: 会话ID
        choice_id: 用户选择的选项ID
        session_data: 会话数据
        enable_audio: 是否生成语音
        voice: 语音类型（可选）

    Yields:
        流式事件字典
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
    is_final_segment = segment_count >= total_segments - 1

    if _should_use_mock():
        yield {
            "type": "status",
            "data": {"status": "processing", "message": "正在继续故事..."},
        }
        yield {
            "type": "result",
            "data": _mock_next_segment(segment_count, is_final_segment),
        }
        yield {
            "type": "complete",
            "data": {"status": "completed", "message": "段落生成完成"},
        }
        return

    # 发送开始事件
    yield {
        "type": "status",
        "data": {
            "status": "started",
            "message": "正在继续故事..." if not is_final_segment else "正在创作结局...",
            "is_ending": is_final_segment,
        },
    }

    # Build story context from previous segments
    story_context = "\n".join(
        [
            f"段落 {s.get('segment_id', i)}: {s.get('text', '')}"
            for i, s in enumerate(segments)
        ]
    )

    # Find what the last choice was
    last_segment = segments[-1] if segments else {}
    last_choices = last_segment.get("choices", [])
    chosen_option = None
    for c in last_choices:
        if c.get("choice_id") == choice_id:
            chosen_option = c.get("text", "")
            break

    choice_history_context = _build_choice_history_context(segments, choice_history)
    opening_hook = _extract_opening_hook(segments)

    prompt = _build_next_segment_prompt(
        story_title=story_title,
        age_group=age_group,
        interests=interests,
        theme=theme,
        segment_count=segment_count,
        total_segments=total_segments,
        is_final_segment=is_final_segment,
        story_context=story_context,
        choice_id=choice_id,
        chosen_option=chosen_option,
        config=config,
        choice_history_context=choice_history_context,
        opening_hook=opening_hook,
    )

    # Determine if we should generate audio based on age_group audio_mode
    audio_mode = config.get("audio_mode", "simultaneous")
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or config.get("voice", "nova")
    audio_speed = config.get("speed", 1.0)

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt = _append_tts_instructions(
            prompt, actual_voice, audio_speed, "会话ID", session_id
        )

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers={"safety-check": safety_server, "tts-generation": tts_server},
        allowed_tools=[
            "mcp__safety-check__check_content_safety",
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=10,  # Increased to allow for TTS generation
        output_format={
            "type": "json_schema",
            "schema": NextSegmentOutput.model_json_schema(),
        },
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

                    content = getattr(message, "content", None)

                    if isinstance(content, str) and content:
                        yield {
                            "type": "thinking",
                            "data": {
                                "content": content[:200] + "..."
                                if len(content) > 200
                                else content,
                                "turn": turn_count,
                            },
                        }
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, ToolUseBlock):
                                tool_name = getattr(block, "name", "unknown")
                                tool_messages = {
                                    "mcp__safety-check__check_content_safety": "正在检查内容安全...",
                                    "mcp__tts-generation__generate_story_audio": "正在生成语音...",
                                }
                                yield {
                                    "type": "tool_use",
                                    "data": {
                                        "tool": tool_name,
                                        "message": tool_messages.get(
                                            tool_name, f"正在使用 {tool_name}..."
                                        ),
                                    },
                                }
                            elif isinstance(block, ToolResultBlock):
                                # Try to extract audio path from TTS result
                                result_content = getattr(block, "content", None)
                                if result_content and isinstance(result_content, str):
                                    try:
                                        result_json = json.loads(result_content)
                                        if "audio_path" in result_json:
                                            audio_path = result_json["audio_path"]
                                            yield {
                                                "type": "audio_generated",
                                                "data": {
                                                    "audio_path": audio_path,
                                                    "message": "语音生成完成",
                                                },
                                            }
                                    except (json.JSONDecodeError, TypeError):
                                        pass

                                yield {
                                    "type": "tool_result",
                                    "data": {"status": "completed"},
                                }
                            elif hasattr(block, "text"):
                                text = block.text
                                if text:
                                    yield {
                                        "type": "thinking",
                                        "data": {
                                            "content": text[:200] + "..."
                                            if len(text) > 200
                                            else text,
                                            "turn": turn_count,
                                        },
                                    }

                elif isinstance(message, ResultMessage):
                    if (
                        hasattr(message, "structured_output")
                        and message.structured_output
                    ):
                        result_data = message.structured_output
                    elif message.result:
                        if isinstance(message.result, dict):
                            result_data = message.result
                        else:
                            result_data = _create_default_segment(
                                segment_count, is_final_segment, chosen_option
                            )
                    break

    except Exception as e:
        yield {
            "type": "error",
            "data": {"error": str(e), "message": "生成故事时发生错误"},
        }
        result_data = _create_default_segment(
            segment_count, is_final_segment, chosen_option
        )

    # Validate and ensure required structure
    if not result_data or "segment" not in result_data:
        result_data = _create_default_segment(
            segment_count, is_final_segment, chosen_option
        )

    result_data["is_ending"] = is_final_segment

    if "segment" in result_data:
        result_data["segment"]["segment_id"] = segment_count
        result_data["segment"]["is_ending"] = is_final_segment
        result_data["segment"]["choices"] = _normalize_choices(
            result_data["segment"].get("choices", []),
            segment_id=segment_count,
            is_final_segment=is_final_segment,
            age_group=age_group,
        )
        if is_final_segment:
            result_data["segment"]["text"] = _ensure_ending_coherence(
                result_data["segment"].get("text", ""),
                opening_hook=opening_hook,
                chosen_option=chosen_option,
                choice_history_context=choice_history_context,
            )

    if is_final_segment and "educational_summary" not in result_data:
        result_data["educational_summary"] = {
            "themes": ["勇气", "友谊"],
            "concepts": ["决策", "探索"],
            "moral": "勇敢面对挑战，和朋友一起会更有力量",
        }

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    yield {"type": "result", "data": result_data}

    yield {
        "type": "complete",
        "data": {
            "status": "completed",
            "message": "故事创作完成！" if is_final_segment else "段落生成完成！",
        },
    }


async def generate_next_segment(
    session_id: str,
    choice_id: str,
    session_data: Dict[str, Any],
    enable_audio: bool = True,
    voice: str = None,
) -> Dict[str, Any]:
    """
    根据选择生成下一个故事段落

    Args:
        session_id: 会话ID
        choice_id: 用户选择的选项ID
        session_data: 会话数据，包含之前的段落和选择历史
        enable_audio: 是否生成语音
        voice: 语音类型（可选）

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

    if _should_use_mock():
        return _mock_next_segment(segment_count, is_final_segment)

    # Build story context from previous segments
    story_context = "\n".join(
        [
            f"段落 {s.get('segment_id', i)}: {s.get('text', '')}"
            for i, s in enumerate(segments)
        ]
    )

    # Find what the last choice was
    last_segment = segments[-1] if segments else {}
    last_choices = last_segment.get("choices", [])
    chosen_option = None
    for c in last_choices:
        if c.get("choice_id") == choice_id:
            chosen_option = c.get("text", "")
            break

    choice_history_context = _build_choice_history_context(segments, choice_history)
    opening_hook = _extract_opening_hook(segments)

    prompt = _build_next_segment_prompt(
        story_title=story_title,
        age_group=age_group,
        interests=interests,
        theme=theme,
        segment_count=segment_count,
        total_segments=total_segments,
        is_final_segment=is_final_segment,
        story_context=story_context,
        choice_id=choice_id,
        chosen_option=chosen_option,
        config=config,
        choice_history_context=choice_history_context,
        opening_hook=opening_hook,
    )

    # Determine if we should generate audio based on age_group audio_mode
    audio_mode = config.get("audio_mode", "simultaneous")
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or config.get("voice", "nova")
    audio_speed = config.get("speed", 1.0)

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt = _append_tts_instructions(
            prompt, actual_voice, audio_speed, "会话ID", session_id
        )

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers={"safety-check": safety_server, "tts-generation": tts_server},
        allowed_tools=[
            "mcp__safety-check__check_content_safety",
            "mcp__tts-generation__generate_story_audio",
        ],
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=10,  # Increased to allow for TTS generation
        output_format={
            "type": "json_schema",
            "schema": NextSegmentOutput.model_json_schema(),
        },
    )

    result_data = {}
    audio_path = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            # Check for TTS tool results in assistant messages
            if isinstance(message, AssistantMessage):
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            # Try to extract audio path from TTS result
                            result_content = getattr(block, "content", None)
                            if result_content and isinstance(result_content, str):
                                try:
                                    result_json = json.loads(result_content)
                                    if "audio_path" in result_json:
                                        audio_path = result_json["audio_path"]
                                except (json.JSONDecodeError, TypeError):
                                    pass

            if isinstance(message, ResultMessage):
                if hasattr(message, "structured_output") and message.structured_output:
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
        result_data["segment"]["choices"] = _normalize_choices(
            result_data["segment"].get("choices", []),
            segment_id=segment_count,
            is_final_segment=is_final_segment,
            age_group=age_group,
        )
        if is_final_segment:
            result_data["segment"]["text"] = _ensure_ending_coherence(
                result_data["segment"].get("text", ""),
                opening_hook=opening_hook,
                chosen_option=chosen_option,
                choice_history_context=choice_history_context,
            )

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Add educational summary for endings
    if is_final_segment and "educational_summary" not in result_data:
        result_data["educational_summary"] = {
            "themes": ["勇气", "友谊"],
            "concepts": ["决策", "探索"],
            "moral": "勇敢面对挑战，和朋友一起会更有力量",
        }

    return result_data


def _create_default_opening(
    theme: str, interests: List[str], config: Dict
) -> Dict[str, Any]:
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
                {"choice_id": "choice_0_c", "text": "仔细观察一下", "emoji": "👀"},
            ],
            "is_ending": False,
        },
    }


def _create_default_segment(
    segment_id: int, is_ending: bool, choice_text: str = None
) -> Dict[str, Any]:
    """创建默认段落（当AI生成失败时使用）"""
    if is_ending:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": "经过这次奇妙的冒险，小主人公学会了很多。不管遇到什么困难，只要勇敢面对，善待朋友，就一定能找到解决办法。这真是一次难忘的经历！",
                "choices": [],
                "is_ending": True,
            },
            "is_ending": True,
            "educational_summary": {
                "themes": ["勇气", "友谊"],
                "concepts": ["决策", "探索"],
                "moral": "勇敢面对挑战，和朋友一起会更有力量",
            },
        }
    else:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": f"小主人公决定{choice_text or '继续探索'}。前方出现了一条分岔路，一边通向神秘的森林，一边通向闪闪发光的小溪...",
                "choices": [
                    {
                        "choice_id": f"choice_{segment_id}_a",
                        "text": "走向森林",
                        "emoji": "🌲",
                    },
                    {
                        "choice_id": f"choice_{segment_id}_b",
                        "text": "走向小溪",
                        "emoji": "💧",
                    },
                ],
                "is_ending": False,
            },
            "is_ending": False,
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
                theme="恐龙世界探险",
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
                    "story_title": opening.get("title", "冒险故事"),
                },
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
