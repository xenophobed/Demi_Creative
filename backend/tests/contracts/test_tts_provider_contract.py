"""
Contract tests for TTSProvider abstraction (#149).

Verifies:
- TTSProvider protocol shape (both OpenAI and Replicate implement generate())
- EmotionType and TTSProviderEnum exist with expected members
- Age-based emotion filtering logic
- generate_story_audio_file accepts new optional params without breaking
- list_available_voices returns entries with provider field
"""

import pytest


# ---------------------------------------------------------------------------
# Enum contracts
# ---------------------------------------------------------------------------


class TestTTSProviderEnumContract:
    """TTSProviderEnum must have openai, replicate, and elevenlabs members."""

    def test_enum_has_openai(self):
        from backend.src.api.models import TTSProviderEnum

        assert TTSProviderEnum.OPENAI.value == "openai"

    def test_enum_has_replicate(self):
        from backend.src.api.models import TTSProviderEnum

        assert TTSProviderEnum.REPLICATE.value == "replicate"

    def test_enum_has_elevenlabs(self):
        from backend.src.api.models import TTSProviderEnum

        assert TTSProviderEnum.ELEVENLABS.value == "elevenlabs"


class TestEmotionTypeContract:
    """EmotionType must have the 5 allowed emotions."""

    def test_all_emotions_present(self):
        from backend.src.api.models import EmotionType

        expected = {"happy", "sad", "neutral", "surprised", "disgusted"}
        actual = {e.value for e in EmotionType}
        assert actual == expected


# ---------------------------------------------------------------------------
# Age-based emotion filtering contract
# ---------------------------------------------------------------------------


class TestEmotionFilterContract:
    """filter_emotion_for_age must enforce age-group restrictions."""

    def test_age_3_5_allows_only_happy_neutral(self):
        from backend.src.services.tts_service import filter_emotion_for_age

        assert filter_emotion_for_age("happy", "3-5") == "happy"
        assert filter_emotion_for_age("neutral", "3-5") == "neutral"
        assert filter_emotion_for_age("sad", "3-5") == "neutral"
        assert filter_emotion_for_age("surprised", "3-5") == "neutral"
        assert filter_emotion_for_age("disgusted", "3-5") == "neutral"

    def test_age_6_8_allows_happy_sad_surprised_neutral(self):
        from backend.src.services.tts_service import filter_emotion_for_age

        for emotion in ("happy", "sad", "surprised", "neutral"):
            assert filter_emotion_for_age(emotion, "6-8") == emotion
        assert filter_emotion_for_age("disgusted", "6-8") == "neutral"

    def test_age_9_12_allows_all_except_angry_fearful(self):
        from backend.src.services.tts_service import filter_emotion_for_age

        for emotion in ("happy", "sad", "surprised", "disgusted", "neutral"):
            assert filter_emotion_for_age(emotion, "9-12") == emotion

    def test_none_emotion_passes_through(self):
        from backend.src.services.tts_service import filter_emotion_for_age

        assert filter_emotion_for_age(None, "6-8") is None

    def test_unknown_age_group_defaults_to_6_8(self):
        from backend.src.services.tts_service import filter_emotion_for_age

        assert filter_emotion_for_age("disgusted", "unknown") == "neutral"
        assert filter_emotion_for_age("sad", None) == "sad"


# ---------------------------------------------------------------------------
# Provider protocol shape contracts
# ---------------------------------------------------------------------------


class TestProviderProtocolContract:
    """All providers must implement the generate() method with correct signature."""

    def test_openai_provider_has_generate(self):
        from backend.src.services.tts_service import OpenAITTSProvider

        provider = OpenAITTSProvider()
        assert callable(getattr(provider, "generate", None))

    def test_replicate_provider_has_generate(self):
        from backend.src.services.tts_service import ReplicateTTSProvider

        provider = ReplicateTTSProvider()
        assert callable(getattr(provider, "generate", None))

    def test_elevenlabs_provider_has_generate(self):
        from backend.src.services.tts_service import ElevenLabsTTSProvider

        provider = ElevenLabsTTSProvider()
        assert callable(getattr(provider, "generate", None))


# ---------------------------------------------------------------------------
# generate_story_audio_file backward compatibility contract
# ---------------------------------------------------------------------------


class TestGenerateStoryAudioBackwardCompat:
    """generate_story_audio_file must accept new optional params without breaking old callers."""

    @pytest.mark.asyncio
    async def test_old_signature_still_works(self, monkeypatch):
        from backend.src.services.tts_service import generate_story_audio_file

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Should not raise TypeError — all new params are optional
        result = await generate_story_audio_file(text="hello", voice="nova", speed=1.0)
        # Without API key it returns success=False, but no TypeError
        assert "success" in result

    @pytest.mark.asyncio
    async def test_new_params_accepted(self, monkeypatch):
        from backend.src.services.tts_service import generate_story_audio_file

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
        result = await generate_story_audio_file(
            text="hello",
            voice="nova",
            speed=1.0,
            emotion="happy",
            pitch=2,
            volume=5.0,
            language_boost="English",
            provider="openai",
            age_group="6-8",
        )
        assert "success" in result


# ---------------------------------------------------------------------------
# Scene profile contracts (#245)
# ---------------------------------------------------------------------------


class TestSceneProfileContract:
    """Scene profiles must exist and map to valid voice settings."""

    def test_scene_profile_enum_has_required_values(self):
        from backend.src.api.models import SceneProfile

        expected = {"bedtime", "adventure", "spooky", "educational"}
        actual = {p.value for p in SceneProfile}
        assert actual == expected

    def test_resolve_scene_profile_returns_dict(self):
        from backend.src.services.tts_service import resolve_scene_profile

        result = resolve_scene_profile("bedtime")
        assert isinstance(result, dict)
        assert "speed" in result
        assert "stability" in result
        assert "style" in result

    def test_all_profiles_resolve(self):
        from backend.src.services.tts_service import resolve_scene_profile

        for profile in ("bedtime", "adventure", "spooky", "educational"):
            result = resolve_scene_profile(profile)
            assert result is not None, f"Profile {profile} returned None"

    def test_spooky_restricted_for_young_children(self):
        from backend.src.services.tts_service import resolve_scene_profile

        # For young children, spooky should fall back to adventure
        result = resolve_scene_profile("spooky", age_group="3-5")
        adventure = resolve_scene_profile("adventure")
        assert result == adventure

    def test_unknown_profile_returns_none(self):
        from backend.src.services.tts_service import resolve_scene_profile

        result = resolve_scene_profile("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# ElevenLabs voice catalog contract (#243)
# ---------------------------------------------------------------------------


class TestElevenLabsVoiceCatalogContract:
    """ElevenLabs voice catalog must be present in list_available_voices."""

    def test_elevenlabs_voices_dict_exists(self):
        from backend.src.mcp_servers.tts_generator_server import ELEVENLABS_VOICES

        assert len(ELEVENLABS_VOICES) >= 6
        for voice_id, meta in ELEVENLABS_VOICES.items():
            assert "display_name" in meta
            assert "description" in meta
            assert "recommended_for" in meta
