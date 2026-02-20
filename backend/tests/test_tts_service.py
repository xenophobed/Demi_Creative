import os

import pytest

from backend.src.services.tts_service import generate_story_audio_file


@pytest.mark.asyncio
async def test_generate_story_audio_file_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await generate_story_audio_file(text="hello world")

    assert result["success"] is False
    assert result["audio_path"] is None
    assert "OPENAI_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_generate_story_audio_file_success(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

    class FakeSpeechResponse:
        def stream_to_file(self, path):
            with open(path, "wb") as f:
                f.write(b"fake-mp3-data")

    class FakeSpeechAPI:
        @staticmethod
        def create(**kwargs):
            assert kwargs["model"] == "tts-1"
            assert kwargs["voice"] == "alloy"
            return FakeSpeechResponse()

    class FakeAudioAPI:
        speech = FakeSpeechAPI()

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.audio = FakeAudioAPI()

    monkeypatch.setattr("backend.src.services.tts_service.OpenAI", FakeOpenAI)

    result = await generate_story_audio_file(
        text="A short story for testing.",
        voice="alloy",
        speed=None,
        child_age=4,
    )

    assert result["success"] is True
    assert result["audio_path"] is not None
    assert os.path.exists(result["audio_path"])
    assert result["speed"] == 0.9
    assert result["duration"] > 0
