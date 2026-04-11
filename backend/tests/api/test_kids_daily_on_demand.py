"""API tests for Kids Daily on-demand generation endpoints (#311).

Tests cover:
- POST /generate-now — success, unsubscribed category (400), rate limit (429)
- POST /generate-now/stream — SSE event ordering
"""

from __future__ import annotations

import json
import uuid

import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_MOCK_GENERATED = {
    "kid_title": "Coral Reef Discovery",
    "kid_content": "Scientists found a new coral reef that helps sea animals.",
    "why_care": "Coral reefs protect ocean life.",
    "key_concepts": [],
    "interactive_questions": [],
    "dialogue_script": {
        "lines": [
            {
                "role": "curious_kid",
                "text": "Mimi: What is a coral reef?",
                "display_name": "Mimi",
                "timestamp_start": 0.0,
                "timestamp_end": 4.0,
            },
            {
                "role": "fun_expert",
                "text": "Duo: It is an underwater garden for fish!",
                "display_name": "Duo",
                "timestamp_start": 4.0,
                "timestamp_end": 8.0,
            },
        ],
        "total_duration": 8.0,
        "guest_character": "Professor Owl",
    },
    "safety_score": 0.92,
    "used_mock": False,
    "guest_character": "Professor Owl",
}

_MOCK_NEWS_TEXT = "Today's news about science:\n- Coral reef found: A new reef protects sea animals"


def _mock_stream_events():
    """Async generator yielding mock SSE events from stream_kids_daily_generation."""
    events = [
        {"type": "status", "data": {"phase": "generating_script", "message": "Generating..."}},
        {"type": "result", "data": _MOCK_GENERATED},
    ]

    async def _gen(**kwargs):
        for e in events:
            yield e

    return _gen


# ---------------------------------------------------------------------------
# Patch targets (routes module imports these at top level)
# ---------------------------------------------------------------------------
_ROUTE = "backend.src.api.routes.kids_daily"
_CONVERT = f"{_ROUTE}.generate_kids_daily_episode"
_STREAM = f"{_ROUTE}.stream_kids_daily_generation"
_FETCH = f"{_ROUTE}.fetch_news_text"
_AUDIO = f"{_ROUTE}.generate_multi_speaker_audio"
_SUB_REPO = f"{_ROUTE}.subscription_repo"
_STORY_REPO = f"{_ROUTE}.story_repo"
_USAGE_REPO = f"{_ROUTE}.usage_repo"
_GEN_ILLUSTRATIONS = f"{_ROUTE}._generate_illustrations"


@pytest.mark.asyncio
class TestGenerateNowEndpoint:
    """POST /api/v1/kids-daily/generate-now"""

    async def test_returns_valid_episode(self, test_client):
        """On-demand generation with mocked agent returns a valid KidsDailyResponse."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with (
            patch(_FETCH, new_callable=AsyncMock, return_value=_MOCK_NEWS_TEXT),
            patch(_CONVERT, new_callable=AsyncMock, return_value=_MOCK_GENERATED),
            patch(_AUDIO, new_callable=AsyncMock, return_value={"0": "/audio/line0.mp3"}),
            patch(_GEN_ILLUSTRATIONS, new_callable=AsyncMock, return_value=[]),
            patch(_SUB_REPO) as mock_sub,
            patch(_STORY_REPO) as mock_story,
            patch(_USAGE_REPO) as mock_usage,
        ):
            mock_sub.has_active_subscription = AsyncMock(return_value=True)
            mock_story.count_recent_on_demand = AsyncMock(return_value=0)
            mock_story.create = AsyncMock(return_value=None)
            mock_usage.increment = AsyncMock(return_value=None)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "episode" in data
            assert "metadata" in data
            assert data["episode"]["story_type"] == "kids_daily"
            assert data["metadata"]["safety_score"] >= 0.85
            assert "generation_id" in data["metadata"]
            assert len(data["episode"]["dialogue_script"]["lines"]) > 0

    async def test_returns_400_for_unsubscribed_category(self, test_client):
        """If the child has no active subscription for the category, returns 400."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with (
            patch(_SUB_REPO) as mock_sub,
        ):
            mock_sub.has_active_subscription = AsyncMock(return_value=False)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 400
            assert "Subscribe" in response.json()["detail"] or "subscribe" in response.json()["detail"].lower()

    async def test_returns_429_when_rate_limited(self, test_client):
        """4th request within 1 hour returns 429 with retry_after."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with (
            patch(_SUB_REPO) as mock_sub,
            patch(_STORY_REPO) as mock_story,
        ):
            mock_sub.has_active_subscription = AsyncMock(return_value=True)
            mock_story.count_recent_on_demand = AsyncMock(return_value=3)  # already at limit
            mock_story.get_oldest_recent_on_demand_ts = AsyncMock(return_value=None)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 429
            data = response.json()
            assert "retry_after" in data
            assert isinstance(data["retry_after"], int)
            assert data["retry_after"] >= 0


@pytest.mark.asyncio
class TestGenerateNowStreamEndpoint:
    """POST /api/v1/kids-daily/generate-now/stream"""

    async def test_stream_returns_sse_events_in_order(self, test_client):
        """SSE stream must emit status events for each phase, then result, then complete."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with (
            patch(_FETCH, new_callable=AsyncMock, return_value=_MOCK_NEWS_TEXT),
            patch(_STREAM, side_effect=_mock_stream_events()),
            patch(_AUDIO, new_callable=AsyncMock, return_value={"0": "/audio/line0.mp3"}),
            patch(_GEN_ILLUSTRATIONS, new_callable=AsyncMock, return_value=[]),
            patch(_CONVERT, new_callable=AsyncMock, return_value=_MOCK_GENERATED),
            patch(_SUB_REPO) as mock_sub,
            patch(_STORY_REPO) as mock_story,
            patch(_USAGE_REPO) as mock_usage,
        ):
            mock_sub.has_active_subscription = AsyncMock(return_value=True)
            mock_story.count_recent_on_demand = AsyncMock(return_value=0)
            mock_story.create = AsyncMock(return_value=None)
            mock_usage.increment = AsyncMock(return_value=None)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now/stream",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            body = response.text
            # Verify all expected SSE phases appear
            assert "event: status" in body
            assert "fetching_news" in body
            assert "generating_script" in body
            assert "generating_audio" in body
            assert "generating_illustrations" in body
            assert "event: result" in body
            assert "event: complete" in body

            # Verify phase ordering: fetching_news before generating_script
            fetching_pos = body.index("fetching_news")
            script_pos = body.index("generating_script")
            audio_pos = body.index("generating_audio")
            illustrations_pos = body.index("generating_illustrations")
            complete_pos = body.index("event: complete")

            assert fetching_pos < script_pos < audio_pos < illustrations_pos < complete_pos

    async def test_stream_returns_400_for_unsubscribed_category(self, test_client):
        """Stream endpoint also checks subscription before starting SSE."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with patch(_SUB_REPO) as mock_sub:
            mock_sub.has_active_subscription = AsyncMock(return_value=False)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now/stream",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 400

    async def test_stream_returns_429_when_rate_limited(self, test_client):
        """Stream endpoint also enforces rate limiting before starting SSE."""
        child_id = f"child-od-{uuid.uuid4().hex[:8]}"

        with (
            patch(_SUB_REPO) as mock_sub,
            patch(_STORY_REPO) as mock_story,
        ):
            mock_sub.has_active_subscription = AsyncMock(return_value=True)
            mock_story.count_recent_on_demand = AsyncMock(return_value=3)
            mock_story.get_oldest_recent_on_demand_ts = AsyncMock(return_value=None)

            async with test_client as client:
                response = await client.post(
                    "/api/v1/kids-daily/generate-now/stream",
                    json={
                        "child_id": child_id,
                        "category": "science",
                        "age_group": "6-8",
                    },
                )

            assert response.status_code == 429
