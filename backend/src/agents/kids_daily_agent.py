"""Kids Daily agent — unified pipeline for kid-friendly news content.

Uses Claude Agent SDK with MCP tool access for live LLM generation.
Falls back to deterministic text processing when the SDK is unavailable
or in test environments.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from ..api.models import DialogueLine, DialogueScript
from ..mcp_servers import safety_server, tts_server, vector_server
from ..utils.model_config import get_claude_agent_model

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


# ===========================================================================
# Constants & Configuration
# ===========================================================================

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "morning-show.md"
_DEFAULT_GUESTS = ("Professor Owl", "Captain Comet")

# Character display names (#140)
ROLE_DISPLAY_NAMES: Dict[str, Optional[str]] = {
    "curious_kid": "Mimi",
    "fun_expert": "Duo",
    "guest": None,
}

# Age rules for text conversion
AGE_RULES: Dict[str, Dict[str, Any]] = {
    "3-5": {"max_sentences": 2, "max_words": 70, "tone": "warm and very simple"},
    "6-8": {"max_sentences": 3, "max_words": 110, "tone": "simple and curious"},
    "9-12": {
        "max_sentences": 4,
        "max_words": 150,
        "tone": "clear with a bit more detail",
    },
}

# Age config for dialogue generation
_AGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "3-5": {
        "line_count": 6,
        "line_duration": 7.5,
        "question_style": "why",
        "answer_style": "one short sentence",
    },
    "6-8": {
        "line_count": 8,
        "line_duration": 9.0,
        "question_style": "how or what if",
        "answer_style": "simple analogy",
    },
    "9-12": {
        "line_count": 10,
        "line_duration": 10.0,
        "question_style": "but what about",
        "answer_style": "deeper analysis",
    },
}


# ===========================================================================
# Pydantic output models (Structured Output for SDK)
# ===========================================================================


class KidsNewsOutput(BaseModel):
    """Structured output for news-to-kids text conversion."""

    kid_title: str
    kid_content: str
    why_care: str
    key_concepts: List[Dict[str, str]] = []
    interactive_questions: List[Dict[str, str]] = []
    safety_score: float = 0.9


class DialogueLineOutput(BaseModel):
    """A single dialogue line in the SDK output."""

    role: str
    text: str
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0


class DialogueScriptOutput(BaseModel):
    """Structured output for Kids Daily dialogue generation."""

    lines: List[DialogueLineOutput] = []
    total_duration: float = 0.0
    guest_character: str = "Professor Owl"
    safety_score: float = 0.9


# ===========================================================================
# Text Conversion Helpers
# ===========================================================================


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = _normalize(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(" ,.;:") + "..."


def _build_kid_content(news_text: str, age_group: str, category: str) -> str:
    rules = AGE_RULES.get(age_group, AGE_RULES["6-8"])
    sentences = _split_sentences(news_text)

    if not sentences:
        fallback = "There is new information to learn today, and it helps us understand our world better."
        return f"Here is a {category or 'general'} update in a {rules['tone']} style: {fallback}"

    selected = " ".join(sentences[: rules["max_sentences"]])
    selected = _trim_words(selected, rules["max_words"])
    return f"Here is a {category or 'general'} update in a {rules['tone']} style: {selected}"


def _build_why_care(category: str) -> str:
    category_label = (category or "general").replace("_", " ")
    return (
        f"This {category_label} story matters because it can affect everyday life, "
        "helps kids ask thoughtful questions, and builds better understanding of the world around them."
    )


def _build_key_concepts(text: str, max_items: int = 3) -> List[Dict[str, str]]:
    words = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text)
    freq: Dict[str, int] = {}
    for word in words:
        key = word.lower()
        if key in {"this", "that", "with", "from", "have", "were", "their", "about"}:
            continue
        freq[key] = freq.get(key, 0) + 1

    ranked = sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:max_items]
    if not ranked:
        ranked = [("news", 1)]

    return [
        {
            "term": term,
            "explanation": f"{term.capitalize()} is an important idea in this story and helps explain what happened.",
            "emoji": "💡",
        }
        for term, _ in ranked
    ]


def _build_questions(category: str) -> List[Dict[str, str]]:
    label = (category or "general").replace("_", " ")
    return [
        {
            "question": f"What part of this {label} story felt most important to you?",
            "hint": "Pick one detail and explain your reason.",
            "emoji": "🤔",
        },
        {
            "question": "If you could help in this situation, what would you do first?",
            "hint": "Think about a kind and practical action.",
            "emoji": "✨",
        },
    ]


# ===========================================================================
# Audio & SDK guard helpers
# ===========================================================================


def _get_audio_config(age_group: str) -> dict:
    """Get audio configuration for age group."""
    configs = {
        "3-5": {"audio_mode": "audio_first", "voice": "nova", "speed": 0.9},
        "6-8": {"audio_mode": "simultaneous", "voice": "shimmer", "speed": 1.0},
        "9-12": {"audio_mode": "text_first", "voice": "alloy", "speed": 1.1},
    }
    return configs.get(age_group, configs["6-8"])


def _should_use_mock() -> bool:
    """Return True when running inside pytest, SDK unavailable, or force-mock flag set."""
    force_mock = (
        os.getenv("KIDS_DAILY_FORCE_MOCK", os.getenv("MORNING_SHOW_FORCE_MOCK", ""))
        .strip()
        .lower()
    )
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
        or force_mock in {"1", "true", "yes"}
    )


# ===========================================================================
# JSON extraction helpers
# ===========================================================================


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if not cleaned:
        return {}

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_key_concepts(raw: Any, source: str) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return _build_key_concepts(source)

    out: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        if not term or not explanation:
            continue
        emoji = str(item.get("emoji", "💡")).strip() or "💡"
        out.append({"term": term, "explanation": explanation, "emoji": emoji})
    return out or _build_key_concepts(source)


def _normalize_questions(raw: Any, category: str) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return _build_questions(category)

    out: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        hint = item.get("hint")
        normalized_hint = str(hint).strip() if isinstance(hint, str) else None
        emoji = str(item.get("emoji", "🤔")).strip() or "🤔"
        out.append({"question": question, "hint": normalized_hint, "emoji": emoji})
    return out or _build_questions(category)


# ===========================================================================
# Live LLM text conversion via Claude Agent SDK
# ===========================================================================


async def _generate_kids_daily_text_live(
    source: str,
    age_group: str,
    category: str,
    enable_audio: bool = True,
    voice: Optional[str] = None,
    child_id: str = "",
) -> Dict[str, Any]:
    """Generate kid-friendly news content using Claude Agent SDK with MCP safety check."""
    rules = AGE_RULES.get(age_group, AGE_RULES["6-8"])
    age_map = {"3-5": 4, "6-8": 7, "9-12": 11}
    target_age = age_map.get(age_group, 7)

    # Audio configuration
    audio_config = _get_audio_config(age_group)
    should_generate_audio = enable_audio and audio_config["audio_mode"] in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    prompt = (
        "Rewrite the following news text for children.\n"
        f"Age group: {age_group}\n"
        f"Category: {category or 'general'}\n"
        f"Tone: {rules['tone']}\n"
        f"Maximum words for kid_content: {rules['max_words']}\n"
        "Return strict JSON with keys exactly:\n"
        "- kid_title (string)\n"
        "- kid_content (string)\n"
        "- why_care (string)\n"
        "- key_concepts (array of {term, explanation, emoji})\n"
        "- interactive_questions (array of {question, hint, emoji})\n"
        "No markdown, no extra keys.\n\n"
        f"News text:\n{source}\n\n"
        "**Safety check (mandatory)**:\n"
        "After generating the content, you MUST use `mcp__safety-check__check_content_safety` "
        "to verify the content is safe for children, with:\n"
        f"- content_text: the kid_content you generated\n"
        f"- target_age: {target_age}\n"
        '- content_type: "news"\n'
        "If the safety check fails (passed == false), revise the content and re-check. "
        "Include the safety_score in your output.\n"
    )

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        prompt += (
            f"\n**语音生成**：\n"
            f"内容转换完成后，请使用 `mcp__tts-generation__generate_story_audio` 工具为 kid_content 生成语音。\n"
            f"- 语音类型: {actual_voice}\n"
            f"- 语速: {audio_speed}\n"
            f"- 儿童ID: {child_id}\n"
        )

    # Build MCP servers and allowed tools lists
    mcp_servers: Dict[str, Any] = {
        "safety-check": safety_server,
    }
    allowed_tools = [
        "mcp__safety-check__check_content_safety",
        "mcp__safety-check__suggest_content_improvements",
    ]

    if should_generate_audio:
        mcp_servers["tts-generation"] = tts_server
        allowed_tools.append("mcp__tts-generation__generate_story_audio")

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers=mcp_servers,
        allowed_tools=allowed_tools,
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=8,
        output_format={
            "type": "json_schema",
            "schema": KidsNewsOutput.model_json_schema(),
        },
    )

    result_data: Dict[str, Any] = {}
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
                        result_data = _extract_json_object(str(message.result))
                break

    if not result_data:
        raise RuntimeError("Empty model output from Claude Agent SDK")

    # Normalize and validate fields
    kid_title = (
        str(result_data.get("kid_title", "")).strip()
        or f"Kid News: {(category or 'general').title()}"
    )
    kid_content = str(result_data.get("kid_content", "")).strip() or _build_kid_content(
        source, age_group, category
    )
    why_care = str(result_data.get("why_care", "")).strip() or _build_why_care(category)
    key_concepts = _normalize_key_concepts(result_data.get("key_concepts"), source)
    questions = _normalize_questions(result_data.get("interactive_questions"), category)

    kid_content = _trim_words(kid_content, rules["max_words"])

    # Extract safety score from SDK output (safety check was done via MCP tool)
    safety_score = float(result_data.get("safety_score", 0.9))
    safety_score = max(0.0, min(1.0, safety_score))

    # Safety floor enforcement — all content must pass >= 0.85 (CLAUDE.md)
    if safety_score < 0.85:
        raise RuntimeError(
            f"Live news content failed safety check (score={safety_score:.2f})"
        )

    return {
        "kid_title": kid_title,
        "kid_content": kid_content,
        "why_care": why_care,
        "key_concepts": key_concepts,
        "interactive_questions": questions,
        "audio_path": audio_path,
        "safety_score": safety_score,
    }


# ===========================================================================
# Dialogue Helpers
# ===========================================================================


def _age_bucket(age_group: str) -> str:
    if age_group in _AGE_CONFIG:
        return age_group
    return "6-8"


def _target_age(age_group: str) -> int:
    if age_group == "3-5":
        return 4
    if age_group == "6-8":
        return 7
    return 10


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Generate a safe kids morning show dialogue in JSON."


def _clean_source_text(news_text: str, news_url: Optional[str]) -> str:
    text = (news_text or "").strip()
    if text:
        return text
    if news_url:
        return f"Kid update source: {news_url}."
    return "There is an exciting update to explain to kids today."


def _headline_from_text(text: str) -> str:
    snippet = text.strip().split(". ")[0].strip()
    if not snippet:
        snippet = "Today's big discovery"
    if len(snippet) > 90:
        snippet = snippet[:87].rstrip(" ,.;:") + "..."
    return snippet


# ===========================================================================
# Mock dialogue builder (deterministic fallback)
# ===========================================================================


def _build_line_text(
    role: str, topic: str, age_group: str, idx: int, guest_name: str
) -> str:
    bucket = _age_bucket(age_group)

    if role == "curious_kid":
        if bucket == "3-5":
            prompts = [
                f"Mimi: Why is the {topic} news so special?",
                f"Mimi: What happened first in this {topic} story?",
                f"Mimi: Can this help kids like me?",
            ]
        elif bucket in {"6-8"}:
            prompts = [
                f"Mimi: How did this {topic} story begin?",
                f"Mimi: What if we tried this idea at school?",
                f"Mimi: Why does this matter in real life?",
            ]
        else:
            prompts = [
                f"Mimi: But what about the hardest part of this {topic} challenge?",
                "Mimi: How do experts know this will work long-term?",
                "Mimi: What could go wrong, and how can people prepare?",
            ]
        return prompts[idx % len(prompts)]

    if role == "guest":
        return f"{guest_name} says: I can help explain this with a fun example from my own adventures!"

    # fun_expert
    if bucket == "3-5":
        answers = [
            f"Duo: Great question! Think of {topic} like building a tiny helper for our world.",
            "Duo: People worked together carefully, step by step, to keep everyone safe.",
            "Duo: Yes. Small kind actions from kids can make a big difference.",
        ]
    elif bucket in {"6-8"}:
        answers = [
            f"Duo: Imagine {topic} as a team puzzle where each piece solves part of the problem.",
            "Duo: Scientists tested ideas, compared results, and improved the plan.",
            "Duo: It matters because it can shape what we learn, build, and protect next.",
        ]
    else:
        answers = [
            f"Duo: The big idea is that {topic} combines evidence, tradeoffs, and long-term planning.",
            "Duo: Researchers validate with repeated observations and peer review.",
            "Duo: Policy, engineering, and community behavior all affect final outcomes.",
        ]
    return answers[idx % len(answers)]


def _build_mock_dialogue_script(
    topic: str, age_group: str, guest_name: str
) -> DialogueScript:
    config = _AGE_CONFIG[_age_bucket(age_group)]
    line_count = int(config["line_count"])
    line_duration = float(config["line_duration"])

    lines: List[DialogueLine] = []
    current_time = 0.0

    for idx in range(line_count):
        if idx == line_count // 2:
            role = "guest"
        else:
            role = "curious_kid" if idx % 2 == 0 else "fun_expert"

        text = _build_line_text(role, topic, age_group, idx, guest_name)

        start = round(current_time, 2)
        end = round(current_time + line_duration, 2)
        lines.append(
            DialogueLine(
                role=role,
                text=text,
                display_name=ROLE_DISPLAY_NAMES.get(role),
                timestamp_start=start,
                timestamp_end=end,
            )
        )
        current_time = end

    return DialogueScript(
        lines=lines,
        total_duration=round(current_time, 2),
        guest_character=guest_name,
    )


# ===========================================================================
# Live dialogue generation via Claude Agent SDK
# ===========================================================================


async def _generate_dialogue_with_sdk(
    *,
    source_text: str,
    age_group: str,
    guest_name: str,
    child_id: Optional[str],
) -> Tuple[DialogueScript, float]:
    """Generate dialogue via Claude Agent SDK with MCP safety check and vector search.

    Returns (DialogueScript, safety_score) tuple.
    """
    config = _AGE_CONFIG[_age_bucket(age_group)]
    line_count = int(config["line_count"])
    line_duration = float(config["line_duration"])
    target_age_val = _target_age(age_group)

    prompt_template = _load_prompt()
    user_prompt = (
        f"{prompt_template}\n\n"
        "Generate one complete script for the input below.\n"
        f"- age_group: {age_group}\n"
        f"- target_line_count: {line_count}\n"
        f"- target_line_duration_seconds: {line_duration}\n"
        f"- guest_character: {guest_name}\n"
        f"- source_news_text: {source_text}\n\n"
        "Output must be valid JSON and contain only the required keys.\n\n"
    )

    # Add vector search instruction for guest character personalization
    if child_id:
        user_prompt += (
            "**Guest character personalization**:\n"
            "Use `mcp__vector-search__search_similar_drawings` to find recurring characters "
            f"for child_id '{child_id}'. If a recurring character is found, use their name "
            "as the guest_character in the script.\n"
            "Parameters: drawing_description='recurring character for morning show guest anchor', "
            f"child_id='{child_id}', top_k=5\n\n"
        )

    # Add safety check instruction
    user_prompt += (
        "**Safety check (mandatory)**:\n"
        "After generating the dialogue, you MUST use `mcp__safety-check__check_content_safety` "
        "to verify the content is safe for children, with:\n"
        "- content_text: all dialogue lines joined by newlines\n"
        f"- target_age: {target_age_val}\n"
        '- content_type: "kids_daily_dialogue"\n'
        "If the safety check fails (passed == false), revise the content and re-check. "
        "Include the safety_score in your output.\n"
    )

    mcp_servers: Dict[str, Any] = {
        "safety-check": safety_server,
    }
    allowed_tools = [
        "mcp__safety-check__check_content_safety",
        "mcp__safety-check__suggest_content_improvements",
    ]

    # Only include vector-search if we have a child_id for personalization
    if child_id:
        mcp_servers["vector-search"] = vector_server
        allowed_tools.append("mcp__vector-search__search_similar_drawings")

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers=mcp_servers,
        allowed_tools=allowed_tools,
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=10,
        output_format={
            "type": "json_schema",
            "schema": DialogueScriptOutput.model_json_schema(),
        },
    )

    result_data: Dict[str, Any] = {}

    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_prompt)

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                if hasattr(message, "structured_output") and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    if isinstance(message.result, dict):
                        result_data = message.result
                    else:
                        # Try to extract JSON from text result
                        raw_text = str(message.result).strip()
                        try:
                            result_data = json.loads(raw_text)
                        except json.JSONDecodeError:
                            match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
                            if match:
                                result_data = json.loads(match.group(0))
                            else:
                                raise RuntimeError("Model output is not valid JSON")
                break

    if not result_data:
        raise RuntimeError("Empty model output from Claude Agent SDK")

    # Parse and normalize lines
    raw_lines = result_data.get("lines", [])
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RuntimeError("Model output missing lines")

    normalized_lines: List[DialogueLine] = []
    current_time = 0.0
    for idx, item in enumerate(raw_lines):
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip()
        if role not in {"curious_kid", "fun_expert", "guest"}:
            role = "curious_kid" if idx % 2 == 0 else "fun_expert"

        text = str(item.get("text", "")).strip()
        if not text:
            continue

        start_value = item.get("timestamp_start", current_time)
        end_value = item.get("timestamp_end", current_time + line_duration)

        try:
            start = max(float(start_value), current_time)
        except Exception:
            start = current_time

        try:
            end = float(end_value)
        except Exception:
            end = start + line_duration
        if end <= start:
            end = start + line_duration

        normalized_lines.append(
            DialogueLine(
                role=role,
                text=text,
                display_name=ROLE_DISPLAY_NAMES.get(role),
                timestamp_start=round(start, 2),
                timestamp_end=round(end, 2),
            )
        )
        current_time = round(end, 2)

    if not normalized_lines:
        raise RuntimeError("Model output produced no valid dialogue lines")

    # Ensure guest line exists
    if not any(line.role == "guest" for line in normalized_lines):
        midpoint = len(normalized_lines) // 2
        guest_start = normalized_lines[midpoint].timestamp_start
        guest_end = normalized_lines[midpoint].timestamp_end
        actual_guest = (
            str(result_data.get("guest_character") or guest_name).strip() or guest_name
        )
        normalized_lines[midpoint] = DialogueLine(
            role="guest",
            text=f"{actual_guest} joins us with a fun tip: keep being curious and kind!",
            display_name=None,
            timestamp_start=guest_start,
            timestamp_end=guest_end,
        )

    total_duration = max(line.timestamp_end for line in normalized_lines)
    declared_duration = result_data.get("total_duration")
    try:
        total_duration = max(total_duration, float(declared_duration))
    except Exception:
        pass

    actual_guest = (
        str(result_data.get("guest_character") or guest_name).strip() or guest_name
    )

    script = DialogueScript(
        lines=normalized_lines,
        total_duration=round(total_duration, 2),
        guest_character=actual_guest,
    )

    # Extract safety score from SDK structured output
    safety_score = float(result_data.get("safety_score", 0.9))
    safety_score = max(0.0, min(1.0, safety_score))

    try:
        return DialogueScript.model_validate(script.model_dump()), safety_score
    except ValidationError as exc:
        raise RuntimeError(f"Invalid dialogue schema: {exc}") from exc


# ===========================================================================
# Guest anchor resolution
# ===========================================================================


def _default_guest(child_id: Optional[str]) -> str:
    """Pick a deterministic default guest by child_id hash."""
    if not child_id:
        return _DEFAULT_GUESTS[0]
    index = abs(hash(child_id)) % len(_DEFAULT_GUESTS)
    return _DEFAULT_GUESTS[index]


# ===========================================================================
# Public API: Text Conversion
# ===========================================================================


async def generate_kids_daily_text(
    *,
    news_text: str,
    age_group: str,
    child_id: str,
    category: str,
    news_url: Optional[str] = None,
    enable_audio: bool = True,
    voice: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert news article to kid-friendly text content."""
    source = _normalize(news_text)
    if not source and news_url:
        source = f"Article source: {news_url}."

    if not _should_use_mock():
        try:
            result = await _generate_kids_daily_text_live(
                source, age_group, category, enable_audio, voice, child_id
            )
            result["used_mock"] = False
            result["degraded_reason"] = None
            return result
        except Exception as exc:
            degraded_reason = f"live_generation_failed: {exc}"
    else:
        degraded_reason = "mock_environment"

    content = _build_kid_content(source, age_group, category)
    why_care = _build_why_care(category)
    key_concepts = _build_key_concepts(source)
    questions = _build_questions(category)

    return {
        "kid_title": f"Kid News: {(category or 'general').title()}",
        "kid_content": content,
        "why_care": why_care,
        "key_concepts": key_concepts,
        "interactive_questions": questions,
        "audio_path": None,
        "used_mock": True,
        "degraded_reason": degraded_reason,
    }


async def stream_kids_daily_text(
    *,
    news_text: str,
    age_group: str,
    child_id: str,
    category: str,
    news_url: Optional[str] = None,
    enable_audio: bool = True,
    voice: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream text conversion progress events."""
    yield {
        "type": "status",
        "data": {"stage": "started", "message": "Starting conversion"},
    }
    yield {
        "type": "progress",
        "data": {"percent": 25, "message": "Reading source text"},
    }
    yield {"type": "thinking", "data": {"message": "Simplifying article for children"}}

    result = await generate_kids_daily_text(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        category=category,
        news_url=news_url,
        enable_audio=enable_audio,
        voice=voice,
    )
    yield {
        "type": "progress",
        "data": {"percent": 85, "message": "Preparing final result"},
    }
    yield {"type": "result", "data": result}
    yield {"type": "complete", "data": {"message": "Conversion complete"}}


# ===========================================================================
# Public API: Dialogue Generation
# ===========================================================================


async def generate_kids_daily_dialogue(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str] = None,
    news_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate Kids Daily dialogue script with safety metadata."""

    source_text = _clean_source_text(news_text, news_url)
    topic = _headline_from_text(source_text)
    guest_name = _default_guest(child_id)
    used_mock = _should_use_mock()
    degraded_reason: Optional[str] = None

    if used_mock:
        script = _build_mock_dialogue_script(topic, age_group, guest_name)
        safety_score = 0.95  # Deterministic content is pre-vetted
        degraded_reason = "mock_environment"
    else:
        try:
            script, safety_score = await _generate_dialogue_with_sdk(
                source_text=source_text,
                age_group=age_group,
                guest_name=guest_name,
                child_id=child_id,
            )
            used_mock = False
        except Exception as exc:
            script = _build_mock_dialogue_script(topic, age_group, guest_name)
            used_mock = True
            safety_score = 0.95
            degraded_reason = f"live_generation_failed: {exc}"

    # Safety hard floor — if below 0.85, fall back to deterministic content
    if safety_score < 0.85:
        script = _build_mock_dialogue_script(topic, age_group, guest_name)
        safety_score = 0.95
        used_mock = True
        degraded_reason = "safety_score_below_threshold"

    return {
        "dialogue_script": script.model_dump(),
        "safety_score": round(safety_score, 3),
        "used_mock": used_mock,
        "degraded_reason": degraded_reason,
        "guest_character": script.guest_character or guest_name,
        "role_display_names": dict(ROLE_DISPLAY_NAMES),
    }


# ===========================================================================
# Public API: Full Episode (text + dialogue)
# ===========================================================================


async def generate_kids_daily_episode(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str],
    category: str,
    news_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose kid summary + dialogue script payload for Kids Daily."""

    base = await generate_kids_daily_text(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id or "kids_daily_child",
        category=category,
        news_url=news_url,
        enable_audio=False,
        voice=None,
    )

    dialogue_data = await generate_kids_daily_dialogue(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        news_url=news_url,
    )

    return {
        "kid_title": base.get("kid_title", "Kids Daily"),
        "kid_content": base.get("kid_content", ""),
        "why_care": base.get("why_care", ""),
        "key_concepts": base.get("key_concepts", []),
        "interactive_questions": base.get("interactive_questions", []),
        "dialogue_script": dialogue_data["dialogue_script"],
        "safety_score": dialogue_data["safety_score"],
        "used_mock": dialogue_data["used_mock"],
        "degraded_reason": dialogue_data.get("degraded_reason"),
        "guest_character": dialogue_data["guest_character"],
    }


async def stream_kids_daily_generation(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str],
    category: str,
    news_url: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream Kids Daily generation progress events."""

    yield {
        "type": "status",
        "data": {"stage": "started", "message": "Starting Kids Daily generation"},
    }
    yield {
        "type": "progress",
        "data": {"percent": 25, "message": "Simplifying news for kids"},
    }
    yield {
        "type": "progress",
        "data": {"percent": 55, "message": "Generating dialogue script"},
    }

    result = await generate_kids_daily_episode(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        category=category,
        news_url=news_url,
    )

    yield {
        "type": "progress",
        "data": {"percent": 85, "message": "Validating safety and metadata"},
    }
    yield {"type": "result", "data": result}
    yield {"type": "complete", "data": {"message": "Kids Daily generation complete"}}


# ===========================================================================
# Voice helper (shared with TTS orchestration)
# ===========================================================================


def pick_age_voice(role: str, age_group: str) -> Tuple[str, float]:
    """Shared voice map helper for TTS orchestration."""
    bucket = _age_bucket(age_group)
    table = {
        "3-5": {
            "curious_kid": ("nova", 0.9),
            "fun_expert": ("shimmer", 0.9),
            "guest": ("alloy", 0.9),
        },
        "6-8": {
            "curious_kid": ("shimmer", 1.0),
            "fun_expert": ("fable", 1.0),
            "guest": ("alloy", 1.0),
        },
        "9-12": {
            "curious_kid": ("echo", 1.1),
            "fun_expert": ("fable", 1.1),
            "guest": ("alloy", 1.1),
        },
    }
    mapping = table.get(bucket, table["6-8"])
    return mapping.get(role, ("alloy", 1.0))


__all__ = [
    "generate_kids_daily_text",
    "stream_kids_daily_text",
    "generate_kids_daily_dialogue",
    "generate_kids_daily_episode",
    "stream_kids_daily_generation",
    "pick_age_voice",
    "ROLE_DISPLAY_NAMES",
]
