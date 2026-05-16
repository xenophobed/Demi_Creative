"""
Interactive Story Contract Tests (Issue #499)

Closes the test-coverage gap identified during #499 investigation: there
was no dedicated contract test for interactive_story (only memory-focused
tests existed). Mirrors the pattern in test_image_to_story_contract.py.

Validates:
1. StoryOpeningOutput / NextSegmentOutput / StorySegmentOutput / StoryChoiceOutput
   Pydantic models have stable field shapes
2. AGE_CONFIG has all three age groups with expected keys
3. get_total_segments returns correct values for known modes

Parent Epic: #436 (My Agent — Personal Creative Buddy)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestStoryChoiceOutputContract:
    """Contract: StoryChoiceOutput is the per-choice schema."""

    def test_valid_choice(self):
        from backend.src.agents.interactive_story_agent import StoryChoiceOutput

        choice = StoryChoiceOutput(choice_id="a", text="Open the door", emoji="🚪")

        assert choice.choice_id == "a"
        assert choice.text == "Open the door"
        assert choice.emoji == "🚪"

    def test_all_fields_required(self):
        from backend.src.agents.interactive_story_agent import StoryChoiceOutput

        with pytest.raises(ValidationError) as exc:
            StoryChoiceOutput()  # type: ignore[call-arg]

        msg = str(exc.value)
        for required in ("choice_id", "text", "emoji"):
            assert required in msg, f"{required} should be required"


class TestStorySegmentOutputContract:
    """Contract: StorySegmentOutput is the per-segment schema."""

    def test_valid_segment(self):
        from backend.src.agents.interactive_story_agent import (
            StoryChoiceOutput,
            StorySegmentOutput,
        )

        segment = StorySegmentOutput(
            segment_id=1,
            text="Once upon a time...",
            choices=[StoryChoiceOutput(choice_id="a", text="Go", emoji="➡️")],
            is_ending=False,
        )

        assert segment.segment_id == 1
        assert segment.text == "Once upon a time..."
        assert len(segment.choices) == 1
        assert segment.is_ending is False

    def test_choices_default_empty(self):
        from backend.src.agents.interactive_story_agent import StorySegmentOutput

        seg = StorySegmentOutput(segment_id=1, text="x")
        assert seg.choices == []

    def test_is_ending_defaults_false(self):
        from backend.src.agents.interactive_story_agent import StorySegmentOutput

        seg = StorySegmentOutput(segment_id=1, text="x")
        assert seg.is_ending is False

    def test_segment_id_and_text_required(self):
        from backend.src.agents.interactive_story_agent import StorySegmentOutput

        with pytest.raises(ValidationError) as exc:
            StorySegmentOutput()  # type: ignore[call-arg]

        msg = str(exc.value)
        assert "segment_id" in msg
        assert "text" in msg


class TestStoryOpeningOutputContract:
    """Contract: StoryOpeningOutput wraps title + opening segment."""

    def test_valid_opening(self):
        from backend.src.agents.interactive_story_agent import (
            StoryOpeningOutput,
            StorySegmentOutput,
        )

        opening = StoryOpeningOutput(
            title="The Mystery Hat",
            segment=StorySegmentOutput(segment_id=1, text="A wizard found a hat..."),
        )

        assert opening.title == "The Mystery Hat"
        assert opening.segment.segment_id == 1

    def test_title_and_segment_required(self):
        from backend.src.agents.interactive_story_agent import StoryOpeningOutput

        with pytest.raises(ValidationError) as exc:
            StoryOpeningOutput()  # type: ignore[call-arg]

        msg = str(exc.value)
        assert "title" in msg
        assert "segment" in msg


class TestNextSegmentOutputContract:
    """Contract: NextSegmentOutput is the response shape for continuation turns."""

    def test_valid_next_segment(self):
        from backend.src.agents.interactive_story_agent import (
            NextSegmentOutput,
            StorySegmentOutput,
        )

        out = NextSegmentOutput(
            segment=StorySegmentOutput(segment_id=2, text="Then..."),
            is_ending=False,
        )

        assert out.segment.segment_id == 2
        assert out.is_ending is False
        assert out.educational_summary is None

    def test_educational_summary_is_optional(self):
        from backend.src.agents.interactive_story_agent import (
            NextSegmentOutput,
            StorySegmentOutput,
        )

        out = NextSegmentOutput(
            segment=StorySegmentOutput(segment_id=3, text="The end."),
            is_ending=True,
            educational_summary={"vocabulary": ["brave", "kind"]},
        )

        assert out.educational_summary == {"vocabulary": ["brave", "kind"]}


class TestAgeConfigContract:
    """Contract: AGE_CONFIG must cover all three age groups with expected keys."""

    def test_all_age_groups_present(self):
        from backend.src.agents.interactive_story_agent import AGE_CONFIG

        for age in ("3-5", "6-8", "9-12"):
            assert age in AGE_CONFIG, f"Missing age group: {age}"

    def test_required_keys_per_group(self):
        from backend.src.agents.interactive_story_agent import AGE_CONFIG

        required_keys = {
            "word_count",
            "complexity",
            "voice",
            "total_segments",
        }

        for age, cfg in AGE_CONFIG.items():
            missing = required_keys - set(cfg.keys())
            assert not missing, f"Age {age} missing keys: {missing}"

    def test_total_segments_is_positive_integer(self):
        from backend.src.agents.interactive_story_agent import AGE_CONFIG

        for age, cfg in AGE_CONFIG.items():
            assert isinstance(cfg["total_segments"], int)
            assert cfg["total_segments"] > 0, (
                f"Age {age} has non-positive total_segments"
            )


class TestGetTotalSegmentsContract:
    """Contract: get_total_segments() returns stable values for known modes."""

    def test_function_is_importable(self):
        from backend.src.agents.interactive_story_agent import get_total_segments

        assert callable(get_total_segments)

    def test_returns_integer(self):
        from backend.src.agents.interactive_story_agent import get_total_segments

        result = get_total_segments("short", "6-8")
        assert isinstance(result, int)
        assert result > 0

    def test_handles_all_age_groups(self):
        from backend.src.agents.interactive_story_agent import get_total_segments

        for age in ("3-5", "6-8", "9-12"):
            result = get_total_segments("short", age)
            assert isinstance(result, int)
            assert result > 0
