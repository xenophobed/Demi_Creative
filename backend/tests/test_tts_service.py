import os

import pytest

from backend.src.services.tts_service import (
    filter_emotion_for_age,
    generate_story_audio_file,
    ReplicateTTSProvider,
)


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
    assert result["provider"] == "openai"
    assert result["fallback_used"] is False


# ---------------------------------------------------------------------------
# Replicate provider unit tests (#149)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replicate_provider_calls_sdk(monkeypatch, tmp_path):
    """ReplicateTTSProvider should call replicate.run with correct params."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")

    captured_args = {}

    class FakeFileOutput:
        def read(self):
            return b"fake-replicate-audio"

    def fake_run(model, input):
        captured_args["model"] = model
        captured_args["input"] = input
        return FakeFileOutput()

    import types
    fake_module = types.ModuleType("replicate")
    fake_module.run = fake_run
    monkeypatch.setattr("backend.src.services.tts_service._replicate_module", fake_module)

    provider = ReplicateTTSProvider()
    audio_path = str(tmp_path / "test.mp3")

    result = await provider.generate(
        text="Hello world",
        voice="Deep_Voice_Man",
        speed=1.0,
        audio_path=audio_path,
        emotion="happy",
        pitch=2,
        volume=5.0,
        language_boost="English",
    )

    assert result["success"] is True
    assert result["provider"] == "replicate"
    assert captured_args["model"] == "minimax/speech-02-turbo"
    assert captured_args["input"]["text"] == "Hello world"
    assert captured_args["input"]["voice_id"] == "Deep_Voice_Man"
    assert captured_args["input"]["emotion"] == "happy"
    assert captured_args["input"]["pitch"] == 2
    assert os.path.exists(audio_path)


@pytest.mark.asyncio
async def test_replicate_provider_missing_token(monkeypatch):
    """ReplicateTTSProvider should fail gracefully without API token."""
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)

    provider = ReplicateTTSProvider()
    result = await provider.generate(
        text="Hello", voice="Deep_Voice_Man", speed=1.0, audio_path="/tmp/x.mp3",
    )

    assert result["success"] is False
    assert "REPLICATE_API_TOKEN" in result["error"]


# ---------------------------------------------------------------------------
# Fallback logic tests (#149)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_from_replicate_to_openai(monkeypatch, tmp_path):
    """When Replicate fails, generate_story_audio_file should fall back to OpenAI."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

    # Make Replicate always fail
    import types
    fake_replicate = types.ModuleType("replicate")
    fake_replicate.run = lambda model, input: (_ for _ in ()).throw(RuntimeError("replicate down"))
    monkeypatch.setattr("backend.src.services.tts_service._replicate_module", fake_replicate)

    # Make OpenAI succeed
    class FakeSpeechResponse:
        def stream_to_file(self, path):
            with open(path, "wb") as f:
                f.write(b"fallback-audio")

    class FakeSpeechAPI:
        @staticmethod
        def create(**kwargs):
            return FakeSpeechResponse()

    class FakeAudioAPI:
        speech = FakeSpeechAPI()

    class FakeOpenAI:
        def __init__(self, api_key):
            self.audio = FakeAudioAPI()

    monkeypatch.setattr("backend.src.services.tts_service.OpenAI", FakeOpenAI)

    result = await generate_story_audio_file(
        text="A test story",
        voice="alloy",
        speed=1.0,
        provider="replicate",
    )

    assert result["success"] is True
    assert result["fallback_used"] is True
    assert result["provider"] == "openai"


@pytest.mark.asyncio
async def test_openai_provider_with_emotion_params(monkeypatch, tmp_path):
    """OpenAI provider ignores emotion params gracefully (they're not supported)."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

    class FakeSpeechResponse:
        def stream_to_file(self, path):
            with open(path, "wb") as f:
                f.write(b"fake-audio")

    class FakeSpeechAPI:
        @staticmethod
        def create(**kwargs):
            return FakeSpeechResponse()

    class FakeAudioAPI:
        speech = FakeSpeechAPI()

    class FakeOpenAI:
        def __init__(self, api_key):
            self.audio = FakeAudioAPI()

    monkeypatch.setattr("backend.src.services.tts_service.OpenAI", FakeOpenAI)

    result = await generate_story_audio_file(
        text="Story with emotion",
        voice="nova",
        speed=1.0,
        emotion="happy",
        pitch=3,
        volume=7.0,
        age_group="6-8",
    )

    assert result["success"] is True
    assert result["provider"] == "openai"
