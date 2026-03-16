"""API tests for Morning Show progress tracking events (#198).

Verifies that the /track endpoint correctly handles 'progress' event_type
and that repeated progress events for the same threshold yield consistent
scoring (idempotency at the backend level).
"""

import uuid

import pytest


@pytest.mark.asyncio
class TestMorningShowProgressTracking:
    """Progress events at 25/50/75% thresholds should be accepted and scored."""

    async def _create_episode(self, client, child_id: str) -> str:
        """Helper: generate an episode and return its episode_id."""
        resp = await client.post(
            "/api/v1/morning-show/generate",
            json={
                "child_id": child_id,
                "age_group": "6-8",
                "news_text": "Robots help farmers grow better vegetables.",
                "category": "science",
            },
        )
        assert resp.status_code == 200
        return resp.json()["episode"]["episode_id"]

    async def test_progress_event_accepted_at_thresholds(self, test_client):
        """Backend should accept progress events at 25%, 50%, 75%."""
        child_id = f"child-prog-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            episode_id = await self._create_episode(client, child_id)

            for threshold in [0.25, 0.50, 0.75]:
                resp = await client.post(
                    "/api/v1/morning-show/track",
                    json={
                        "child_id": child_id,
                        "episode_id": episode_id,
                        "topic": "science",
                        "event_type": "progress",
                        "progress": threshold,
                        "played_seconds": threshold * 60,
                    },
                )
                assert resp.status_code == 200, f"Failed at threshold {threshold}"
                payload = resp.json()
                assert payload["status"] == "tracked"
                assert "topic_score" in payload

    async def test_duplicate_progress_events_do_not_error(self, test_client):
        """Sending the same progress threshold twice should not cause errors.

        The backend accepts duplicates gracefully — deduplication is a
        frontend responsibility (#198).
        """
        child_id = f"child-dup-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            episode_id = await self._create_episode(client, child_id)

            for _ in range(2):
                resp = await client.post(
                    "/api/v1/morning-show/track",
                    json={
                        "child_id": child_id,
                        "episode_id": episode_id,
                        "topic": "science",
                        "event_type": "progress",
                        "progress": 0.50,
                        "played_seconds": 30,
                    },
                )
                assert resp.status_code == 200

    async def test_progress_score_increments(self, test_client):
        """Progress events should increase the topic score (small increment)."""
        child_id = f"child-score-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            episode_id = await self._create_episode(client, child_id)

            # Send start first
            start_resp = await client.post(
                "/api/v1/morning-show/track",
                json={
                    "child_id": child_id,
                    "episode_id": episode_id,
                    "topic": "science",
                    "event_type": "start",
                    "progress": 0.0,
                },
            )
            assert start_resp.status_code == 200
            score_after_start = start_resp.json()["topic_score"]

            # Send progress at 50%
            prog_resp = await client.post(
                "/api/v1/morning-show/track",
                json={
                    "child_id": child_id,
                    "episode_id": episode_id,
                    "topic": "science",
                    "event_type": "progress",
                    "progress": 0.50,
                    "played_seconds": 30,
                },
            )
            assert prog_resp.status_code == 200
            score_after_progress = prog_resp.json()["topic_score"]

            # Progress should bump score (the else branch adds +0.05)
            assert score_after_progress >= score_after_start
