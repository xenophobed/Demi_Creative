"""
Story Memory Contract Tests (#165)

Verifies that get_story_memory_prompt returns a usable prompt section
and that the interactive/image-to-story agents inject it correctly.

Parent Epic: #42 | Issue: #165
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def story_memory_module():
    from backend.src.services.story_memory import get_story_memory_prompt
    return get_story_memory_prompt


class TestGetStoryMemoryPrompt:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_stories(self, story_memory_module):
        get_story_memory_prompt = story_memory_module
        with patch("backend.src.services.story_memory.story_repo") as mock_repo:
            mock_repo.list_by_child = AsyncMock(return_value=[])
            result = await get_story_memory_prompt("child-new")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_prompt_with_story_previews(self, story_memory_module):
        get_story_memory_prompt = story_memory_module
        stories = [
            {
                "story_text": "Lightning Dog flew to the moon and found a glowing rock.",
                "themes": json.dumps(["space", "adventure"]),
            },
            {
                "story_text": "A tiny cat explored the deep ocean with a submarine.",
                "themes": json.dumps(["ocean", "exploration"]),
            },
        ]
        with patch("backend.src.services.story_memory.story_repo") as mock_repo:
            mock_repo.list_by_child = AsyncMock(return_value=stories)
            result = await get_story_memory_prompt("child-abc")

        assert "Story Memory" in result
        assert "Lightning Dog" in result
        assert "tiny cat" in result
        assert "space" in result

    @pytest.mark.asyncio
    async def test_truncates_long_story_text(self, story_memory_module):
        get_story_memory_prompt = story_memory_module
        long_text = "A" * 200
        stories = [{"story_text": long_text, "themes": "[]"}]
        with patch("backend.src.services.story_memory.story_repo") as mock_repo:
            mock_repo.list_by_child = AsyncMock(return_value=stories)
            result = await get_story_memory_prompt("child-long")

        assert "..." in result

    @pytest.mark.asyncio
    async def test_handles_themes_as_list(self, story_memory_module):
        get_story_memory_prompt = story_memory_module
        stories = [
            {"story_text": "A story about cats.", "themes": ["cats", "fun"]},
        ]
        with patch("backend.src.services.story_memory.story_repo") as mock_repo:
            mock_repo.list_by_child = AsyncMock(return_value=stories)
            result = await get_story_memory_prompt("child-list")

        assert "cats" in result

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, story_memory_module):
        get_story_memory_prompt = story_memory_module
        with patch("backend.src.services.story_memory.story_repo") as mock_repo:
            mock_repo.list_by_child = AsyncMock(return_value=[])
            await get_story_memory_prompt("child-lim", limit=5)
            mock_repo.list_by_child.assert_called_once_with("child-lim", limit=5)


class TestPromptInjection:
    @pytest.mark.asyncio
    async def test_interactive_story_prompt_includes_memory(self):
        """interactive_story_agent injects story memory into opening prompt."""
        from backend.src.agents.interactive_story_agent import _build_opening_prompt

        prompt = _build_opening_prompt(
            child_id="child-1",
            age_group="6-8",
            interests_str="space, dogs",
            theme_str="adventure",
            config={
                "word_count": "100-150",
                "sentence_length": "medium",
                "complexity": "moderate",
                "vocab_level": "grade 2-3",
                "theme_depth": "moderate",
                "choices_style": "action-based",
            },
            story_memory_section="**Story Memory**:\n1. Lightning Dog flew...",
        )
        assert "Story Memory" in prompt
        assert "Lightning Dog" in prompt

    @pytest.mark.asyncio
    async def test_interactive_story_prompt_ok_without_memory(self):
        """interactive_story_agent works fine with empty story memory."""
        from backend.src.agents.interactive_story_agent import _build_opening_prompt

        prompt = _build_opening_prompt(
            child_id="child-1",
            age_group="6-8",
            interests_str="space, dogs",
            theme_str="adventure",
            config={
                "word_count": "100-150",
                "sentence_length": "medium",
                "complexity": "moderate",
                "vocab_level": "grade 2-3",
                "theme_depth": "moderate",
                "choices_style": "action-based",
            },
            story_memory_section="",
        )
        assert "Story Memory" not in prompt
