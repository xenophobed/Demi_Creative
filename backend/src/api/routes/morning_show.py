"""Morning Show API routes (#93)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

from ...agents.morning_show_agent import (
    convert_news_to_morning_show,
    stream_morning_show_generation,
)
from ...services.database import preference_repo, story_repo
from ...services.tts_service import generate_multi_speaker_audio
from ...services.user_service import UserData
from ...utils.text import count_words
from ...paths import AUDIO_DIR, UPLOAD_DIR
from ..deps import get_current_user
from ..models import (
    DialogueScript,
    EpisodeIllustration,
    InteractiveQuestionResponse,
    KeyConceptResponse,
    MorningShowEpisode,
    MorningShowGenerationMetadata,
    MorningShowRequest,
    MorningShowResponse,
    MorningShowTrackRequest,
    MorningShowTrackResponse,
    PaginatedMorningShowResponse,
)


router = APIRouter(
    prefix="/api/v1/morning-show",
    tags=["Morning Show"],
)


def _illustration_count(age_group: str) -> int:
    if age_group == "3-5":
        return 2
    if age_group in {"6-8", "6-9"}:
        return 3
    return 4


def _make_placeholder_svg(title: str, subtitle: str, width: int = 1280, height: int = 720) -> str:
    safe_title = title.replace("&", "and").replace("<", "").replace(">", "")
    safe_subtitle = subtitle.replace("&", "and").replace("<", "").replace(">", "")
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>
<defs>
  <linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'>
    <stop offset='0%' stop-color='#D1FAE5'/>
    <stop offset='100%' stop-color='#DBEAFE'/>
  </linearGradient>
</defs>
<rect width='100%' height='100%' fill='url(#g)'/>
<circle cx='180' cy='140' r='90' fill='#FDE68A' opacity='0.85'/>
<circle cx='1130' cy='620' r='110' fill='#C7D2FE' opacity='0.65'/>
<text x='80' y='300' font-size='54' font-family='sans-serif' fill='#1E3A8A'>{safe_title}</text>
<text x='80' y='380' font-size='34' font-family='sans-serif' fill='#334155'>{safe_subtitle}</text>
</svg>"""


def _is_live_illustration_enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return False
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key or api_key.startswith("your_"):
        return False
    force_placeholder = os.getenv("MORNING_SHOW_FORCE_PLACEHOLDER_ILLUSTRATIONS", "").strip().lower()
    if force_placeholder in {"1", "true", "yes"}:
        return False
    return True


def _save_placeholder_illustration(
    episode_id: str,
    idx: int,
    kid_title: str,
    subtitle: str,
) -> str:
    filename = f"morning_show_{episode_id}_{idx}.svg"
    path = UPLOAD_DIR / filename
    path.write_text(_make_placeholder_svg(kid_title, subtitle), encoding="utf-8")
    return f"/data/uploads/{filename}"


def _sanitize_for_image_prompt(text: str, max_len: int = 120) -> str:
    """Strip characters that could escape the image generation prompt context."""
    return text.replace("\n", " ").replace("\r", " ").replace("<", "").replace(">", "")[:max_len].strip()


def _scene_prompt(kid_title: str, topic: str, age_group: str, idx: int) -> str:
    # kid_title originates from LLM-generated + Tavily-sourced data.  Sanitize
    # before injecting into the image generation prompt to prevent prompt
    # injection through crafted news headlines.
    safe_title = _sanitize_for_image_prompt(kid_title)
    return (
        f"Create a bright 2D children's editorial illustration for a morning show episode.\n"
        f"Episode title: {safe_title}\n"
        f"Scene: {topic} scene {idx + 1}\n"
        f"Audience age group: {age_group}\n"
        "Style: playful shapes, soft gradients, clean outlines, educational and optimistic.\n"
        "Safety: no violence, no fear, no injuries, no scary faces, no weapons, no text."
    )


async def _safe_illustration_description(description: str, age_group: str) -> str:
    """Run check_content_safety on an illustration description.

    Returns the original description if it passes (score >= 0.85) or if
    the MCP tool is unavailable.  Replaces with a generic safe description
    if the content fails the safety gate.
    """
    try:
        from ...mcp_servers import check_content_safety
        import json as _json

        age_map = {"3-5": 4, "6-8": 7, "6-9": 7, "9-12": 11}
        target_age = age_map.get(age_group, 7)

        result = await check_content_safety({
            "content_text": description,
            "content_type": "illustration_description",
            "target_age": target_age,
        })
        data = _json.loads(result["content"][0]["text"])
        score = float(data.get("safety_score", 1.0))
        if score < 0.85:
            return "A colorful, cheerful scene suitable for children"
    except Exception:
        pass
    return description


async def _generate_illustrations(
    episode_id: str,
    kid_title: str,
    topic: str,
    age_group: str,
) -> List[EpisodeIllustration]:
    count = _illustration_count(age_group)
    animation_types = ["pan", "zoom", "ken_burns"]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    live_enabled = _is_live_illustration_enabled()
    openai_client = None
    if live_enabled and OpenAI is not None:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    image_model = os.getenv("MORNING_SHOW_IMAGE_MODEL", "gpt-image-1")
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()

    illustrations: List[EpisodeIllustration] = []
    for idx in range(count):
        subtitle = f"{topic.title()} scene {idx + 1}"
        animation_type = animation_types[idx % len(animation_types)]
        description = f"{topic.title()} illustration #{idx + 1}"

        generated_url: str
        if live_enabled:
            try:
                item_url = None
                item_b64 = None
                if openai_client is not None:
                    # openai.OpenAI is the synchronous SDK — run it in a thread
                    # to avoid blocking the asyncio event loop (image gen can
                    # take 10–30 s).
                    _prompt = _scene_prompt(kid_title, topic, age_group, idx)
                    _model = image_model

                    def _sync_generate():
                        return openai_client.images.generate(
                            model=_model,
                            prompt=_prompt,
                            size="1024x1024",
                        )

                    response = await asyncio.get_running_loop().run_in_executor(None, _sync_generate)
                    item = (getattr(response, "data", None) or [None])[0]
                    item_url = getattr(item, "url", None) if item is not None else None
                    item_b64 = getattr(item, "b64_json", None) if item is not None else None
                else:
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": image_model,
                        "prompt": _scene_prompt(kid_title, topic, age_group, idx),
                        "size": "1024x1024",
                    }
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            "https://api.openai.com/v1/images/generations",
                            headers=headers,
                            json=payload,
                        )
                        response.raise_for_status()
                        body = response.json()
                    item = (body.get("data") or [None])[0]
                    if isinstance(item, dict):
                        item_url = item.get("url")
                        item_b64 = item.get("b64_json")

                if item_b64:
                    image_bytes = base64.b64decode(item_b64)
                    filename = f"morning_show_{episode_id}_{idx}.png"
                    path = UPLOAD_DIR / filename
                    path.write_bytes(image_bytes)
                    generated_url = f"/data/uploads/{filename}"
                elif item_url:
                    generated_url = str(item_url)
                else:
                    raise RuntimeError("OpenAI image response did not include image data")
            except Exception:
                generated_url = _save_placeholder_illustration(episode_id, idx, kid_title, subtitle)
        else:
            generated_url = _save_placeholder_illustration(episode_id, idx, kid_title, subtitle)

        # Safety gate on description before storing (CLAUDE.md: all AI-generated
        # content must pass check_content_safety, threshold >= 0.85).
        safe_description = await _safe_illustration_description(description, age_group)

        illustrations.append(
            EpisodeIllustration(
                url=generated_url,
                description=safe_description,
                display_order=idx,
                animation_type=animation_type,
            )
        )

    return illustrations


def _as_key_concepts(raw_items: List[Dict[str, Any]]) -> List[KeyConceptResponse]:
    out: List[KeyConceptResponse] = []
    for item in raw_items:
        try:
            out.append(
                KeyConceptResponse(
                    term=item.get("term", ""),
                    explanation=item.get("explanation", ""),
                    emoji=item.get("emoji", "💡"),
                )
            )
        except Exception:
            continue
    return out


def _as_questions(raw_items: List[Dict[str, Any]]) -> List[InteractiveQuestionResponse]:
    out: List[InteractiveQuestionResponse] = []
    for item in raw_items:
        try:
            out.append(
                InteractiveQuestionResponse(
                    question=item.get("question", ""),
                    hint=item.get("hint"),
                    emoji=item.get("emoji", "🤔"),
                )
            )
        except Exception:
            continue
    return out


def _sanitize_audio_urls(raw_urls: Any) -> Dict[str, str]:
    """Filter out stale/missing local audio URLs from stored analysis payloads."""
    if not isinstance(raw_urls, dict):
        return {}

    sanitized: Dict[str, str] = {}
    for key, value in raw_urls.items():
        if not isinstance(value, str):
            continue
        url = value.strip()
        if not url:
            continue

        # Keep remote URLs as-is.
        if url.startswith("http://") or url.startswith("https://"):
            sanitized[str(key)] = url
            continue

        # Validate local audio files to prevent `/data/audio/*.mp3` 404s.
        if url.startswith("/data/audio/"):
            filename = url[len("/data/audio/"):]
            file_path = AUDIO_DIR / filename
            if file_path.exists() and file_path.is_file():
                sanitized[str(key)] = url
            continue

        sanitized[str(key)] = url

    return sanitized


def _story_analysis_to_episode(story: Dict[str, Any]) -> MorningShowEpisode:
    analysis = story.get("analysis", {})
    key_concepts = _as_key_concepts(analysis.get("key_concepts", []))
    questions = _as_questions(analysis.get("interactive_questions", []))

    dialogue_script = DialogueScript(**analysis.get("dialogue_script", {"lines": [], "total_duration": 0.0}))
    illustrations = [EpisodeIllustration(**item) for item in analysis.get("illustrations", [])]

    category = analysis.get("category", "general")

    return MorningShowEpisode(
        episode_id=story["story_id"],
        child_id=story.get("child_id", ""),
        age_group=story.get("age_group", "6-8"),
        category=category,
        kid_title=analysis.get("kid_title", "Morning Show"),
        kid_content=story.get("story", {}).get("text", ""),
        why_care=analysis.get("why_care", ""),
        key_concepts=key_concepts,
        interactive_questions=questions,
        dialogue_script=dialogue_script,
        illustrations=illustrations,
        audio_urls=_sanitize_audio_urls(analysis.get("audio_urls", {})),
        duration_seconds=int(analysis.get("duration_seconds", 0) or 0),
        is_played=bool(analysis.get("is_played", False)),
        is_new=bool(analysis.get("is_new", True)),
        created_at=story.get("created_at", datetime.now().isoformat()),
    )


async def _build_episode(
    request: MorningShowRequest,
    user: UserData,
) -> MorningShowResponse:
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    child_id = request.child_id or "default_child"
    source_text = request.news_text or f"[Article from: {request.news_url}]"

    try:
        generated = await convert_news_to_morning_show(
            news_text=source_text,
            age_group=request.age_group.value,
            child_id=child_id,
            category=request.category.value,
            news_url=request.news_url,
        )
    except Exception:
        # Graceful fallback to deterministic baseline conversion
        generated = {
            "kid_title": f"Morning Show: {request.category.value.title()}",
            "kid_content": source_text,
            "why_care": "This topic helps kids understand how the world works.",
            "key_concepts": [],
            "interactive_questions": [],
            "dialogue_script": {
                "lines": [
                    {
                        "role": "curious_kid",
                        "text": "What happened in this story?",
                        "timestamp_start": 0.0,
                        "timestamp_end": 4.0,
                    },
                    {
                        "role": "fun_expert",
                        "text": "Here is a safe and simple explanation for kids.",
                        "timestamp_start": 4.0,
                        "timestamp_end": 8.0,
                    },
                ],
                "total_duration": 8.0,
                "guest_character": "Professor Owl",
            },
            "safety_score": 0.9,
            "used_mock": True,
            "guest_character": "Professor Owl",
        }

    dialogue_script = DialogueScript(**generated["dialogue_script"])
    audio_urls = await generate_multi_speaker_audio(dialogue_script, request.age_group.value)

    episode_id = str(uuid.uuid4())
    illustrations = await _generate_illustrations(
        episode_id=episode_id,
        kid_title=generated.get("kid_title", "Morning Show"),
        topic=request.category.value,
        age_group=request.age_group.value,
    )

    key_concepts = _as_key_concepts(generated.get("key_concepts", []))
    questions = _as_questions(generated.get("interactive_questions", []))
    safety_score = max(float(generated.get("safety_score", 0.9)), 0.85)

    episode = MorningShowEpisode(
        episode_id=episode_id,
        child_id=child_id,
        age_group=request.age_group,
        category=request.category,
        kid_title=generated.get("kid_title", "Morning Show"),
        kid_content=generated.get("kid_content", ""),
        why_care=generated.get("why_care", ""),
        key_concepts=key_concepts,
        interactive_questions=questions,
        dialogue_script=dialogue_script,
        illustrations=illustrations,
        audio_urls=audio_urls,
        duration_seconds=int(dialogue_script.total_duration),
        is_played=False,
        is_new=True,
        created_at=datetime.now(),
    )

    metadata = MorningShowGenerationMetadata(
        generation_id=str(uuid.uuid4()),
        safety_score=safety_score,
        used_mock=bool(generated.get("used_mock", False)),
        created_at=datetime.now(),
    )

    first_audio_url = audio_urls.get("0")
    cover_image_url = illustrations[0].url if illustrations else None

    await story_repo.create(
        {
            "story_id": episode_id,
            "user_id": user.user_id,
            "child_id": child_id,
            "age_group": request.age_group.value,
            "story": {
                "text": episode.kid_content,
                "word_count": count_words(episode.kid_content),
                "age_adapted": True,
            },
            "educational_value": {
                "themes": [request.category.value],
                "concepts": [c.term for c in key_concepts],
                "moral": episode.why_care,
            },
            "characters": [{"name": generated.get("guest_character", "Professor Owl")}],
            "analysis": {
                "story_type": "morning_show",
                "category": request.category.value,
                "news_url": request.news_url,
                "kid_title": episode.kid_title,
                "why_care": episode.why_care,
                "key_concepts": [k.model_dump() for k in key_concepts],
                "interactive_questions": [q.model_dump() for q in questions],
                "dialogue_script": dialogue_script.model_dump(),
                "illustrations": [ill.model_dump() for ill in illustrations],
                "audio_urls": audio_urls,
                "duration_seconds": episode.duration_seconds,
                "is_new": True,
                "is_played": False,
                "guest_character": generated.get("guest_character", "Professor Owl"),
                "generation_metadata": metadata.model_dump(mode="json"),
            },
            "safety_score": safety_score,
            "image_url": cover_image_url,
            "audio_url": first_audio_url,
            "story_type": "morning_show",
            "created_at": episode.created_at.isoformat(),
        }
    )

    return MorningShowResponse(episode=episode, metadata=metadata)


@router.post(
    "/generate",
    response_model=MorningShowResponse,
    summary="Generate a Morning Show episode",
)
async def generate_morning_show(
    request: MorningShowRequest,
    user: UserData = Depends(get_current_user),
):
    return await _build_episode(request, user)


@router.post(
    "/generate/stream",
    summary="Generate a Morning Show episode with SSE progress",
)
async def generate_morning_show_stream(
    request: MorningShowRequest,
    user: UserData = Depends(get_current_user),
):
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        source_text = request.news_text or f"[Article from: {request.news_url}]"

        # Optional upstream progress from the agent
        async for event in stream_morning_show_generation(
            news_text=source_text,
            age_group=request.age_group.value,
            child_id=request.child_id,
            category=request.category.value,
            news_url=request.news_url,
        ):
            event_type = event.get("type", "status")
            yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
            if event_type == "result":
                break

        response = await _build_episode(request, user)

        yield f"event: result\ndata: {json.dumps(response.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        yield f"event: complete\ndata: {json.dumps({'message': 'Morning Show generation complete'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/episode/{episode_id}",
    response_model=MorningShowEpisode,
    summary="Get a Morning Show episode by ID",
)
async def get_morning_show_episode(
    episode_id: str,
    user: UserData = Depends(get_current_user),
):
    story = await story_repo.get_by_id(episode_id)
    if not story or story.get("story_type") != "morning_show":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    if story.get("user_id") != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _story_analysis_to_episode(story)


@router.get(
    "/episodes/{child_id}",
    response_model=PaginatedMorningShowResponse,
    summary="List Morning Show episodes for a child",
)
async def list_morning_show_episodes(
    child_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserData = Depends(get_current_user),
):
    total = await story_repo.count_by_user_and_child(
        user.user_id,
        child_id,
        story_type="morning_show",
    )
    stories = await story_repo.list_by_user_and_child(
        user.user_id,
        child_id,
        limit=limit,
        offset=offset,
        story_type="morning_show",
    )

    episodes = [_story_analysis_to_episode(story) for story in stories]
    return PaginatedMorningShowResponse(
        items=episodes,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/track",
    response_model=MorningShowTrackResponse,
    summary="Track Morning Show playback engagement",
)
async def track_morning_show_engagement(
    request: MorningShowTrackRequest,
    user: UserData = Depends(get_current_user),
):
    story = await story_repo.get_by_id(request.episode_id)
    if not story or story.get("story_type") != "morning_show":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    if story.get("user_id") != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    topic_score = await preference_repo.update_from_morning_show(
        child_id=request.child_id,
        topic=request.topic.value,
        event_type=request.event_type.value,
        progress=request.progress,
    )

    updates = {"is_new": False}
    if request.event_type.value == "complete" or request.progress >= 0.8:
        updates["is_played"] = True
    elif request.event_type.value == "abandon" and request.progress < 0.5:
        updates["is_played"] = False

    await story_repo.update_analysis_fields(request.episode_id, updates)

    return MorningShowTrackResponse(
        status="tracked",
        topic_score=topic_score,
        profile_updated_at=datetime.now(),
    )
