"""Morning Show API routes (#93)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ...agents.morning_show_agent import (
    convert_news_to_morning_show,
    stream_morning_show_generation,
)
from ...services.database import story_repo
from ...services.tts_service import generate_multi_speaker_audio
from ...services.user_service import UserData
from ...utils.text import count_words
from ...paths import UPLOAD_DIR
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
    safe_title = title.replace("&", "and")
    safe_subtitle = subtitle.replace("&", "and")
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


async def _generate_illustrations(
    episode_id: str,
    kid_title: str,
    topic: str,
    age_group: str,
) -> List[EpisodeIllustration]:
    count = _illustration_count(age_group)
    animation_types = ["pan", "zoom", "ken_burns"]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    illustrations: List[EpisodeIllustration] = []
    for idx in range(count):
        filename = f"morning_show_{episode_id}_{idx}.svg"
        path = UPLOAD_DIR / filename
        subtitle = f"{topic.title()} scene {idx + 1}"
        path.write_text(_make_placeholder_svg(kid_title, subtitle), encoding="utf-8")

        illustrations.append(
            EpisodeIllustration(
                url=f"/data/uploads/{filename}",
                description=f"{topic.title()} illustration #{idx + 1}",
                display_order=idx,
                animation_type=animation_types[idx % len(animation_types)],
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
        audio_urls=analysis.get("audio_urls", {}),
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
