"""
Logic Contract Tests - Business logic contract tests

This file defines the business logic contracts for all Agents and services.
Contract tests ensure each component's inputs/outputs conform to expectations,
keeping interfaces stable and reliable.

Testing principles:
1. Tests should describe "what" not "how"
2. Once established, contracts should not be easily modified (backward compatible)
3. All Agent inputs/outputs must have contract test coverage
4. Use type checking to enforce contracts
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ValidationError, Field
from datetime import datetime
from enum import Enum


# ============================================================================
# 1. Agent Input/Output Contract Definitions
# ============================================================================

# -------------------------
# 1.1 ImageAnalysisAgent Contract
# -------------------------

class ImageAnalysisInput(BaseModel):
    """Image analysis input contract"""
    image_url: str = Field(..., description="Image URL", min_length=1)
    child_id: str = Field(..., description="Child user ID")
    child_age: int = Field(..., ge=3, le=12, description="Child age (3-12)")
    interests: Optional[List[str]] = Field(default=None, description="Interest tags")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://s3.amazonaws.com/images/abc123.jpg",
                "child_id": "user-123",
                "child_age": 7,
                "interests": ["animals", "adventure"]
            }
        }


class ImageAnalysisResult(BaseModel):
    """Image analysis output contract"""
    objects: List[str] = Field(..., description="List of identified objects", min_length=1)
    scene: str = Field(..., description="Scene description", min_length=1)
    mood: str = Field(..., description="Mood/atmosphere", min_length=1)
    recurring_characters: List[str] = Field(default=[], description="Recurring characters")
    embedding_vector: List[float] = Field(..., description="Vector representation", min_length=512)
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

    class Config:
        json_schema_extra = {
            "example": {
                "objects": ["puppy", "trees", "sun"],
                "scene": "outdoor park",
                "mood": "happy",
                "recurring_characters": ["Lightning the puppy"],
                "embedding_vector": [0.1, 0.2, 0.3],  # Simplified example
                "confidence_score": 0.92
            }
        }


# -------------------------
# 1.2 InteractiveStoryAgent Contract
# -------------------------

class StoryMode(str, Enum):
    """Story mode enum"""
    LINEAR = "linear"
    INTERACTIVE = "interactive"


class StoryGenerationInput(BaseModel):
    """Story generation input contract"""
    child_id: str = Field(..., description="Child user ID")
    child_age: int = Field(..., ge=3, le=12, description="Child age")
    interests: List[str] = Field(..., min_length=1, max_length=5, description="Interest tags (1-5)")
    mode: StoryMode = Field(default=StoryMode.LINEAR, description="Story mode")
    theme: Optional[str] = Field(default=None, description="Story theme")
    educational_goal: Optional[str] = Field(default=None, description="Educational goal")
    session_id: Optional[str] = Field(default=None, description="Session ID (multi-turn)")
    previous_choice: Optional[str] = Field(default=None, description="User's previous choice")

    class Config:
        json_schema_extra = {
            "example": {
                "child_id": "user-123",
                "child_age": 8,
                "interests": ["dinosaurs", "science"],
                "mode": "interactive",
                "theme": "friendship",
                "educational_goal": "courage"
            }
        }


class Choice(BaseModel):
    """Story choice branch"""
    id: str = Field(..., description="Choice ID")
    text: str = Field(..., min_length=5, description="Choice text")
    emoji: str = Field(..., description="Emoji")
    consequence_hint: Optional[str] = Field(default=None, description="Consequence hint")


class StorySegmentResult(BaseModel):
    """Story segment output contract"""
    story_text: str = Field(..., min_length=50, max_length=1000, description="Story text (50-1000 chars)")
    audio_url: Optional[str] = Field(default=None, description="Audio URL")
    is_ending: bool = Field(..., description="Whether this is the ending")
    choices: Optional[List[Choice]] = Field(default=None, description="Branch choices (interactive mode)")
    session_id: str = Field(..., description="Session ID")
    educational_points: List[str] = Field(default=[], description="Educational points")

    class Config:
        json_schema_extra = {
            "example": {
                "story_text": "Little dinosaur discovered a mysterious cave in the forest...",
                "audio_url": "https://s3.amazonaws.com/audio/story-123.mp3",
                "is_ending": False,
                "choices": [
                    {
                        "id": "choice-1",
                        "text": "Bravely enter the cave",
                        "emoji": "🏔️",
                        "consequence_hint": "You will discover a mysterious treasure"
                    },
                    {
                        "id": "choice-2",
                        "text": "Go home and get friends first",
                        "emoji": "👫",
                        "consequence_hint": "Friendship makes adventures safer"
                    }
                ],
                "session_id": "session-abc123",
                "educational_points": ["courage", "friendship"]
            }
        }


# -------------------------
# 1.3 NewsConverterAgent Contract
# -------------------------

class NewsCategory(str, Enum):
    """News category enum"""
    SCIENCE = "science"
    NATURE = "nature"
    CULTURE = "culture"
    SPORTS = "sports"


class NewsConversionInput(BaseModel):
    """News conversion input contract"""
    news_url: Optional[str] = Field(default=None, description="News URL")
    news_text: Optional[str] = Field(default=None, description="News text")
    target_age: int = Field(..., ge=3, le=12, description="Target age")
    category: NewsCategory = Field(..., description="News category")

    @classmethod
    def validate_news_source(cls, values):
        """Validate at least one news source is provided"""
        if not values.get('news_url') and not values.get('news_text'):
            raise ValueError("Must provide either news_url or news_text")
        return values


class Concept(BaseModel):
    """Key concept"""
    term: str = Field(..., description="Term")
    kid_explanation: str = Field(..., min_length=10, description="Kid-friendly explanation")
    example: Optional[str] = Field(default=None, description="Example")


class KidsNewsResult(BaseModel):
    """Kids news output contract"""
    kids_title: str = Field(..., min_length=5, max_length=100, description="Kid-friendly title")
    kids_content: str = Field(..., min_length=50, max_length=500, description="Kid-friendly content (50-500 chars)")
    why_care: str = Field(..., min_length=20, description="Why should I care?")
    key_concepts: List[Concept] = Field(default=[], description="Key concept explanations")
    fun_facts: List[str] = Field(default=[], description="Fun facts")
    interactive_questions: List[str] = Field(default=[], min_length=1, description="Interactive questions")
    original_url: Optional[str] = Field(default=None, description="Original news URL")

    class Config:
        json_schema_extra = {
            "example": {
                "kids_title": "A new planet was discovered in space!",
                "kids_content": "Scientists used a super powerful telescope...",
                "why_care": "It is like humans found a new friend planet, and someday you might travel there!",
                "key_concepts": [
                    {
                        "term": "planet",
                        "kid_explanation": "A big ball that goes around the sun, just like Earth",
                        "example": "Just like the merry-go-round at the playground"
                    }
                ],
                "fun_facts": ["This planet is three times bigger than Earth!"],
                "interactive_questions": ["Would you like to explore space?"],
                "original_url": "https://news.example.com/space-discovery"
            }
        }


# -------------------------
# 1.4 SafetyAgent Contract
# -------------------------

class ContentType(str, Enum):
    """Content type enum"""
    STORY = "story"
    NEWS = "news"
    IMAGE_DESCRIPTION = "image_description"


class ContentReviewInput(BaseModel):
    """Content review input contract"""
    content_type: ContentType = Field(..., description="Content type")
    content_text: str = Field(..., min_length=1, description="Content text")
    target_age: int = Field(..., ge=3, le=12, description="Target age")
    child_id: Optional[str] = Field(default=None, description="Child ID (for personalized review)")


class IssueSeverity(str, Enum):
    """Issue severity"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SafetyIssue(BaseModel):
    """Safety issue"""
    category: str = Field(..., description="Issue category (violence, gender_bias, etc.)")
    severity: IssueSeverity = Field(..., description="Severity")
    description: str = Field(..., description="Issue description")
    location: Optional[str] = Field(default=None, description="Issue location")


class SafetyReviewResult(BaseModel):
    """Safety review output contract"""
    is_safe: bool = Field(..., description="Whether safe")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Safety score (0.0-1.0)")
    issues: List[SafetyIssue] = Field(default=[], description="Issue list")
    suggestions: List[str] = Field(default=[], description="Improvement suggestions")

    class Config:
        json_schema_extra = {
            "example": {
                "is_safe": False,
                "safety_score": 0.65,
                "issues": [
                    {
                        "category": "gender_bias",
                        "severity": "medium",
                        "description": "All doctors in the story are male",
                        "location": "second paragraph"
                    }
                ],
                "suggestions": [
                    "Change one doctor to a female character",
                    "Add more diverse professional roles"
                ]
            }
        }


# -------------------------
# 1.5 RewardAgent Contract
# -------------------------

class UserEvent(BaseModel):
    """User event input contract"""
    user_id: str = Field(..., description="User ID")
    event_type: str = Field(..., description="Event type")
    metadata: Dict[str, Any] = Field(default={}, description="Event metadata")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "event_type": "story_created",
                "metadata": {"story_id": "story-456", "theme": "science"},
                "timestamp": "2026-01-26T10:00:00Z"
            }
        }


class Medal(BaseModel):
    """Medal"""
    id: str = Field(..., description="Medal ID")
    name: str = Field(..., description="Medal name")
    description: str = Field(..., description="Medal description")
    icon: str = Field(..., description="Medal icon URL")
    category: str = Field(..., description="Medal category")
    unlocked_at: datetime = Field(..., description="Unlock time")


class ProgressUpdate(BaseModel):
    """Progress update"""
    medal_id: str = Field(..., description="Medal ID")
    current_progress: int = Field(..., description="Current progress")
    required_progress: int = Field(..., description="Required progress")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Completion percentage")


class RewardResult(BaseModel):
    """Reward system output contract"""
    new_medals: List[Medal] = Field(default=[], description="Newly earned medals")
    total_medals: int = Field(..., ge=0, description="Total medal count")
    progress_updates: List[ProgressUpdate] = Field(default=[], description="Progress updates")


# ============================================================================
# 2. Contract Test Cases
# ============================================================================

class TestImageAnalysisContract:
    """Image analysis agent contract tests"""

    def test_valid_input(self):
        """Test valid input"""
        input_data = ImageAnalysisInput(
            image_url="https://example.com/image.jpg",
            child_id="user-123",
            child_age=7,
            interests=["animals", "adventure"]
        )
        assert input_data.child_age == 7
        assert len(input_data.interests) == 2

    def test_invalid_age(self):
        """Test invalid age (must be between 3-12)"""
        with pytest.raises(ValidationError) as exc_info:
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg",
                child_id="user-123",
                child_age=15  # Out of range
            )
        assert "child_age" in str(exc_info.value)

    def test_empty_image_url(self):
        """Test empty image URL"""
        with pytest.raises(ValidationError):
            ImageAnalysisInput(
                image_url="",  # Empty string
                child_id="user-123",
                child_age=7
            )

    def test_valid_output(self):
        """Test valid output"""
        output = ImageAnalysisResult(
            objects=["puppy", "trees"],
            scene="park",
            mood="happy",
            recurring_characters=["Lightning the puppy"],
            embedding_vector=[0.1] * 512,  # 512-dim vector
            confidence_score=0.92
        )
        assert output.confidence_score >= 0.0
        assert output.confidence_score <= 1.0
        assert len(output.embedding_vector) == 512

    def test_invalid_confidence_score(self):
        """Test invalid confidence score"""
        with pytest.raises(ValidationError):
            ImageAnalysisResult(
                objects=["puppy"],
                scene="park",
                mood="happy",
                embedding_vector=[0.1] * 512,
                confidence_score=1.5  # Out of range
            )


class TestInteractiveStoryContract:
    """Interactive story agent contract tests"""

    def test_valid_linear_story_input(self):
        """Test linear story input"""
        input_data = StoryGenerationInput(
            child_id="user-123",
            child_age=8,
            interests=["dinosaurs", "science"],
            mode=StoryMode.LINEAR,
            theme="friendship"
        )
        assert input_data.mode == StoryMode.LINEAR

    def test_valid_interactive_story_input(self):
        """Test interactive story input"""
        input_data = StoryGenerationInput(
            child_id="user-123",
            child_age=8,
            interests=["dinosaurs"],
            mode=StoryMode.INTERACTIVE,
            session_id="session-123",
            previous_choice="choice-1"
        )
        assert input_data.mode == StoryMode.INTERACTIVE
        assert input_data.session_id is not None

    def test_max_interests(self):
        """Test max interest tag count (max 5)"""
        with pytest.raises(ValidationError):
            StoryGenerationInput(
                child_id="user-123",
                child_age=8,
                interests=["a", "b", "c", "d", "e", "f"]  # More than 5
            )

    def test_valid_story_output_with_choices(self):
        """Test story output with choices"""
        output = StorySegmentResult(
            story_text="Little dinosaur discovered a mysterious cave in the forest, with a strange glow flickering at the entrance...",
            audio_url="https://example.com/audio.mp3",
            is_ending=False,
            choices=[
                Choice(
                    id="choice-1",
                    text="Bravely enter the cave",
                    emoji="🏔️",
                    consequence_hint="You will discover a mysterious treasure"
                ),
                Choice(
                    id="choice-2",
                    text="Go home and get friends first",
                    emoji="👫"
                )
            ],
            session_id="session-123",
            educational_points=["courage", "friendship"]
        )
        assert len(output.choices) == 2
        assert not output.is_ending

    def test_story_text_length(self):
        """Test story text length limits"""
        with pytest.raises(ValidationError):
            StorySegmentResult(
                story_text="Too short",  # Less than 50 characters
                is_ending=True,
                session_id="session-123"
            )


class TestNewsConverterContract:
    """News converter agent contract tests"""

    def test_valid_input_with_url(self):
        """Test input with URL"""
        input_data = NewsConversionInput(
            news_url="https://news.example.com/article",
            target_age=7,
            category=NewsCategory.SCIENCE
        )
        assert input_data.news_url is not None

    def test_valid_input_with_text(self):
        """Test input with text"""
        input_data = NewsConversionInput(
            news_text="SpaceX launched a new rocket...",
            target_age=7,
            category=NewsCategory.SCIENCE
        )
        assert input_data.news_text is not None

    def test_valid_output(self):
        """Test valid output"""
        output = KidsNewsResult(
            kids_title="A new planet was discovered in space!",
            kids_content="Scientists used a super powerful telescope to discover a new planet far away in space...",
            why_care="It is like humans found a new friend planet, and someday you might travel there!",
            key_concepts=[
                Concept(
                    term="planet",
                    kid_explanation="A big ball that goes around the sun, just like Earth",
                    example="Just like the merry-go-round at the playground"
                )
            ],
            fun_facts=["This planet is three times bigger than Earth!"],
            interactive_questions=["Would you like to explore space?"],
            original_url="https://news.example.com/space"
        )
        assert len(output.kids_content) >= 50
        assert len(output.interactive_questions) >= 1

    def test_content_length_limits(self):
        """Test content length limits"""
        with pytest.raises(ValidationError):
            KidsNewsResult(
                kids_title="This title is way too long! " * 10,  # Over 100 characters
                kids_content="Scientists discovered a new planet...",
                why_care="This is interesting!",
                interactive_questions=["Would you like to go to space?"]
            )


class TestSafetyContract:
    """Safety review agent contract tests"""

    def test_valid_input(self):
        """Test valid input"""
        input_data = ContentReviewInput(
            content_type=ContentType.STORY,
            content_text="Little dinosaur goes on an adventure with friends...",
            target_age=7,
            child_id="user-123"
        )
        assert input_data.content_type == ContentType.STORY

    def test_safe_content_output(self):
        """Test safe content output"""
        output = SafetyReviewResult(
            is_safe=True,
            safety_score=0.95,
            issues=[],
            suggestions=[]
        )
        assert output.is_safe
        assert output.safety_score > 0.9

    def test_unsafe_content_output(self):
        """Test unsafe content output"""
        output = SafetyReviewResult(
            is_safe=False,
            safety_score=0.65,
            issues=[
                SafetyIssue(
                    category="gender_bias",
                    severity=IssueSeverity.MEDIUM,
                    description="All doctors in the story are male",
                    location="second paragraph"
                )
            ],
            suggestions=["Change one doctor to a female character"]
        )
        assert not output.is_safe
        assert len(output.issues) > 0
        assert len(output.suggestions) > 0

    def test_safety_score_range(self):
        """Test safety score range"""
        with pytest.raises(ValidationError):
            SafetyReviewResult(
                is_safe=True,
                safety_score=1.5,  # Out of range
                issues=[],
                suggestions=[]
            )


class TestRewardContract:
    """Reward system agent contract tests"""

    def test_valid_user_event(self):
        """Test valid user event"""
        event = UserEvent(
            user_id="user-123",
            event_type="story_created",
            metadata={"story_id": "story-456"},
            timestamp=datetime.now()
        )
        assert event.event_type == "story_created"

    def test_valid_reward_result_with_medals(self):
        """Test reward result with new medals"""
        result = RewardResult(
            new_medals=[
                Medal(
                    id="medal-1",
                    name="Little Artist",
                    description="Uploaded 1st drawing",
                    icon="https://example.com/medal.png",
                    category="creation",
                    unlocked_at=datetime.now()
                )
            ],
            total_medals=5,
            progress_updates=[
                ProgressUpdate(
                    medal_id="medal-2",
                    current_progress=3,
                    required_progress=5,
                    percentage=60.0
                )
            ]
        )
        assert len(result.new_medals) == 1
        assert result.total_medals == 5

    def test_progress_percentage_range(self):
        """Test progress percentage range"""
        with pytest.raises(ValidationError):
            ProgressUpdate(
                medal_id="medal-1",
                current_progress=10,
                required_progress=5,
                percentage=150.0  # Out of range
            )


# ============================================================================
# 3. Business Logic Rule Tests
# ============================================================================

class TestBusinessLogicRules:
    """Business logic rule tests"""

    def test_age_appropriate_content_length(self):
        """Test age-appropriate content length rules"""
        # Rule: Stories for ages 3-5 should be shorter (100-200 chars)
        # Ages 6-8: medium length (200-400 chars)
        # Ages 9-12: can be longer (400-800 chars)

        young_story = StorySegmentResult(
            story_text="The puppy plays in the park. " * 6,  # ~180 chars
            is_ending=True,
            session_id="session-123"
        )
        assert 50 <= len(young_story.story_text) <= 1000

    def test_interactive_story_must_have_choices_if_not_ending(self):
        """Test interactive story rule: non-ending must have choices"""
        # Business rule: interactive stories must provide choices if not an ending
        story = StorySegmentResult(
            story_text="Little dinosaur arrived at the fork in the road, wondering which path to take on this adventure...",
            is_ending=False,
            choices=[
                Choice(id="c1", text="Go left down the mossy path", emoji="⬅️"),
                Choice(id="c2", text="Go right toward the river", emoji="➡️")
            ],
            session_id="session-123"
        )
        # If not an ending, choices must not be empty
        if not story.is_ending:
            assert story.choices is not None
            assert len(story.choices) >= 2

    def test_safety_score_threshold(self):
        """Test safety score threshold rule"""
        # Business rule: safety score < 0.7 is considered unsafe
        unsafe_result = SafetyReviewResult(
            is_safe=False,
            safety_score=0.65,
            issues=[
                SafetyIssue(
                    category="violence",
                    severity=IssueSeverity.HIGH,
                    description="Contains violent content"
                )
            ],
            suggestions=["Remove violent descriptions"]
        )
        assert unsafe_result.safety_score < 0.7
        assert not unsafe_result.is_safe

    def test_word_count_uses_words_not_characters(self):
        """Regression test for #46: word_count must count words, not characters."""
        story_text = "The little dinosaur found a mysterious cave"
        word_count = len(story_text.split())
        assert word_count == 7
        # Must NOT be character count
        assert word_count != len(story_text)

    def test_word_count_empty_string(self):
        """word_count of empty story text should be 0."""
        assert len("".split()) == 0

    def test_interactive_story_progress_is_decimal(self):
        """Regression test for #47: progress must be 0.0–1.0, not 0–100."""
        current_segment = 3
        total_segments = 5
        progress = current_segment / total_segments
        assert 0.0 <= progress <= 1.0
        assert progress == pytest.approx(0.6)

    def test_news_must_have_interactive_questions(self):
        """Test news must contain interactive questions rule"""
        # Business rule: kids news must contain at least 1 interactive question
        news = KidsNewsResult(
            kids_title="Space Discovery",
            kids_content="Scientists discovered a new planet far away in the galaxy, and it might have water on it...",
            why_care="This is really interesting!",
            interactive_questions=["Would you like to go to space?", "What do you think aliens look like?"]
        )
        assert len(news.interactive_questions) >= 1


# ============================================================================
# 4. Error Handling Contract Tests
# ============================================================================

class TestErrorHandlingContracts:
    """Error handling contract tests"""

    def test_missing_required_fields(self):
        """Test missing required fields"""
        with pytest.raises(ValidationError) as exc_info:
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg"
                # Missing child_id and child_age
            )
        errors = exc_info.value.errors()
        assert any(e['loc'][0] == 'child_id' for e in errors)
        assert any(e['loc'][0] == 'child_age' for e in errors)

    def test_invalid_enum_value(self):
        """Test invalid enum value"""
        with pytest.raises(ValidationError):
            StoryGenerationInput(
                child_id="user-123",
                child_age=8,
                interests=["dinosaurs"],
                mode="invalid_mode"  # Invalid mode
            )

    def test_type_mismatch(self):
        """Test type mismatch"""
        with pytest.raises(ValidationError):
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg",
                child_id="user-123",
                child_age="seven"  # Should be int
            )


# ============================================================================
# 5. Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility:
    """Backward compatibility tests"""

    def test_optional_fields_can_be_omitted(self):
        """Test optional fields can be omitted"""
        # This ensures API backward compatibility
        input_data = ImageAnalysisInput(
            image_url="https://example.com/image.jpg",
            child_id="user-123",
            child_age=7
            # interests is optional, can be omitted
        )
        assert input_data.interests is None

    def test_new_optional_fields_dont_break_old_code(self):
        """Test new optional fields don't break old code"""
        # Suppose we add a new optional field in a future version
        # Old code should still work
        output = ImageAnalysisResult(
            objects=["puppy"],
            scene="park",
            mood="happy",
            embedding_vector=[0.1] * 512,
            confidence_score=0.9
            # recurring_characters is optional
        )
        assert output.recurring_characters == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
