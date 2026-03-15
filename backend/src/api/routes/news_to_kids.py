"""
News-to-Kids API Routes

Endpoints for converting news articles into kid-friendly content.
Supports both non-streaming and SSE streaming responses.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from ...utils.text import count_words

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from ..models import (
    NewsToKidsRequest,
    NewsToKidsResponse,
    KeyConceptResponse,
    InteractiveQuestionResponse,
    PaginatedNewsResponse,
)
from ..deps import get_current_user
from ...services.database import story_repo, preference_repo
from ...services.user_service import UserData
from ...agents.news_to_kids_agent import convert_news_to_kids, stream_news_to_kids
from ...mcp_servers import fetch_article_text

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/news-to-kids",
    tags=["News-to-Kids"]
)


async def _fetch_text_from_url(url: str) -> str:
    """Fetch article text from a URL via the web-search MCP tool.

    Raises ``HTTPException`` (422) when the article cannot be retrieved so that
    callers never fall through to placeholder text.
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

    # If URL provided but no text, fetch the real article content
    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = await _fetch_text_from_url(request.news_url)

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
            "safety_score": result.get("safety_score", 0.0),
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
    http_request: Request,
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

    # Fetch article text before entering the generator so failures return
    # a proper HTTP error instead of an SSE error event with placeholder text.
    news_text = request.news_text or ""
    if request.news_url and not news_text:
        news_text = await _fetch_text_from_url(request.news_url)

    async def event_generator() -> AsyncGenerator[str, None]:
        client_disconnected = False
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
                # Check if client has disconnected
                if await http_request.is_disconnected():
                    logger.info("Client disconnected during news conversion, aborting")
                    client_disconnected = True
                    break

                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    # Final disconnect check before persisting
                    if await http_request.is_disconnected():
                        logger.info("Client disconnected before news save, skipping persist")
                        client_disconnected = True
                        break

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
                        "safety_score": event_data.get("safety_score", 0.0),
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


@router.get(
    "/history/{child_id}",
    response_model=PaginatedNewsResponse,
    summary="Get news conversion history",
    description="Get past news-to-kids conversions for a child (paginated)",
)
async def get_news_history(
    child_id: str,
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserData = Depends(get_current_user),
):
    """Get paginated news conversion history for a child. Requires authentication."""
    total = await story_repo.count_by_user_and_child(
        user.user_id, child_id, story_type="news_to_kids"
    )
    news_stories = await story_repo.list_by_user_and_child(
        user.user_id, child_id, limit=limit, offset=offset, story_type="news_to_kids"
    )
    return PaginatedNewsResponse(
        items=news_stories,
        total=total,
        limit=limit,
        offset=offset,
    )
