"""
Tests for Voice Preview API (#333, #336)

Tests the GET /api/v1/audio/preview endpoint:
- Returns cached audio on repeat requests
- Validates provider parameter
- Rate limiting (429)
- Response schema contract
"""

import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.main import app
from backend.src.api.routes.audio import _preview_rate


PREVIEW_DIR = Path("./data/audio/previews")


@pytest.fixture(autouse=True)
def _clean_preview_state():
    """Reset rate limiter and preview cache between tests."""
    _preview_rate.clear()
    # Clean test preview files
    if PREVIEW_DIR.exists():
        for f in PREVIEW_DIR.glob("openai_test_*.mp3"):
            f.unlink(missing_ok=True)
        for f in PREVIEW_DIR.glob("replicate_test_*.mp3"):
            f.unlink(missing_ok=True)
    yield
    # Cleanup after test
    if PREVIEW_DIR.exists():
        for f in PREVIEW_DIR.glob("openai_test_*.mp3"):
            f.unlink(missing_ok=True)
        for f in PREVIEW_DIR.glob("replicate_test_*.mp3"):
            f.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestVoicePreview:
    """Voice preview endpoint tests (#333)."""

    async def test_preview_generates_audio(self, test_client):
        """Preview endpoint generates audio and returns URL."""
        mock_result = {
            "success": True,
            "audio_path": "./data/audio/story_test_preview.mp3",
        }
        # Create the fake generated file so rename works
        Path("./data/audio").mkdir(parents=True, exist_ok=True)
        Path("./data/audio/story_test_preview.mp3").write_bytes(b"fake-audio-data")

        with patch(
            "backend.src.api.routes.audio.generate_story_audio_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with test_client as client:
                resp = await client.get(
                    "/api/v1/audio/preview",
                    params={"voice_id": "test_nova", "provider": "openai"},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["voice_id"] == "test_nova"
            assert data["provider"] == "openai"
            assert data["audio_url"] == "/data/audio/previews/openai_test_nova.mp3"
            assert data["cached"] is False

    async def test_preview_returns_cached(self, test_client):
        """Second request returns cached file without calling TTS."""
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = PREVIEW_DIR / "openai_test_cached.mp3"
        cache_file.write_bytes(b"cached-audio")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/audio/preview",
                params={"voice_id": "test_cached", "provider": "openai"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        assert data["audio_url"] == "/data/audio/previews/openai_test_cached.mp3"

        # Cleanup
        cache_file.unlink(missing_ok=True)

    async def test_preview_invalid_provider(self, test_client):
        """Invalid provider returns 400."""
        async with test_client as client:
            resp = await client.get(
                "/api/v1/audio/preview",
                params={"voice_id": "nova", "provider": "invalid_provider"},
            )

        assert resp.status_code == 400
        assert "Invalid provider" in resp.json()["detail"]

    async def test_preview_rate_limit(self, test_client):
        """Exceeding rate limit returns 429."""
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

        # Pre-create cache files so we don't need TTS mock
        for i in range(11):
            (PREVIEW_DIR / f"openai_test_rl{i}.mp3").write_bytes(b"data")

        async with test_client as client:
            for i in range(10):
                resp = await client.get(
                    "/api/v1/audio/preview",
                    params={"voice_id": f"test_rl{i}", "provider": "openai"},
                )
                assert resp.status_code == 200

            # 11th request should be rate limited
            resp = await client.get(
                "/api/v1/audio/preview",
                params={"voice_id": "test_rl10", "provider": "openai"},
            )
            assert resp.status_code == 429

        # Cleanup
        for i in range(11):
            (PREVIEW_DIR / f"openai_test_rl{i}.mp3").unlink(missing_ok=True)

    async def test_preview_tts_failure(self, test_client):
        """TTS failure returns 502."""
        mock_result = {"success": False, "error": "API key missing"}

        with patch(
            "backend.src.api.routes.audio.generate_story_audio_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with test_client as client:
                resp = await client.get(
                    "/api/v1/audio/preview",
                    params={"voice_id": "test_fail", "provider": "openai"},
                )

        assert resp.status_code == 502
        assert "Preview generation failed" in resp.json()["detail"]


@pytest.mark.asyncio
class TestVoicePreviewContract:
    """Response schema contract tests (#336)."""

    async def test_response_schema(self, test_client):
        """Response matches { voice_id, provider, audio_url, cached } schema."""
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = PREVIEW_DIR / "openai_test_schema.mp3"
        cache_file.write_bytes(b"schema-test")

        async with test_client as client:
            resp = await client.get(
                "/api/v1/audio/preview",
                params={"voice_id": "test_schema", "provider": "openai"},
            )

        assert resp.status_code == 200
        data = resp.json()

        # All required fields present
        assert "voice_id" in data
        assert "provider" in data
        assert "audio_url" in data
        assert "cached" in data

        # Types
        assert isinstance(data["voice_id"], str)
        assert isinstance(data["provider"], str)
        assert isinstance(data["audio_url"], str)
        assert isinstance(data["cached"], bool)

        # audio_url starts with expected prefix
        assert data["audio_url"].startswith("/data/audio/previews/")

        cache_file.unlink(missing_ok=True)
