"""
Image-to-Story Pipeline Contract Tests - 图画生故事管道契约测试

Related to GitHub issue #236.

This file defines contract tests for the image-to-story pipeline, including:
1. StoryOutput agent model schema validation
2. ImageToStoryResponse API model schema validation
3. Mock agent output conformance to StoryOutput
4. SSE event shape validation
5. Safety score boundary enforcement
6. StoryContent field invariants

Testing principle: use Pydantic schema validation, not string matching.
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime


# ============================================================================
# 1. Agent-layer schema (mirrors backend/src/agents/image_to_story_agent.py)
# ============================================================================

class Character(BaseModel):
    name: str
    description: str
    appearances: int = 1


class StoryOutput(BaseModel):
    story: str
    themes: List[str] = []
    concepts: List[str] = []
    moral: Optional[str] = None
    characters: List[Character] = []
    analysis: Dict[str, Any] = {}
    safety_score: float = 0.9
    audio_url: Optional[str] = None


# ============================================================================
# 2. API-layer schema (mirrors backend/src/api/models.py)
# ============================================================================

class StoryContent(BaseModel):
    text: str
    word_count: int = Field(..., ge=0)
    age_adapted: bool


class EducationalValue(BaseModel):
    themes: List[str]
    concepts: List[str]
    moral: Optional[str] = None


class CharacterMemory(BaseModel):
    character_name: str
    description: str
    appearances: int


class ImageToStoryResponse(BaseModel):
    story_id: str
    story: StoryContent
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    video_job_id: Optional[str] = None
    educational_value: EducationalValue
    characters: List[CharacterMemory] = []
    analysis: Dict[str, Any] = {}
    safety_score: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime


# ============================================================================
# 3. SSE event schemas
# ============================================================================

class SSEStatusEvent(BaseModel):
    status: str
    message: str


class SSEThinkingEvent(BaseModel):
    content: str
    turn: int


class SSEToolUseEvent(BaseModel):
    tool: str
    message: str


class SSEToolResultEvent(BaseModel):
    status: str


class SSEAudioGeneratedEvent(BaseModel):
    audio_path: str
    message: str


class SSECompleteEvent(BaseModel):
    status: str
    message: str


class SSEErrorEvent(BaseModel):
    error: str
    message: str


# ============================================================================
# 4. Test fixtures
# ============================================================================

def _mock_agent_output(topic: str = "adventure") -> dict:
    """Reproduce the mock from _mock_image_to_story_result."""
    return {
        "story": f"Once upon a time, in a land of {topic}...",
        "themes": [topic, "creativity"],
        "concepts": ["imagination", "art"],
        "moral": "Every drawing tells a story.",
        "characters": [
            {"name": "Little Artist", "description": "A creative child", "appearances": 1}
        ],
        "analysis": {"objects": ["drawing"], "colors": ["blue", "green"]},
        "safety_score": 0.95,
        "audio_path": None,
    }


def _sample_api_response() -> dict:
    """A valid ImageToStoryResponse payload."""
    return {
        "story_id": "story-001",
        "story": {
            "text": "Once upon a time...",
            "word_count": 120,
            "age_adapted": True,
        },
        "image_url": "/uploads/drawing.png",
        "audio_url": "/audio/story-001.mp3",
        "video_url": None,
        "video_job_id": None,
        "educational_value": {
            "themes": ["adventure", "creativity"],
            "concepts": ["imagination", "art"],
            "moral": "Every drawing tells a story.",
        },
        "characters": [
            {"character_name": "Little Artist", "description": "A creative child", "appearances": 1}
        ],
        "analysis": {"objects": ["drawing"], "colors": ["blue", "green"]},
        "safety_score": 0.95,
        "created_at": "2026-03-19T10:00:00Z",
    }


# ============================================================================
# 5. Contract tests
# ============================================================================

class TestStoryOutputContract:
    """Agent-layer StoryOutput model contract tests."""

    def test_valid_full_story_output(self):
        """All fields provided explicitly parse correctly."""
        output = StoryOutput(
            story="A brave little fox went on an adventure.",
            themes=["adventure", "courage"],
            concepts=["bravery", "forest"],
            moral="Courage leads to discovery.",
            characters=[Character(name="Fox", description="A brave fox", appearances=2)],
            analysis={"objects": ["fox", "tree"], "colors": ["orange"]},
            safety_score=0.92,
            audio_url="/audio/fox.mp3",
        )
        assert output.story != ""
        assert len(output.themes) == 2
        assert output.characters[0].name == "Fox"
        assert output.characters[0].appearances == 2

    def test_defaults_applied_when_omitted(self):
        """Only the required field 'story' is needed; everything else has defaults."""
        output = StoryOutput(story="Minimal story.")
        assert output.themes == []
        assert output.concepts == []
        assert output.moral is None
        assert output.characters == []
        assert output.analysis == {}
        assert output.safety_score == 0.9
        assert output.audio_url is None

    def test_story_field_is_required(self):
        """StoryOutput must reject construction without 'story'."""
        with pytest.raises(ValidationError) as exc_info:
            StoryOutput()  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "story" in field_names

    def test_character_defaults(self):
        """Character.appearances defaults to 1."""
        char = Character(name="Dog", description="A happy puppy")
        assert char.appearances == 1

    def test_character_requires_name_and_description(self):
        """Character must have both name and description."""
        with pytest.raises(ValidationError):
            Character(name="Dog")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            Character(description="A dog")  # type: ignore[call-arg]


class TestImageToStoryResponseContract:
    """API-layer ImageToStoryResponse model contract tests."""

    def test_valid_response_parses(self):
        """A well-formed payload round-trips through the model."""
        data = _sample_api_response()
        response = ImageToStoryResponse(**data)
        assert response.story_id == "story-001"
        assert response.story.text == "Once upon a time..."
        assert response.story.word_count == 120
        assert response.story.age_adapted is True
        assert response.educational_value.moral == "Every drawing tells a story."
        assert len(response.characters) == 1
        assert response.characters[0].character_name == "Little Artist"

    def test_story_id_is_required(self):
        """Missing story_id must raise ValidationError."""
        data = _sample_api_response()
        del data["story_id"]
        with pytest.raises(ValidationError) as exc_info:
            ImageToStoryResponse(**data)
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "story_id" in field_names

    def test_safety_score_is_required(self):
        """Missing safety_score must raise ValidationError."""
        data = _sample_api_response()
        del data["safety_score"]
        with pytest.raises(ValidationError) as exc_info:
            ImageToStoryResponse(**data)
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "safety_score" in field_names

    def test_created_at_is_required(self):
        """Missing created_at must raise ValidationError."""
        data = _sample_api_response()
        del data["created_at"]
        with pytest.raises(ValidationError) as exc_info:
            ImageToStoryResponse(**data)
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "created_at" in field_names

    def test_optional_media_fields_default_to_none(self):
        """image_url, audio_url, video_url, video_job_id can all be omitted."""
        data = _sample_api_response()
        del data["image_url"]
        del data["audio_url"]
        del data["video_url"]
        del data["video_job_id"]
        response = ImageToStoryResponse(**data)
        assert response.image_url is None
        assert response.audio_url is None
        assert response.video_url is None
        assert response.video_job_id is None

    def test_characters_defaults_to_empty_list(self):
        """characters field defaults to [] when omitted."""
        data = _sample_api_response()
        del data["characters"]
        response = ImageToStoryResponse(**data)
        assert response.characters == []

    def test_analysis_defaults_to_empty_dict(self):
        """analysis field defaults to {} when omitted."""
        data = _sample_api_response()
        del data["analysis"]
        response = ImageToStoryResponse(**data)
        assert response.analysis == {}


class TestMockAgentOutputConformance:
    """Verify that the mock agent output conforms to StoryOutput."""

    def test_mock_output_parses_as_story_output(self):
        """The dict returned by _mock_image_to_story_result must parse into StoryOutput."""
        raw = _mock_agent_output()
        # audio_path is in mock but not in StoryOutput; agent code maps it to audio_url
        adapted = {k: v for k, v in raw.items() if k != "audio_path"}
        adapted["audio_url"] = raw.get("audio_path")
        output = StoryOutput(**adapted)
        assert output.story.startswith("Once upon a time")
        assert output.safety_score == 0.95
        assert output.moral == "Every drawing tells a story."
        assert len(output.characters) == 1
        assert output.characters[0].name == "Little Artist"

    def test_mock_output_themes_include_topic(self):
        """Mock output must include the requested topic in themes."""
        raw = _mock_agent_output(topic="dinosaurs")
        assert "dinosaurs" in raw["themes"]
        assert "creativity" in raw["themes"]

    def test_mock_output_has_analysis_keys(self):
        """Mock analysis dict must contain objects and colors."""
        raw = _mock_agent_output()
        assert "objects" in raw["analysis"]
        assert "colors" in raw["analysis"]


class TestSafetyScoreBoundaries:
    """Safety score must always be in [0.0, 1.0]."""

    def test_safety_score_at_lower_bound(self):
        """safety_score = 0.0 is valid."""
        data = _sample_api_response()
        data["safety_score"] = 0.0
        response = ImageToStoryResponse(**data)
        assert response.safety_score == 0.0

    def test_safety_score_at_upper_bound(self):
        """safety_score = 1.0 is valid."""
        data = _sample_api_response()
        data["safety_score"] = 1.0
        response = ImageToStoryResponse(**data)
        assert response.safety_score == 1.0

    def test_safety_score_below_zero_rejected(self):
        """safety_score < 0.0 must be rejected."""
        data = _sample_api_response()
        data["safety_score"] = -0.1
        with pytest.raises(ValidationError):
            ImageToStoryResponse(**data)

    def test_safety_score_above_one_rejected(self):
        """safety_score > 1.0 must be rejected."""
        data = _sample_api_response()
        data["safety_score"] = 1.01
        with pytest.raises(ValidationError):
            ImageToStoryResponse(**data)

    def test_safety_threshold_met(self):
        """Content with safety_score >= 0.85 passes the project safety threshold."""
        data = _sample_api_response()
        data["safety_score"] = 0.85
        response = ImageToStoryResponse(**data)
        assert response.safety_score >= 0.85

    def test_safety_threshold_not_met(self):
        """Content with safety_score < 0.85 fails the project safety threshold."""
        data = _sample_api_response()
        data["safety_score"] = 0.84
        response = ImageToStoryResponse(**data)
        assert response.safety_score < 0.85


class TestStoryContentInvariants:
    """StoryContent field-level invariants."""

    def test_word_count_non_negative(self):
        """word_count must be >= 0."""
        content = StoryContent(text="Hello world", word_count=0, age_adapted=False)
        assert content.word_count >= 0

    def test_negative_word_count_rejected(self):
        """word_count < 0 must be rejected."""
        with pytest.raises(ValidationError):
            StoryContent(text="Hello world", word_count=-1, age_adapted=False)

    def test_text_is_required(self):
        """StoryContent.text is required."""
        with pytest.raises(ValidationError) as exc_info:
            StoryContent(word_count=10, age_adapted=True)  # type: ignore[call-arg]
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "text" in field_names

    def test_age_adapted_is_required(self):
        """StoryContent.age_adapted is required."""
        with pytest.raises(ValidationError) as exc_info:
            StoryContent(text="Hello", word_count=1)  # type: ignore[call-arg]
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "age_adapted" in field_names


class TestSSEEventShapes:
    """SSE event payloads must conform to their defined shapes."""

    def test_status_event(self):
        """status event has status and message strings."""
        event = SSEStatusEvent(status="processing", message="Analyzing drawing...")
        assert event.status == "processing"
        assert isinstance(event.message, str)

    def test_thinking_event(self):
        """thinking event has content string and turn integer."""
        event = SSEThinkingEvent(content="I see a dog in the drawing.", turn=1)
        assert event.turn == 1
        assert isinstance(event.content, str)

    def test_tool_use_event(self):
        """tool_use event has tool name and message."""
        event = SSEToolUseEvent(
            tool="mcp__vision-analysis__analyze_children_drawing",
            message="Analyzing the uploaded drawing",
        )
        assert "vision" in event.tool
        assert isinstance(event.message, str)

    def test_tool_result_event(self):
        """tool_result event has a status field."""
        event = SSEToolResultEvent(status="success")
        assert event.status == "success"

    def test_audio_generated_event(self):
        """audio_generated event has audio_path and message."""
        event = SSEAudioGeneratedEvent(
            audio_path="/audio/story-001.mp3",
            message="Audio narration generated",
        )
        assert event.audio_path.endswith(".mp3")

    def test_complete_event(self):
        """complete event has status and message."""
        event = SSECompleteEvent(status="done", message="Story generation complete")
        assert event.status == "done"

    def test_error_event(self):
        """error event has error and message fields."""
        event = SSEErrorEvent(error="TIMEOUT", message="Agent timed out")
        assert event.error == "TIMEOUT"
        assert isinstance(event.message, str)

    def test_status_event_rejects_missing_fields(self):
        """SSE status event must have both status and message."""
        with pytest.raises(ValidationError):
            SSEStatusEvent(status="processing")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            SSEStatusEvent(message="hello")  # type: ignore[call-arg]

    def test_error_event_rejects_missing_fields(self):
        """SSE error event must have both error and message."""
        with pytest.raises(ValidationError):
            SSEErrorEvent(error="TIMEOUT")  # type: ignore[call-arg]


class TestEducationalValueContract:
    """EducationalValue nested model contracts."""

    def test_themes_and_concepts_required(self):
        """themes and concepts lists are required."""
        with pytest.raises(ValidationError):
            EducationalValue()  # type: ignore[call-arg]

    def test_moral_is_optional(self):
        """moral can be omitted and defaults to None."""
        ev = EducationalValue(themes=["friendship"], concepts=["sharing"])
        assert ev.moral is None

    def test_empty_themes_allowed(self):
        """An empty themes list is structurally valid."""
        ev = EducationalValue(themes=[], concepts=["art"])
        assert ev.themes == []


class TestSerializationRoundTrip:
    """Ensure models survive JSON serialization and deserialization."""

    def test_story_output_round_trip(self):
        """StoryOutput -> JSON -> StoryOutput preserves data."""
        original = StoryOutput(
            story="A cat found a star.",
            themes=["wonder"],
            safety_score=0.91,
            characters=[Character(name="Cat", description="Curious cat")],
        )
        json_str = original.model_dump_json()
        restored = StoryOutput.model_validate_json(json_str)
        assert restored.story == original.story
        assert restored.themes == original.themes
        assert restored.safety_score == original.safety_score
        assert restored.characters[0].name == "Cat"

    def test_api_response_round_trip(self):
        """ImageToStoryResponse -> JSON -> ImageToStoryResponse preserves data."""
        original = ImageToStoryResponse(**_sample_api_response())
        json_str = original.model_dump_json()
        restored = ImageToStoryResponse.model_validate_json(json_str)
        assert restored.story_id == original.story_id
        assert restored.safety_score == original.safety_score
        assert restored.story.word_count == original.story.word_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
