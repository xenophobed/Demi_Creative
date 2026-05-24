"""Kids Daily API routes — kid-friendly news content under /api/v1/kids-daily."""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

logger = logging.getLogger(__name__)

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import fallback for test env
    OpenAI = None

from ...agents.kids_daily_agent import (
    generate_kids_daily_episode,
    generate_kids_daily_text,
    stream_kids_daily_generation,
    stream_kids_daily_text,
)
from ...mcp_servers import fetch_article_text as _raw_fetch_article
fetch_article_text = getattr(_raw_fetch_article, "handler", _raw_fetch_article)
from ...services.database import db_manager, preference_repo, story_repo, subscription_repo
from ...services.news_headline_fetcher import fetch_news_text
from ...services.provenance_tracker import ProvenanceTracker
from ...services.models.artifact_models import (
    ArtifactType,
    WorkflowType,
    StoryArtifactRole,
    ArtifactMetadata,
)
from ...services.tts_service import generate_multi_speaker_audio
from ...services.user_service import UserData
from ...utils.text import count_words
from ...paths import AUDIO_DIR, UPLOAD_DIR
from ..deps import (
    check_generation_quota,
    get_current_user,
    has_visible_hub_post,
    require_owned_child_profile,
)
from ...services.database import usage_repo
from ..models import (
    DialogueScript,
    EpisodeIllustration,
    InteractiveQuestionResponse,
    KeyConceptResponse,
    KidsDailyEpisode,
    KidsDailyGenerationMetadata,
    KidsDailyOnDemandRequest,
    KidsDailyRateLimitResponse,
    KidsDailyRequest,
    KidsDailyResponse,
    KidsDailyTextRequest,
    KidsDailyTextResponse,
    KidsDailyTrackRequest,
    KidsDailyTrackResponse,
    PaginatedKidsDailyResponse,
    PaginatedNewsResponse,
)


router = APIRouter(
    prefix="/api/v1/kids-daily",
    tags=["Kids Daily"],
)


# ===========================================================================
# Illustration helpers
# ===========================================================================

def _illustration_count(age_group: str) -> int:
    """One illustration per episode to control API costs when live generation is on."""
    return 1


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


def _is_live_illustration_enabled() -> bool:
    """Live image generation is OFF by default to avoid per-request API costs.

    Set ``KIDS_DAILY_LIVE_ILLUSTRATIONS=1`` (or legacy ``MORNING_SHOW_LIVE_ILLUSTRATIONS=1``) to opt in.
    """
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return False
    opt_in = os.getenv("KIDS_DAILY_LIVE_ILLUSTRATIONS",
                       os.getenv("MORNING_SHOW_LIVE_ILLUSTRATIONS", "")).strip().lower()
    if opt_in not in {"1", "true", "yes"}:
        return False
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key or api_key.startswith("your_"):
        return False
    return True


def _save_placeholder_illustration(
    episode_id: str,
    idx: int,
    kid_title: str,
    subtitle: str,
) -> str:
    filename = f"kids_daily_{episode_id}_{idx}.svg"
    path = UPLOAD_DIR / filename
    path.write_text(_make_placeholder_svg(kid_title, subtitle), encoding="utf-8")
    return f"/data/uploads/{filename}"


def _scene_prompt(kid_title: str, topic: str, age_group: str, idx: int) -> str:
    return (
        f"Create a bright 2D children's editorial illustration for a Kids Daily episode.\n"
        f"Episode title: {kid_title}\n"
        f"Scene: {topic} scene {idx + 1}\n"
        f"Audience age group: {age_group}\n"
        "Style: playful shapes, soft gradients, clean outlines, educational and optimistic.\n"
        "Safety: no violence, no fear, no injuries, no scary faces, no weapons, no text."
    )


async def _safe_illustration_description(description: str, age_group: str) -> str:
    """Run check_content_safety on an illustration description."""
    try:
        from ...mcp_servers import check_content_safety as _raw_safety
        check_content_safety = getattr(_raw_safety, "handler", _raw_safety)
        import json as _json

        age_map = {"3-5": 4, "6-8": 7, "9-12": 11}
        target_age = age_map.get(age_group, 7)

        result = await check_content_safety({
            "content_text": description,
            "content_type": "illustration_description",
            "target_age": target_age,
        })
        data = _json.loads(result["content"][0]["text"])
        if "error" in data:
            logger.warning("Safety MCP returned error for illustration, using safe fallback")
            return "A colorful, cheerful scene suitable for children"
        score = float(data.get("safety_score", 0.0))
        if score < 0.85:
            return "A colorful, cheerful scene suitable for children"
    except Exception:
        logger.warning(
            "Safety check unavailable for illustration, using safe fallback (fail-closed)",
            exc_info=True,
        )
        return "A colorful, cheerful scene suitable for children"
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
    image_model = os.getenv("KIDS_DAILY_IMAGE_MODEL",
                            os.getenv("MORNING_SHOW_IMAGE_MODEL", "gpt-image-1-mini"))
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
                    response = openai_client.images.generate(
                        model=image_model,
                        prompt=_scene_prompt(kid_title, topic, age_group, idx),
                        size="1024x1024",
                    )
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
                    filename = f"kids_daily_{episode_id}_{idx}.png"
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


# ===========================================================================
# Shared helpers
# ===========================================================================

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

        if url.startswith("http://") or url.startswith("https://"):
            sanitized[str(key)] = url
            continue

        if url.startswith("/data/audio/"):
            filename = url[len("/data/audio/"):]
            file_path = AUDIO_DIR / filename
            if file_path.exists() and file_path.is_file():
                sanitized[str(key)] = url
            continue

        sanitized[str(key)] = url

    return sanitized


def _story_analysis_to_episode(story: Dict[str, Any]) -> KidsDailyEpisode:
    analysis = story.get("analysis", {})
    key_concepts = _as_key_concepts(analysis.get("key_concepts", []))
    questions = _as_questions(analysis.get("interactive_questions", []))

    dialogue_script = DialogueScript(**analysis.get("dialogue_script", {"lines": [], "total_duration": 0.0}))
    illustrations = [EpisodeIllustration(**item) for item in analysis.get("illustrations", [])]
    audio_urls = _sanitize_audio_urls(analysis.get("audio_urls", {}))
    kid_content = story.get("story", {}).get("text", "")

    # Legacy fallback: text-only conversions stored a single top-level audio_url
    # and no dialogue script. Synthesize a one-line dialogue so the unified
    # Kids Daily player can render and play them.
    if not dialogue_script.lines and story.get("audio_url"):
        legacy_audio = story["audio_url"]
        if not audio_urls:
            audio_urls = {"0": legacy_audio}
        dialogue_script = DialogueScript(
            lines=[{
                "role": "fun_expert",
                "text": kid_content or analysis.get("kid_title", ""),
                "display_name": "Duo",
                "timestamp_start": 0.0,
                "timestamp_end": float(analysis.get("duration_seconds") or 30.0),
            }],
            total_duration=float(analysis.get("duration_seconds") or 30.0),
            guest_character=analysis.get("guest_character", "Professor Owl"),
        )

    category = analysis.get("category", "general")

    return KidsDailyEpisode(
        episode_id=story["story_id"],
        child_id=story.get("child_id", ""),
        age_group=story.get("age_group", "6-8"),
        category=category,
        kid_title=analysis.get("kid_title", "Kids Daily"),
        kid_content=kid_content,
        why_care=analysis.get("why_care", ""),
        key_concepts=key_concepts,
        interactive_questions=questions,
        dialogue_script=dialogue_script,
        illustrations=illustrations,
        audio_urls=audio_urls,
        duration_seconds=int(analysis.get("duration_seconds", 0) or 0),
        is_played=bool(analysis.get("is_played", False)),
        is_new=bool(analysis.get("is_new", True)),
        is_degraded=bool(analysis.get("is_degraded", False)),
        degraded_reason=analysis.get("degraded_reason"),
        created_at=story.get("created_at", datetime.now().isoformat()),
    )


async def _fetch_text_from_url(url: str) -> str:
    """Fetch article text from a URL via the web-search MCP tool.

    Raises ``HTTPException`` (422) when the article cannot be retrieved.
    """
    try:
        result = await fetch_article_text({"url": url})
        data = json.loads(result["content"][0]["text"])
        text = (data.get("text") or "").strip()
        if not text or data.get("error"):
            error_detail = data.get("error", "empty article body")
            logger.warning("Failed to fetch article from %s: %s", url, error_detail)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not fetch article text from URL: {error_detail}",
            )
        return text
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error fetching article from %s: %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch article text from URL: {exc}",
        )


# ===========================================================================
# Episode builder (core pipeline)
# ===========================================================================

async def _build_episode(
    request: KidsDailyRequest,
    user: UserData,
    source: str = "manual",
) -> KidsDailyResponse:
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    child_id = request.child_id or "default_child"
    source_text = request.news_text or ""
    if request.news_url and not source_text:
        source_text = await _fetch_text_from_url(request.news_url)

    try:
        generated = await generate_kids_daily_episode(
            news_text=source_text,
            age_group=request.age_group.value,
            child_id=child_id,
            category=request.category.value,
            news_url=request.news_url,
            user_id=user.user_id,
        )
    except Exception:
        # Graceful fallback to deterministic baseline conversion
        generated = {
            "kid_title": f"Kids Daily: {request.category.value.title()}",
            "kid_content": source_text,
            "why_care": "This topic helps kids understand how the world works.",
            "key_concepts": [],
            "interactive_questions": [],
            "dialogue_script": {
                "lines": [
                    {
                        "role": "curious_kid",
                        "text": "Mimi: What happened in this story?",
                        "display_name": "Mimi",
                        "timestamp_start": 0.0,
                        "timestamp_end": 4.0,
                    },
                    {
                        "role": "fun_expert",
                        "text": "Duo: Here is a safe and simple explanation for kids.",
                        "display_name": "Duo",
                        "timestamp_start": 4.0,
                        "timestamp_end": 8.0,
                    },
                ],
                "total_duration": 8.0,
                "guest_character": "Professor Owl",
            },
            "safety_score": 0.0,
            "used_mock": True,
            "degraded_reason": "agent_fallback",
            "guest_character": "Professor Owl",
        }

    dialogue_script = DialogueScript(**generated["dialogue_script"])
    audio_urls = await generate_multi_speaker_audio(dialogue_script, request.age_group.value)

    episode_id = str(uuid.uuid4())
    illustrations = await _generate_illustrations(
        episode_id=episode_id,
        kid_title=generated.get("kid_title", "Kids Daily"),
        topic=request.category.value,
        age_group=request.age_group.value,
    )

    key_concepts = _as_key_concepts(generated.get("key_concepts", []))
    questions = _as_questions(generated.get("interactive_questions", []))
    safety_score = float(generated.get("safety_score", 0.0))
    used_mock = bool(generated.get("used_mock", False))
    degraded_reason = generated.get("degraded_reason")
    is_degraded = used_mock

    episode = KidsDailyEpisode(
        episode_id=episode_id,
        child_id=child_id,
        age_group=request.age_group,
        category=request.category,
        kid_title=generated.get("kid_title", "Kids Daily"),
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
        is_degraded=is_degraded,
        degraded_reason=degraded_reason,
        created_at=datetime.now(),
    )

    metadata = KidsDailyGenerationMetadata(
        generation_id=str(uuid.uuid4()),
        safety_score=safety_score,
        used_mock=used_mock,
        is_degraded=is_degraded,
        degraded_reason=degraded_reason,
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
                "story_type": "kids_daily",
                "source": source,
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
                "is_degraded": is_degraded,
                "degraded_reason": degraded_reason,
                "guest_character": generated.get("guest_character", "Professor Owl"),
                "generation_metadata": metadata.model_dump(mode="json"),
            },
            "safety_score": safety_score,
            "image_url": cover_image_url,
            "audio_url": first_audio_url,
            "story_type": "kids_daily",
            "created_at": episode.created_at.isoformat(),
        }
    )

    try:
        await preference_repo.update_from_news(
            child_id=child_id,
            category=request.category.value,
            key_concepts=[k.model_dump() for k in key_concepts],
            user_id=user.user_id,
        )
    except Exception:
        logger.warning(
            "Preference update failed for kids daily episode %s",
            episode_id,
            exc_info=True,
        )

    # --- Provenance tracking (#141) — never blocks content delivery ---
    try:
        tracker = ProvenanceTracker(db_manager)
        run_id = await tracker.start_run(episode_id, WorkflowType.KIDS_DAILY)

        # Step 1: news conversion
        step1_id = await tracker.start_step(run_id, "news_conversion", 1,
            input_data={"category": request.category.value, "age_group": request.age_group.value})
        text_art_id = await tracker.record_artifact(
            step1_id, ArtifactType.TEXT, run_id=run_id,
            artifact_payload=episode.kid_content,
            description="Kids Daily converted news text",
            safety_score=safety_score,
            agent_name="kids_daily",
            metadata=ArtifactMetadata(
                word_count=count_words(episode.kid_content),
                custom={
                    "is_degraded": is_degraded,
                    "degraded_reason": degraded_reason,
                },
            ),
        )
        script_art_id = await tracker.record_artifact(
            step1_id, ArtifactType.JSON, run_id=run_id,
            artifact_payload=dialogue_script.model_dump_json(),
            description="Kids Daily dialogue script",
            safety_score=safety_score,
            agent_name="kids_daily",
            input_artifact_ids=[text_art_id],
            metadata=ArtifactMetadata(
                custom={
                    "script_format": "dialogue",
                    "line_count": len(dialogue_script.lines),
                    "is_degraded": is_degraded,
                    "degraded_reason": degraded_reason,
                },
            ),
        )
        await tracker.complete_step(step1_id, output_data={
            "text_artifact_id": text_art_id,
            "script_artifact_id": script_art_id,
        })

        # Step 2: TTS generation
        step2_id = await tracker.start_step(run_id, "tts_generation", 2,
            input_data={"dialogue_lines": len(dialogue_script.lines)})
        audio_art_ids = []
        for idx_str, url in audio_urls.items():
            aid = await tracker.record_artifact(
                step2_id, ArtifactType.AUDIO, run_id=run_id,
                artifact_url=url,
                description=f"Kids Daily TTS audio segment {idx_str}",
                mime_type="audio/mpeg",
                agent_name="tts_generation",
                input_artifact_ids=[script_art_id],
            )
            audio_art_ids.append(aid)
        await tracker.complete_step(step2_id, output_data={"audio_count": len(audio_art_ids)})

        # Step 3: illustration generation
        step3_id = await tracker.start_step(run_id, "illustration_generation", 3,
            input_data={"illustration_count": len(illustrations)})
        illust_art_ids = []
        for ill in illustrations:
            iid = await tracker.record_artifact(
                step3_id, ArtifactType.IMAGE, run_id=run_id,
                artifact_url=ill.url,
                description=ill.description,
                agent_name="illustration_generation",
                input_artifact_ids=[script_art_id],
            )
            illust_art_ids.append(iid)
        await tracker.complete_step(step3_id, output_data={"illustration_count": len(illust_art_ids)})

        # Promote and link artifacts
        artifact_repo = tracker._artifact_repo
        await artifact_repo.update_lifecycle_state(text_art_id, "candidate")
        await artifact_repo.update_lifecycle_state(text_art_id, "published")
        await tracker.link_to_story(episode_id, text_art_id, StoryArtifactRole.STORY_TEXT)

        await artifact_repo.update_lifecycle_state(script_art_id, "candidate")
        await artifact_repo.update_lifecycle_state(script_art_id, "published")
        await tracker.link_to_story(
            episode_id, script_art_id, StoryArtifactRole.STORY_TEXT, is_primary=False
        )

        for aid in audio_art_ids:
            await artifact_repo.update_lifecycle_state(aid, "candidate")
            await artifact_repo.update_lifecycle_state(aid, "published")
            await tracker.link_to_story(episode_id, aid, StoryArtifactRole.FINAL_AUDIO, is_primary=False)

        for idx, iid in enumerate(illust_art_ids):
            await artifact_repo.update_lifecycle_state(iid, "candidate")
            await artifact_repo.update_lifecycle_state(iid, "published")
            role = StoryArtifactRole.COVER if idx == 0 else StoryArtifactRole.SCENE_IMAGE
            await tracker.link_to_story(episode_id, iid, role, is_primary=(idx == 0), position=idx)

        await tracker.complete_run(run_id, result_summary={
            "artifacts_created": 2 + len(audio_art_ids) + len(illust_art_ids),
            "episode_id": episode_id,
        })
    except Exception:
        logger.warning("Provenance tracking failed for kids daily episode %s", episode_id, exc_info=True)

    return KidsDailyResponse(episode=episode, metadata=metadata)


# ===========================================================================
# Episode endpoints
# ===========================================================================

@router.post(
    "/generate",
    response_model=KidsDailyResponse,
    summary="Generate a Kids Daily episode",
)
async def generate_kids_daily(
    request: KidsDailyRequest,
    user: UserData = Depends(check_generation_quota),
):
    await require_owned_child_profile(user, request.child_id)
    result = await _build_episode(request, user)
    await usage_repo.increment(user.user_id, "kids_daily")
    return result


_ON_DEMAND_MAX_PER_HOUR = 3


@router.post(
    "/generate-now",
    response_model=KidsDailyResponse,
    summary="Generate a Kids Daily episode on demand (auto-fetches headlines)",
    responses={
        429: {"model": KidsDailyRateLimitResponse, "description": "Rate limit exceeded"},
    },
)
async def generate_kids_daily_on_demand(
    request: KidsDailyOnDemandRequest,
    user: UserData = Depends(check_generation_quota),
):
    """On-demand generation: fetches live headlines and builds an episode."""
    await require_owned_child_profile(user, request.child_id)
    topic = request.category.value

    # 1. Verify the child has an active subscription for this category
    has_sub = await subscription_repo.has_active_subscription(
        user.user_id, request.child_id, topic,
    )
    if not has_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please subscribe to this channel first",
        )

    # 2. Rate limit: max N on-demand generations per child per hour
    since = (datetime.now() - timedelta(hours=1)).isoformat()
    recent_count = await story_repo.count_recent_on_demand(
        request.child_id,
        since,
        user.user_id,
    )
    if recent_count >= _ON_DEMAND_MAX_PER_HOUR:
        oldest_ts = await story_repo.get_oldest_recent_on_demand_ts(
            request.child_id,
            since,
            user.user_id,
        )
        retry_after = 3600  # fallback
        if oldest_ts:
            try:
                oldest_dt = datetime.fromisoformat(oldest_ts)
                retry_after = max(0, int((oldest_dt + timedelta(hours=1) - datetime.now()).total_seconds()))
            except (ValueError, TypeError):
                pass
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "message": f"You've listened to a lot today! Try again in {retry_after // 60} minutes",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Fetch live headlines
    news_text = await fetch_news_text(topic)
    if news_text is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fresh news available right now, please try again in a few minutes",
        )

    # 4. Build episode using the shared pipeline
    build_request = KidsDailyRequest(
        child_id=request.child_id,
        age_group=request.age_group,
        category=request.category,
        news_text=news_text,
        news_url=None,
    )
    result = await _build_episode(build_request, user, source="on_demand")
    await usage_repo.increment(user.user_id, "kids_daily")
    return result


@router.post(
    "/generate-now/stream",
    summary="Generate a Kids Daily episode on demand with SSE progress",
    responses={
        429: {"model": KidsDailyRateLimitResponse, "description": "Rate limit exceeded"},
    },
)
async def generate_kids_daily_on_demand_stream(
    http_request: Request,
    request: KidsDailyOnDemandRequest,
    user: UserData = Depends(check_generation_quota),
):
    """On-demand SSE streaming generation: fetches live headlines and streams progress."""
    await require_owned_child_profile(user, request.child_id)
    topic = request.category.value

    # 1. Verify subscription
    has_sub = await subscription_repo.has_active_subscription(
        user.user_id, request.child_id, topic,
    )
    if not has_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please subscribe to this channel first",
        )

    # 2. Rate limit
    since = (datetime.now() - timedelta(hours=1)).isoformat()
    recent_count = await story_repo.count_recent_on_demand(
        request.child_id,
        since,
        user.user_id,
    )
    if recent_count >= _ON_DEMAND_MAX_PER_HOUR:
        oldest_ts = await story_repo.get_oldest_recent_on_demand_ts(
            request.child_id,
            since,
            user.user_id,
        )
        retry_after = 3600
        if oldest_ts:
            try:
                oldest_dt = datetime.fromisoformat(oldest_ts)
                retry_after = max(0, int((oldest_dt + timedelta(hours=1) - datetime.now()).total_seconds()))
            except (ValueError, TypeError):
                pass
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "message": f"You've listened to a lot today! Try again in {retry_after // 60} minutes",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Fetch live headlines BEFORE entering SSE generator
    news_text = await fetch_news_text(topic)
    if news_text is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fresh news available right now, please try again in a few minutes",
        )

    build_request = KidsDailyRequest(
        child_id=request.child_id,
        age_group=request.age_group,
        category=request.category,
        news_text=news_text,
        news_url=None,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"event: status\ndata: {json.dumps({'phase': 'fetching_news', 'message': 'Fetching news...'}, ensure_ascii=False)}\n\n"

        if await http_request.is_disconnected():
            logger.info("Client disconnected during on-demand stream, aborting")
            return

        yield f"event: status\ndata: {json.dumps({'phase': 'generating_script', 'message': 'Generating script...'}, ensure_ascii=False)}\n\n"

        async for event in stream_kids_daily_generation(
            news_text=news_text,
            age_group=build_request.age_group.value,
            child_id=build_request.child_id,
            category=build_request.category.value,
            news_url=None,
            user_id=user.user_id,
        ):
            if await http_request.is_disconnected():
                logger.info("Client disconnected during on-demand script generation, aborting")
                return

            event_type = event.get("type", "status")
            yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
            if event_type == "result":
                break

        if await http_request.is_disconnected():
            logger.info("Client disconnected before on-demand audio/illustration, skipping")
            return

        yield f"event: status\ndata: {json.dumps({'phase': 'generating_audio', 'message': 'Generating audio...'}, ensure_ascii=False)}\n\n"

        if await http_request.is_disconnected():
            return

        yield f"event: status\ndata: {json.dumps({'phase': 'generating_illustrations', 'message': 'Generating illustrations...'}, ensure_ascii=False)}\n\n"

        if await http_request.is_disconnected():
            return

        try:
            response = await _build_episode(build_request, user, source="on_demand")
            await usage_repo.increment(user.user_id, "kids_daily")

            yield f"event: result\ndata: {json.dumps(response.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            yield f"event: complete\ndata: {json.dumps({'phase': 'complete', 'message': 'Kids Daily generation complete'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("On-demand kids daily build failed: %s", exc)
            yield f"event: error\ndata: {json.dumps({'phase': 'error', 'message': 'Episode generation failed, please try again later'}, ensure_ascii=False)}\n\n"
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/generate/stream",
    summary="Generate a Kids Daily episode with SSE progress",
)
async def generate_kids_daily_stream(
    http_request: Request,
    request: KidsDailyRequest,
    user: UserData = Depends(check_generation_quota),
):
    await require_owned_child_profile(user, request.child_id)
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    source_text = request.news_text or ""
    if request.news_url and not source_text:
        source_text = await _fetch_text_from_url(request.news_url)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in stream_kids_daily_generation(
            news_text=source_text,
            age_group=request.age_group.value,
            child_id=request.child_id,
            category=request.category.value,
            news_url=request.news_url,
            user_id=user.user_id,
        ):
            if await http_request.is_disconnected():
                logger.info("Client disconnected during kids daily generation, aborting")
                return

            event_type = event.get("type", "status")
            yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
            if event_type == "result":
                break

        if await http_request.is_disconnected():
            logger.info("Client disconnected before kids daily save, skipping persist")
            return

        response = await _build_episode(request, user)
        await usage_repo.increment(user.user_id, "kids_daily")

        yield f"event: result\ndata: {json.dumps(response.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        yield f"event: complete\ndata: {json.dumps({'message': 'Kids Daily generation complete'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===========================================================================
# Text-only conversion endpoints (legacy news-to-kids)
# ===========================================================================

@router.post(
    "/convert",
    response_model=KidsDailyTextResponse,
    summary="Convert news to kid-friendly text content",
    description="Convert a news article into age-appropriate text for children (without dialogue)",
)
async def convert_news(
    request: KidsDailyTextRequest,
    user: UserData = Depends(get_current_user),
):
    """Convert news article to kid-friendly text content. Requires authentication."""
    await require_owned_child_profile(user, request.child_id)
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = await _fetch_text_from_url(request.news_url)

    try:
        result = await generate_kids_daily_text(
            news_text=news_text,
            age_group=request.age_group.value,
            child_id=request.child_id,
            category=request.category.value,
            news_url=request.news_url,
            enable_audio=request.enable_audio,
            voice=request.voice.value if request.voice else None,
            user_id=user.user_id,
        )

        conversion_id = str(uuid.uuid4())
        used_mock = bool(result.get("used_mock", False))
        degraded_reason = result.get("degraded_reason")
        is_degraded = used_mock

        audio_url = None
        if result.get("audio_path"):
            audio_filename = Path(result["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        story_data = {
            "story_id": conversion_id,
            "user_id": user.user_id,
            "child_id": request.child_id,
            "age_group": request.age_group.value,
            "story": {
                "text": result.get("kid_content", ""),
                "word_count": count_words(result.get("kid_content", "")),
                "age_adapted": True,
            },
            "educational_value": {
                "themes": [request.category.value],
                "concepts": [c.get("term", "") for c in result.get("key_concepts", [])],
                "moral": result.get("why_care"),
            },
            "characters": [],
            "analysis": {
                "story_type": "kids_daily",
                "category": request.category.value,
                "original_url": request.news_url,
                "kid_title": result.get("kid_title", ""),
                "why_care": result.get("why_care", ""),
                "key_concepts": result.get("key_concepts", []),
                "interactive_questions": result.get("interactive_questions", []),
                "used_mock": used_mock,
                "is_degraded": is_degraded,
                "degraded_reason": degraded_reason,
            },
            "story_type": "kids_daily",
            "safety_score": result.get("safety_score", 0.0),
            "audio_url": audio_url,
        }
        await story_repo.create(story_data)

        try:
            await preference_repo.update_from_news(
                child_id=request.child_id,
                category=request.category.value,
                key_concepts=result.get("key_concepts", []),
                user_id=user.user_id,
            )
        except Exception:
            pass  # Non-critical

        key_concepts = [
            KeyConceptResponse(
                term=c.get("term", ""),
                explanation=c.get("explanation", ""),
                emoji=c.get("emoji", "💡"),
            )
            for c in result.get("key_concepts", [])
        ]

        interactive_questions = [
            InteractiveQuestionResponse(
                question=q.get("question", ""),
                hint=q.get("hint"),
                emoji=q.get("emoji", "🤔"),
            )
            for q in result.get("interactive_questions", [])
        ]

        # --- Provenance tracking ---
        try:
            tracker = ProvenanceTracker(db_manager)
            run_id = await tracker.start_run(conversion_id, WorkflowType.KIDS_DAILY)

            step1_id = await tracker.start_step(run_id, "news_conversion", 1,
                input_data={"category": request.category.value, "age_group": request.age_group.value})
            text_art_id = await tracker.record_artifact(
                step1_id, ArtifactType.TEXT, run_id=run_id,
                artifact_payload=result.get("kid_content", ""),
                description="Converted news text for kids",
                safety_score=result.get("safety_score"),
                agent_name="kids_daily",
                metadata=ArtifactMetadata(
                    word_count=count_words(result.get("kid_content", "")),
                    custom={
                        "is_degraded": is_degraded,
                        "degraded_reason": degraded_reason,
                    },
                ),
            )
            await tracker.complete_step(step1_id, output_data={"text_artifact_id": text_art_id})

            if audio_url:
                step2_id = await tracker.start_step(run_id, "tts_generation", 2,
                    input_data={"voice": request.voice.value if request.voice else "default"})
                audio_art_id = await tracker.record_artifact(
                    step2_id, ArtifactType.AUDIO, run_id=run_id,
                    artifact_url=audio_url,
                    description="News narration audio",
                    mime_type="audio/mpeg",
                    agent_name="tts_generation",
                    input_artifact_ids=[text_art_id],
                )
                await tracker.complete_step(step2_id, output_data={"audio_artifact_id": audio_art_id})

                art_repo = tracker._artifact_repo
                await art_repo.update_lifecycle_state(audio_art_id, "candidate")
                await art_repo.update_lifecycle_state(audio_art_id, "published")
                await tracker.link_to_story(conversion_id, audio_art_id, StoryArtifactRole.FINAL_AUDIO)

            art_repo = tracker._artifact_repo
            await art_repo.update_lifecycle_state(text_art_id, "candidate")
            await art_repo.update_lifecycle_state(text_art_id, "published")
            await tracker.link_to_story(conversion_id, text_art_id, StoryArtifactRole.STORY_TEXT)

            await tracker.complete_run(run_id, result_summary={
                "artifacts_created": 2 if audio_url else 1,
                "conversion_id": conversion_id,
            })
        except Exception:
            logger.warning("Provenance tracking failed for news conversion %s", conversion_id, exc_info=True)

        return KidsDailyTextResponse(
            conversion_id=conversion_id,
            kid_title=result.get("kid_title", "News for Kids"),
            kid_content=result.get("kid_content", ""),
            why_care=result.get("why_care", ""),
            key_concepts=key_concepts,
            interactive_questions=interactive_questions,
            category=request.category,
            age_group=request.age_group,
            audio_url=audio_url,
            original_url=request.news_url,
            is_degraded=is_degraded,
            degraded_reason=degraded_reason,
            created_at=datetime.now(),
        )

    except Exception as e:
        print(f"Error converting news: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert news article",
        )


@router.post(
    "/convert/stream",
    summary="Convert news to kid-friendly text content (streaming)",
    description="Convert news with SSE streaming progress updates",
)
async def convert_news_stream(
    http_request: Request,
    request: KidsDailyTextRequest,
    user: UserData = Depends(get_current_user),
):
    """Stream text conversion with Server-Sent Events. Requires authentication."""
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = await _fetch_text_from_url(request.news_url)

    async def event_generator() -> AsyncGenerator[str, None]:
        client_disconnected = False
        try:
            async for event in stream_kids_daily_text(
                news_text=news_text,
                age_group=request.age_group.value,
                child_id=request.child_id,
                category=request.category.value,
                news_url=request.news_url,
                enable_audio=request.enable_audio,
                voice=request.voice.value if request.voice else None,
            ):
                if await http_request.is_disconnected():
                    logger.info("Client disconnected during news conversion, aborting")
                    client_disconnected = True
                    break

                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    if await http_request.is_disconnected():
                        logger.info("Client disconnected before news save, skipping persist")
                        client_disconnected = True
                        break

                    conversion_id = str(uuid.uuid4())
                    audio_url = None
                    if event_data.get("audio_path"):
                        audio_filename = Path(event_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    used_mock = bool(event_data.get("used_mock", False))
                    degraded_reason = event_data.get("degraded_reason")
                    is_degraded = used_mock

                    story_data = {
                        "story_id": conversion_id,
                        "user_id": user.user_id,
                        "child_id": request.child_id,
                        "age_group": request.age_group.value,
                        "story": {
                            "text": event_data.get("kid_content", ""),
                            "word_count": count_words(event_data.get("kid_content", "")),
                            "age_adapted": True,
                        },
                        "educational_value": {
                            "themes": [request.category.value],
                            "concepts": [c.get("term", "") for c in event_data.get("key_concepts", [])],
                            "moral": event_data.get("why_care"),
                        },
                        "characters": [],
                        "analysis": {
                            "story_type": "kids_daily",
                            "category": request.category.value,
                            "original_url": request.news_url,
                            "kid_title": event_data.get("kid_title", ""),
                            "why_care": event_data.get("why_care", ""),
                            "key_concepts": event_data.get("key_concepts", []),
                            "interactive_questions": event_data.get("interactive_questions", []),
                            "used_mock": used_mock,
                            "is_degraded": is_degraded,
                            "degraded_reason": degraded_reason,
                        },
                        "story_type": "kids_daily",
                        "safety_score": event_data.get("safety_score", 0.0),
                        "audio_url": audio_url,
                    }
                    await story_repo.create(story_data)

                    try:
                        await preference_repo.update_from_news(
                            child_id=request.child_id,
                            category=request.category.value,
                            key_concepts=event_data.get("key_concepts", []),
                            user_id=user.user_id,
                        )
                    except Exception:
                        pass  # Non-critical

                    event_data["conversion_id"] = conversion_id
                    event_data["audio_url"] = audio_url
                    event_data["category"] = request.category.value
                    event_data["age_group"] = request.age_group.value
                    event_data["original_url"] = request.news_url

                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_data = {"error": str(e), "message": "News conversion failed"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

        if client_disconnected:
            logger.info("News streaming aborted due to client disconnect; content was not saved")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===========================================================================
# Read endpoints
# ===========================================================================

@router.get(
    "/episode/{episode_id}",
    response_model=KidsDailyEpisode,
    summary="Get a Kids Daily episode by ID",
)
async def get_kids_daily_episode(
    episode_id: str,
    user: UserData = Depends(get_current_user),
):
    story = await story_repo.get_by_id(episode_id)
    if not story or story.get("story_type") not in ("kids_daily", "morning_show", "news_to_kids"):  # legacy DB compat
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    if story.get("user_id") != user.user_id:
        is_shared = await has_visible_hub_post(
            source_id=episode_id,
            source_types=("kids_daily",),
            user_id=user.user_id,
        )
        if not is_shared:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _story_analysis_to_episode(story)


@router.get(
    "/conversion/{conversion_id}",
    response_model=KidsDailyTextResponse,
    summary="Get a saved news conversion by ID",
)
async def get_news_conversion(
    conversion_id: str,
    user: UserData = Depends(get_current_user),
):
    """Retrieve a saved text conversion by its ID. Requires authentication."""
    story = await story_repo.get_by_id(conversion_id)
    if not story or story.get("story_type") not in ("kids_daily", "news_to_kids", "morning_show"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversion not found")

    if story.get("user_id") != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversion not found")

    analysis = story.get("analysis", {})
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except (json.JSONDecodeError, ValueError):
            analysis = {}

    educational_value = story.get("educational_value", {})
    if isinstance(educational_value, str):
        try:
            educational_value = json.loads(educational_value)
        except (json.JSONDecodeError, ValueError):
            educational_value = {}

    raw_concepts = analysis.get("key_concepts", [])
    key_concepts = [
        KeyConceptResponse(
            term=c.get("term", ""),
            explanation=c.get("explanation", ""),
            emoji=c.get("emoji", "💡"),
        )
        for c in raw_concepts
        if isinstance(c, dict)
    ]
    if not key_concepts:
        for term in educational_value.get("concepts", []):
            if isinstance(term, str) and term.strip():
                key_concepts.append(KeyConceptResponse(term=term, explanation="", emoji="💡"))

    interactive_questions = [
        InteractiveQuestionResponse(
            question=q.get("question", ""),
            hint=q.get("hint"),
            emoji=q.get("emoji", "🤔"),
        )
        for q in analysis.get("interactive_questions", [])
        if isinstance(q, dict)
    ]

    return KidsDailyTextResponse(
        conversion_id=story["story_id"],
        kid_title=analysis.get("kid_title", "News for Kids"),
        kid_content=story.get("story", {}).get("text", ""),
        why_care=analysis.get("why_care") or educational_value.get("moral", ""),
        key_concepts=key_concepts,
        interactive_questions=interactive_questions,
        category=analysis.get("category", "general"),
        age_group=story.get("age_group", "6-8"),
        audio_url=story.get("audio_url"),
        original_url=analysis.get("original_url"),
        is_degraded=bool(analysis.get("is_degraded", False)),
        degraded_reason=analysis.get("degraded_reason"),
        created_at=story.get("created_at", datetime.now().isoformat()),
    )


@router.get(
    "/episodes/{child_id}",
    response_model=PaginatedKidsDailyResponse,
    summary="List Kids Daily episodes for a child",
)
async def list_kids_daily_episodes(
    child_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserData = Depends(get_current_user),
):
    total = await story_repo.count_by_user_and_child(
        user.user_id,
        child_id,
        story_type="kids_daily",
    )
    stories = await story_repo.list_by_user_and_child(
        user.user_id,
        child_id,
        limit=limit,
        offset=offset,
        story_type="kids_daily",
    )

    episodes = [_story_analysis_to_episode(story) for story in stories]
    return PaginatedKidsDailyResponse(
        items=episodes,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/history/{child_id}",
    response_model=PaginatedNewsResponse,
    summary="Get text conversion history for a child",
    description="Get past text conversions for a child (paginated)",
)
async def get_news_history(
    child_id: str,
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Get paginated text conversion history for a child. Requires authentication."""
    total = await story_repo.count_by_user_and_child(
        user.user_id, child_id, story_type="kids_daily"
    )
    news_stories = await story_repo.list_by_user_and_child(
        user.user_id, child_id, limit=limit, offset=offset, story_type="kids_daily"
    )
    return PaginatedNewsResponse(
        items=news_stories,
        total=total,
        limit=limit,
        offset=offset,
    )


# ===========================================================================
# Engagement tracking
# ===========================================================================

@router.post(
    "/track",
    response_model=KidsDailyTrackResponse,
    summary="Track Kids Daily playback engagement",
)
async def track_kids_daily_engagement(
    request: KidsDailyTrackRequest,
    user: UserData = Depends(get_current_user),
):
    story = await story_repo.get_by_id(request.episode_id)
    if not story or story.get("story_type") not in ("kids_daily", "morning_show"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    if story.get("user_id") != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    trusted_child_id = story.get("child_id", request.child_id)
    analysis = story.get("analysis", {})
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except (json.JSONDecodeError, ValueError):
            analysis = {}
    trusted_topic = analysis.get("category", request.topic.value)

    topic_score = await preference_repo.update_from_kids_daily(
        child_id=trusted_child_id,
        topic=trusted_topic,
        event_type=request.event_type.value,
        progress=request.progress,
        user_id=user.user_id,
    )

    updates = {"is_new": False}
    if request.event_type.value == "complete" or request.progress >= 0.8:
        updates["is_played"] = True
    elif request.event_type.value == "abandon" and request.progress < 0.5:
        updates["is_played"] = False

    await story_repo.update_analysis_fields(request.episode_id, updates)

    return KidsDailyTrackResponse(
        status="tracked",
        topic_score=topic_score,
        profile_updated_at=datetime.now(),
    )
