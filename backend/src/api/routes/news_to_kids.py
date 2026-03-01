"""
News-to-Kids API Routes

Endpoints for converting news articles into kid-friendly content.
Supports both non-streaming and SSE streaming responses.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from ...utils.text import count_words

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..models import (
    NewsToKidsRequest,
    NewsToKidsResponse,
    KeyConceptResponse,
    InteractiveQuestionResponse,
)
from ..deps import get_current_user
from ...services.database import story_repo, preference_repo
from ...services.user_service import UserData
from ...agents.news_to_kids_agent import convert_news_to_kids, stream_news_to_kids


router = APIRouter(
    prefix="/api/v1/news-to-kids",
    tags=["News-to-Kids"]
)


@router.post(
    "/convert",
    response_model=NewsToKidsResponse,
    summary="Convert news to kid-friendly content",
    description="Convert a news article into age-appropriate content for children",
)
async def convert_news(
    request: NewsToKidsRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Convert news article to kid-friendly content. Requires authentication.
    """
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    # If URL provided but no text, fetch the article
    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = f"[Article from: {request.news_url}]\nPlease fetch and summarize the content from this URL."

    try:
        result = await convert_news_to_kids(
            news_text=news_text,
            age_group=request.age_group.value,
            child_id=request.child_id,
            category=request.category.value,
            news_url=request.news_url,
            enable_audio=request.enable_audio,
            voice=request.voice.value if request.voice else None,
        )

        conversion_id = str(uuid.uuid4())

        # Build audio URL from path
        audio_url = None
        if result.get("audio_path"):
            audio_filename = Path(result["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        # Save as a story record
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
                "story_type": "news_to_kids",
                "category": request.category.value,
                "original_url": request.news_url,
                "kid_title": result.get("kid_title", ""),
            },
            "story_type": "news_to_kids",
            "safety_score": 0.9,
            "audio_url": audio_url,
        }
        await story_repo.create(story_data)

        # Update child preferences (Advanced Memory)
        try:
            await preference_repo.update_from_news(
                child_id=request.child_id,
                category=request.category.value,
                key_concepts=result.get("key_concepts", []),
            )
        except Exception:
            pass  # Non-critical

        # Build response
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

        return NewsToKidsResponse(
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
    summary="Convert news to kid-friendly content (streaming)",
    description="Convert news with SSE streaming progress updates",
)
async def convert_news_stream(
    request: NewsToKidsRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Stream news-to-kids conversion with Server-Sent Events. Requires authentication.
    """
    if not request.news_url and not request.news_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either news_url or news_text must be provided",
        )

    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = f"[Article from: {request.news_url}]\nPlease fetch and summarize the content from this URL."

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in stream_news_to_kids(
                news_text=news_text,
                age_group=request.age_group.value,
                child_id=request.child_id,
                category=request.category.value,
                news_url=request.news_url,
                enable_audio=request.enable_audio,
                voice=request.voice.value if request.voice else None,
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    # Save to DB and enrich the response
                    conversion_id = str(uuid.uuid4())
                    audio_url = None
                    if event_data.get("audio_path"):
                        audio_filename = Path(event_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

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
                            "story_type": "news_to_kids",
                            "category": request.category.value,
                            "original_url": request.news_url,
                            "kid_title": event_data.get("kid_title", ""),
                        },
                        "story_type": "news_to_kids",
                        "safety_score": 0.9,
                        "audio_url": audio_url,
                    }
                    await story_repo.create(story_data)

                    # Update child preferences (Advanced Memory)
                    try:
                        await preference_repo.update_from_news(
                            child_id=request.child_id,
                            category=request.category.value,
                            key_concepts=event_data.get("key_concepts", []),
                        )
                    except Exception:
                        pass  # Non-critical

                    # Enrich result
                    event_data["conversion_id"] = conversion_id
                    event_data["audio_url"] = audio_url
                    event_data["category"] = request.category.value
                    event_data["age_group"] = request.age_group.value
                    event_data["original_url"] = request.news_url

                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_data = {"error": str(e), "message": "News conversion failed"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

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
    "/history/{child_id}",
    summary="Get news conversion history",
    description="Get past news-to-kids conversions for a child",
)
async def get_news_history(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Get news conversion history for a child. Requires authentication."""
    stories = await story_repo.list_by_user_and_child(user.user_id, child_id, limit=50)
    news_stories = [s for s in stories if s.get("story_type") == "news_to_kids"]
    return news_stories
