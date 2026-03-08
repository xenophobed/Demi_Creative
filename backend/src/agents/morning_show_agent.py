"""Morning Show dialogue agent (#90).

Transforms news content into a dual-character (plus optional guest) dialogue script.
Uses Claude Agent SDK with MCP tool access for live generation.
Includes a deterministic mock fallback when the SDK is unavailable.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from ..api.models import DialogueLine, DialogueScript
from ..mcp_servers import safety_server, vector_server
from .news_to_kids_agent import convert_news_to_kids

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


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "morning-show.md"
_DEFAULT_GUESTS = ("Professor Owl", "Captain Comet")

_AGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "3-5": {"line_count": 6, "line_duration": 7.5, "question_style": "why", "answer_style": "one short sentence"},
    "6-8": {"line_count": 8, "line_duration": 9.0, "question_style": "how or what if", "answer_style": "simple analogy"},
    "9-12": {"line_count": 10, "line_duration": 10.0, "question_style": "but what about", "answer_style": "deeper analysis"},
}


# ---------------------------------------------------------------------------
# Pydantic output model (Structured Output)
# ---------------------------------------------------------------------------

class DialogueLineOutput(BaseModel):
    """A single dialogue line in the SDK output."""
    role: str
    text: str
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0


class DialogueScriptOutput(BaseModel):
    """Structured output for Morning Show dialogue generation."""
    lines: List[DialogueLineOutput] = []
    total_duration: float = 0.0
    guest_character: str = "Professor Owl"
    safety_score: float = 0.9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _should_use_mock() -> bool:
    """Return True when running inside pytest or when the SDK is unavailable."""
    return (
        ClaudeSDKClient is None
        or ClaudeAgentOptions is None
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


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


# ---------------------------------------------------------------------------
# Mock dialogue builder (deterministic fallback)
# ---------------------------------------------------------------------------

def _build_line_text(role: str, topic: str, age_group: str, idx: int, guest_name: str) -> str:
    bucket = _age_bucket(age_group)

    if role == "curious_kid":
        if bucket == "3-5":
            prompts = [
                f"Why is the {topic} news so special?",
                f"What happened first in this {topic} story?",
                f"Can this help kids like me?",
            ]
        elif bucket in {"6-8"}:
            prompts = [
                f"How did this {topic} story begin?",
                f"What if we tried this idea at school?",
                f"Why does this matter in real life?",
            ]
        else:
            prompts = [
                f"But what about the hardest part of this {topic} challenge?",
                "How do experts know this will work long-term?",
                "What could go wrong, and how can people prepare?",
            ]
        return prompts[idx % len(prompts)]

    if role == "guest":
        return f"{guest_name} says: I can help explain this with a fun example from my own adventures!"

    # fun_expert
    if bucket == "3-5":
        answers = [
            f"Great question! Think of {topic} like building a tiny helper for our world.",
            "People worked together carefully, step by step, to keep everyone safe.",
            "Yes. Small kind actions from kids can make a big difference.",
        ]
    elif bucket in {"6-8"}:
        answers = [
            f"Imagine {topic} as a team puzzle where each piece solves part of the problem.",
            "Scientists tested ideas, compared results, and improved the plan.",
            "It matters because it can shape what we learn, build, and protect next.",
        ]
    else:
        answers = [
            f"The big idea is that {topic} combines evidence, tradeoffs, and long-term planning.",
            "Researchers validate with repeated observations and peer review.",
            "Policy, engineering, and community behavior all affect final outcomes.",
        ]
    return answers[idx % len(answers)]


def _build_mock_dialogue_script(topic: str, age_group: str, guest_name: str) -> DialogueScript:
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


# ---------------------------------------------------------------------------
# Live generation via Claude Agent SDK
# ---------------------------------------------------------------------------

async def _generate_with_sdk(
    *,
    source_text: str,
    age_group: str,
    guest_name: str,
    child_id: Optional[str],
) -> Tuple[DialogueScript, float]:
    """Generate dialogue via Claude Agent SDK with MCP safety check and vector search.

    Returns (DialogueScript, safety_score) tuple. The safety_score is extracted
    from the SDK structured output rather than hardcoded (#135).
    """
    config = _AGE_CONFIG[_age_bucket(age_group)]
    line_count = int(config["line_count"])
    line_duration = float(config["line_duration"])
    target_age = _target_age(age_group)

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
        f"- target_age: {target_age}\n"
        "- content_type: \"morning_show_dialogue\"\n"
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
        actual_guest = str(result_data.get("guest_character") or guest_name).strip() or guest_name
        normalized_lines[midpoint] = DialogueLine(
            role="guest",
            text=f"{actual_guest} joins us with a fun tip: keep being curious and kind!",
            timestamp_start=guest_start,
            timestamp_end=guest_end,
        )

    total_duration = max(line.timestamp_end for line in normalized_lines)
    declared_duration = result_data.get("total_duration")
    try:
        total_duration = max(total_duration, float(declared_duration))
    except Exception:
        pass

    actual_guest = str(result_data.get("guest_character") or guest_name).strip() or guest_name

    script = DialogueScript(
        lines=normalized_lines,
        total_duration=round(total_duration, 2),
        guest_character=actual_guest,
    )

    # Extract safety score from SDK structured output (#135)
    safety_score = float(result_data.get("safety_score", 0.9))
    safety_score = max(0.0, min(1.0, safety_score))

    try:
        return DialogueScript.model_validate(script.model_dump()), safety_score
    except ValidationError as exc:
        raise RuntimeError(f"Invalid dialogue schema: {exc}") from exc


# ---------------------------------------------------------------------------
# Guest anchor resolution (deterministic fallback when SDK is unavailable)
# ---------------------------------------------------------------------------

def _default_guest(child_id: Optional[str]) -> str:
    """Pick a deterministic default guest by child_id hash."""
    if not child_id:
        return _DEFAULT_GUESTS[0]
    index = abs(hash(child_id)) % len(_DEFAULT_GUESTS)
    return _DEFAULT_GUESTS[index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_morning_show_dialogue(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str] = None,
    news_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate Morning Show dialogue script with safety metadata."""

    source_text = _clean_source_text(news_text, news_url)
    topic = _headline_from_text(source_text)
    guest_name = _default_guest(child_id)
    used_mock = _should_use_mock()

    if used_mock:
        script = _build_mock_dialogue_script(topic, age_group, guest_name)
        safety_score = 0.95  # Deterministic content is pre-vetted
    else:
        try:
            script, safety_score = await _generate_with_sdk(
                source_text=source_text,
                age_group=age_group,
                guest_name=guest_name,
                child_id=child_id,
            )
            used_mock = False
        except Exception:
            script = _build_mock_dialogue_script(topic, age_group, guest_name)
            used_mock = True
            safety_score = 0.95

    # Safety hard floor — if below 0.85, fall back to deterministic content
    if safety_score < 0.85:
        script = _build_mock_dialogue_script(topic, age_group, guest_name)
        safety_score = 0.95
        used_mock = True

    return {
        "dialogue_script": script.model_dump(),
        "safety_score": round(safety_score, 3),
        "used_mock": used_mock,
        "guest_character": script.guest_character or guest_name,
    }


async def convert_news_to_morning_show(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str],
    category: str,
    news_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose kid summary + dialogue script payload for Morning Show."""

    base = await convert_news_to_kids(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id or "morning_show_child",
        category=category,
        news_url=news_url,
        enable_audio=False,
        voice=None,
    )

    dialogue_data = await generate_morning_show_dialogue(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        news_url=news_url,
    )

    return {
        "kid_title": base.get("kid_title", "Morning Show"),
        "kid_content": base.get("kid_content", ""),
        "why_care": base.get("why_care", ""),
        "key_concepts": base.get("key_concepts", []),
        "interactive_questions": base.get("interactive_questions", []),
        "dialogue_script": dialogue_data["dialogue_script"],
        "safety_score": dialogue_data["safety_score"],
        "used_mock": dialogue_data["used_mock"],
        "guest_character": dialogue_data["guest_character"],
    }


async def stream_morning_show_generation(
    *,
    news_text: str,
    age_group: str,
    child_id: Optional[str],
    category: str,
    news_url: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream Morning Show generation progress events."""

    yield {"type": "status", "data": {"stage": "started", "message": "Starting Morning Show generation"}}
    yield {"type": "progress", "data": {"percent": 25, "message": "Simplifying news for kids"}}
    yield {"type": "progress", "data": {"percent": 55, "message": "Generating dialogue script"}}

    result = await convert_news_to_morning_show(
        news_text=news_text,
        age_group=age_group,
        child_id=child_id,
        category=category,
        news_url=news_url,
    )

    yield {"type": "progress", "data": {"percent": 85, "message": "Validating safety and metadata"}}
    yield {"type": "result", "data": result}
    yield {"type": "complete", "data": {"message": "Morning Show generation complete"}}


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
    "convert_news_to_morning_show",
    "generate_morning_show_dialogue",
    "stream_morning_show_generation",
    "pick_age_voice",
]
