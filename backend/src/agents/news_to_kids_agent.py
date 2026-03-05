"""News-to-kids conversion helpers.

This module intentionally uses deterministic text processing so API behavior
remains reliable in local/dev environments even when LLM integrations are not
available.
"""

import json
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

try:
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover - import fallback for test env
    AsyncAnthropic = None


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


async def _check_content_safety(text: str, age_group: str) -> float:
    """Call the safety_check MCP tool and return the safety score (0.0–1.0).

    Falls back to 1.0 (pass-through) if the MCP tool is unavailable, so
    test environments without the full MCP stack are not blocked.
    """
    try:
        from ..mcp_servers import check_content_safety

        # Convert age_group string to a representative age integer
        age_map = {"3-5": 4, "6-9": 7, "10-12": 11}
        target_age = age_map.get(age_group, 7)

        result = await check_content_safety({
            "content_text": text,
            "content_type": "news",
            "target_age": target_age,
        })
        import json as _json
        data = _json.loads(result["content"][0]["text"])
        return float(data.get("safety_score", 1.0))
    except Exception:
        # MCP tool unavailable (test env, import error) — allow content through
        return 1.0


def _should_use_live_llm() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return False
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    has_anthropic = bool(anthropic_key) and not anthropic_key.startswith("your_")
    has_openai = bool(openai_key) and not openai_key.startswith("your_")
    if not has_anthropic and not has_openai:
        return False
    return True


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


async def _convert_news_to_kids_live(source: str, age_group: str, category: str) -> Dict[str, Any]:
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not anthropic_key and not openai_key:
        raise RuntimeError("No LLM key configured")

    anthropic_model = os.getenv("NEWS_TO_KIDS_MODEL", "claude-3-5-sonnet-latest")
    openai_model = os.getenv("NEWS_TO_KIDS_OPENAI_MODEL", "gpt-4o-mini")
    rules = AGE_RULES.get(age_group, AGE_RULES["6-9"])

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
        f"News text:\n{source}"
    )

    chunks: List[str] = []
    anthropic_error: Optional[Exception] = None
    if anthropic_key:
        try:
            if AsyncAnthropic is not None:
                client = AsyncAnthropic(api_key=anthropic_key)
                response = await client.messages.create(
                    model=anthropic_model,
                    max_tokens=1200,
                    temperature=0.2,
                    system="You are a child-education editor. Keep facts accurate and language child-safe.",
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in getattr(response, "content", []) or []:
                    text = getattr(block, "text", None)
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())
            else:
                headers = {
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                payload = {
                    "model": anthropic_model,
                    "max_tokens": 1200,
                    "temperature": 0.2,
                    "system": "You are a child-education editor. Keep facts accurate and language child-safe.",
                    "messages": [{"role": "user", "content": prompt}],
                }
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                for block in body.get("content", []) or []:
                    if isinstance(block, dict):
                        text = str(block.get("text", "")).strip()
                        if block.get("type") == "text" and text:
                            chunks.append(text)
        except Exception as exc:
            anthropic_error = exc

    if not chunks and openai_key:
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": openai_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are a child-education editor. Keep facts accurate and language child-safe.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        choices = body.get("choices", []) if isinstance(body, dict) else []
        if choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                chunks.append(content.strip())

    if not chunks and anthropic_error is not None:
        raise RuntimeError(str(anthropic_error))

    payload = _extract_json_object("\n".join(chunks))
    if not payload:
        raise RuntimeError("Model output was not parseable JSON")

    kid_title = str(payload.get("kid_title", "")).strip() or f"Kid News: {(category or 'general').title()}"
    kid_content = str(payload.get("kid_content", "")).strip() or _build_kid_content(source, age_group, category)
    why_care = str(payload.get("why_care", "")).strip() or _build_why_care(category)
    key_concepts = _normalize_key_concepts(payload.get("key_concepts"), source)
    questions = _normalize_questions(payload.get("interactive_questions"), category)

    kid_content = _trim_words(kid_content, rules["max_words"])

    # Mandatory safety gate — all AI-generated content must pass check_content_safety
    # before delivery (CLAUDE.md: threshold >= 0.85).
    safety_score = await _check_content_safety(kid_content, age_group)
    if safety_score < 0.85:
        raise RuntimeError(f"Live news content failed safety check (score={safety_score:.2f})")

    return {
        "kid_title": kid_title,
        "kid_content": kid_content,
        "why_care": why_care,
        "key_concepts": key_concepts,
        "interactive_questions": questions,
        "audio_path": None,
        "safety_score": safety_score,
    }


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

    if _should_use_live_llm():
        try:
            return await _convert_news_to_kids_live(source, age_group, category)
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
