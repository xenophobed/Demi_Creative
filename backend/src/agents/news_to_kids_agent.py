"""Fallback News-to-Kids agent implementation."""

import re
from typing import Any, AsyncGenerator, Dict, List, Optional


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _first_sentences(text: str, max_sentences: int = 3) -> str:
    cleaned = _normalize(text)
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return " ".join(parts[:max_sentences]).strip()


def _concepts(text: str) -> List[Dict[str, str]]:
    words = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text)
    seen = []
    for word in words:
        key = word.lower()
        if key not in seen:
            seen.append(key)
        if len(seen) >= 3:
            break

    if not seen:
        seen = ["news"]

    return [
        {
            "term": term,
            "explanation": f"{term.capitalize()} is a key idea from this story.",
            "emoji": "💡",
        }
        for term in seen
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

    summary = _first_sentences(source) or "There is a new story to learn from today."
    content = f"For ages {age_group}, here is a simple {category or 'general'} update: {summary}"

    return {
        "kid_title": f"Kid News: {(category or 'general').title()}",
        "kid_content": content,
        "why_care": "Learning about news helps kids understand the world and ask good questions.",
        "key_concepts": _concepts(source),
        "interactive_questions": [
            {
                "question": "What was the most interesting part of this story?",
                "hint": "Pick one detail and explain why.",
                "emoji": "🤔",
            },
            {
                "question": "What kind action could help in a story like this?",
                "hint": "Think about helping people, animals, or the planet.",
                "emoji": "✨",
            },
        ],
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
    yield {"type": "result", "data": result}
    yield {"type": "complete", "data": {"message": "Conversion complete"}}
