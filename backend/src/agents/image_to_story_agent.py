"""
Image to Story Agent

Uses Claude Agent SDK to transform children's drawings into personalized stories.
Supports streaming responses to reduce timeouts and improve user experience.
"""

import json
import inspect
import os
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional

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


import logging

from ..utils.model_config import get_claude_agent_model
from ..utils.text import count_words

logger = logging.getLogger(__name__)


# ============================================================================
# Story length validation per age group (#233)
# ============================================================================

AGE_GROUP_WORD_RANGES = {
    "3-5": (100, 200),
    "6-8": (200, 400),
    "9-12": (400, 800),
}


def validate_story_length(story_text: str, age_group: str) -> dict:
    """Validate story word count against age-group range.

    Returns a dict with:
      - word_count: int
      - in_range: bool (within min..max)
      - degraded_length: bool (out of range)
      - needs_retry: bool (drastically out of range: <50% min or >150% max)
    """
    word_count = count_words(story_text)
    min_words, max_words = AGE_GROUP_WORD_RANGES.get(age_group, (200, 400))

    in_range = min_words <= word_count <= max_words
    drastically_short = word_count < min_words * 0.5
    drastically_long = word_count > max_words * 1.5

    needs_retry = drastically_short or drastically_long
    degraded_length = not in_range

    if degraded_length:
        logger.warning(
            "Story length out of range for age group %s: %d words (expected %d-%d)%s",
            age_group,
            word_count,
            min_words,
            max_words,
            " — needs retry" if needs_retry else "",
        )

    return {
        "word_count": word_count,
        "in_range": in_range,
        "degraded_length": degraded_length,
        "needs_retry": needs_retry,
    }


def _ensure_terminal_punctuation(text: str) -> str:
    """Finish repaired English prose with sentence punctuation."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if cleaned[-1] not in ".!?":
        return f"{cleaned}."
    return cleaned


def _trim_story_to_max_words(story_text: str, min_words: int, max_words: int) -> str:
    """Trim an over-long story while preferring a sentence boundary."""
    words = story_text.split()
    if len(words) <= max_words:
        return _ensure_terminal_punctuation(story_text)

    candidate = " ".join(words[:max_words]).strip()
    sentence_end = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_end > 0:
        sentence_candidate = candidate[: sentence_end + 1].strip()
        if count_words(sentence_candidate) >= min_words:
            return sentence_candidate
    return _ensure_terminal_punctuation(candidate)


def repair_story_length(story_text: str, age_group: str) -> tuple[str, dict]:
    """Repair story text so it fits the age-group word-count contract.

    This is a delivery-time guardrail for occasional model drift. It trims
    over-long stories and adds simple, age-neutral closing beats to short
    stories, then returns the repaired text plus fresh validation metadata.
    """
    min_words, max_words = AGE_GROUP_WORD_RANGES.get(
        age_group, AGE_GROUP_WORD_RANGES["6-8"]
    )
    length_info = validate_story_length(story_text, age_group)
    if length_info["in_range"]:
        return story_text, {**length_info, "repaired": False}

    if length_info["word_count"] > max_words:
        repaired = _trim_story_to_max_words(story_text, min_words, max_words)
    else:
        repaired = _ensure_terminal_punctuation(story_text)
        if not repaired:
            repaired = "Once upon a time, a child's drawing opened a bright little doorway to a kind adventure."

        expansion_sentences = [
            "The hero looked closely at the colors in the picture and noticed one more clue waiting to be discovered.",
            "With a brave smile, the friends worked together, listened to each other, and found a gentle way forward.",
            "Every shape in the drawing seemed to help, from the smallest dot to the tallest line.",
            "By the end of the adventure, the hero felt proud, curious, and ready to create something new.",
            "The picture stayed special because it reminded everyone that imagination can turn simple marks into a whole world.",
        ]
        index = 0
        while count_words(repaired) < min_words:
            repaired = f"{repaired} {expansion_sentences[index % len(expansion_sentences)]}"
            index += 1
            if count_words(repaired) > max_words:
                repaired = _trim_story_to_max_words(repaired, min_words, max_words)
                break

    repaired_info = validate_story_length(repaired, age_group)
    return repaired, {**repaired_info, "repaired": True}


from ..mcp_servers import (
    analyze_children_drawing,
    check_content_safety,
    generate_story_audio,
    image_style_server,
    safety_server,
    search_similar_stories,
    transform_art_style,
    tts_server,
    vector_server,
    vision_server,
)
from ..services.story_memory import get_story_memory_prompt
from ..services.my_agent_context import build_my_agent_context
from ._safety import enforce_post_gen_safety


def _age_group_from_int(age: int) -> str:
    """Map an integer child age to the canonical 3-band age group used
    by the safety helper. Mirrors logic in `kids_daily_agent`."""

    if age <= 5:
        return "3-5"
    if age <= 8:
        return "6-8"
    return "9-12"


async def _search_story_dedup(
    child_id: str, description: str, threshold: float = 0.9
) -> str:
    """Search for similar past stories and return a variation nudge if duplicates found.

    Returns an empty string if no similar stories are found or if the search
    fails (best-effort — never blocks generation). (#290)
    """
    if not child_id or not description:
        return ""
    try:
        result = await _call_mcp_tool(
            search_similar_stories,
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
The child has heard similar stories before. Here are summaries of past stories with high similarity:
{summaries}
Please create a FRESH, DIFFERENT story with a new angle, different plot structure, and different character dynamics. Avoid repeating the same themes and conclusions.
"""
    except Exception:
        return ""  # Best-effort: proceed without dedup


async def _call_mcp_tool(tool_ref: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke an MCP tool, unwrapping SDK tool objects when needed.

    claude_agent_sdk's @tool decorator returns an SdkMcpTool wrapper with a
    `.handler` coroutine instead of a directly-callable async function.
    The direct production pipeline must support both shapes.
    """
    handler = getattr(tool_ref, "handler", tool_ref)
    result = handler(args)
    if inspect.isawaitable(result):
        return await result
    return result


def _should_use_mock() -> bool:
    """Return True in pytest, or when force-mock is enabled in test env only."""
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True

    force_mock = os.getenv("IMAGE_TO_STORY_FORCE_MOCK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not force_mock:
        return False

    env_name = os.getenv("ENVIRONMENT", "").strip().lower()
    if env_name == "test":
        return True

    logger.warning(
        "Ignoring IMAGE_TO_STORY_FORCE_MOCK outside test environment (ENVIRONMENT=%s)",
        env_name or "unset",
    )
    return False


def _runtime_unavailable_reason() -> Optional[str]:
    """Return a human-readable reason when image-to-story runtime is unavailable."""
    missing: List[str] = []
    if ClaudeSDKClient is None:
        missing.append("ClaudeSDKClient")
    if ClaudeAgentOptions is None:
        missing.append("ClaudeAgentOptions")
    if missing:
        return (
            "Image-to-story runtime unavailable: claude-agent-sdk import incomplete "
            f"(missing: {', '.join(missing)}). Install backend dependencies from "
            "requirements.txt (not requirements_minimal.txt)."
        )
    return None


def _cli_available() -> bool:
    """Check if the Claude Code CLI binary is available (required by ClaudeSDKClient)."""
    import shutil
    if shutil.which("claude"):
        return True
    # Check bundled path
    try:
        import claude_agent_sdk
        bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
        if bundled.exists() and bundled.is_file():
            return True
    except Exception:
        pass
    return False


def _mock_image_to_story_result(
    interests: list[str], art_theme: str = None
) -> Dict[str, Any]:
    """Deterministic mock result for test environments.

    The story text is sized for the 6-8 age group (200-400 words) so that
    post-generation length validation passes without a retry.
    """
    topic = interests[0] if interests else "adventure"
    # ~210 words — comfortably inside the 6-8 range and above the 3-5 minimum
    story = (
        f"Once upon a time, a child drew a beautiful picture about {topic}. "
        "The drawing came to life and took the child on a wonderful journey "
        "through a magical land filled with colorful flowers and friendly animals. "
        "The child met a talking rabbit who loved to paint and a wise old owl "
        "who knew every story ever told. Together they explored a forest where "
        "the trees whispered secrets and the rivers sang gentle songs. "
        "The rabbit showed the child how to mix colors to make new ones, "
        "and the owl told tales of brave adventurers from long ago. "
        "As the sun began to set, the sky turned orange and pink, "
        "and the child realized it was time to go home. "
        "But the magical friends promised they would always be there, "
        "waiting inside the drawing whenever the child wanted to visit again. "
        "The child smiled and waved goodbye, feeling happy and inspired. "
        "Back at home, the child picked up the crayons once more "
        "and started a brand new drawing, imagining all the wonderful places "
        "they would visit next time. Every line and color held a promise "
        "of another adventure waiting to unfold. The child knew that "
        "creativity was the key to unlocking endless worlds of wonder. "
        "And so the story continued, one drawing at a time, "
        "each picture opening a door to a new and exciting journey "
        "that only the imagination could create. The end."
    )
    return {
        "story": story,
        "themes": [topic, "creativity"],
        "concepts": ["imagination", "art"],
        "moral": "Every drawing tells a story.",
        "characters": [
            {
                "name": "Little Artist",
                "description": "A creative child",
                "appearances": 1,
            },
        ],
        "analysis": {"objects": ["drawing"], "colors": ["blue", "green"]},
        "safety_score": 0.95,
        "audio_path": None,
        "styled_image_path": f"data/styled/mock_{art_theme}.jpg" if art_theme else None,
    }


# ============================================================================
# Pydantic model definitions (for Structured Output)
# ============================================================================


class Character(BaseModel):
    """A character in the story"""

    name: str
    description: str
    appearances: int = 1


class StoryOutput(BaseModel):
    """Structured output for story generation"""

    story: str
    themes: List[str] = []
    concepts: List[str] = []
    moral: Optional[str] = None
    characters: List[Character] = []
    analysis: Dict[str, Any] = {}
    safety_score: float = 0.9
    audio_url: Optional[str] = None


# ============================================================================
# Agent functions
# ============================================================================


def _get_age_group_from_age(age: int) -> str:
    """Convert age to canonical age group string (PRD §2.1)."""
    if age <= 5:
        return "3-5"
    elif age <= 8:
        return "6-8"
    else:
        return "9-12"


def _get_audio_config(age_group: str) -> dict:
    """Get audio configuration for age group."""
    configs = {
        "3-5": {"audio_mode": "audio_first", "voice": "nova", "speed": 0.9},
        "6-8": {"audio_mode": "simultaneous", "voice": "shimmer", "speed": 1.0},
        "9-12": {"audio_mode": "text_first", "voice": "alloy", "speed": 1.1},
    }
    return configs.get(age_group, configs["6-8"])


def _get_story_length_range(age_group: str) -> tuple[int, int]:
    """Return target word range for the given age group."""
    return AGE_GROUP_WORD_RANGES.get(age_group, AGE_GROUP_WORD_RANGES["6-8"])


async def image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None,
    enable_audio: bool = True,
    voice: str = None,
    art_theme: str = None,
    user_id: str = "",
    provider: str = None,
) -> Dict[str, Any]:
    """
    Transform a child's drawing into a personalized story

    Args:
        image_path: Path to the drawing image
        child_id: Child ID
        child_age: Child's age (3-12)
        interests: List of child's interest tags
        enable_audio: Whether to generate audio
        voice: Voice type (optional, defaults based on age group)
        art_theme: Art style theme (optional, e.g. "cartoon", "watercolor")

    Returns:
        Dictionary containing story, audio, and other information
    """
    if _should_use_mock():
        return _mock_image_to_story_result(interests or [], art_theme=art_theme)
    runtime_issue = _runtime_unavailable_reason()
    if runtime_issue:
        raise RuntimeError(runtime_issue)

    # Direct Anthropic API pipeline — no subprocess, no OOM risk (#417)
    logger.info("Using direct API pipeline for image-to-story (non-streaming)")
    result = {}
    async for event in _direct_stream_image_to_story(
        image_path=image_path,
        child_id=child_id,
        child_age=child_age,
        interests=interests,
        enable_audio=enable_audio,
        voice=voice,
        art_theme=art_theme,
        user_id=user_id,
        provider=provider,
    ):
        if event.get("type") == "result":
            result = event.get("data", {})
        elif event.get("type") == "error":
            raise RuntimeError(event["data"].get("message", "Story generation failed"))
    return result


# ---------------------------------------------------------------------------
# Legacy SDK path (non-streaming) — kept for reference but no longer called.
# The ClaudeSDKClient subprocess approach caused OOM kills on Railway (#416).
# ---------------------------------------------------------------------------
def _legacy_sdk_note():
    """Marker: code below this point was the ClaudeSDKClient non-streaming path.
    It is retained in the file for reference but is never executed.
    The direct API path above is the active code path."""
    pass  # pragma: no cover


async def _legacy_image_to_story_sdk(  # pragma: no cover
    image_path, child_id, child_age, interests, enable_audio, voice, art_theme, user_id, provider,
):
    """Legacy SDK path — not called in production. See _direct_stream_image_to_story instead."""
    # Validate input
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if not 3 <= child_age <= 12:
        raise ValueError("Child age must be between 3 and 12")

    interests_str = ", ".join(interests) if interests else "not specified"

    # Get age-based audio config
    age_group = _get_age_group_from_age(child_age)
    min_words, max_words = _get_story_length_range(age_group)
    audio_config = _get_audio_config(age_group)
    audio_mode = audio_config["audio_mode"]
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    # Build story memory section for cross-story references (#165)
    story_memory_section = ""
    try:
        story_memory_section = await get_story_memory_prompt(child_id, user_id=user_id)
    except Exception:
        pass  # Non-critical

    # Story dedup check (#290): search for similar past stories
    dedup_nudge = ""
    try:
        dedup_nudge = await _search_story_dedup(child_id, interests_str)
    except Exception:
        pass  # Best-effort

    # Build prompt
    prompt = f"""Please create a story suitable for a {child_age}-year-old child based on this children's drawing.

**Task Information**:
- Drawing path: {image_path}
- Child ID: {child_id}
- Child age: {child_age} years old
- Interests: {interests_str}
{story_memory_section}{dedup_nudge}
**Requirements**:
1. First, use the `mcp__vision-analysis__analyze_children_drawing` tool to analyze the drawing
2. Use the `mcp__vector-search__search_similar_drawings` tool to search for this child's previous similar drawings to maintain character and story continuity
3. Based on the analysis results, create a warm, educational story
4. Story length should be approximately {min_words}-{max_words} words
5. Language should be appropriate for a {child_age}-year-old child
6. **Important**: After the story is created, use the `mcp__vector-search__store_drawing_embedding` tool to store the drawing in the vector database with the following parameters:
   - drawing_description: Text description of the drawing (from the analysis results)
   - child_id: {child_id}
   - drawing_analysis: Drawing analysis results (including objects, scene, mood, colors, recurring_characters)
   - story_text: The generated story text
   - image_path: {image_path}

Please create a story based on the drawing content, and extract themes, concepts, and moral lessons.

**Safety Check (Mandatory)**:
After the story is created, you **must** use the `mcp__safety-check__check_content_safety` tool to check the story content safety with the following parameters:
- content_text: The generated story text
- target_age: {child_age}
- content_type: "story"
If the safety check fails (passed == false), you **must** use the `mcp__safety-check__suggest_content_improvements` tool to improve the content, then re-check, up to 3 retries.
Only proceed to the next steps after the safety check passes.

Always respond in English.
"""

    # Add style transfer instruction if art_theme is specified
    if art_theme and art_theme != "none":
        prompt += f"""
**Art Style Transfer**:
After analyzing the drawing and before creating the story, use the `mcp__image-style__transform_art_style` tool to transform the drawing into "{art_theme}" style. Parameters:
- image_path: {image_path}
- theme: {art_theme}
- child_age: {child_age}
- session_id: {child_id}

The transformed image will serve as the story cover. Please consider this art style in the story creation, matching the story's tone and atmosphere to the style.
If the style transfer fails, continue using the original drawing.
"""

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        provider_line = f"\n- Provider: {provider}" if provider else ""
        prompt += f"""
**Audio Generation**:
After the story is created, use the `mcp__tts-generation__generate_story_audio` tool to generate audio narration for the story text.
- Voice type: {actual_voice}
- Speed: {audio_speed}
- Child ID: {child_id}{provider_line}
"""

    # Configure Agent options (using Structured Output)
    mcp_servers = {
        "vision-analysis": vision_server,
        "vector-search": vector_server,
        "safety-check": safety_server,
        "tts-generation": tts_server,
    }

    allowed_tools = [
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
    ]

    if art_theme and art_theme != "none":
        mcp_servers["image-style"] = image_style_server
        allowed_tools.append("mcp__image-style__transform_art_style")

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers=mcp_servers,
        allowed_tools=allowed_tools,
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=15,  # Increase turns to accommodate more tool calls
        # Use Structured Output
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema(),
        },
    )

    # Use ClaudeSDKClient to invoke the Agent
    result_data = {}
    audio_path = None
    styled_image_path = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            # Check for TTS tool results in assistant messages
            if isinstance(message, AssistantMessage):
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            # Try to extract audio/styled image path from tool result
                            result_content = getattr(block, "content", None)
                            result_text = None
                            if isinstance(result_content, str):
                                result_text = result_content
                            elif isinstance(result_content, list):
                                for item in result_content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type") == "text"
                                    ):
                                        result_text = item.get("text")
                                        break
                                    text_val = getattr(item, "text", None)
                                    if text_val:
                                        result_text = text_val
                                        break
                            if result_text:
                                try:
                                    result_json = json.loads(result_text)
                                    if "audio_path" in result_json:
                                        audio_path = result_json["audio_path"]
                                    if "styled_image_path" in result_json:
                                        styled_image_path = result_json[
                                            "styled_image_path"
                                        ]
                                except (json.JSONDecodeError, TypeError):
                                    pass

            if isinstance(message, ResultMessage):
                # Use structured_output to get structured results
                if hasattr(message, "structured_output") and message.structured_output:
                    result_data = message.structured_output
                elif message.result:
                    # Fallback: if no structured_output, try parsing result
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
                            "safety_score": 0.9,
                        }
                break

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Add styled image path to result if available
    if styled_image_path:
        result_data["styled_image_path"] = styled_image_path

    return result_data


# ============================================================================
# Direct API fallback (when Claude CLI is not available, e.g. Railway)
# ============================================================================


async def _direct_stream_image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None,
    enable_audio: bool = True,
    voice: str = None,
    art_theme: str = None,
    user_id: str = "",
    provider: str = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Direct API pipeline — bypasses Claude Agent SDK, calls MCP tools directly.

    Used in production (Railway) where the Claude Code CLI binary is not installed.
    Replicates the same SSE event sequence as the SDK-based streaming path.
    """
    from anthropic import AsyncAnthropic

    interests_str = ", ".join(interests) if interests else "not specified"
    age_group = _get_age_group_from_age(child_age)
    min_words, max_words = _get_story_length_range(age_group)
    audio_config = _get_audio_config(age_group)
    audio_mode = audio_config["audio_mode"]
    should_generate_audio = enable_audio and audio_mode in ["audio_first", "simultaneous"]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    yield {"type": "status", "data": {"status": "started", "message": "Analyzing drawing..."}}

    # Step 1: Vision analysis
    yield {"type": "tool_use", "data": {"tool": "mcp__vision-analysis__analyze_children_drawing", "message": "Analyzing drawing..."}}

    analysis_result = await _call_mcp_tool(
        analyze_children_drawing,
        {"image_path": image_path, "child_age": child_age},
    )
    analysis_text = analysis_result.get("content", [{}])[0].get("text", "{}")
    try:
        analysis_data = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis_data = {"objects": [], "scene": "unknown", "mood": "unknown", "confidence_score": 0.0}

    yield {"type": "tool_result", "data": {"status": "completed"}}

    if analysis_data.get("error"):
        yield {"type": "error", "data": {"error": "VisionError", "message": f"Drawing analysis failed: {analysis_data['error']}"}}
        return

    # Step 2: Story memory + dedup
    stream_memory_section = ""
    try:
        stream_memory_section = await get_story_memory_prompt(child_id, user_id=user_id)
    except Exception:
        pass

    stream_dedup_nudge = ""
    try:
        stream_dedup_nudge = await _search_story_dedup(child_id, interests_str)
    except Exception:
        pass

    my_agent_context = ""
    try:
        my_agent_context = await build_my_agent_context(user_id=user_id, child_id=child_id)
    except Exception:
        pass

    # Step 3: Generate story via Anthropic API
    yield {"type": "tool_use", "data": {"tool": "story_generation", "message": "Creating your story..."}}

    story_prompt = f"""You are a children's story writer. Based on the following drawing analysis, create a warm, educational story.

Drawing Analysis:
{json.dumps(analysis_data, indent=2, ensure_ascii=False)}

Child age: {child_age} years old
Interests: {interests_str}
{my_agent_context}
{stream_memory_section}{stream_dedup_nudge}
Requirements:
- Story length: approximately {min_words}-{max_words} words
- Language appropriate for a {child_age}-year-old child
- Include themes, concepts, and a moral lesson
- Always respond in English

Return your response as JSON:
{{
  "story": "the story text",
  "themes": ["theme1", "theme2"],
  "concepts": ["concept1", "concept2"],
  "moral": "the moral lesson",
  "characters": [{{"name": "...", "description": "...", "appearances": 1}}]
}}"""

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    try:
        import anyio
        with anyio.fail_after(120):
            response = await client.messages.create(
                model=get_claude_agent_model(),
                max_tokens=2048,
                messages=[{"role": "user", "content": story_prompt}],
            )
    except Exception as e:
        yield {"type": "error", "data": {"error": "StoryGenerationError", "message": f"Story generation failed: {str(e)}"}}
        return

    response_text = response.content[0].text
    try:
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        story_data = json.loads(response_text)
    except json.JSONDecodeError:
        story_data = {
            "story": response_text,
            "themes": [],
            "concepts": [],
            "moral": None,
            "characters": [],
        }

    yield {"type": "tool_result", "data": {"status": "completed"}}

    # Step 4: Programmatic post-generation safety enforcement (#421).
    # Non-bypassable in code: even if the SDK prompt is ignored, this
    # gate runs before content is returned. One retry via
    # ``suggest_content_improvements`` on failure; if it still fails,
    # emit a structured error event and stop the stream.
    yield {"type": "tool_use", "data": {"tool": "mcp__safety-check__check_content_safety", "message": "Checking content safety..."}}

    raw_story_text = story_data.get("story", "")
    safety_age_group = _age_group_from_int(child_age)
    try:
        improved_story, safety_score, _retried = await enforce_post_gen_safety(
            raw_story_text,
            content_type="image_story",
            age_group=safety_age_group,
        )
        story_data["story"] = improved_story
        safety_data = {"safety_score": safety_score, "passed": True}
    except RuntimeError as safety_exc:
        yield {
            "type": "error",
            "data": {
                "error": "SafetyCheckFailed",
                "message": (
                    "We couldn't make this story safe enough after a repair "
                    "attempt. Please try again with a different drawing."
                ),
                "detail": str(safety_exc),
            },
        }
        return

    yield {"type": "tool_result", "data": {"status": "completed"}}

    # Step 5: Art style transfer (if requested)
    styled_image_path = None
    if art_theme and art_theme != "none":
        yield {"type": "tool_use", "data": {"tool": "mcp__image-style__transform_art_style", "message": "Applying art style..."}}
        try:
            style_result = await _call_mcp_tool(
                transform_art_style,
                {
                    "image_path": image_path,
                    "theme": art_theme,
                    "child_age": child_age,
                    "session_id": child_id,
                },
            )
            style_text = style_result.get("content", [{}])[0].get("text", "{}")
            style_data = json.loads(style_text)
            styled_image_path = style_data.get("styled_image_path")
        except Exception:
            pass
        # Step 5b: Re-validate the styled image for child safety (#710).
        # The API routes already gate stylized images via validate_and_fallback;
        # the agent-direct path (used by My Agent) bypassed that check, so the
        # styled image could be returned without a vision safety pass. We
        # fail closed here — discard the styled image and fall back to the
        # original drawing if validation fails or errors.
        if styled_image_path and Path(styled_image_path).exists():
            try:
                from ..mcp_servers.image_style_server import validate_and_fallback

                styled_image_safety = await validate_and_fallback(
                    styled_image_path=styled_image_path,
                    original_image_path=str(image_path),
                    child_age=child_age,
                    theme=art_theme,
                    session_id=child_id,
                )
                if not styled_image_safety.get("safety_passed"):
                    styled_image_path = None
            except Exception:
                logger.warning(
                    "Styled image safety validation failed (agent path), using original",
                    exc_info=True,
                )
                styled_image_path = None
        yield {"type": "tool_result", "data": {"status": "completed"}}

    # Step 6: Audio generation (if enabled)
    audio_path = None
    if should_generate_audio:
        yield {"type": "tool_use", "data": {"tool": "mcp__tts-generation__generate_story_audio", "message": "Generating audio..."}}
        try:
            audio_result = await _call_mcp_tool(
                generate_story_audio,
                {
                    "story_text": story_data.get("story", ""),
                    "voice": actual_voice,
                    "speed": audio_speed,
                    "child_age": child_age,
                    "provider": provider or "openai",
                },
            )
            audio_text = audio_result.get("content", [{}])[0].get("text", "{}")
            audio_data = json.loads(audio_text)
            audio_path = audio_data.get("audio_path")
            if audio_path:
                yield {"type": "audio_generated", "data": {"audio_path": audio_path, "message": "Audio generation complete"}}
        except Exception:
            logger.warning("Audio generation failed in direct pipeline", exc_info=True)
        yield {"type": "tool_result", "data": {"status": "completed"}}

    # Build result
    repaired_story, length_info = repair_story_length(
        story_data.get("story", ""),
        age_group,
    )
    if length_info["repaired"]:
        logger.info(
            "Repaired direct image-to-story length for age group %s to %d words",
            age_group,
            length_info["word_count"],
        )

    result_data = {
        "story": repaired_story,
        "themes": story_data.get("themes", []),
        "concepts": story_data.get("concepts", []),
        "moral": story_data.get("moral"),
        "characters": story_data.get("characters", []),
        "analysis": analysis_data,
        "safety_score": safety_data.get("safety_score", 0.9),
    }
    if audio_path:
        result_data["audio_path"] = audio_path
    if styled_image_path:
        result_data["styled_image_path"] = styled_image_path

    yield {"type": "result", "data": result_data}
    yield {"type": "complete", "data": {"status": "completed", "message": "Story creation complete!"}}


async def stream_image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None,
    enable_audio: bool = True,
    voice: str = None,
    art_theme: str = None,
    user_id: str = "",
    provider: str = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream story generation progress

    Args:
        image_path: Path to the drawing image
        child_id: Child ID
        child_age: Child's age
        interests: List of interest tags
        enable_audio: Whether to generate audio
        voice: Voice type (optional)
        art_theme: Art style theme (optional, e.g. "cartoon", "watercolor")

    Yields:
        Streaming event dictionaries containing type and data fields
    """
    if _should_use_mock():
        yield {
            "type": "status",
            "data": {"status": "started", "message": "Analyzing drawing..."},
        }
        yield {
            "type": "result",
            "data": _mock_image_to_story_result(interests or [], art_theme=art_theme),
        }
        yield {
            "type": "complete",
            "data": {"status": "completed", "message": "Story generation complete"},
        }
        return
    runtime_issue = _runtime_unavailable_reason()
    if runtime_issue:
        yield {
            "type": "error",
            "data": {"error": "RuntimeError", "message": runtime_issue},
        }
        return

    # Direct Anthropic API pipeline — no subprocess, no OOM risk (#417)
    logger.info("Using direct API pipeline for image-to-story (streaming)")
    async for event in _direct_stream_image_to_story(
        image_path=image_path,
        child_id=child_id,
        child_age=child_age,
        interests=interests,
        enable_audio=enable_audio,
        voice=voice,
        art_theme=art_theme,
        user_id=user_id,
        provider=provider,
    ):
        yield event
    return


# ---------------------------------------------------------------------------
# Legacy SDK path (streaming) — retained for reference, never called (#416).
# ---------------------------------------------------------------------------
async def _legacy_stream_image_to_story_sdk(  # pragma: no cover
    image_path, child_id, child_age, interests, enable_audio, voice, art_theme, user_id, provider,
):
    """Legacy SDK streaming path — not called. See _direct_stream_image_to_story instead."""
    # Validate input
    if not Path(image_path).exists():
        yield {
            "type": "error",
            "data": {
                "error": "FileNotFoundError",
                "message": f"Image file not found: {image_path}",
            },
        }
        return

    if not 3 <= child_age <= 12:
        yield {
            "type": "error",
            "data": {"error": "ValueError", "message": "Child age must be between 3 and 12"},
        }
        return

    interests_str = ", ".join(interests) if interests else "not specified"

    # Get age-based audio config
    age_group = _get_age_group_from_age(child_age)
    min_words, max_words = _get_story_length_range(age_group)
    audio_config = _get_audio_config(age_group)
    audio_mode = audio_config["audio_mode"]
    should_generate_audio = enable_audio and audio_mode in [
        "audio_first",
        "simultaneous",
    ]
    actual_voice = voice or audio_config["voice"]
    audio_speed = audio_config["speed"]

    # Send start event
    yield {
        "type": "status",
        "data": {"status": "started", "message": "Analyzing drawing..."},
    }

    # Build story memory section for streaming path (#165)
    stream_memory_section = ""
    try:
        stream_memory_section = await get_story_memory_prompt(child_id, user_id=user_id)
    except Exception:
        pass

    # Story dedup check for streaming path (#290)
    stream_dedup_nudge = ""
    try:
        stream_dedup_nudge = await _search_story_dedup(child_id, interests_str)
    except Exception:
        pass  # Best-effort

    prompt = f"""Please create a story suitable for a {child_age}-year-old child based on this children's drawing.

**Task Information**:
- Drawing path: {image_path}
- Child ID: {child_id}
- Child age: {child_age} years old
- Interests: {interests_str}
{stream_memory_section}{stream_dedup_nudge}
**Requirements**:
1. First, use the `mcp__vision-analysis__analyze_children_drawing` tool to analyze the drawing
2. Use the `mcp__vector-search__search_similar_drawings` tool to search for this child's previous similar drawings to maintain character and story continuity
3. Based on the analysis results, create a warm, educational story
4. Story length should be approximately {min_words}-{max_words} words
5. Language should be appropriate for a {child_age}-year-old child
6. **Important**: After the story is created, use the `mcp__vector-search__store_drawing_embedding` tool to store the drawing in the vector database with the following parameters:
   - drawing_description: Text description of the drawing (from the analysis results)
   - child_id: {child_id}
   - drawing_analysis: Drawing analysis results (including objects, scene, mood, colors, recurring_characters)
   - story_text: The generated story text
   - image_path: {image_path}

Please create a story based on the drawing content, and extract themes, concepts, and moral lessons.

**Safety Check (Mandatory)**:
After the story is created, you **must** use the `mcp__safety-check__check_content_safety` tool to check the story content safety with the following parameters:
- content_text: The generated story text
- target_age: {child_age}
- content_type: "story"
If the safety check fails (passed == false), you **must** use the `mcp__safety-check__suggest_content_improvements` tool to improve the content, then re-check, up to 3 retries.
Only proceed to the next steps after the safety check passes.

Always respond in English.
"""

    # Add style transfer instruction if art_theme is specified
    if art_theme and art_theme != "none":
        prompt += f"""
**Art Style Transfer**:
After analyzing the drawing and before creating the story, use the `mcp__image-style__transform_art_style` tool to transform the drawing into "{art_theme}" style. Parameters:
- image_path: {image_path}
- theme: {art_theme}
- child_age: {child_age}
- session_id: {child_id}

The transformed image will serve as the story cover. Please consider this art style in the story creation, matching the story's tone and atmosphere to the style.
If the style transfer fails, continue using the original drawing.
"""

    # Add TTS instruction if audio should be generated
    if should_generate_audio:
        provider_line = f"\n- Provider: {provider}" if provider else ""
        prompt += f"""
**Audio Generation**:
After the story is created, use the `mcp__tts-generation__generate_story_audio` tool to generate audio narration for the story text.
- Voice type: {actual_voice}
- Speed: {audio_speed}
- Child ID: {child_id}{provider_line}
"""

    mcp_servers = {
        "vision-analysis": vision_server,
        "vector-search": vector_server,
        "safety-check": safety_server,
        "tts-generation": tts_server,
    }

    allowed_tools = [
        "mcp__vision-analysis__analyze_children_drawing",
        "mcp__vector-search__search_similar_drawings",
        "mcp__vector-search__store_drawing_embedding",
        "mcp__safety-check__check_content_safety",
        "mcp__safety-check__suggest_content_improvements",
        "mcp__tts-generation__generate_story_audio",
    ]

    if art_theme and art_theme != "none":
        mcp_servers["image-style"] = image_style_server
        allowed_tools.append("mcp__image-style__transform_art_style")

    options = ClaudeAgentOptions(
        model=get_claude_agent_model(),
        mcp_servers=mcp_servers,
        allowed_tools=allowed_tools,
        cwd=".",
        permission_mode="acceptEdits",
        max_turns=15,  # Increase turns to accommodate more tool calls
        output_format={
            "type": "json_schema",
            "schema": StoryOutput.model_json_schema(),
        },
    )

    result_data = {}
    turn_count = 0
    audio_path = None
    styled_image_path = None

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                # Process assistant messages (thinking and tool use)
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
                                # Friendly tool name mapping
                                tool_messages = {
                                    "mcp__vision-analysis__analyze_children_drawing": "Analyzing drawing...",
                                    "mcp__vector-search__search_similar_drawings": "Searching similar drawings...",
                                    "mcp__vector-search__store_drawing_embedding": "Saving drawing to memory...",
                                    "mcp__safety-check__check_content_safety": "Checking content safety...",
                                    "mcp__tts-generation__generate_story_audio": "Generating audio...",
                                    "mcp__image-style__transform_art_style": "Applying art style...",
                                }
                                yield {
                                    "type": "tool_use",
                                    "data": {
                                        "tool": tool_name,
                                        "message": tool_messages.get(
                                            tool_name, f"Using {tool_name}..."
                                        ),
                                    },
                                }
                            elif isinstance(block, ToolResultBlock):
                                # Try to extract audio/styled image path from tool results
                                result_content = getattr(block, "content", None)
                                result_text = None
                                if isinstance(result_content, str):
                                    result_text = result_content
                                elif isinstance(result_content, list):
                                    for item in result_content:
                                        if (
                                            isinstance(item, dict)
                                            and item.get("type") == "text"
                                        ):
                                            result_text = item.get("text")
                                            break
                                        text_val = getattr(item, "text", None)
                                        if text_val:
                                            result_text = text_val
                                            break
                                if result_text:
                                    try:
                                        result_json = json.loads(result_text)
                                        if "audio_path" in result_json:
                                            audio_path = result_json["audio_path"]
                                            yield {
                                                "type": "audio_generated",
                                                "data": {
                                                    "audio_path": audio_path,
                                                    "message": "Audio generation complete",
                                                },
                                            }
                                        if "styled_image_path" in result_json:
                                            styled_image_path = result_json[
                                                "styled_image_path"
                                            ]
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

                # Process final result
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
                            result_data = {
                                "story": str(message.result),
                                "themes": [],
                                "concepts": [],
                                "moral": None,
                                "characters": [],
                                "analysis": {},
                                "safety_score": 0.9,
                            }
                    break

    except Exception as e:
        yield {
            "type": "error",
            "data": {
                "error": str(type(e).__name__),
                "message": f"Error generating story: {str(e)}",
            },
        }
        return

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Add styled image path to result if available
    if styled_image_path:
        result_data["styled_image_path"] = styled_image_path

    # Send final result
    yield {"type": "result", "data": result_data}

    yield {
        "type": "complete",
        "data": {"status": "completed", "message": "Story creation complete!"},
    }


if __name__ == "__main__":
    """Test Agent"""
    import asyncio

    async def test():
        print("=== Test Image to Story Agent ===\n")

        # Create test image
        from PIL import Image

        test_image_path = "./test_drawing.png"
        img = Image.new("RGB", (400, 300), color="lightblue")
        img.save(test_image_path)

        try:
            result = await image_to_story(
                image_path=test_image_path,
                child_id="test_child_001",
                child_age=7,
                interests=["animals", "adventure"],
            )

            print("Story generation successful!")
            print("\nResult:")
            print(result)

        except Exception as e:
            print(f"Error: {e}")

        finally:
            # Clean up test file
            if Path(test_image_path).exists():
                Path(test_image_path).unlink()

    asyncio.run(test())
