import os

import pytest

from backend.src.services.tts_service import (
    filter_emotion_for_age,
    generate_story_audio_file,
    ReplicateTTSProvider,
    ElevenLabsTTSProvider,
    resolve_scene_profile,
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


# ---------------------------------------------------------------------------
# ElevenLabs provider unit tests (#243)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_elevenlabs_provider_calls_sdk(monkeypatch, tmp_path):
    """ElevenLabsTTSProvider should call ElevenLabs API with correct params."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    captured = {}

    class FakeVoiceSettings:
        def __init__(self, **kwargs):
            captured["voice_settings"] = kwargs

    class FakeConvertResult:
        """Async iterator that yields audio bytes."""
        def __init__(self):
            self._data = [b"fake-elevenlabs-audio"]
            self._index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._index < len(self._data):
                chunk = self._data[self._index]
                self._index += 1
                return chunk
            raise StopAsyncIteration

    class FakeTTS:
        async def convert(self, **kwargs):
            captured["tts_kwargs"] = kwargs
            return FakeConvertResult()

    class FakeAsyncClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.text_to_speech = FakeTTS()

    monkeypatch.setattr(
        "backend.src.services.tts_service._elevenlabs_AsyncClient", FakeAsyncClient
    )
    monkeypatch.setattr(
        "backend.src.services.tts_service._elevenlabs_VoiceSettings", FakeVoiceSettings
    )

    provider = ElevenLabsTTSProvider()
    audio_path = str(tmp_path / "test.mp3")

    result = await provider.generate(
        text="Hello world",
        voice="test-voice-id",
        speed=1.0,
        audio_path=audio_path,
        emotion="happy",
    )

    assert result["success"] is True
    assert result["provider"] == "elevenlabs"
    assert captured["api_key"] == "test-key"
    assert captured["tts_kwargs"]["voice_id"] == "test-voice-id"
    assert os.path.exists(audio_path)


@pytest.mark.asyncio
async def test_elevenlabs_provider_missing_key(monkeypatch):
    """ElevenLabsTTSProvider should fail gracefully without API key."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    provider = ElevenLabsTTSProvider()
    result = await provider.generate(
        text="Hello", voice="test", speed=1.0, audio_path="/tmp/x.mp3",
    )

    assert result["success"] is False
    assert "ELEVENLABS_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_elevenlabs_emotion_to_stability_mapping():
    """Emotion should map to ElevenLabs stability/style presets."""
    provider = ElevenLabsTTSProvider()

    mapping = provider._emotion_to_voice_settings("happy")
    assert mapping["stability"] < 0.5  # More expressive
    assert mapping["style"] > 0

    mapping = provider._emotion_to_voice_settings("neutral")
    assert mapping["stability"] > 0.5  # More stable
    assert mapping["style"] == 0.0

    # Unknown emotion returns neutral-like defaults
    mapping = provider._emotion_to_voice_settings(None)
    assert mapping["stability"] > 0.5


@pytest.mark.asyncio
async def test_fallback_from_elevenlabs_to_openai(monkeypatch, tmp_path):
    """When ElevenLabs fails, generate_story_audio_file should fall back to OpenAI."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

    # Make ElevenLabs always fail
    from backend.src.services.tts_service import ElevenLabsTTSProvider as _EL

    async def _fail_generate(self, **kwargs):
        return {"success": False, "error": "elevenlabs down"}

    monkeypatch.setattr(_EL, "generate", _fail_generate)

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
        provider="elevenlabs",
    )

    assert result["success"] is True
    assert result["fallback_used"] is True
    assert result["provider"] == "openai"


# ---------------------------------------------------------------------------
# Scene profile tests (#245)
# ---------------------------------------------------------------------------


def test_resolve_scene_profile_bedtime():
    result = resolve_scene_profile("bedtime")
    assert result["speed"] < 1.0
    assert result["stability"] > 0.5


def test_resolve_scene_profile_adventure():
    result = resolve_scene_profile("adventure")
    assert result["speed"] >= 1.0
    assert result["style"] > 0


def test_resolve_scene_profile_spooky_restricted_for_young():
    result = resolve_scene_profile("spooky", age_group="3-5")
    adventure = resolve_scene_profile("adventure")
    assert result == adventure


def test_resolve_scene_profile_unknown():
    assert resolve_scene_profile("nonexistent") is None
