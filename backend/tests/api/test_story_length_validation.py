"""
Tests for post-generation story length validation per age group (#233).

Covers:
- validate_story_length() for each age group at-range, under-range, over-range
- Drastic out-of-range detection (needs_retry)
- Edge cases (empty text, unknown age group)
"""

import pytest

from backend.src.agents.image_to_story_agent import (
    validate_story_length,
    repair_story_length,
    AGE_GROUP_WORD_RANGES,
)


# ---------------------------------------------------------------------------
# Helper: build a story with an exact word count
# ---------------------------------------------------------------------------

def _make_story(word_count: int) -> str:
    """Return a string with exactly ``word_count`` whitespace-separated words."""
    return " ".join(f"word{i}" for i in range(word_count))


# ---------------------------------------------------------------------------
# Tests for each age group
# ---------------------------------------------------------------------------

class TestValidateStoryLength:
    """Unit tests for validate_story_length()."""

    # --- 3-5 age group (100-200 words) ---

    def test_age_3_5_at_minimum(self):
        result = validate_story_length(_make_story(100), "3-5")
        assert result["word_count"] == 100
        assert result["in_range"] is True
        assert result["degraded_length"] is False
        assert result["needs_retry"] is False

    def test_age_3_5_at_maximum(self):
        result = validate_story_length(_make_story(200), "3-5")
        assert result["word_count"] == 200
        assert result["in_range"] is True
        assert result["degraded_length"] is False
        assert result["needs_retry"] is False

    def test_age_3_5_in_middle(self):
        result = validate_story_length(_make_story(150), "3-5")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_age_3_5_slightly_under(self):
        """Under range but not drastically (>= 50% of min)."""
        result = validate_story_length(_make_story(80), "3-5")
        assert result["in_range"] is False
        assert result["degraded_length"] is True
        assert result["needs_retry"] is False  # 80 >= 50 (50% of 100)

    def test_age_3_5_slightly_over(self):
        """Over range but not drastically (<= 150% of max)."""
        result = validate_story_length(_make_story(250), "3-5")
        assert result["in_range"] is False
        assert result["degraded_length"] is True
        assert result["needs_retry"] is False  # 250 <= 300 (150% of 200)

    def test_age_3_5_drastically_short(self):
        """Below 50% of minimum → needs_retry."""
        result = validate_story_length(_make_story(40), "3-5")
        assert result["degraded_length"] is True
        assert result["needs_retry"] is True  # 40 < 50 (50% of 100)

    def test_age_3_5_drastically_long(self):
        """Above 150% of maximum → needs_retry."""
        result = validate_story_length(_make_story(350), "3-5")
        assert result["degraded_length"] is True
        assert result["needs_retry"] is True  # 350 > 300 (150% of 200)

    # --- 6-8 age group (200-400 words) ---

    def test_age_6_8_at_minimum(self):
        result = validate_story_length(_make_story(200), "6-8")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_age_6_8_at_maximum(self):
        result = validate_story_length(_make_story(400), "6-8")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_age_6_8_under_range(self):
        result = validate_story_length(_make_story(150), "6-8")
        assert result["degraded_length"] is True
        assert result["needs_retry"] is False  # 150 >= 100 (50% of 200)

    def test_age_6_8_drastically_short(self):
        result = validate_story_length(_make_story(80), "6-8")
        assert result["needs_retry"] is True  # 80 < 100 (50% of 200)

    def test_age_6_8_drastically_long(self):
        result = validate_story_length(_make_story(650), "6-8")
        assert result["needs_retry"] is True  # 650 > 600 (150% of 400)

    # --- 9-12 age group (400-800 words) ---

    def test_age_9_12_at_minimum(self):
        result = validate_story_length(_make_story(400), "9-12")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_age_9_12_at_maximum(self):
        result = validate_story_length(_make_story(800), "9-12")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_age_9_12_under_range(self):
        result = validate_story_length(_make_story(350), "9-12")
        assert result["degraded_length"] is True
        assert result["needs_retry"] is False  # 350 >= 200 (50% of 400)

    def test_age_9_12_drastically_short(self):
        result = validate_story_length(_make_story(150), "9-12")
        assert result["needs_retry"] is True  # 150 < 200 (50% of 400)

    def test_age_9_12_drastically_long(self):
        result = validate_story_length(_make_story(1300), "9-12")
        assert result["needs_retry"] is True  # 1300 > 1200 (150% of 800)

    # --- Edge cases ---

    def test_empty_text(self):
        result = validate_story_length("", "6-8")
        assert result["word_count"] == 0
        assert result["degraded_length"] is True
        assert result["needs_retry"] is True

    def test_unknown_age_group_defaults_to_6_8(self):
        """Unknown age group falls back to (200, 400)."""
        result = validate_story_length(_make_story(300), "unknown")
        assert result["in_range"] is True
        assert result["degraded_length"] is False

    def test_exact_boundary_50_percent_min(self):
        """Exactly at 50% of minimum — NOT drastically short."""
        # 3-5: min=100, 50% = 50 → exactly 50 should NOT trigger retry
        result = validate_story_length(_make_story(50), "3-5")
        assert result["needs_retry"] is False
        assert result["degraded_length"] is True

    def test_exact_boundary_150_percent_max(self):
        """Exactly at 150% of maximum — NOT drastically long."""
        # 3-5: max=200, 150% = 300 → exactly 300 should NOT trigger retry
        result = validate_story_length(_make_story(300), "3-5")
        assert result["needs_retry"] is False
        assert result["degraded_length"] is True


class TestRepairStoryLength:
    """Unit tests for delivery-time story length repair."""

    def test_repairs_short_story_to_age_range(self):
        repaired, info = repair_story_length("Tiny story.", "6-8")

        assert info["repaired"] is True
        assert info["in_range"] is True
        assert 200 <= info["word_count"] <= 400
        assert repaired.startswith("Tiny story.")

    def test_repairs_long_story_to_age_range(self):
        repaired, info = repair_story_length(_make_story(500), "3-5")

        assert info["repaired"] is True
        assert info["in_range"] is True
        assert 100 <= info["word_count"] <= 200
        assert repaired.endswith(".")

    def test_in_range_story_is_unchanged(self):
        story = _make_story(220)

        repaired, info = repair_story_length(story, "6-8")

        assert repaired == story
        assert info["repaired"] is False
        assert info["in_range"] is True
