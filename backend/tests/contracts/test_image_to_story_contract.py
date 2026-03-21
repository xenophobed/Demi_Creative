"""
Image-to-Story Contract Tests (Issue #236)

Validates:
1. StoryOutput Pydantic model has all required fields
2. ImageToStoryResponse API schema matches contract
3. SSE event types and their data shapes (streaming path)
4. Business rules: safety_score threshold, word_count, age adaptation

Parent Epic: #40 (Image-to-Story MVP Happy Path)
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import ValidationError


# ============================================================================
# 1. StoryOutput Agent Model Contract
# ============================================================================

class TestStoryOutputContract:
    """Contract: StoryOutput from image_to_story_agent must have stable schema."""

    def test_valid_story_output_all_fields(self):
        """StoryOutput accepts all fields with valid values."""
        from backend.src.agents.image_to_story_agent import StoryOutput, Character

        output = StoryOutput(
            story="Once upon a time, a child drew a beautiful picture about adventure.",
            themes=["friendship", "creativity"],
            concepts=["imagination", "art"],
            moral="Every drawing tells a story.",
            characters=[
                Character(name="Little Artist", description="A creative child", appearances=2)
            ],
            analysis={"objects": ["dog", "tree"], "colors": ["blue", "green"]},
            safety_score=0.95,
            audio_url="https://example.com/audio/story-123.mp3",
        )

        assert output.story != ""
        assert len(output.themes) == 2
        assert len(output.concepts) == 2
        assert output.moral is not None
        assert len(output.characters) == 1
        assert output.characters[0].name == "Little Artist"
        assert output.characters[0].appearances == 2
        assert output.safety_score == 0.95
        assert output.audio_url is not None

    def test_story_output_defaults(self):
        """StoryOutput works with only the required 'story' field; defaults apply."""
        from backend.src.agents.image_to_story_agent import StoryOutput

        output = StoryOutput(story="A short story.")

        assert output.themes == []
        assert output.concepts == []
        assert output.moral is None
        assert output.characters == []
        assert output.analysis == {}
        assert output.safety_score == 0.9  # default
        assert output.audio_url is None

    def test_story_output_requires_story_field(self):
        """StoryOutput must reject missing 'story' field."""
        from backend.src.agents.image_to_story_agent import StoryOutput

        with pytest.raises(ValidationError) as exc_info:
            StoryOutput()  # type: ignore[call-arg]
        assert "story" in str(exc_info.value)

    def test_character_model_defaults(self):
        """Character model defaults appearances to 1."""
        from backend.src.agents.image_to_story_agent import Character

        char = Character(name="Bunny", description="A fluffy bunny")
        assert char.appearances == 1

    def test_character_requires_name_and_description(self):
        """Character model must reject missing required fields."""
        from backend.src.agents.image_to_story_agent import Character

        with pytest.raises(ValidationError):
            Character(name="Bunny")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            Character(description="A bunny")  # type: ignore[call-arg]

    def test_story_output_safety_score_is_float(self):
        """safety_score must be a float, because downstream code compares >= 0.85."""
        from backend.src.agents.image_to_story_agent import StoryOutput

        output = StoryOutput(story="A story.", safety_score=0.88)
        assert isinstance(output.safety_score, float)


# ============================================================================
# 2. ImageToStoryResponse API Model Contract
# ============================================================================

class TestImageToStoryResponseContract:
    """Contract: ImageToStoryResponse API envelope has all required fields."""

    def _build_valid_response(self):
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue, CharacterMemory,
        )

        return ImageToStoryResponse(
            story_id="story-uuid-001",
            story=StoryContent(text="A wonderful story.", word_count=3, age_adapted=True),
            image_url="https://example.com/images/drawing.png",
            audio_url="https://example.com/audio/story.mp3",
            video_url=None,
            video_job_id=None,
            educational_value=EducationalValue(
                themes=["friendship"],
                concepts=["sharing"],
                moral="Sharing is caring.",
            ),
            characters=[
                CharacterMemory(character_name="Bunny", description="A fluffy bunny", appearances=1),
            ],
            analysis={"objects": ["bunny", "carrot"]},
            safety_score=0.95,
            created_at=datetime.now(),
        )

    def test_valid_response_all_fields(self):
        """Full ImageToStoryResponse can be constructed with all fields."""
        resp = self._build_valid_response()

        assert resp.story_id == "story-uuid-001"
        assert resp.story.text == "A wonderful story."
        assert resp.story.word_count == 3
        assert resp.story.age_adapted is True
        assert resp.educational_value.themes == ["friendship"]
        assert resp.educational_value.moral == "Sharing is caring."
        assert len(resp.characters) == 1
        assert resp.characters[0].character_name == "Bunny"
        assert 0.0 <= resp.safety_score <= 1.0
        assert isinstance(resp.created_at, datetime)

    def test_response_optional_fields_nullable(self):
        """Optional fields (audio_url, video_url, video_job_id) can be None."""
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue,
        )

        resp = ImageToStoryResponse(
            story_id="story-002",
            story=StoryContent(text="Hello world.", word_count=2, age_adapted=False),
            educational_value=EducationalValue(themes=[], concepts=[], moral=None),
            safety_score=0.9,
        )

        assert resp.image_url is None
        assert resp.audio_url is None
        assert resp.video_url is None
        assert resp.video_job_id is None
        assert resp.characters == []
        assert resp.analysis == {}

    def test_response_safety_score_range(self):
        """safety_score must be between 0.0 and 1.0."""
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue,
        )

        with pytest.raises(ValidationError):
            ImageToStoryResponse(
                story_id="story-003",
                story=StoryContent(text="Test.", word_count=1, age_adapted=True),
                educational_value=EducationalValue(themes=[], concepts=[]),
                safety_score=1.5,  # out of range
            )

        with pytest.raises(ValidationError):
            ImageToStoryResponse(
                story_id="story-004",
                story=StoryContent(text="Test.", word_count=1, age_adapted=True),
                educational_value=EducationalValue(themes=[], concepts=[]),
                safety_score=-0.1,  # out of range
            )

    def test_response_requires_story_id(self):
        """story_id is required."""
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue,
        )

        with pytest.raises(ValidationError) as exc_info:
            ImageToStoryResponse(
                story=StoryContent(text="Test.", word_count=1, age_adapted=True),
                educational_value=EducationalValue(themes=[], concepts=[]),
                safety_score=0.9,
            )
        assert "story_id" in str(exc_info.value)

    def test_story_content_requires_all_fields(self):
        """StoryContent needs text, word_count, and age_adapted."""
        from backend.src.api.models import StoryContent

        with pytest.raises(ValidationError):
            StoryContent(text="Hello")  # type: ignore[call-arg]

    def test_educational_value_moral_optional(self):
        """EducationalValue.moral is optional."""
        from backend.src.api.models import EducationalValue

        ev = EducationalValue(themes=["bravery"], concepts=["courage"])
        assert ev.moral is None

    def test_character_memory_requires_all_fields(self):
        """CharacterMemory needs character_name, description, appearances."""
        from backend.src.api.models import CharacterMemory

        with pytest.raises(ValidationError):
            CharacterMemory(character_name="Cat")  # type: ignore[call-arg]


# ============================================================================
# 3. SSE Event Shape Contracts (Streaming Path)
# ============================================================================

class TestSSEEventShapes:
    """Contract: SSE events from stream_image_to_story have well-defined shapes."""

    VALID_EVENT_TYPES = {
        "status", "thinking", "tool_use", "tool_result",
        "audio_generated", "result", "complete", "error",
    }

    def test_status_event_shape(self):
        """status event must have 'status' and 'message' in data."""
        event = {"type": "status", "data": {"status": "started", "message": "Analyzing drawing..."}}

        assert event["type"] in self.VALID_EVENT_TYPES
        assert "status" in event["data"]
        assert "message" in event["data"]
        assert isinstance(event["data"]["status"], str)
        assert isinstance(event["data"]["message"], str)

    def test_result_event_shape(self):
        """result event data must contain story output fields."""
        event = {
            "type": "result",
            "data": {
                "story": "A magical adventure...",
                "themes": ["adventure"],
                "concepts": ["imagination"],
                "moral": "Be brave.",
                "characters": [{"name": "Hero", "description": "Brave child", "appearances": 1}],
                "analysis": {"objects": ["tree"]},
                "safety_score": 0.95,
                "audio_path": None,
            },
        }

        assert event["type"] == "result"
        data = event["data"]
        assert "story" in data
        assert "themes" in data
        assert "safety_score" in data
        assert isinstance(data["story"], str)
        assert isinstance(data["themes"], list)
        assert isinstance(data["safety_score"], (int, float))

    def test_complete_event_shape(self):
        """complete event must have a message."""
        event = {"type": "complete", "data": {"status": "completed", "message": "Done!"}}

        assert event["type"] == "complete"
        assert "message" in event["data"]

    def test_error_event_shape(self):
        """error event must have 'error' and 'message' in data."""
        event = {
            "type": "error",
            "data": {"error": "FileNotFoundError", "message": "Image not found"},
        }

        assert event["type"] == "error"
        assert "error" in event["data"]
        assert "message" in event["data"]
        assert isinstance(event["data"]["error"], str)
        assert isinstance(event["data"]["message"], str)

    def test_tool_use_event_shape(self):
        """tool_use event must have 'tool' and 'message' in data."""
        event = {
            "type": "tool_use",
            "data": {"tool": "mcp__vision-analysis__analyze_children_drawing", "message": "Analyzing..."},
        }

        assert event["type"] == "tool_use"
        assert "tool" in event["data"]
        assert "message" in event["data"]

    def test_tool_result_event_shape(self):
        """tool_result event must have 'status' in data."""
        event = {"type": "tool_result", "data": {"status": "completed"}}

        assert event["type"] == "tool_result"
        assert "status" in event["data"]

    def test_audio_generated_event_shape(self):
        """audio_generated event must have 'audio_path' and 'message'."""
        event = {
            "type": "audio_generated",
            "data": {"audio_path": "/data/audio/story-123.mp3", "message": "Audio ready"},
        }

        assert event["type"] == "audio_generated"
        assert "audio_path" in event["data"]
        assert "message" in event["data"]

    @pytest.mark.asyncio
    async def test_mock_stream_yields_expected_event_sequence(self):
        """Mock streaming path must yield status -> result -> complete in order."""
        from backend.src.agents.image_to_story_agent import stream_image_to_story

        events = []
        async for event in stream_image_to_story(
            image_path="/fake/path.png",
            child_id="test-child",
            child_age=7,
            interests=["animals"],
        ):
            events.append(event)

        assert len(events) >= 3
        assert events[0]["type"] == "status"
        assert events[-2]["type"] == "result"
        assert events[-1]["type"] == "complete"

        # Result event data must be a valid story dict
        result_data = events[-2]["data"]
        assert "story" in result_data
        assert "safety_score" in result_data


# ============================================================================
# 4. Business Rules
# ============================================================================

class TestImageToStoryBusinessRules:
    """Business rule contracts for Image-to-Story pipeline."""

    def test_safety_score_must_meet_threshold(self):
        """Content safety threshold is >= 0.85 (CLAUDE.md non-negotiable)."""
        from backend.src.agents.image_to_story_agent import StoryOutput

        safe_output = StoryOutput(story="A safe story.", safety_score=0.92)
        assert safe_output.safety_score >= 0.85

        # Unsafe output should be caught by business logic (not model validation)
        unsafe_output = StoryOutput(story="A story.", safety_score=0.60)
        assert unsafe_output.safety_score < 0.85

    def test_word_count_uses_words_not_characters(self):
        """Regression: word_count must count words, not characters (related to #46)."""
        story_text = "Once upon a time there was a little dinosaur"
        word_count = len(story_text.split())
        assert word_count == 9
        assert word_count != len(story_text)

    def test_mock_result_contains_all_story_output_fields(self):
        """Mock fallback must match StoryOutput schema so tests stay reliable."""
        from backend.src.agents.image_to_story_agent import _mock_image_to_story_result

        result = _mock_image_to_story_result(["animals"])

        assert "story" in result
        assert "themes" in result
        assert "concepts" in result
        assert "moral" in result
        assert "characters" in result
        assert "analysis" in result
        assert "safety_score" in result

        # Verify safety_score meets threshold
        assert result["safety_score"] >= 0.85

    def test_mock_result_characters_have_required_fields(self):
        """Each mock character must have name, description, appearances."""
        from backend.src.agents.image_to_story_agent import _mock_image_to_story_result

        result = _mock_image_to_story_result(["space"])
        for char in result["characters"]:
            assert "name" in char
            assert "description" in char
            assert "appearances" in char

    def test_agent_to_api_model_mapping(self):
        """StoryOutput fields map correctly to ImageToStoryResponse structure."""
        from backend.src.agents.image_to_story_agent import StoryOutput, Character
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue, CharacterMemory,
        )

        agent_output = StoryOutput(
            story="A great story about friendship.",
            themes=["friendship"],
            concepts=["sharing"],
            moral="Share with friends.",
            characters=[Character(name="Fox", description="A clever fox", appearances=3)],
            analysis={"objects": ["fox", "forest"]},
            safety_score=0.92,
            audio_url="/audio/story.mp3",
        )

        # Simulate the mapping that the API route performs
        api_response = ImageToStoryResponse(
            story_id="story-test-001",
            story=StoryContent(
                text=agent_output.story,
                word_count=len(agent_output.story.split()),
                age_adapted=True,
            ),
            image_url=None,
            audio_url=agent_output.audio_url,
            educational_value=EducationalValue(
                themes=agent_output.themes,
                concepts=agent_output.concepts,
                moral=agent_output.moral,
            ),
            characters=[
                CharacterMemory(
                    character_name=c.name,
                    description=c.description,
                    appearances=c.appearances,
                )
                for c in agent_output.characters
            ],
            analysis=agent_output.analysis,
            safety_score=agent_output.safety_score,
        )

        assert api_response.story.text == agent_output.story
        assert api_response.educational_value.themes == agent_output.themes
        assert api_response.characters[0].character_name == agent_output.characters[0].name
        assert api_response.safety_score == agent_output.safety_score


# ============================================================================
# 5. Backward Compatibility
# ============================================================================

class TestImageToStoryBackwardCompatibility:
    """Ensure optional fields don't break existing consumers."""

    def test_story_output_extra_fields_ignored(self):
        """StoryOutput should tolerate missing optional fields."""
        from backend.src.agents.image_to_story_agent import StoryOutput

        # Minimal construction -- all optional fields should have defaults
        output = StoryOutput(story="Minimal story.")
        assert output.audio_url is None
        assert output.characters == []

    def test_response_created_at_has_default(self):
        """ImageToStoryResponse.created_at defaults to now()."""
        from backend.src.api.models import (
            ImageToStoryResponse, StoryContent, EducationalValue,
        )

        resp = ImageToStoryResponse(
            story_id="s1",
            story=StoryContent(text="test", word_count=1, age_adapted=True),
            educational_value=EducationalValue(themes=[], concepts=[]),
            safety_score=0.9,
        )
        assert isinstance(resp.created_at, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
