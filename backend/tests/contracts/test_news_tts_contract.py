"""Contract tests for News-to-Kids TTS audio narration (issue #155).

Verifies:
- _get_audio_config returns correct config per age group
- convert_news_to_kids accepts enable_audio/voice params
- enable_audio=False returns audio_path: None
- enable_audio=True in mock env returns result (audio_path may be None)
"""

import pytest

from backend.src.agents.news_to_kids_agent import (
    _get_audio_config,
    convert_news_to_kids,
)


class TestGetAudioConfig:
    """Contract: _get_audio_config returns age-appropriate TTS settings."""

    def test_age_3_5_returns_audio_first_nova(self):
        config = _get_audio_config("3-5")
        assert config["audio_mode"] == "audio_first"
        assert config["voice"] == "nova"
        assert config["speed"] == 0.9

    def test_age_6_8_returns_simultaneous_shimmer(self):
        config = _get_audio_config("6-8")
        assert config["audio_mode"] == "simultaneous"
        assert config["voice"] == "shimmer"
        assert config["speed"] == 1.0

    def test_age_9_12_returns_text_first_alloy(self):
        config = _get_audio_config("9-12")
        assert config["audio_mode"] == "text_first"
        assert config["voice"] == "alloy"
        assert config["speed"] == 1.1

    def test_unknown_age_falls_back_to_6_8(self):
        config = _get_audio_config("unknown")
        assert config == _get_audio_config("6-8")


class TestConvertNewsToKidsAudioParams:
    """Contract: convert_news_to_kids accepts and handles audio parameters."""

    @pytest.mark.asyncio
    async def test_audio_disabled_returns_none_audio_path(self):
        result = await convert_news_to_kids(
            news_text="Scientists discovered a new species of butterfly in the Amazon rainforest.",
            age_group="6-8",
            child_id="test-child-1",
            category="science",
            enable_audio=False,
            voice=None,
        )
        assert "audio_path" in result
        assert result["audio_path"] is None

    @pytest.mark.asyncio
    async def test_audio_enabled_returns_result_with_audio_path_key(self):
        result = await convert_news_to_kids(
            news_text="A new park opened in the city center with a big playground.",
            age_group="3-5",
            child_id="test-child-2",
            category="community",
            enable_audio=True,
            voice="nova",
        )
        assert "audio_path" in result
        # In mock/test env, audio_path will be None (no real TTS call)
        assert result["audio_path"] is None

    @pytest.mark.asyncio
    async def test_result_still_contains_required_fields(self):
        result = await convert_news_to_kids(
            news_text="The school robotics team won the national competition.",
            age_group="9-12",
            child_id="test-child-3",
            category="education",
            enable_audio=True,
        )
        assert "kid_title" in result
        assert "kid_content" in result
        assert "why_care" in result
        assert "key_concepts" in result
        assert "interactive_questions" in result
        assert "audio_path" in result

    @pytest.mark.asyncio
    async def test_signature_accepts_voice_param(self):
        """Ensure the function signature accepts voice without TypeError."""
        result = await convert_news_to_kids(
            news_text="Weather forecast shows sunny skies all week.",
            age_group="6-8",
            child_id="test-child-4",
            category="weather",
            enable_audio=True,
            voice="shimmer",
        )
        assert isinstance(result, dict)
