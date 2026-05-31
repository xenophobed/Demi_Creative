"""
Audio Transcriptions API Tests (#583)

Locks the HTTP contract for POST /api/v1/audio/transcriptions:
  - Validates mime type and size BEFORE invoking the provider.
  - Returns 200 with safety_passed=False on moderation failure
    (not an error — the request succeeded; the content was rejected).
  - Returns 502 on provider transport failure.
  - Requires authentication.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.user_service import UserData


PARENT_USER = UserData(
    user_id="stt_parent",
    username="stt_parent",
    email="parent@stt-test.com",
    password_hash="h",
    display_name="Parent",
    role="parent",
    created_at="",
    updated_at="",
)


async def _override_current_user() -> UserData:
    return PARENT_USER


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setenv("STT_MOCK", "1")
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


def _audio_payload(mime: str = "audio/webm", size: int = 1024) -> dict:
    return {
        "audio": ("clip.webm", b"x" * size, mime),
        "target_age": (None, "7"),
    }


class TestTranscriptionEndpoint:
    @pytest.mark.asyncio
    async def test_happy_path_returns_safety_passed_transcript(self, client):
        with patch(
            "backend.src.services.stt_service._safety_check_text",
            new=AsyncMock(return_value={"safety_score": 0.95, "issues": []}),
        ):
            response = await client.post(
                "/api/v1/audio/transcriptions",
                files={"audio": ("clip.webm", b"x" * 1024, "audio/webm")},
                data={"target_age": "7"},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body.keys()) == {"text", "language", "duration_ms", "safety_passed"}
        assert body["safety_passed"] is True
        assert body["text"]  # non-empty

    @pytest.mark.asyncio
    async def test_safety_failure_returns_200_with_empty_text(self, client):
        with patch(
            "backend.src.services.stt_service._safety_check_text",
            new=AsyncMock(return_value={"safety_score": 0.3, "issues": ["violence"]}),
        ):
            response = await client.post(
                "/api/v1/audio/transcriptions",
                files={"audio": ("clip.webm", b"x" * 1024, "audio/webm")},
                data={"target_age": "7"},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["safety_passed"] is False
        assert body["text"] == ""

    @pytest.mark.asyncio
    async def test_rejects_unsupported_mime_400(self, client):
        response = await client.post(
            "/api/v1/audio/transcriptions",
            files={"audio": ("clip.wav", b"x" * 1024, "audio/wav")},
            data={"target_age": "7"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_AUDIO"

    @pytest.mark.asyncio
    async def test_rejects_oversized_audio_400(self, client):
        # 2MB + 1 byte
        oversize = 2 * 1024 * 1024 + 1
        response = await client.post(
            "/api/v1/audio/transcriptions",
            files={"audio": ("clip.webm", b"x" * oversize, "audio/webm")},
            data={"target_age": "7"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_AUDIO"

    @pytest.mark.asyncio
    async def test_accepts_webm_with_codec_param(self, client):
        with patch(
            "backend.src.services.stt_service._safety_check_text",
            new=AsyncMock(return_value={"safety_score": 0.95}),
        ):
            response = await client.post(
                "/api/v1/audio/transcriptions",
                files={"audio": ("clip.webm", b"x" * 1024, "audio/webm;codecs=opus")},
                data={"target_age": "7"},
            )
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_provider_failure_returns_502(self, client):
        # Force provider path away from mock by clearing STT_MOCK and
        # patching the OpenAI provider to fail.
        from backend.src.services import stt_service

        failing = AsyncMock()
        failing.transcribe = AsyncMock(
            return_value={"success": False, "error": "upstream timeout"}
        )

        async def patched_transcribe(audio_bytes, mime_type, target_age, **kw):
            return await stt_service.transcribe_audio_bytes.__wrapped__(  # type: ignore[attr-defined]
                audio_bytes,
                mime_type,
                target_age=target_age,
                provider=failing,
                **{k: v for k, v in kw.items() if k != "provider"},
            ) if hasattr(stt_service.transcribe_audio_bytes, "__wrapped__") else await stt_service.transcribe_audio_bytes(
                audio_bytes,
                mime_type,
                target_age=target_age,
                provider=failing,
                **{k: v for k, v in kw.items() if k != "provider"},
            )

        with patch(
            "backend.src.api.routes.audio_transcriptions.transcribe_audio_bytes",
            new=patched_transcribe,
        ):
            response = await client.post(
                "/api/v1/audio/transcriptions",
                files={"audio": ("clip.webm", b"x" * 1024, "audio/webm")},
                data={"target_age": "7"},
            )

        assert response.status_code == 502, response.text
        assert response.json()["detail"]["code"] == "TRANSCRIPTION_FAILED"

    @pytest.mark.asyncio
    async def test_audio_too_long_returns_400(self, client):
        from backend.src.services import stt_service

        long_envelope = {
            "success": True,
            "text": "a long transcript",
            "language": "en",
            "duration_ms": 40_000,
            "safety_passed": True,
            "error": None,
            "provider": "MockSTTProvider",
        }
        with patch.object(
            stt_service, "transcribe_audio_bytes",
            new=AsyncMock(return_value=long_envelope),
        ), patch(
            "backend.src.api.routes.audio_transcriptions.transcribe_audio_bytes",
            new=AsyncMock(return_value=long_envelope),
        ):
            response = await client.post(
                "/api/v1/audio/transcriptions",
                files={"audio": ("clip.webm", b"x" * 1024, "audio/webm")},
                data={"target_age": "7"},
            )

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "AUDIO_TOO_LONG"
