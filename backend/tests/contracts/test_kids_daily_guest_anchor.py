"""
Kids Daily — Guest Anchor selection + name-prefix bug fix.

Covers two defects:
1. Speaker names must NOT appear in spoken `text` (they belong in display_name /
   role label) — otherwise TTS reads the name aloud and the UI shows it twice.
2. When a child has 2+ characters, the user can choose which one is the Guest
   Anchor; an unknown/spoofed pick falls back to the most-frequent character.
"""

import pytest

from backend.src.agents import kids_daily_agent as agent
from backend.src.agents.kids_daily_agent import (
    ROLE_DISPLAY_NAMES,
    _build_mock_dialogue_script,
    _resolve_guest_choice,
    generate_kids_daily_dialogue,
    strip_self_name_prefix,
)
from backend.src.services.tts_service import _strip_self_name_prefix as tts_strip


# ---------------------------------------------------------------------------
# Issue 1: spoken text is name-free
# ---------------------------------------------------------------------------
class TestNameNotInSpokenText:
    def test_mock_lines_do_not_prefix_speaker_name(self):
        script = _build_mock_dialogue_script("space", "6-8", "Lightning Dog")
        for line in script.lines:
            assert not line.text.startswith("Mimi:"), line.text
            assert not line.text.startswith("Duo:"), line.text
            # Guest must not announce its own name either.
            assert not line.text.startswith("Lightning Dog"), line.text

    def test_curious_kid_and_expert_keep_fixed_display_names(self):
        script = _build_mock_dialogue_script("animals", "3-5", "Rainbow Cat")
        for line in script.lines:
            if line.role == "curious_kid":
                assert line.display_name == ROLE_DISPLAY_NAMES["curious_kid"] == "Mimi"
            elif line.role == "fun_expert":
                assert line.display_name == ROLE_DISPLAY_NAMES["fun_expert"] == "Duo"

    def test_guest_line_labeled_with_chosen_character(self):
        script = _build_mock_dialogue_script("science", "9-12", "Rainbow Cat")
        guest_lines = [ln for ln in script.lines if ln.role == "guest"]
        assert guest_lines, "mock script should contain a guest line"
        for line in guest_lines:
            assert line.display_name == "Rainbow Cat"

    @pytest.mark.parametrize(
        "text,name,expected",
        [
            ("Duo: Great question!", "Duo", "Great question!"),
            ("Mimi: Why is this cool?", "Mimi", "Why is this cool?"),
            ("Lightning Dog says: Hello!", "Lightning Dog", "Hello!"),
            ("duo - hi there", "Duo", "hi there"),
            # Must NOT strip legitimate content that merely contains a colon.
            ("Today: we learned to share.", "Duo", "Today: we learned to share."),
            ("No prefix here.", "Mimi", "No prefix here."),
            ("Anything", None, "Anything"),
        ],
    )
    def test_strip_self_name_prefix(self, text, name, expected):
        assert strip_self_name_prefix(text, name) == expected
        # The TTS-side guard mirrors the agent-side guard.
        assert tts_strip(text, name) == expected


# ---------------------------------------------------------------------------
# Issue 2: user-chosen Guest Anchor
# ---------------------------------------------------------------------------
class TestResolveGuestChoice:
    ROSTER = [
        {"name": "Lightning Dog", "appearance_count": 9},
        {"name": "Rainbow Cat", "appearance_count": 3},
    ]

    def test_honors_valid_pick(self):
        assert _resolve_guest_choice("Rainbow Cat", self.ROSTER, "Owl") == "Rainbow Cat"

    def test_pick_is_case_and_space_insensitive(self):
        assert _resolve_guest_choice("  rainbow cat ", self.ROSTER, "Owl") == "Rainbow Cat"

    def test_empty_pick_falls_back_to_most_frequent(self):
        assert _resolve_guest_choice(None, self.ROSTER, "Owl") == "Lightning Dog"
        assert _resolve_guest_choice("  ", self.ROSTER, "Owl") == "Lightning Dog"

    def test_unknown_pick_falls_back_to_most_frequent(self):
        # A name the child does not own must never reach the show.
        assert _resolve_guest_choice("Spooky Ghost", self.ROSTER, "Owl") == "Lightning Dog"


@pytest.mark.asyncio
class TestGenerateDialogueHonorsGuest:
    ROSTER = [
        {"name": "Lightning Dog", "appearance_count": 9},
        {"name": "Rainbow Cat", "appearance_count": 3},
    ]

    async def test_chosen_guest_is_used(self, monkeypatch):
        async def fake_get_characters(user_id, child_id):
            return self.ROSTER

        monkeypatch.setattr(agent.character_repo, "get_characters", fake_get_characters)

        result = await generate_kids_daily_dialogue(
            news_text="A friendly news story about space rocks.",
            age_group="6-8",
            child_id="child-1",
            user_id="user-1",
            guest_character="Rainbow Cat",
        )
        assert result["guest_character"] == "Rainbow Cat"
        guest_lines = [
            ln for ln in result["dialogue_script"]["lines"] if ln["role"] == "guest"
        ]
        assert guest_lines and all(ln["display_name"] == "Rainbow Cat" for ln in guest_lines)

    async def test_unknown_guest_falls_back_to_most_frequent(self, monkeypatch):
        async def fake_get_characters(user_id, child_id):
            return self.ROSTER

        monkeypatch.setattr(agent.character_repo, "get_characters", fake_get_characters)

        result = await generate_kids_daily_dialogue(
            news_text="A friendly news story about animals.",
            age_group="6-8",
            child_id="child-1",
            user_id="user-1",
            guest_character="Not A Real Character",
        )
        assert result["guest_character"] == "Lightning Dog"
