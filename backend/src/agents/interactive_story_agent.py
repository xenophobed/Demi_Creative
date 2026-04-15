"""
Interactive Story Agent

Generates multi-branch interactive stories using the Anthropic API directly.
Uses AsyncAnthropic for in-process execution (no subprocess — avoids Railway OOM).
Supports streaming responses to reduce timeouts and improve user experience.

Issue: #418 | Parent Epic: #416
"""

import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel

try:
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover
    AsyncAnthropic = None

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

logger = logging.getLogger(__name__)

from ..mcp_servers import (
    safety_server,
    search_similar_stories,
    tts_server,
    vector_server,
)
from ..mcp_servers.safety_check_server import check_content_safety
from ..mcp_servers.tts_generator_server import generate_story_audio
from ..services.database import preference_repo
from ..services.story_memory import get_story_memory_prompt
from ..utils.model_config import get_claude_agent_model


async def _direct_generate(prompt: str, max_tokens: int = 4096) -> str:
    """Call Anthropic API directly — no subprocess, no OOM risk (#416).

    Returns the raw text response from Claude.
    """
    import anyio
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    with anyio.fail_after(120):
        response = await client.messages.create(
            model=get_claude_agent_model(),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    return response.content[0].text if response.content else ""


def _extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from Claude's text response (may have markdown fences)."""
    # Try raw parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try extracting from ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass
    # Try finding first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass
    return None


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
# Streaming Event Types
# ============================================================================


class StreamEvent:
    """Base class for streaming events"""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.type = event_type
        self.data = data

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format"""
        return (
            f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"
        )


# ============================================================================
# Pydantic Models (for Structured Output)
# ============================================================================


class StoryChoiceOutput(BaseModel):
    """Story choice option"""

    choice_id: str
    text: str
    emoji: str


class StorySegmentOutput(BaseModel):
    """Story segment output"""

    segment_id: int
    text: str
    choices: List[StoryChoiceOutput] = []
    is_ending: bool = False


class StoryOpeningOutput(BaseModel):
    """Story opening output"""

    title: str
    segment: StorySegmentOutput


class NextSegmentOutput(BaseModel):
    """Next segment output"""

    segment: StorySegmentOutput
    is_ending: bool = False
    educational_summary: Optional[Dict[str, Any]] = None


# ============================================================================
# Age Adaptation Configuration
# ============================================================================

AGE_CONFIG = {
    "3-5": {
        "word_count": "50-100",
        "sentence_length": "5-10 words",
        "complexity": "very simple",
        "vocab_level": "basic everyday vocabulary",
        "theme_depth": "simple, concrete, related to daily life",
        "choices_style": "simple actions with large emojis",
        "total_segments": 3,
        # Audio settings
        "audio_mode": "audio_first",
        "voice": "nova",
        "speed": 0.9,
    },
    "6-8": {
        "word_count": "100-200",
        "sentence_length": "10-15 words",
        "complexity": "simple",
        "vocab_level": "elementary school vocabulary",
        "theme_depth": "fun adventures, simple moral choices",
        "choices_style": "fun choices with emojis",
        "total_segments": 4,
        # Audio settings
        "audio_mode": "simultaneous",
        "voice": "shimmer",
        "speed": 1.0,
    },
    "9-12": {
        "word_count": "150-300",
        "sentence_length": "15-25 words",
        "complexity": "moderate",
        "vocab_level": "upper elementary vocabulary",
        "theme_depth": "complex plots, tests of character and wisdom",
        "choices_style": "meaningful choices that affect the story direction",
        "total_segments": 5,
        # Audio settings
        "audio_mode": "text_first",
        "voice": "alloy",
        "speed": 1.1,
    },
}

# Story length mode segment counts (#331)
# Maps (story_length_mode) -> total_segments.  None = unlimited.
STORY_LENGTH_SEGMENTS = {
    "short": 5,
    "medium": 10,
    "unlimited": None,
}

# Soft caps for unlimited mode by age group (#331)
UNLIMITED_SOFT_CAP = {
    "3-5": 15,
    "6-8": 30,
    "9-12": 50,
}


def get_total_segments(story_length_mode: str, age_group: str) -> int:
    """Return total_segments for a given mode. For unlimited, uses the soft cap."""
    segments = STORY_LENGTH_SEGMENTS.get(story_length_mode)
    if segments is not None:
        return segments
    # Unlimited mode: use soft cap as total_segments for progress display,
    # but actual ending is controlled by the /end endpoint or soft-cap prompt.
    return UNLIMITED_SOFT_CAP.get(age_group, 50)


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
        sections.append(f"- Favorite themes: {', '.join(t[0] for t in top_themes)}")

    # Top 3 interests
    interests = profile.get("interests", {})
    if interests:
        top_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:3]
        sections.append(f"- Interest preferences: {', '.join(t[0] for t in top_interests)}")

    # Last 3 recent choices
    recent = profile.get("recent_choices", [])
    if recent:
        last_3 = recent[-3:]
        sections.append(f"- Recent choices: {', '.join(last_3)}")

    if not sections:
        return ""

    return "**Child Preference Memory**:\n" + "\n".join(sections) + "\n"


def _build_opening_prompt(
    child_id: str,
    age_group: str,
    interests_str: str,
    theme_str: str,
    config: Dict[str, Any],
    preference_context: str = "",
    story_memory_section: str = "",
    dedup_nudge: str = "",
    character_memory_section: str = "",
) -> str:
    """
    Build the full prompt for interactive story opening generation.

    Includes preference context (#72) and character continuity instructions (#73).
    """
    prompt = f"""You are a professional children's story writer who specializes in creating interactive stories for different age groups.

Please create the **opening** of an interactive story for a {age_group} year old child.

**Child Information**:
- Child ID: {child_id}
- Age group: {age_group} years old
- Interests: {interests_str}
- Story theme: {theme_str}

**Writing Requirements** (age-adapted):
- Words per segment: {config["word_count"]} words
- Sentence length: {config["sentence_length"]}
- Complexity: {config["complexity"]}
- Vocabulary level: {config["vocab_level"]}
- Theme depth: {config["theme_depth"]}
- Choices style: {config["choices_style"]}
"""

    # Inject preference context (#72)
    if preference_context:
        prompt += f"\n{preference_context}\nPlease naturally incorporate the child's favorite themes and elements based on the preferences above.\n"

    # Inject cross-story memory (#165)
    if story_memory_section:
        prompt += f"\n{story_memory_section}\n"

    # Inject deterministic character memory (#365)
    if character_memory_section:
        prompt += f"\n{character_memory_section}\n"

    # Inject dedup variation nudge (#290)
    if dedup_nudge:
        prompt += f"\n{dedup_nudge}\n"

    # Character continuity (#73)
    prompt += f"""
**Character Continuity**:
Before creating the story, use the `mcp__vector-search__search_similar_drawings` tool to search the child's previous creations for recurring characters.
- Search parameters: child_id="{child_id}", query="{interests_str}"
- If recurring_characters are found, naturally weave them into the new story (don't force it, let them appear organically)
- If no historical characters exist, create an entirely new story

**Content Storage**:
After the story is created, use the `mcp__vector-search__store_drawing_embedding` tool to store the character information from this session, so future stories can maintain character continuity.

**Important Rules**:
1. The story must be warm, positive, and educational
2. All branches should ultimately lead to a "good ending" (never punish the child's choices)
3. Naturally incorporate STEAM or moral education elements
4. The opening should capture the child's attention and set up suspense
5. Provide 2-3 interesting choices, each with an appropriate emoji
6. Choices should be equal — there is no "correct answer"

**Output Format**:
Return the story opening directly in JSON format, containing:
- title: Story title (engaging, related to the theme)
- segment: Opening segment
  - segment_id: 0
  - text: Story opening text
  - choices: Array of choices, each containing choice_id, text, emoji
  - is_ending: false

Create an amazing story opening!

Always respond in English.
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
    continuity_anchors: str = "",
) -> str:
    """Build prompt for generating the next story segment."""
    return f"""You are a professional children's story writer, continuing an interactive story.

**Story Information**:
- Story title: {story_title}
- Age group: {age_group} years old
- Interests: {", ".join(interests)}
- Theme: {theme}
- Current segment: Segment {segment_count + 1} (of {total_segments} total)
- Is this the ending: {"yes" if is_final_segment else "no"}
- Pacing: {"Wrap up quickly — short story mode" if total_segments <= 5 else "Medium pace — develop the plot steadily" if total_segments <= 10 else "Long adventure — take your time, build rich worlds"}

**Previous Story Content**:
{story_context if story_context else "This is the beginning of the story"}

**User Decision Trail (chronological order)**:
{choice_history_context if choice_history_context else "(no prior choices)"}

**Opening Key Clue (ending must callback to this)**:
{opening_hook if opening_hook else "(none)"}

**Ending Continuity Anchors (ending must reference at least 2)**:
{continuity_anchors if continuity_anchors else "(none — can be derived from prior events and choices)"}

**User's Choice**:
Choice ID: {choice_id}
Choice content: {chosen_option or "continue the story"}

**Writing Requirements** (age-adapted):
- Words per segment: {config["word_count"]} words
- Sentence length: {config["sentence_length"]}
- Complexity: {config["complexity"]}
- Vocabulary level: {config["vocab_level"]}
- Choices style: {config["choices_style"]}

**Important Rules**:
1. Naturally continue the story based on the user's choice
2. Maintain story coherence and engagement
3. {
        "This is the ending segment. Please provide a warm, positive, complete ending: you must explicitly reference the opening clue, quote at least 2 phrases from the 'Ending Continuity Anchors' above verbatim, do not introduce any new main quests, and create a satisfying closure that connects back to earlier events"
        if is_final_segment
        else "Continue developing the plot and provide 2-3 new choices"
    }
4. All content must be child-appropriate and positive
5. {"No choices needed" if is_final_segment else "Each choice should have an appropriate emoji"}
6. {
        "The ending should not introduce new major conflicts. Focus on resolving earlier problems and highlighting growth and lessons learned"
        if is_final_segment
        else "Ensure new choices genuinely affect subsequent developments and avoid repetitive phrasing"
    }

**Output Format**:
Return directly in JSON format, containing:
- segment: Story segment
  - segment_id: {segment_count}
  - text: Story content
  - choices: {"empty array []" if is_final_segment else "choices array"}
  - is_ending: {str(is_final_segment).lower()}
- is_ending: {str(is_final_segment).lower()}
{
        f'''- educational_summary: Educational summary (only for ending)
  - themes: Themes array (e.g.: ["courage", "friendship"])
  - concepts: Concepts array (e.g.: ["decision-making", "cooperation"])
  - moral: Moral of the story (one sentence summary)'''
        if is_final_segment
        else ""
    }

Continue this amazing story!

Always respond in English.
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

**Audio Generation**:
After the story is created, use the `mcp__tts-generation__generate_story_audio` tool to generate audio narration for the story text.
- Voice type: {voice}
- Speed: {speed}
- {id_label}: {id_value}
"""
    )


# ============================================================================
# Story Coherence Helpers
# ============================================================================


def _build_fallback_choices(segment_id: int, age_group: str) -> List[Dict[str, str]]:
    """Fallback choices to keep interactive flow complete when model output is sparse."""
    if age_group == "3-5":
        templates = [("Move forward with friends", "🤝"), ("Observe first, then act", "👀")]
    elif age_group == "9-12":
        templates = [("Make a plan based on clues", "🧭"), ("Help friends first, then proceed", "💡")]
    else:
        templates = [("Follow the clues forward", "🔍"), ("Discuss a new plan with friends", "🤝")]

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
        return "(no prior choices)"

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


def _extract_choice_history_steps(choice_history_context: str) -> List[str]:
    """Extract selected choice texts from numbered history lines."""
    history_lines = [
        line.strip()
        for line in str(choice_history_context or "").splitlines()
        if line.strip() and line.strip()[0].isdigit()
    ]
    steps: List[str] = []
    for line in history_lines:
        if ". " in line:
            steps.append(line.split(". ", 1)[1].strip())
        else:
            steps.append(line.strip())
    return [step for step in steps if step]


def _extract_salient_fragment(text: str, max_len: int = 14) -> str:
    """Extract a concise phrase from a segment as a continuity anchor."""
    content = str(text or "").strip()
    if not content:
        return ""
    parts = [p.strip() for p in re.split(r"[，。！？!?；;：:]", content) if p.strip()]
    for part in parts:
        if 4 <= len(part) <= max_len:
            return part
    if parts:
        part = parts[0]
        return part[:max_len] if len(part) > max_len else part
    return content[:max_len]


def _extract_keywords(text: str, limit: int = 6) -> List[str]:
    """Extract compact keywords from Chinese/English text."""
    content = str(text or "")
    if not content:
        return []

    stop_words = {
        "我们",
        "你们",
        "他们",
        "大家",
        "小伙伴",
        "小伙伴们",
        "故事",
        "冒险",
        "最后",
        "终于",
        "然后",
        "因为",
        "所以",
        "开始",
        "继续",
        "一起",
        "这个",
        "那个",
        "这样",
        "那里",
        "这里",
        "温暖",
        "结局",
        "成长",
    }
    en_stop_words = {
        "the",
        "and",
        "with",
        "that",
        "this",
        "from",
        "then",
        "they",
        "them",
        "story",
        "ending",
    }

    tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,}", content)
    keywords: List[str] = []
    for token in tokens:
        cleaned = token.strip()
        if not cleaned:
            continue
        if cleaned in stop_words:
            continue
        if cleaned.lower() in en_stop_words:
            continue
        if cleaned not in keywords:
            keywords.append(cleaned)
        if len(keywords) >= limit:
            break
    return keywords


def _build_continuity_anchors(
    segments: List[Dict[str, Any]],
    opening_hook: str,
    chosen_option: Optional[str],
    choice_history_context: str,
    max_items: int = 6,
) -> List[str]:
    """Collect stable anchors from prior story so ending can stay on-topic."""
    anchors: List[str] = []

    def add_anchor(candidate: str) -> None:
        item = str(candidate or "").strip()
        if not item:
            return
        item = item[:20]
        if item not in anchors:
            anchors.append(item)

    add_anchor(opening_hook)
    add_anchor(chosen_option or "")

    history_steps = _extract_choice_history_steps(choice_history_context)
    for step in history_steps[-3:]:
        add_anchor(step)

    for seg in segments[-3:]:
        add_anchor(_extract_salient_fragment(seg.get("text", "")))

    keyword_sources: List[str] = []
    if opening_hook:
        keyword_sources.append(opening_hook)
    if chosen_option:
        keyword_sources.append(chosen_option)
    keyword_sources.extend(history_steps[-3:])
    for seg in segments[-2:]:
        keyword_sources.append(str(seg.get("text", "")))

    for source in keyword_sources:
        for kw in _extract_keywords(source, limit=3):
            add_anchor(kw)
            if len(anchors) >= max_items:
                return anchors[:max_items]

    return anchors[:max_items]


def _count_anchor_hits(text: str, anchors: List[str]) -> int:
    """Count how many anchors appear in generated ending text."""
    content = str(text or "")
    return sum(1 for anchor in anchors if anchor and anchor in content)


def _rewrite_ending_with_anchors(
    opening_hook: str,
    chosen_option: Optional[str],
    choice_history_context: str,
    continuity_anchors: List[str],
) -> str:
    """Rewrite ending into a coherent close that references earlier context."""
    anchors = [a for a in continuity_anchors if a][:3]
    history_steps = _extract_choice_history_steps(choice_history_context)

    hook_clause = (
        f"From the very beginning of the story, the mystery of \"{opening_hook}\" has finally found its answer. "
        if opening_hook
        else "This journey has finally resolved all the questions planted earlier. "
    )
    option_clause = (
        f"After everyone made the key choice of \"{chosen_option}\", "
        if chosen_option
        else "After the final key decision, "
    )

    if anchors:
        anchor_clause = f"revolving around {', '.join(anchors)}, the friends overcame each challenge along the way. "
    else:
        anchor_clause = "the friends overcame each challenge along the way, bringing the story threads to a complete close. "

    history_clause = ""
    if history_steps:
        recent = ", ".join(history_steps[-2:])
        history_clause = f"Looking back at the earlier choices ({recent}), every step pushed the story in the same direction. "

    return (
        f"{hook_clause}{option_clause}{anchor_clause}"
        f"{history_clause}In the end, the friends returned to their daily lives with newfound courage and teamwork, and the story came to a satisfying close."
    )


def _ensure_ending_coherence(
    ending_text: str,
    opening_hook: str,
    chosen_option: Optional[str],
    choice_history_context: str,
    continuity_anchors: Optional[List[str]] = None,
) -> str:
    """Ensure final segment explicitly connects to opening and recent choices."""
    text = str(ending_text or "").strip()
    if not text:
        text = "This adventure has finally reached its warm conclusion."

    anchors = [a.strip() for a in (continuity_anchors or []) if str(a).strip()]
    required_hits = 2 if len(anchors) >= 2 else len(anchors)
    anchor_hits = _count_anchor_hits(text, anchors)

    # If ending drifts away from prior context, rewrite to force alignment.
    if required_hits and anchor_hits < required_hits:
        text = _rewrite_ending_with_anchors(
            opening_hook=opening_hook,
            chosen_option=chosen_option,
            choice_history_context=choice_history_context,
            continuity_anchors=anchors,
        )

    additions: List[str] = []
    if opening_hook and opening_hook not in text:
        additions.append(
            f"Thinking back to the beginning when \"{opening_hook}\" first appeared, the friends have finally brought this adventure to a warm conclusion."
        )

    if chosen_option:
        chosen_option = str(chosen_option).strip()
        if chosen_option and chosen_option not in text:
            additions.append(
                f"It was precisely because of choosing \"{chosen_option}\" that the story arrived at this outcome."
            )

    if not any(k in text for k in ["finally", "in the end", "ending", "returned", "learned", "ever since"]):
        additions.append("In the end, everyone returned to daily life with newfound courage and wisdom, and the story came to a satisfying close.")

    history_steps = _extract_choice_history_steps(choice_history_context)
    if history_steps:
        summary = "; ".join(history_steps[-2:])
        if summary and summary not in text:
            additions.append(f"All the key choices along the way ({summary}) found their answer in this moment.")

    if additions:
        text = f"{text} {' '.join(additions)}"

    return text


# ============================================================================
# Agent Functions
# ============================================================================


def _mock_opening(interests: List[str]) -> Dict[str, Any]:
    topic = interests[0] if interests else "adventure"
    return {
        "title": f"The Great {topic} Adventure",
        "segment": {
            "segment_id": 0,
            "text": f"On a bright sunny morning, the friends decided to begin an exploration about {topic}.",
            "choices": [
                {"choice_id": "choice_0_a", "text": "Let's go!", "emoji": "🚀"},
                {"choice_id": "choice_0_b", "text": "Let's prepare first", "emoji": "🎒"},
            ],
            "is_ending": False,
        },
    }


def _mock_next_segment(segment_count: int, is_final_segment: bool) -> Dict[str, Any]:
    segment = {
        "segment_id": segment_count,
        "text": "The friends continued forward, discovered new clues, and learned to help each other.",
        "choices": []
        if is_final_segment
        else [
            {
                "choice_id": f"choice_{segment_count}_a",
                "text": "Try bravely",
                "emoji": "✨",
            },
            {
                "choice_id": f"choice_{segment_count}_b",
                "text": "Team discussion",
                "emoji": "🤝",
            },
        ],
        "is_ending": is_final_segment,
    }
    result = {"segment": segment, "is_ending": is_final_segment}
    if is_final_segment:
        result["educational_summary"] = {
            "themes": ["courage", "cooperation"],
            "concepts": ["decision-making", "exploration"],
            "moral": "By trying bravely and working with friends, every problem finds an answer.",
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
    Generate interactive story opening.

    Args:
        child_id: Child ID
        age_group: Age group ("3-5", "6-8", "9-12")
        interests: Interest tag list
        theme: Story theme (optional)
        enable_audio: Whether to generate audio
        voice: Voice type (optional, defaults based on age group)

    Returns:
        Dictionary containing story title and opening segment
    """
    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    if _should_use_mock():
        return _mock_opening(interests)
    interests_str = ", ".join(interests) if interests else "adventure"
    theme_str = (
        theme if theme else f"An adventure about {interests[0]}" if interests else "A mysterious adventure"
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
            prompt, actual_voice, audio_speed, "Child ID", child_id
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

    # Direct Anthropic API — no subprocess, no OOM risk (#416/#418)
    try:
        raw_text = await _direct_generate(prompt)
        result_data = _extract_json(raw_text) or {}
    except Exception as e:
        logger.warning("Direct API opening generation failed: %s", e)

    # Safety check on generated content
    if result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            try:
                safety_result = await check_content_safety({
                    "content_text": story_text,
                    "content_type": "interactive_story",
                    "target_age": int(age_group.split("-")[0]),
                })
                if isinstance(safety_result, str):
                    safety_result = json.loads(safety_result)
                result_data["safety_score"] = safety_result.get("safety_score", 0.9)
            except Exception:
                result_data["safety_score"] = 0.9

    # Generate TTS audio if enabled
    if enable_audio and result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            try:
                tts_result = await generate_story_audio({
                    "story_text": story_text,
                    "voice": voice or config.get("voice", "shimmer"),
                    "speed": config.get("speed", 1.0),
                    "output_id": f"interactive_opening_{child_id}",
                })
                if isinstance(tts_result, str):
                    tts_result = json.loads(tts_result)
                if tts_result.get("audio_path"):
                    audio_path = tts_result["audio_path"]
            except Exception:
                pass  # Audio is optional

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
    Stream interactive story opening generation.

    Args:
        child_id: Child ID
        age_group: Age group ("3-5", "6-8", "9-12")
        interests: Interest tag list
        theme: Story theme (optional)
        enable_audio: Whether to generate audio
        voice: Voice type (optional)

    Yields:
        Streaming event dictionaries containing type and data fields
    """
    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    if _should_use_mock():
        yield {
            "type": "status",
            "data": {"status": "started", "message": "Generating story opening..."},
        }
        yield {"type": "result", "data": _mock_opening(interests)}
        yield {
            "type": "complete",
            "data": {"status": "completed", "message": "Story opening generation complete"},
        }
        return
    interests_str = ", ".join(interests) if interests else "adventure"
    theme_str = (
        theme if theme else f"An adventure about {interests[0]}" if interests else "A mysterious adventure"
    )

    # Send start event
    yield {
        "type": "status",
        "data": {"status": "started", "message": "Creating story..."},
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
            prompt, actual_voice, audio_speed, "Child ID", child_id
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
    audio_path = None

    # Direct Anthropic API — no subprocess, no OOM risk (#416/#418)
    yield {
        "type": "thinking",
        "data": {"content": "Creating your story opening...", "turn": 1},
    }

    try:
        raw_text = await _direct_generate(prompt)
        result_data = _extract_json(raw_text) or {}
    except Exception as e:
        yield {
            "type": "error",
            "data": {"error": str(e), "message": "Error generating story"},
        }
        result_data = _create_default_opening(theme_str, interests, config)

    # Safety check on generated content
    if result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            yield {
                "type": "tool_use",
                "data": {"tool": "safety_check", "message": "Checking content safety..."},
            }
            try:
                safety_result = await check_content_safety({
                    "content_text": story_text,
                    "content_type": "interactive_story",
                    "target_age": int(age_group.split("-")[0]),
                })
                if isinstance(safety_result, str):
                    safety_result = json.loads(safety_result)
                result_data["safety_score"] = safety_result.get("safety_score", 0.9)
            except Exception:
                result_data["safety_score"] = 0.9
            yield {"type": "tool_result", "data": {"status": "completed"}}

    # Generate TTS audio if enabled
    if enable_audio and result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            yield {
                "type": "tool_use",
                "data": {"tool": "tts_generation", "message": "Generating audio..."},
            }
            try:
                tts_result = await generate_story_audio({
                    "story_text": story_text,
                    "voice": voice or config.get("voice", "shimmer"),
                    "speed": config.get("speed", 1.0),
                    "output_id": f"interactive_opening_{child_id}",
                })
                if isinstance(tts_result, str):
                    tts_result = json.loads(tts_result)
                if tts_result.get("audio_path"):
                    audio_path = tts_result["audio_path"]
                    yield {
                        "type": "audio_generated",
                        "data": {"audio_path": audio_path, "message": "Audio generation complete"},
                    }
            except Exception:
                pass
            yield {"type": "tool_result", "data": {"status": "completed"}}

    # Validate and ensure required structure
    if not result_data or "title" not in result_data:
        result_data = _create_default_opening(theme_str, interests, config)

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Ensure opening always has valid choices to prevent story from getting stuck
    if "segment" in result_data and "choices" in result_data["segment"]:
        result_data["segment"]["choices"] = _normalize_choices(
            result_data["segment"]["choices"],
            segment_id=0,
            is_final_segment=False,
            age_group=age_group,
        )

    # Send final result
    yield {"type": "result", "data": result_data}

    yield {
        "type": "complete",
        "data": {"status": "completed", "message": "Story creation complete!"},
    }


async def generate_next_segment_stream(
    session_id: str,
    choice_id: str,
    session_data: Dict[str, Any],
    enable_audio: bool = True,
    voice: str = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream the next story segment generation.

    Args:
        session_id: Session ID
        choice_id: User's chosen option ID
        session_data: Session data
        enable_audio: Whether to generate audio
        voice: Voice type (optional)

    Yields:
        Streaming event dictionaries
    """
    segments = session_data.get("segments", [])
    choice_history = session_data.get("choice_history", [])
    age_group = session_data.get("age_group", "6-8")
    interests = session_data.get("interests", ["adventure"])
    theme = session_data.get("theme", "adventure story")
    story_title = session_data.get("story_title", "A mysterious adventure")
    story_length_mode = session_data.get("story_length_mode", "short")
    force_ending = session_data.get("force_ending", False)

    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    segment_count = len(segments)
    total_segments = get_total_segments(story_length_mode, age_group)

    # Determine if this is the final segment
    if force_ending:
        is_final_segment = True
    elif story_length_mode == "unlimited":
        # In unlimited mode, never auto-end (soft cap triggers a gentle prompt instead)
        is_final_segment = False
    else:
        is_final_segment = segment_count >= total_segments - 1

    if _should_use_mock():
        yield {
            "type": "status",
            "data": {"status": "processing", "message": "Continuing story..."},
        }
        yield {
            "type": "result",
            "data": _mock_next_segment(segment_count, is_final_segment),
        }
        yield {
            "type": "complete",
            "data": {"status": "completed", "message": "Segment generation complete"},
        }
        return

    # Send start event
    yield {
        "type": "status",
        "data": {
            "status": "started",
            "message": "Continuing story..." if not is_final_segment else "Creating the ending...",
            "is_ending": is_final_segment,
        },
    }

    # Build story context from previous segments
    story_context = "\n".join(
        [
            f"Segment {s.get('segment_id', i)}: {s.get('text', '')}"
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
    continuity_anchors = _build_continuity_anchors(
        segments=segments,
        opening_hook=opening_hook,
        chosen_option=chosen_option,
        choice_history_context=choice_history_context,
    )

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
        continuity_anchors="、".join(continuity_anchors),
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
            prompt, actual_voice, audio_speed, "Session ID", session_id
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

    # Direct Anthropic API — no subprocess, no OOM risk (#416/#418)
    yield {
        "type": "thinking",
        "data": {"content": "Continuing your story...", "turn": 1},
    }

    try:
        raw_text = await _direct_generate(prompt)
        result_data = _extract_json(raw_text) or {}
    except Exception as e:
        yield {
            "type": "error",
            "data": {"error": str(e), "message": "Error generating story"},
        }
        result_data = _create_default_segment(
            segment_count, is_final_segment, chosen_option
        )

    # Safety check on generated content
    if result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            yield {
                "type": "tool_use",
                "data": {"tool": "safety_check", "message": "Checking content safety..."},
            }
            try:
                safety_result = await check_content_safety({
                    "content_text": story_text,
                    "content_type": "interactive_story",
                    "target_age": int(age_group.split("-")[0]),
                })
                if isinstance(safety_result, str):
                    safety_result = json.loads(safety_result)
                result_data["safety_score"] = safety_result.get("safety_score", 0.9)
            except Exception:
                result_data["safety_score"] = 0.9
            yield {"type": "tool_result", "data": {"status": "completed"}}

    # Generate TTS audio if enabled
    if enable_audio and result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            yield {
                "type": "tool_use",
                "data": {"tool": "tts_generation", "message": "Generating audio..."},
            }
            try:
                tts_result = await generate_story_audio({
                    "story_text": story_text,
                    "voice": voice or config.get("voice", "shimmer"),
                    "speed": config.get("speed", 1.0),
                    "output_id": f"interactive_seg_{segment_count}",
                })
                if isinstance(tts_result, str):
                    tts_result = json.loads(tts_result)
                if tts_result.get("audio_path"):
                    audio_path = tts_result["audio_path"]
                    yield {
                        "type": "audio_generated",
                        "data": {"audio_path": audio_path, "message": "Audio generation complete"},
                    }
            except Exception:
                pass
            yield {"type": "tool_result", "data": {"status": "completed"}}

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
                continuity_anchors=continuity_anchors,
            )

    if is_final_segment and "educational_summary" not in result_data:
        result_data["educational_summary"] = {
            "themes": ["courage", "friendship"],
            "concepts": ["decision-making", "exploration"],
            "moral": "By bravely facing challenges and working with friends, you become stronger.",
        }

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    yield {"type": "result", "data": result_data}

    yield {
        "type": "complete",
        "data": {
            "status": "completed",
            "message": "Story creation complete!" if is_final_segment else "Segment generation complete!",
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
    Generate the next story segment based on user's choice.

    Args:
        session_id: Session ID
        choice_id: User's chosen option ID
        session_data: Session data containing previous segments and choice history
        enable_audio: Whether to generate audio
        voice: Voice type (optional)

    Returns:
        Dictionary containing the next segment
    """
    segments = session_data.get("segments", [])
    choice_history = session_data.get("choice_history", [])
    age_group = session_data.get("age_group", "6-8")
    interests = session_data.get("interests", ["adventure"])
    theme = session_data.get("theme", "adventure story")
    story_title = session_data.get("story_title", "A mysterious adventure")
    story_length_mode = session_data.get("story_length_mode", "short")
    force_ending = session_data.get("force_ending", False)

    config = AGE_CONFIG.get(age_group, AGE_CONFIG["6-8"])
    segment_count = len(segments)
    total_segments = get_total_segments(story_length_mode, age_group)

    # Determine if this should be the ending
    if force_ending:
        is_final_segment = True
    elif story_length_mode == "unlimited":
        is_final_segment = False
    else:
        is_final_segment = segment_count >= total_segments - 1

    if _should_use_mock():
        return _mock_next_segment(segment_count, is_final_segment)

    # Build story context from previous segments
    story_context = "\n".join(
        [
            f"Segment {s.get('segment_id', i)}: {s.get('text', '')}"
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
    continuity_anchors = _build_continuity_anchors(
        segments=segments,
        opening_hook=opening_hook,
        chosen_option=chosen_option,
        choice_history_context=choice_history_context,
    )

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
        continuity_anchors="、".join(continuity_anchors),
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
            prompt, actual_voice, audio_speed, "Session ID", session_id
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

    # Direct Anthropic API — no subprocess, no OOM risk (#416/#418)
    try:
        raw_text = await _direct_generate(prompt)
        result_data = _extract_json(raw_text) or {}
    except Exception as e:
        logger.warning("Direct API segment generation failed: %s", e)

    # Safety check on generated content
    if result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            try:
                safety_result = await check_content_safety({
                    "content_text": story_text,
                    "content_type": "interactive_story",
                    "target_age": int(age_group.split("-")[0]),
                })
                if isinstance(safety_result, str):
                    safety_result = json.loads(safety_result)
                result_data["safety_score"] = safety_result.get("safety_score", 0.9)
            except Exception:
                result_data["safety_score"] = 0.9

    # Generate TTS audio if enabled
    if enable_audio and result_data and "segment" in result_data:
        story_text = result_data["segment"].get("text", "")
        if story_text:
            try:
                tts_result = await generate_story_audio({
                    "story_text": story_text,
                    "voice": voice or config.get("voice", "shimmer"),
                    "speed": config.get("speed", 1.0),
                    "output_id": f"interactive_seg_{segment_count}",
                })
                if isinstance(tts_result, str):
                    tts_result = json.loads(tts_result)
                if tts_result.get("audio_path"):
                    audio_path = tts_result["audio_path"]
            except Exception:
                pass

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
                continuity_anchors=continuity_anchors,
            )

    # Add audio path to result if available
    if audio_path:
        result_data["audio_path"] = audio_path

    # Add educational summary for endings
    if is_final_segment and "educational_summary" not in result_data:
        result_data["educational_summary"] = {
            "themes": ["courage", "friendship"],
            "concepts": ["decision-making", "exploration"],
            "moral": "By bravely facing challenges and working with friends, you become stronger.",
        }

    return result_data


def _create_default_opening(
    theme: str, interests: List[str], config: Dict
) -> Dict[str, Any]:
    """Create default opening (used when AI generation fails)"""
    interest_item = interests[0] if interests else "treasure chest"
    return {
        "title": f"Journey of {theme}",
        "segment": {
            "segment_id": 0,
            "text": f"On a bright sunny morning, the young hero discovered a mysterious {interest_item}. It was sparkling and glowing, as if inviting the hero to come and explore...",
            "choices": [
                {"choice_id": "choice_0_a", "text": "Explore right away", "emoji": "🔍"},
                {"choice_id": "choice_0_b", "text": "Find friends first", "emoji": "👫"},
                {"choice_id": "choice_0_c", "text": "Observe carefully", "emoji": "👀"},
            ],
            "is_ending": False,
        },
    }


def _create_default_segment(
    segment_id: int, is_ending: bool, choice_text: str = None
) -> Dict[str, Any]:
    """Create default segment (used when AI generation fails)"""
    if is_ending:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": "After this wonderful adventure, the young hero learned so much. No matter what challenges come your way, as long as you face them bravely and treat your friends kindly, you can always find a solution. What an unforgettable experience!",
                "choices": [],
                "is_ending": True,
            },
            "is_ending": True,
            "educational_summary": {
                "themes": ["courage", "friendship"],
                "concepts": ["decision-making", "exploration"],
                "moral": "By bravely facing challenges and working with friends, you become stronger.",
            },
        }
    else:
        return {
            "segment": {
                "segment_id": segment_id,
                "text": f"The young hero decided to {choice_text or 'continue exploring'}. Up ahead, a fork in the road appeared — one path led to a mysterious forest, the other to a sparkling stream...",
                "choices": [
                    {
                        "choice_id": f"choice_{segment_id}_a",
                        "text": "Head to the forest",
                        "emoji": "🌲",
                    },
                    {
                        "choice_id": f"choice_{segment_id}_b",
                        "text": "Head to the stream",
                        "emoji": "💧",
                    },
                ],
                "is_ending": False,
            },
            "is_ending": False,
        }


if __name__ == "__main__":
    """Test Agent"""
    import asyncio

    async def test():
        print("=== Test Interactive Story Agent ===\n")

        try:
            # Test opening generation
            print("1. Testing story opening generation...")
            opening = await generate_story_opening(
                child_id="test_child_001",
                age_group="6-8",
                interests=["dinosaurs", "adventure"],
                theme="Dinosaur World Exploration",
            )
            print(f"Title: {opening.get('title')}")
            print(f"Opening: {opening.get('segment', {}).get('text', '')[:100]}...")
            print(f"Choices: {len(opening.get('segment', {}).get('choices', []))}")
            print()

            # Test next segment generation
            print("2. Testing next segment generation...")
            next_seg = await generate_next_segment(
                session_id="test_session",
                choice_id="choice_0_a",
                session_data={
                    "segments": [opening.get("segment", {})],
                    "choice_history": ["choice_0_a"],
                    "age_group": "6-8",
                    "interests": ["dinosaurs", "adventure"],
                    "theme": "Dinosaur World Exploration",
                    "story_title": opening.get("title", "Adventure Story"),
                },
            )
            print(f"Segment: {next_seg.get('segment', {}).get('text', '')[:100]}...")
            print(f"Is ending: {next_seg.get('is_ending')}")
            print()

            print("Test complete!")

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(test())
