"""News-to-kids conversion agent.

Uses Claude Agent SDK with MCP tool access for live LLM generation.
Falls back to deterministic text processing when the SDK is unavailable
or in test environments.
"""

import json
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

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

from ..mcp_servers import safety_server, tts_server


# ---------------------------------------------------------------------------
# Pydantic output model (Structured Output)
# ---------------------------------------------------------------------------

class KidsNewsOutput(BaseModel):
    """Structured output for news-to-kids conversion."""
    kid_title: str
    kid_content: str
    why_care: str
    key_concepts: List[Dict[str, str]] = []
    interactive_questions: List[Dict[str, str]] = []
    safety_score: float = 0.9


# ---------------------------------------------------------------------------
# Age rules & helpers
# ---------------------------------------------------------------------------

AGE_RULES: Dict[str, Dict[str, Any]] = {
    "3-5": {"max_sentences": 2, "max_words": 70, "tone": "warm and very simple"},
    "6-8": {"max_sentences": 3, "max_words": 110, "tone": "simple and curious"},
    "9-12": {"max_sentences": 4, "max_words": 150, "tone": "clear with a bit more detail"},
}


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


# ---------------------------------------------------------------------------
# SDK mock guard
# ---------------------------------------------------------------------------

def _get_audio_config(age_group: str) -> dict:
    """Get audio configuration for age group."""
    configs = {
        "3-5": {"audio_mode": "audio_first", "voice": "nova", "speed": 0.9},
        "6-8": {"audio_mode": "simultaneous", "voice": "shimmer", "speed": 1.0},
        "9-12": {"audio_mode": "text_first", "voice": "alloy", "speed": 1.1},
    }
    return configs.get(age_group, configs["6-8"])


def _should_use_mock() -> bool:
    """Return True when running inside pytest or when the SDK is unavailable."""
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Live LLM generation via Claude Agent SDK
# ---------------------------------------------------------------------------

async def _convert_news_to_kids_live(
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
    should_generate_audio = enable_audio and audio_config["audio_mode"] in ["audio_first", "simultaneous"]
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
        "- content_type: \"news\"\n"
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
    kid_title = str(result_data.get("kid_title", "")).strip() or f"Kid News: {(category or 'general').title()}"
    kid_content = str(result_data.get("kid_content", "")).strip() or _build_kid_content(source, age_group, category)
    why_care = str(result_data.get("why_care", "")).strip() or _build_why_care(category)
    key_concepts = _normalize_key_concepts(result_data.get("key_concepts"), source)
    questions = _normalize_questions(result_data.get("interactive_questions"), category)

    kid_content = _trim_words(kid_content, rules["max_words"])

    # Extract safety score from SDK output (safety check was done via MCP tool)
    safety_score = float(result_data.get("safety_score", 0.9))
    safety_score = max(0.0, min(1.0, safety_score))

    # Safety floor enforcement — all content must pass >= 0.85 (CLAUDE.md)
    if safety_score < 0.85:
        raise RuntimeError(f"Live news content failed safety check (score={safety_score:.2f})")

    return {
        "kid_title": kid_title,
        "kid_content": kid_content,
        "why_care": why_care,
        "key_concepts": key_concepts,
        "interactive_questions": questions,
        "audio_path": audio_path,
        "safety_score": safety_score,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def convert_news_to_kids(
    *,
    news_text: str,
    age_group: str,
    child_id: str,
    category: str,
    news_url: Optional[str] = None,
    enable_audio: bool = True,
    voice: Optional[str] = None,
) -> Dict[str, Any]:
    source = _normalize(news_text)
    if not source and news_url:
        source = f"Article source: {news_url}."

    if not _should_use_mock():
        try:
            return await _convert_news_to_kids_live(
                source, age_group, category, enable_audio, voice, child_id
            )
        except Exception:
            pass

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
    }


async def stream_news_to_kids(
    *,
    news_text: str,
    age_group: str,
    child_id: str,
    category: str,
    news_url: Optional[str] = None,
    enable_audio: bool = True,
    voice: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    yield {"type": "status", "data": {"stage": "started", "message": "Starting conversion"}}
    yield {"type": "progress", "data": {"percent": 25, "message": "Reading source text"}}
    yield {"type": "thinking", "data": {"message": "Simplifying article for children"}}

    result = await convert_news_to_kids(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        category=category,
        news_url=news_url,
        enable_audio=enable_audio,
        voice=voice,
    )
    yield {"type": "progress", "data": {"percent": 85, "message": "Preparing final result"}}
    yield {"type": "result", "data": result}
    yield {"type": "complete", "data": {"message": "Conversion complete"}}
