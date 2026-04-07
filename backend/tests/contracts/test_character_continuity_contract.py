"""
Character Continuity Contract Tests (#365)

Verifies that:
1. get_story_memory_prompt includes character names from character_repository
2. kids_daily_agent uses recurring characters as podcast guest
3. interactive_story_agent prompt includes deterministic character section

Parent Epic: #42 | Issue: #365
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Story memory prompt must include character names
# ---------------------------------------------------------------------------


class TestStoryMemoryIncludesCharacters:
    """get_story_memory_prompt must inject known characters deterministically."""

    @pytest.fixture()
    def get_story_memory_prompt(self):
        from backend.src.services.story_memory import get_story_memory_prompt
        return get_story_memory_prompt

    @pytest.mark.asyncio
    async def test_includes_character_names_when_available(self, get_story_memory_prompt):
        """Character names from character_repo must appear in the memory prompt."""
        stories = [
            {
                "story_text": "Lightning Dog flew to the moon.",
                "themes": json.dumps(["space"]),
            },
        ]
        characters = [
            {
                "name": "Lightning Dog",
                "description": "A brave puppy who can fly",
                "traits": ["brave", "loyal"],
                "appearance_count": 3,
            },
            {
                "name": "Star Cat",
                "description": "A curious cat from the stars",
                "traits": ["curious"],
                "appearance_count": 1,
            },
        ]
        with (
            patch("backend.src.services.story_memory.story_repo") as mock_story,
            patch("backend.src.services.story_memory.character_repo") as mock_char,
        ):
            mock_story.list_by_child = AsyncMock(return_value=stories)
            mock_char.get_characters = AsyncMock(return_value=characters)
            result = await get_story_memory_prompt("child-abc")

        assert "Lightning Dog" in result
        assert "Star Cat" in result
        assert "brave" in result or "loyal" in result

    @pytest.mark.asyncio
    async def test_no_character_section_when_no_characters(self, get_story_memory_prompt):
        """When no characters exist, prompt should still work (stories only)."""
        stories = [
            {
                "story_text": "A fish swam in the ocean.",
                "themes": json.dumps(["ocean"]),
            },
        ]
        with (
            patch("backend.src.services.story_memory.story_repo") as mock_story,
            patch("backend.src.services.story_memory.character_repo") as mock_char,
        ):
            mock_story.list_by_child = AsyncMock(return_value=stories)
            mock_char.get_characters = AsyncMock(return_value=[])
            result = await get_story_memory_prompt("child-empty")

        assert "Story Memory" in result
        # No character section when there are no characters
        assert "Recurring Characters" not in result

    @pytest.mark.asyncio
    async def test_characters_shown_even_without_stories(self, get_story_memory_prompt):
        """If there are characters but no stories, still include character section."""
        characters = [
            {
                "name": "Rainbow Bird",
                "description": "A colorful bird",
                "traits": ["cheerful"],
                "appearance_count": 2,
            },
        ]
        with (
            patch("backend.src.services.story_memory.story_repo") as mock_story,
            patch("backend.src.services.story_memory.character_repo") as mock_char,
        ):
            mock_story.list_by_child = AsyncMock(return_value=[])
            mock_char.get_characters = AsyncMock(return_value=characters)
            result = await get_story_memory_prompt("child-chars-only")

        assert "Rainbow Bird" in result

    @pytest.mark.asyncio
    async def test_user_scoped_character_fetch(self, get_story_memory_prompt):
        """When user_id is provided, character_repo.get_characters uses it."""
        with (
            patch("backend.src.services.story_memory.story_repo") as mock_story,
            patch("backend.src.services.story_memory.character_repo") as mock_char,
        ):
            mock_story.list_by_user_and_child = AsyncMock(return_value=[])
            mock_char.get_characters = AsyncMock(return_value=[])
            await get_story_memory_prompt("child-1", user_id="user-42")

        mock_char.get_characters.assert_called_once_with("user-42", "child-1")


# ---------------------------------------------------------------------------
# 2. Kids daily agent must prefer recurring character as guest
# ---------------------------------------------------------------------------


class TestKidsDailyGuestFromCharacters:
    """Podcast guest should come from child's recurring characters."""

    @pytest.mark.asyncio
    async def test_guest_uses_recurring_character_in_mock(self):
        """In mock mode, guest_character should be top recurring character."""
        from backend.src.agents.kids_daily_agent import generate_kids_daily_dialogue

        characters = [
            {
                "name": "Lightning Dog",
                "description": "A brave puppy",
                "traits": ["brave"],
                "appearance_count": 5,
            },
        ]
        with patch(
            "backend.src.agents.kids_daily_agent.character_repo"
        ) as mock_char:
            mock_char.get_characters = AsyncMock(return_value=characters)
            result = await generate_kids_daily_dialogue(
                news_text="Scientists found a new planet.",
                age_group="6-8",
                child_id="child-with-chars",
            )

        assert result["guest_character"] == "Lightning Dog"

    @pytest.mark.asyncio
    async def test_guest_falls_back_to_default_without_characters(self):
        """Without recurring characters, fall back to default guest."""
        from backend.src.agents.kids_daily_agent import (
            generate_kids_daily_dialogue,
            _DEFAULT_GUESTS,
        )

        with patch(
            "backend.src.agents.kids_daily_agent.character_repo"
        ) as mock_char:
            mock_char.get_characters = AsyncMock(return_value=[])
            result = await generate_kids_daily_dialogue(
                news_text="New robot helps kids learn.",
                age_group="6-8",
                child_id="child-no-chars",
            )

        assert result["guest_character"] in _DEFAULT_GUESTS

    @pytest.mark.asyncio
    async def test_guest_falls_back_without_child_id(self):
        """Without child_id, default guest is used (no character lookup)."""
        from backend.src.agents.kids_daily_agent import (
            generate_kids_daily_dialogue,
            _DEFAULT_GUESTS,
        )

        result = await generate_kids_daily_dialogue(
            news_text="Fun science facts.",
            age_group="6-8",
        )

        assert result["guest_character"] in _DEFAULT_GUESTS


# ---------------------------------------------------------------------------
# 3. Interactive story prompt includes deterministic character section
# ---------------------------------------------------------------------------


class TestInteractiveStoryCharacterInjection:
    """_build_opening_prompt must accept and inject character memory."""

    def test_prompt_includes_character_memory_section(self):
        from backend.src.agents.interactive_story_agent import _build_opening_prompt

        char_section = (
            "\n**Recurring Characters**:\n"
            "- Lightning Dog (appeared 3 times): brave, loyal\n"
        )
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
            character_memory_section=char_section,
        )
        assert "Recurring Characters" in prompt
        assert "Lightning Dog" in prompt
        assert "appeared 3 times" in prompt

    def test_prompt_ok_without_character_memory(self):
        from backend.src.agents.interactive_story_agent import _build_opening_prompt

        prompt = _build_opening_prompt(
            child_id="child-1",
            age_group="6-8",
            interests_str="space",
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
            character_memory_section="",
        )
        assert "Recurring Characters" not in prompt
