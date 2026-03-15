"""
Tests for SSE streaming disconnect handling.

Verifies that when a client disconnects mid-stream, the backend
does not persist the story to the database.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.src.api.routes.image_to_story import event_generator  # noqa – we test indirectly


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fake_stream_image_to_story(**kwargs):
    """Simulate a streaming agent that yields a status event, then a result."""
    yield {"type": "status", "data": {"status": "started"}}
    # Give the test a chance to mark disconnected
    await asyncio.sleep(0)
    yield {
        "type": "result",
        "data": {
            "story": "Once upon a time...",
            "themes": ["adventure"],
            "concepts": [],
            "moral": None,
            "characters": [],
            "analysis": {},
            "safety_score": 0.95,
            "audio_path": None,
        },
    }


async def _fake_stream_disconnects_before_result(**kwargs):
    """Simulate a streaming agent; caller will disconnect before result."""
    yield {"type": "status", "data": {"status": "started"}}
    # After this event the test marks the request as disconnected
    await asyncio.sleep(0)
    yield {
        "type": "result",
        "data": {
            "story": "Should not be saved",
            "themes": [],
            "concepts": [],
            "moral": None,
            "characters": [],
            "analysis": {},
            "safety_score": 0.90,
            "audio_path": None,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreamDisconnect:
    """Verify that story_repo.create is skipped when client disconnects."""

    @patch("backend.src.api.routes.image_to_story.story_repo")
    @patch("backend.src.api.routes.image_to_story.preference_repo")
    @patch("backend.src.api.routes.image_to_story.stream_image_to_story")
    @patch("backend.src.api.routes.image_to_story.save_upload_file")
    @patch("backend.src.api.routes.image_to_story.validate_image_file")
    @patch("backend.src.api.routes.image_to_story.validate_child_id", return_value="child_01")
    async def test_story_not_saved_on_disconnect(
        self,
        mock_validate_child_id,
        mock_validate_image,
        mock_save_upload,
        mock_stream,
        mock_pref_repo,
        mock_story_repo,
    ):
        """When the client disconnects mid-stream, story_repo.create must not be called."""
        from pathlib import Path

        mock_save_upload.return_value = Path("/tmp/fake_image.png")
        mock_story_repo.create = AsyncMock()

        # Track disconnect state
        disconnected = False

        async def is_disconnected():
            return disconnected

        # Simulate the agent stream — disconnect after the first event
        call_count = 0

        async def fake_stream(**kwargs):
            nonlocal call_count, disconnected
            yield {"type": "status", "data": {"status": "started"}}
            call_count += 1
            # Mark as disconnected after first event
            disconnected = True
            await asyncio.sleep(0)
            yield {
                "type": "result",
                "data": {
                    "story": "Should not be saved",
                    "themes": [],
                    "concepts": [],
                    "moral": None,
                    "characters": [],
                    "analysis": {},
                    "safety_score": 0.90,
                    "audio_path": None,
                },
            }

        mock_stream.side_effect = fake_stream

        # Build a mock Request with is_disconnected
        mock_request = MagicMock()
        mock_request.is_disconnected = is_disconnected

        # Build a mock user
        mock_user = MagicMock()
        mock_user.user_id = "test_user"

        # Build a mock AgeGroup
        mock_age_group = MagicMock()
        mock_age_group.value = "6-8"

        # Build a mock UploadFile
        mock_image = MagicMock()
        mock_image.filename = "test.png"
        mock_image.content_type = "image/png"

        # Call the streaming endpoint
        from backend.src.api.routes.image_to_story import create_story_from_image_stream

        response = await create_story_from_image_stream(
            request=mock_request,
            image=mock_image,
            child_id="child_01",
            age_group=mock_age_group,
            interests=None,
            voice="nova",
            enable_audio=True,
            user=mock_user,
        )

        # Drain the generator to execute the logic
        collected = []
        async for chunk in response.body_iterator:
            collected.append(chunk)

        # story_repo.create should NOT have been called
        mock_story_repo.create.assert_not_called()

    @patch("backend.src.api.routes.image_to_story.story_repo")
    @patch("backend.src.api.routes.image_to_story.preference_repo")
    @patch("backend.src.api.routes.image_to_story.stream_image_to_story")
    @patch("backend.src.api.routes.image_to_story.save_upload_file")
    @patch("backend.src.api.routes.image_to_story.validate_image_file")
    @patch("backend.src.api.routes.image_to_story.validate_child_id", return_value="child_01")
    async def test_story_saved_when_connected(
        self,
        mock_validate_child_id,
        mock_validate_image,
        mock_save_upload,
        mock_stream,
        mock_pref_repo,
        mock_story_repo,
    ):
        """When the client stays connected, story_repo.create IS called."""
        from pathlib import Path

        mock_save_upload.return_value = Path("/tmp/fake_image.png")
        mock_story_repo.create = AsyncMock()
        mock_pref_repo.update_from_story_result = AsyncMock()

        async def is_disconnected():
            return False

        mock_stream.side_effect = _fake_stream_image_to_story

        mock_request = MagicMock()
        mock_request.is_disconnected = is_disconnected

        mock_user = MagicMock()
        mock_user.user_id = "test_user"

        mock_age_group = MagicMock()
        mock_age_group.value = "6-8"

        mock_image = MagicMock()
        mock_image.filename = "test.png"
        mock_image.content_type = "image/png"

        from backend.src.api.routes.image_to_story import create_story_from_image_stream

        response = await create_story_from_image_stream(
            request=mock_request,
            image=mock_image,
            child_id="child_01",
            age_group=mock_age_group,
            interests=None,
            voice="nova",
            enable_audio=True,
            user=mock_user,
        )

        # Drain the generator
        collected = []
        async for chunk in response.body_iterator:
            collected.append(chunk)

        # story_repo.create SHOULD have been called
        mock_story_repo.create.assert_called_once()

        # Verify a result event was emitted
        result_events = [c for c in collected if "event: result" in c]
        assert len(result_events) == 1
