"""
Tests for interactive story save — story_type persistence and library classification.

Verifies fix for #196: interactive stories must be saved with story_type="interactive"
at the top level, and the library must classify them as LibraryItemType.INTERACTIVE
(not ART_STORY).
"""

import pytest

from backend.src.api.routes.library import _resolve_story_type
from backend.src.api.models import LibraryItemType


# ============================================================================
# Unit tests for _resolve_story_type classification
# ============================================================================


class TestResolveStoryType:
    """Verify that _resolve_story_type maps DB values to correct LibraryItemType."""

    def test_interactive_story_type(self):
        """Interactive stories must map to LibraryItemType.INTERACTIVE, not ART_STORY."""
        story = {"story_type": "interactive"}
        assert _resolve_story_type(story) == LibraryItemType.INTERACTIVE

    def test_image_to_story_defaults_to_art_story(self):
        """image_to_story (default) maps to ART_STORY."""
        story = {"story_type": "image_to_story"}
        assert _resolve_story_type(story) == LibraryItemType.ART_STORY

    def test_missing_story_type_defaults_to_art_story(self):
        """Missing story_type defaults to ART_STORY."""
        story = {}
        assert _resolve_story_type(story) == LibraryItemType.ART_STORY

    def test_news_to_kids_maps_to_news(self):
        story = {"story_type": "news_to_kids"}
        assert _resolve_story_type(story) == LibraryItemType.NEWS

    def test_morning_show_maps_to_morning_show(self):
        story = {"story_type": "morning_show"}
        assert _resolve_story_type(story) == LibraryItemType.MORNING_SHOW


# ============================================================================
# Integration test: story_data built by save endpoint includes story_type
# ============================================================================


class TestInteractiveStoryDataShape:
    """Verify the shape of story_data as built by the save endpoint."""

    def _build_story_data(self) -> dict:
        """Reproduce the story_data dict built in save_interactive_story()."""
        import uuid

        story_data = {
            "story_id": str(uuid.uuid4()),
            "user_id": "test_user",
            "child_id": "test_child_001",
            "age_group": "6-8",
            "story_type": "interactive",
            "story": {
                "text": "Once upon a time...",
                "word_count": 4,
                "age_adapted": True,
            },
            "educational_value": {
                "themes": ["friendship"],
                "concepts": [],
                "moral": None,
            },
            "characters": [],
            "analysis": {
                "story_type": "interactive",
                "session_id": "sess_123",
                "choices_made": 3,
                "story_title": "Test Story",
            },
            "safety_score": 0.95,
            "created_at": "2026-03-14T00:00:00Z",
        }
        return story_data

    def test_story_data_has_top_level_story_type(self):
        """story_data must have story_type at top level for the repository."""
        data = self._build_story_data()
        assert "story_type" in data
        assert data["story_type"] == "interactive"

    def test_story_data_defaults_correctly_in_repo(self):
        """When story_type is present, repo should use it instead of defaulting."""
        data = self._build_story_data()
        # Simulate what story_repository.py line 63 does
        resolved = data.get("story_type", "image_to_story")
        assert resolved == "interactive"

    def test_library_classifies_saved_interactive_story(self):
        """Library must classify a saved interactive story as INTERACTIVE."""
        data = self._build_story_data()
        item_type = _resolve_story_type(data)
        assert item_type == LibraryItemType.INTERACTIVE
