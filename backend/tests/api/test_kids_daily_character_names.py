"""
API tests for Kids Daily character names (Duo & Mimi) — #140.

Validates that:
- display_name appears on DialogueLine in mock-generated output
- Mimi maps to curious_kid, Duo maps to fun_expert
- role_display_names mapping is included in agent output
- TTS voice assignment is unaffected by display names
"""

import pytest

from backend.src.agents.kids_daily_agent import (
    ROLE_DISPLAY_NAMES,
    generate_kids_daily_dialogue,
    _build_mock_dialogue_script,
    pick_age_voice,
)


class TestCharacterNamesInMockOutput:
    """Validate character names appear in mock-generated dialogue."""

    def test_mock_dialogue_lines_have_display_names(self):
        """Mock output must include display_name on every line (#140).

        The guest's label is the chosen Guest Anchor (not None), so the UI can
        attribute the line without the name being spoken aloud.
        """
        script = _build_mock_dialogue_script("space discovery", "6-8", "Professor Owl")
        for line in script.lines:
            if line.role == "curious_kid":
                assert line.display_name == "Mimi"
            elif line.role == "fun_expert":
                assert line.display_name == "Duo"
            elif line.role == "guest":
                assert line.display_name == "Professor Owl"

    def test_mock_dialogue_text_is_name_free(self):
        """Spoken text must NOT contain the speaker's name — it is read by TTS.

        Attribution lives in display_name / the role label; baking "Mimi:" /
        "Duo:" into text made the narrator say the name aloud and doubled it on
        screen. The name must never start the spoken sentence.
        """
        script = _build_mock_dialogue_script("robots", "6-8", "Professor Owl")
        for line in script.lines:
            assert not line.text.startswith("Mimi:"), line.text
            assert not line.text.startswith("Duo:"), line.text
            assert not line.text.startswith("Professor Owl"), line.text

    def test_role_display_names_constant(self):
        """ROLE_DISPLAY_NAMES must map correctly (#140)."""
        assert ROLE_DISPLAY_NAMES == {
            "curious_kid": "Mimi",
            "fun_expert": "Duo",
            "guest": None,
        }


class TestCharacterNamesInAgentOutput:
    """Validate agent output includes role_display_names."""

    @pytest.mark.asyncio
    async def test_generate_includes_role_display_names(self):
        """generate_kids_daily_dialogue must return role_display_names (#140)."""
        result = await generate_kids_daily_dialogue(
            news_text="Scientists found a new planet.",
            age_group="6-8",
        )
        assert "role_display_names" in result
        assert result["role_display_names"]["curious_kid"] == "Mimi"
        assert result["role_display_names"]["fun_expert"] == "Duo"
        assert result["role_display_names"]["guest"] is None

    @pytest.mark.asyncio
    async def test_generate_dialogue_lines_have_display_name(self):
        """Each dialogue line in agent output must have display_name (#140)."""
        result = await generate_kids_daily_dialogue(
            news_text="New robot helps kids learn.",
            age_group="3-5",
        )
        lines = result["dialogue_script"]["lines"]
        guest_name = result["dialogue_script"]["guest_character"]
        assert len(lines) > 0
        for line in lines:
            if line["role"] == "curious_kid":
                assert line["display_name"] == "Mimi"
            elif line["role"] == "fun_expert":
                assert line["display_name"] == "Duo"
            elif line["role"] == "guest":
                # Guest is labeled with the chosen character, not None.
                assert line["display_name"] == guest_name


class TestTTSVoiceUnchanged:
    """Ensure TTS voice assignment remains role-based, not name-based (#140)."""

    def test_voice_maps_to_role_not_name(self):
        """pick_age_voice must use role, not display name."""
        voice_ck, _ = pick_age_voice("curious_kid", "6-8")
        voice_fe, _ = pick_age_voice("fun_expert", "6-8")
        # Voices are role-based; just verify they still work
        assert isinstance(voice_ck, str)
        assert isinstance(voice_fe, str)
        assert voice_ck != voice_fe
