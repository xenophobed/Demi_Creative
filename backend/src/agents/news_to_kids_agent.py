"""News-to-kids conversion helpers.

This module intentionally uses deterministic text processing so API behavior
remains reliable in local/dev environments even when LLM integrations are not
available.
"""

import re
from typing import Any, AsyncGenerator, Dict, List, Optional


AGE_RULES: Dict[str, Dict[str, Any]] = {
    "3-5": {"max_sentences": 2, "max_words": 70, "tone": "warm and very simple"},
    "6-9": {"max_sentences": 3, "max_words": 110, "tone": "simple and curious"},
    "10-12": {"max_sentences": 4, "max_words": 150, "tone": "clear with a bit more detail"},
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
    rules = AGE_RULES.get(age_group, AGE_RULES["6-9"])
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
    del child_id, enable_audio, voice

    source = _normalize(news_text)
    if not source and news_url:
        source = f"Article source: {news_url}."

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
