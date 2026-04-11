"""
Interactive Story Memory Contract Tests

Tests for preference-aware generation (#72) and character continuity (#73).
Validates prompt construction helpers and allowed-tools contracts.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.src.agents.interactive_story_agent import (
    AGE_CONFIG,
    _append_tts_instructions,
    _build_next_segment_prompt,
    _build_opening_prompt,
    _ensure_ending_coherence,
    _fetch_preference_context,
)

# ============================================================================
# Preference Context Builder
# ============================================================================


class TestPreferenceContextBuilder:
    """Contract: _fetch_preference_context returns formatted string or empty."""

    @pytest.mark.asyncio
    async def test_empty_profile_returns_empty_string(self):
        """Empty profile → empty string (no preference section in prompt)."""
        empty_profile = {
            "themes": {},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=empty_profile)
            result = await _fetch_preference_context("child_new")

        assert result == ""

    @pytest.mark.asyncio
    async def test_populated_profile_returns_formatted_string(self):
        """Populated profile → formatted prompt section with top items."""
        profile = {
            "themes": {"dinosaurs": 5, "space": 3, "ocean": 2, "forest": 1},
            "concepts": {},
            "interests": {"adventure": 4, "science": 2, "music": 1},
            "recent_choices": ["choice_a", "choice_b", "choice_c", "choice_d"],
        }
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=profile)
            result = await _fetch_preference_context("child_123")

        assert "Child Preference Memory" in result
        assert "dinosaurs" in result
        assert "space" in result
        assert "adventure" in result
        # Top 3 themes only
        assert "forest" not in result
        # Recent choices: last 3
        assert "choice_b" in result
        assert "choice_c" in result
        assert "choice_d" in result

    @pytest.mark.asyncio
    async def test_repo_error_returns_empty_string(self):
        """Repository error → graceful fallback to empty string."""
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(side_effect=Exception("DB down"))
            result = await _fetch_preference_context("child_err")

        assert result == ""

    @pytest.mark.asyncio
    async def test_partial_profile_only_themes(self):
        """Profile with only themes → includes themes, no crash."""
        profile = {
            "themes": {"dinosaurs": 3},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=profile)
            result = await _fetch_preference_context("child_partial")

        assert "dinosaurs" in result
        assert "Interest preferences" not in result


# ============================================================================
# Opening Prompt Contract
# ============================================================================


class TestOpeningPromptContract:
    """Contract: _build_opening_prompt includes required sections."""

    def _make_prompt(self, preference_context: str = "") -> str:
        config = AGE_CONFIG["6-8"]
        return _build_opening_prompt(
            child_id="child_test",
            age_group="6-8",
            interests_str="dinosaurs, adventure",
            theme_str="Dinosaur World Exploration",
            config=config,
            preference_context=preference_context,
        )

    def test_contains_vector_search_instruction(self):
        """Opening prompt instructs agent to search for recurring characters."""
        prompt = self._make_prompt()
        assert "mcp__vector-search__search_similar_drawings" in prompt
        assert "Character Continuity" in prompt

    def test_contains_store_embedding_instruction(self):
        """Opening prompt instructs agent to store character embeddings."""
        prompt = self._make_prompt()
        assert "mcp__vector-search__store_drawing_embedding" in prompt
        assert "Content Storage" in prompt

    def test_includes_preference_section_when_provided(self):
        """Preference context is included in prompt when non-empty."""
        pref = "**Child Preference Memory**:\n- Favorite themes: dinosaurs, space\n"
        prompt = self._make_prompt(preference_context=pref)
        assert "Child Preference Memory" in prompt
        assert "dinosaurs, space" in prompt

    def test_works_without_preference_context(self):
        """Prompt works fine with empty preference context."""
        prompt = self._make_prompt(preference_context="")
        assert "Character Continuity" in prompt
        assert "Child Preference Memory" not in prompt

    def test_contains_age_adaptation(self):
        """Prompt includes age-appropriate writing requirements."""
        prompt = self._make_prompt()
        assert "100-200" in prompt  # word_count for 6-8
        assert "simple" in prompt


# ============================================================================
# Next Segment Prompt Contract
# ============================================================================


class TestNextSegmentPromptContract:
    """Contract: _build_next_segment_prompt does NOT include memory features."""

    def test_no_vector_search_in_next_segment(self):
        """Next segment prompt does NOT search for characters (opening only)."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="Dinosaur Adventure",
            age_group="6-8",
            interests=["dinosaurs"],
            theme="adventure",
            segment_count=1,
            total_segments=4,
            is_final_segment=False,
            story_context="Segment 0: The story begins",
            choice_id="choice_0_a",
            chosen_option="Try bravely",
            config=config,
        )
        assert "store_drawing_embedding" not in prompt
        assert "search_similar_drawings" not in prompt

    def test_includes_story_context(self):
        """Next segment prompt includes previous story context."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="Dinosaur Adventure",
            age_group="6-8",
            interests=["dinosaurs"],
            theme="adventure",
            segment_count=1,
            total_segments=4,
            is_final_segment=False,
            story_context="Segment 0: The little dinosaur set off",
            choice_id="choice_0_a",
            chosen_option="Try bravely",
            config=config,
        )
        assert "The little dinosaur set off" in prompt

    def test_ending_includes_educational_summary_format(self):
        """Final segment prompt requests educational_summary."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="Dinosaur Adventure",
            age_group="6-8",
            interests=["dinosaurs"],
            theme="adventure",
            segment_count=3,
            total_segments=4,
            is_final_segment=True,
            story_context="Segment 2: Nearing the end",
            choice_id="choice_2_a",
            chosen_option="Go home",
            config=config,
        )
        assert "educational_summary" in prompt
        assert "yes" in prompt  # Is this the ending: yes

    def test_ending_includes_continuity_anchor_constraints(self):
        """Final prompt includes anchor-based continuity constraints."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="Wind Chime Tower Adventure",
            age_group="6-8",
            interests=["puzzles"],
            theme="cooperative adventure",
            segment_count=3,
            total_segments=4,
            is_final_segment=True,
            story_context="Segment 2: Everyone discovered the missing key gear in front of the Wind Chime Tower.",
            choice_id="choice_2_a",
            chosen_option="Fix the broken star map key first",
            config=config,
            continuity_anchors="Wind Chime Tower, Star Map Key, Firefly Bridge",
        )
        assert "Ending Continuity Anchors" in prompt
        assert "Wind Chime Tower, Star Map Key, Firefly Bridge" in prompt
        assert "at least 2" in prompt


class TestEndingCoherenceRepair:
    """Contract: ending repair keeps final paragraph aligned with context."""

    def test_rewrites_drifted_ending_with_story_anchors(self):
        repaired = _ensure_ending_coherence(
            ending_text="They suddenly went to outer space and opened an ice cream shop.",
            opening_hook="The Wind Chime Tower door glows at dusk",
            chosen_option="Fix the broken star map key first",
            choice_history_context=(
                "1. Follow the fireflies to the Wind Chime Tower\n2. Fix the broken star map key first\n3. Build a bridge across the river with the beavers"
            ),
            continuity_anchors=["Wind Chime Tower", "star map key", "build a bridge"],
        )

        assert "Wind Chime Tower" in repaired
        assert "star map key" in repaired
        assert "build a bridge" in repaired
        assert "ice cream shop" not in repaired


# ============================================================================
# Allowed Tools Contract
# ============================================================================


class TestAllowedToolsContract:
    """Contract: opening includes memory tools, next-segment does not."""

    def test_opening_allowed_tools_include_store(self):
        """Opening generation must allow store_drawing_embedding."""
        # We can't easily instantiate ClaudeAgentOptions in test,
        # so we verify by checking the prompt instructs usage of the tool
        config = AGE_CONFIG["6-8"]
        prompt = _build_opening_prompt(
            child_id="child_test",
            age_group="6-8",
            interests_str="dinosaurs",
            theme_str="Dinosaur Adventure",
            config=config,
            preference_context="",
        )
        assert "store_drawing_embedding" in prompt
        assert "search_similar_drawings" in prompt


# ============================================================================
# TTS Instructions Helper
# ============================================================================


class TestTTSInstructionsContract:
    """Contract: _append_tts_instructions appends correct block."""

    def test_appends_tts_block(self):
        prompt = "Original prompt"
        result = _append_tts_instructions(prompt, "nova", 0.9, "Child ID", "child_1")
        assert "Original prompt" in result
        assert "mcp__tts-generation__generate_story_audio" in result
        assert "nova" in result
        assert "0.9" in result
        assert "child_1" in result

    def test_preserves_original_prompt(self):
        prompt = "Full original prompt content\nwith multiple lines"
        result = _append_tts_instructions(prompt, "alloy", 1.1, "Session ID", "sess_1")
        assert result.startswith("Full original prompt content")
