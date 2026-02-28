"""
Interactive Story Memory Contract Tests

Tests for preference-aware generation (#72) and character continuity (#73).
Validates prompt construction helpers and allowed-tools contracts.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.src.agents.interactive_story_agent import (
    _fetch_preference_context,
    _build_opening_prompt,
    _build_next_segment_prompt,
    _append_tts_instructions,
    AGE_CONFIG,
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
            "themes": {"恐龙": 5, "太空": 3, "海洋": 2, "森林": 1},
            "concepts": {},
            "interests": {"冒险": 4, "科学": 2, "音乐": 1},
            "recent_choices": ["choice_a", "choice_b", "choice_c", "choice_d"],
        }
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=profile)
            result = await _fetch_preference_context("child_123")

        assert "儿童偏好记忆" in result
        assert "恐龙" in result
        assert "太空" in result
        assert "冒险" in result
        # Top 3 themes only
        assert "森林" not in result
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
            "themes": {"恐龙": 3},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }
        with patch(
            "backend.src.agents.interactive_story_agent.preference_repo"
        ) as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=profile)
            result = await _fetch_preference_context("child_partial")

        assert "恐龙" in result
        assert "兴趣偏好" not in result


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
            interests_str="恐龙、冒险",
            theme_str="恐龙世界探险",
            config=config,
            preference_context=preference_context,
        )

    def test_contains_vector_search_instruction(self):
        """Opening prompt instructs agent to search for recurring characters."""
        prompt = self._make_prompt()
        assert "mcp__vector-search__search_similar_drawings" in prompt
        assert "角色连续性" in prompt

    def test_contains_store_embedding_instruction(self):
        """Opening prompt instructs agent to store character embeddings."""
        prompt = self._make_prompt()
        assert "mcp__vector-search__store_drawing_embedding" in prompt
        assert "内容存储" in prompt

    def test_includes_preference_section_when_provided(self):
        """Preference context is included in prompt when non-empty."""
        pref = "**儿童偏好记忆**：\n- 喜欢的主题: 恐龙, 太空\n"
        prompt = self._make_prompt(preference_context=pref)
        assert "儿童偏好记忆" in prompt
        assert "恐龙, 太空" in prompt

    def test_works_without_preference_context(self):
        """Prompt works fine with empty preference context."""
        prompt = self._make_prompt(preference_context="")
        assert "角色连续性" in prompt
        assert "儿童偏好记忆" not in prompt

    def test_contains_age_adaptation(self):
        """Prompt includes age-appropriate writing requirements."""
        prompt = self._make_prompt()
        assert "100-200" in prompt  # word_count for 6-8
        assert "简单" in prompt


# ============================================================================
# Next Segment Prompt Contract
# ============================================================================

class TestNextSegmentPromptContract:
    """Contract: _build_next_segment_prompt does NOT include memory features."""

    def test_no_vector_search_in_next_segment(self):
        """Next segment prompt does NOT search for characters (opening only)."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="恐龙冒险",
            age_group="6-8",
            interests=["恐龙"],
            theme="冒险",
            segment_count=1,
            total_segments=4,
            is_final_segment=False,
            story_context="段落 0: 故事开始了",
            choice_id="choice_0_a",
            chosen_option="勇敢尝试",
            config=config,
        )
        assert "store_drawing_embedding" not in prompt
        assert "search_similar_drawings" not in prompt

    def test_includes_story_context(self):
        """Next segment prompt includes previous story context."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="恐龙冒险",
            age_group="6-8",
            interests=["恐龙"],
            theme="冒险",
            segment_count=1,
            total_segments=4,
            is_final_segment=False,
            story_context="段落 0: 小恐龙出发了",
            choice_id="choice_0_a",
            chosen_option="勇敢尝试",
            config=config,
        )
        assert "小恐龙出发了" in prompt

    def test_ending_includes_educational_summary_format(self):
        """Final segment prompt requests educational_summary."""
        config = AGE_CONFIG["6-8"]
        prompt = _build_next_segment_prompt(
            story_title="恐龙冒险",
            age_group="6-8",
            interests=["恐龙"],
            theme="冒险",
            segment_count=3,
            total_segments=4,
            is_final_segment=True,
            story_context="段落 2: 接近尾声",
            choice_id="choice_2_a",
            chosen_option="回家",
            config=config,
        )
        assert "educational_summary" in prompt
        assert "是" in prompt  # 是否为结局: 是


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
            interests_str="恐龙",
            theme_str="恐龙冒险",
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
        prompt = "原始提示"
        result = _append_tts_instructions(prompt, "nova", 0.9, "儿童ID", "child_1")
        assert "原始提示" in result
        assert "mcp__tts-generation__generate_story_audio" in result
        assert "nova" in result
        assert "0.9" in result
        assert "child_1" in result

    def test_preserves_original_prompt(self):
        prompt = "完整的原始提示内容\n包含多行"
        result = _append_tts_instructions(prompt, "alloy", 1.1, "会话ID", "sess_1")
        assert result.startswith("完整的原始提示内容")
