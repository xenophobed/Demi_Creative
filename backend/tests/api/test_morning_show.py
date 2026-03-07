"""API tests for Morning Show endpoints (#88, #93)."""

import json
import uuid

import pytest


@pytest.mark.asyncio
class TestMorningShowEndpoints:
    async def test_generate_episode_success(self, test_client):
        child_id = f"child-ms-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/morning-show/generate",
                json={
                    "child_id": child_id,
                    "age_group": "6-8",
                    "news_text": "Scientists found a new coral reef that helps sea animals.",
                    "news_url": "https://example.com/coral-reef",
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert "episode" in data
            assert "metadata" in data
            assert data["episode"]["story_type"] == "morning_show"
            assert len(data["episode"]["dialogue_script"]["lines"]) > 0
            assert data["metadata"]["safety_score"] >= 0.85

    async def test_generate_stream_sse(self, test_client):
        child_id = f"child-ms-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/morning-show/generate/stream",
                json={
                    "child_id": child_id,
                    "age_group": "3-5",
                    "news_text": "A panda sanctuary welcomed two baby pandas this week.",
                },
            )

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = response.text
            assert "event: status" in body
            assert "event: result" in body
            assert "event: complete" in body

    async def test_get_episode_by_id(self, test_client):
        child_id = f"child-ms-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            generate = await client.post(
                "/api/v1/morning-show/generate",
                json={
                    "child_id": child_id,
                    "age_group": "9-12",
                    "news_text": "A new space telescope captured colorful nebula images.",
                },
            )
            assert generate.status_code == 200
            episode_id = generate.json()["episode"]["episode_id"]

            response = await client.get(f"/api/v1/morning-show/episode/{episode_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["episode_id"] == episode_id
            assert data["story_type"] == "morning_show"
            assert len(data["dialogue_script"]["lines"]) > 0

    async def test_list_child_episodes(self, test_client):
        child_id = f"child-ms-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            for idx in range(2):
                generate = await client.post(
                    "/api/v1/morning-show/generate",
                    json={
                        "child_id": child_id,
                        "age_group": "6-8",
                        "news_text": f"Topic {idx}: Nature discovery update for kids.",
                    },
                )
                assert generate.status_code == 200

            response = await client.get(f"/api/v1/morning-show/episodes/{child_id}?limit=10&offset=0")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] >= 2
            assert all(item["story_type"] == "morning_show" for item in data["items"])

    async def test_generate_requires_news_text_or_url(self, test_client):
        async with test_client as client:
            response = await client.post(
                "/api/v1/morning-show/generate",
                json={
                    "child_id": f"child-ms-{uuid.uuid4().hex[:8]}",
                    "age_group": "6-8",
                },
            )

            assert response.status_code == 400
            assert "Either news_url or news_text must be provided" in response.json()["detail"]

    async def test_track_engagement_updates_topic_score(self, test_client):
        child_id = f"child-ms-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            generate = await client.post(
                "/api/v1/morning-show/generate",
                json={
                    "child_id": child_id,
                    "age_group": "6-8",
                    "news_text": "Scientists built a cleaner ocean robot for coral reefs.",
                    "category": "science",
                },
            )
            assert generate.status_code == 200
            episode_id = generate.json()["episode"]["episode_id"]

            tracked = await client.post(
                "/api/v1/morning-show/track",
                json={
                    "child_id": child_id,
                    "episode_id": episode_id,
                    "topic": "science",
                    "event_type": "complete",
                    "progress": 0.92,
                    "played_seconds": 90,
                },
            )

            assert tracked.status_code == 200
            payload = tracked.json()
            assert payload["status"] == "tracked"
            assert payload["topic_score"] > 0
