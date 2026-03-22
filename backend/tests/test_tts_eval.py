"""Tests for the TTS evaluation harness (#246)."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import tts_eval  # noqa: E402


class TestStoryDiscovery:
    """Golden story set must be complete and well-named."""

    def test_discovers_15_stories(self):
        stories = tts_eval.discover_stories()
        assert len(stories) == 15, f"Expected 15 golden stories, got {len(stories)}"

    def test_5_stories_per_age_group(self):
        stories = tts_eval.discover_stories()
        for ag in ["3-5", "6-8", "9-12"]:
            count = sum(1 for s in stories if s["age_group"] == ag)
            assert count == 5, f"Expected 5 stories for {ag}, got {count}"

    def test_scene_types_present(self):
        stories = tts_eval.discover_stories()
        scene_types = {s["scene_type"] for s in stories}
        assert "bedtime" in scene_types
        assert "adventure" in scene_types
        assert "educational" in scene_types

    def test_stories_are_nonempty(self):
        stories = tts_eval.discover_stories()
        for s in stories:
            text = Path(s["path"]).read_text(encoding="utf-8").strip()
            assert len(text) > 50, f"Story {s['filename']} is too short ({len(text)} chars)"


class TestVoiceMatrix:
    """Voice matrix must cover all providers × age groups."""

    def test_all_providers_present(self):
        for p in tts_eval.PROVIDERS:
            assert p in tts_eval.VOICE_MATRIX, f"Provider {p} missing from VOICE_MATRIX"

    def test_all_age_groups_per_provider(self):
        for p in tts_eval.PROVIDERS:
            for ag in tts_eval.AGE_GROUPS:
                assert ag in tts_eval.VOICE_MATRIX[p], \
                    f"Age group {ag} missing for provider {p}"


class TestEvalResult:
    """EvalResult data class must serialize correctly."""

    def test_serializable(self):
        from dataclasses import asdict
        r = tts_eval.EvalResult(
            story_file="test.txt",
            age_group="3-5",
            scene_type="bedtime",
            provider="openai",
            voice="nova",
            success=True,
            latency_ms=1234.5,
            file_size_bytes=65536,
            text_length=200,
        )
        d = asdict(r)
        assert d["provider"] == "openai"
        assert d["latency_ms"] == 1234.5
        # Must be JSON-serializable
        json.dumps(d)


class TestSummarize:
    """Summary statistics must be computed correctly."""

    def test_computes_averages(self):
        results = [
            tts_eval.EvalResult("a.txt", "3-5", "bedtime", "openai", "nova", True, 100, 1000, 50),
            tts_eval.EvalResult("b.txt", "3-5", "adventure", "openai", "nova", True, 200, 2000, 60),
            tts_eval.EvalResult("c.txt", "6-8", "bedtime", "openai", "nova", False, 500, 0, 70, error="fail"),
        ]
        summaries = tts_eval.summarize(results)
        assert len(summaries) == 1
        s = summaries[0]
        assert s.provider == "openai"
        assert s.total_runs == 3
        assert s.successes == 2
        assert s.failures == 1
        assert s.avg_latency_ms == 150.0  # (100+200)/2, failure excluded
        assert s.success_rate == pytest.approx(0.667, abs=0.01)

    def test_multiple_providers(self):
        results = [
            tts_eval.EvalResult("a.txt", "3-5", "bedtime", "openai", "nova", True, 100, 1000, 50),
            tts_eval.EvalResult("a.txt", "3-5", "bedtime", "elevenlabs", "x", True, 200, 2000, 50),
        ]
        summaries = tts_eval.summarize(results)
        assert len(summaries) == 2
        providers = {s.provider for s in summaries}
        assert providers == {"openai", "elevenlabs"}


class TestEvaluateSingle:
    """Single-sample evaluation with mocked TTS."""

    @pytest.mark.asyncio
    async def test_success_path(self, tmp_path):
        story = {
            "path": str(tmp_path / "test.txt"),
            "age_group": "3-5",
            "scene_type": "bedtime",
            "filename": "test.txt",
        }
        (tmp_path / "test.txt").write_text("Hello world test story.")

        mock_audio = tmp_path / "mock.mp3"
        mock_audio.write_bytes(b"\xff" * 100)

        with patch("tts_eval.generate_story_audio_file", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "success": True,
                "audio_path": str(mock_audio),
                "latency_ms": 500,
                "fallback_used": False,
            }

            result = await tts_eval.evaluate_single(story, "openai", tmp_path / "out")

        assert result.success is True
        assert result.provider == "openai"
        assert result.text_length == len("Hello world test story.")

    @pytest.mark.asyncio
    async def test_failure_path(self, tmp_path):
        story = {
            "path": str(tmp_path / "test.txt"),
            "age_group": "6-8",
            "scene_type": "adventure",
            "filename": "test.txt",
        }
        (tmp_path / "test.txt").write_text("A short test story.")

        with patch("tts_eval.generate_story_audio_file", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = RuntimeError("API key missing")

            result = await tts_eval.evaluate_single(story, "elevenlabs", tmp_path / "out")

        assert result.success is False
        assert "API key" in result.error
