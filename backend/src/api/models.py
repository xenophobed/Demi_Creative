"""
API Request/Response Models

Pydantic models defining request and response formats for all API endpoints
"""

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Enum Types
# ============================================================================

class AgeGroup(str, Enum):
    """Age group (PRD §2.1 canonical: 3-5, 6-8, 9-12)"""
    AGE_3_5 = "3-5"
    AGE_6_8 = "6-8"
    AGE_9_12 = "9-12"


class TTSProviderEnum(str, Enum):
    """TTS provider selection (#149, #243)"""
    OPENAI = "openai"
    REPLICATE = "replicate"
    ELEVENLABS = "elevenlabs"


class SceneProfile(str, Enum):
    """TTS scene profile presets (#245)"""
    BEDTIME = "bedtime"
    ADVENTURE = "adventure"
    SPOOKY = "spooky"
    EDUCATIONAL = "educational"


class EmotionType(str, Enum):
    """Allowed TTS emotions (#149). Age-filtered at service layer."""
    HAPPY = "happy"
    SAD = "sad"
    NEUTRAL = "neutral"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"


class VoiceType(str, Enum):
    """Voice type"""
    NOVA = "nova"           # gentle female
    SHIMMER = "shimmer"     # energetic female
    ALLOY = "alloy"         # neutral
    ECHO = "echo"           # male
    FABLE = "fable"         # storyteller
    ONYX = "onyx"           # deep male


class StoryLengthMode(str, Enum):
    """Story length mode for interactive stories (#331)"""
    SHORT = "short"         # 5 choices — Quick Tale / 小故事
    MEDIUM = "medium"       # 10 choices — Short Story / 短文章
    UNLIMITED = "unlimited" # No limit — Endless Adventure / 小说


class StoryMode(str, Enum):
    """Story mode"""
    LINEAR = "linear"           # linear story
    INTERACTIVE = "interactive" # interactive story


class SessionStatus(str, Enum):
    """Session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class VideoStyle(str, Enum):
    """Video style"""
    GENTLE_ANIMATION = "gentle_animation"  # gentle animation, child-friendly
    PLAYFUL = "playful"                    # playful style
    STORYBOOK = "storybook"                # storybook style


class MembershipTier(str, Enum):
    """Membership tier for referral-based upgrades (PRD §3.9.4)"""
    FREE = "free"
    PLUS = "plus"


class ArtTheme(str, Enum):
    """Art style transfer theme for image-to-story (PRD §3.1.1)"""
    CARTOON = "cartoon"
    OIL_PAINTING = "oil_painting"
    WATERCOLOR = "watercolor"
    PIXEL_ART = "pixel_art"
    ANIME = "anime"
    CRAYON = "crayon"
    STORYBOOK = "storybook"
    NONE = "none"


class VideoStatus(str, Enum):
    """Video generation status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NewsCategory(str, Enum):
    """News category"""
    SCIENCE = "science"
    NATURE = "nature"
    TECHNOLOGY = "technology"
    SPACE = "space"
    ANIMALS = "animals"
    SPORTS = "sports"
    CULTURE = "culture"
    GENERAL = "general"


# ============================================================================
# Image-to-Story API Models
# ============================================================================

class ImageToStoryRequest(BaseModel):
    """Image-to-story request"""
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Child unique identifier"
    )
    age_group: AgeGroup = Field(
        ...,
        description="Age group: 3-5, 6-9, 10-12"
    )
    interests: Optional[List[str]] = Field(
        default=None,
        max_length=5,
        description="Interest tags, maximum 5"
    )
    voice: VoiceType = Field(
        default=VoiceType.NOVA,
        description="Voice type"
    )
    enable_audio: bool = Field(
        default=True,
        description="Whether to generate audio"
    )

    @field_validator('interests')
    @classmethod
    def validate_interests(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("Maximum 5 interest tags")
        return v


class StoryContent(BaseModel):
    """Story content"""
    text: str = Field(..., description="Story text")
    word_count: int = Field(..., description="Word count")
    age_adapted: bool = Field(..., description="Whether age-adapted")
    degraded_length: bool = Field(False, description="Story length outside expected range for age group")


class EducationalValue(BaseModel):
    """Educational value"""
    themes: List[str] = Field(..., description="Themes (e.g., friendship, courage)")
    concepts: List[str] = Field(..., description="Concepts (e.g., colors, numbers)")
    moral: Optional[str] = Field(None, description="Moral lesson")


class CharacterMemory(BaseModel):
    """Character memory"""
    character_name: str = Field(..., description="Character name")
    description: str = Field(..., description="Character description")
    appearances: int = Field(..., description="Appearance count")


class ImageToStoryResponse(BaseModel):
    """Image-to-story response"""
    story_id: str = Field(..., description="Story unique ID")
    story: StoryContent = Field(..., description="Story content")
    image_url: Optional[str] = Field(None, description="Drawing image URL")
    styled_image_url: Optional[str] = Field(None, description="Styled image URL")
    audio_url: Optional[str] = Field(None, description="Audio file URL")
    video_url: Optional[str] = Field(None, description="Video file URL")
    video_job_id: Optional[str] = Field(None, description="Video generation job ID")
    educational_value: EducationalValue = Field(..., description="Educational value")
    characters: List[CharacterMemory] = Field(
        default_factory=list,
        description="Recognized characters"
    )
    analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Drawing analysis result"
    )
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Safety score")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Created at"
    )


# ============================================================================
# Interactive Story API Models
# ============================================================================

class InteractiveStoryStartRequest(BaseModel):
    """Start interactive story request"""
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Child unique identifier"
    )
    age_group: AgeGroup = Field(..., description="Age group")
    interests: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Interest tags, 1-5"
    )
    theme: Optional[str] = Field(
        None,
        description="Story theme (optional)"
    )
    voice: VoiceType = Field(
        default=VoiceType.FABLE,
        description="Voice type"
    )
    enable_audio: bool = Field(
        default=True,
        description="Whether to generate audio"
    )
    story_length: StoryLengthMode = Field(
        default=StoryLengthMode.SHORT,
        description="Story length mode: short (5 choices), medium (10), unlimited"
    )

    @field_validator('interests')
    @classmethod
    def validate_interests(cls, v):
        if len(v) < 1 or len(v) > 5:
            raise ValueError("Interest tags count must be between 1 and 5")
        return v


class StoryChoice(BaseModel):
    """Story choice"""
    choice_id: str = Field(..., description="Choice ID")
    text: str = Field(..., description="Choice text")
    emoji: str = Field(..., description="Choice icon")


class StorySegment(BaseModel):
    """Story segment"""
    segment_id: int = Field(..., description="Segment number")
    text: str = Field(..., description="Segment text")
    audio_url: Optional[str] = Field(None, description="Audio URL")
    choices: List[StoryChoice] = Field(
        default_factory=list,
        description="Available branching choices"
    )
    is_ending: bool = Field(
        default=False,
        description="Whether this is an ending"
    )
    # Optional content support for age-based behavior
    primary_mode: str = Field(
        default="both",
        description="Primary content mode: 'audio' | 'text' | 'both'"
    )
    optional_content_available: bool = Field(
        default=False,
        description="Whether optional content button is available"
    )
    optional_content_type: Optional[str] = Field(
        None,
        description="Optional content type: 'text' (show text for 3-5) | 'audio' (play audio for 10-12)"
    )


class InteractiveStoryStartResponse(BaseModel):
    """Start interactive story response"""
    session_id: str = Field(..., description="Session ID")
    story_title: str = Field(..., description="Story title")
    opening: StorySegment = Field(..., description="Opening segment")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Created at"
    )


class ChoiceRequest(BaseModel):
    """Branch choice request"""
    choice_id: str = Field(..., description="Selected choice ID")


class ChoiceResponse(BaseModel):
    """Branch choice response"""
    session_id: str = Field(..., description="Session ID")
    next_segment: StorySegment = Field(..., description="Next segment")
    choice_history: List[str] = Field(..., description="Choice history")
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress (0-1)")


class SessionStatusResponse(BaseModel):
    """Session status response"""
    session_id: str = Field(..., description="Session ID")
    status: SessionStatus = Field(..., description="Session status")
    child_id: str = Field(..., description="Child ID")
    story_title: str = Field(..., description="Story title")
    current_segment: int = Field(..., description="Current segment number")
    total_segments: int = Field(..., description="Total segments")
    choice_history: List[str] = Field(..., description="Choice history")
    educational_summary: Optional[EducationalValue] = Field(
        None,
        description="Educational summary (after completion)"
    )
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
    expires_at: datetime = Field(..., description="Expires at")


class SessionResumeResponse(BaseModel):
    """Resume an in-progress interactive story session."""
    session_id: str = Field(..., description="Session ID")
    status: SessionStatus = Field(..., description="Session status")
    story_title: str = Field(..., description="Story title")
    age_group: AgeGroup = Field(..., description="Age group")
    segments: List[StorySegment] = Field(..., description="All generated segments")
    choice_history: List[str] = Field(..., description="Choice history")
    progress: float = Field(..., ge=0.0, description="Completion progress 0-1")
    total_segments: int = Field(..., description="Total segments")
    story_length_mode: StoryLengthMode = Field(
        default=StoryLengthMode.SHORT,
        description="Story length mode"
    )
    educational_summary: Optional[EducationalValue] = Field(None, description="Educational summary")


class SaveInteractiveStoryResponse(BaseModel):
    """Save interactive story response"""
    story_id: str = Field(..., description="Saved story ID")
    session_id: str = Field(..., description="Interactive session ID")
    message: str = Field(..., description="Operation result message")
    already_saved: bool = Field(False, description="Whether the story was already saved previously")


class KeyConceptResponse(BaseModel):
    """News key concept"""
    term: str = Field(..., description="Concept term")
    explanation: str = Field(..., description="Child-friendly explanation")
    emoji: str = Field(default="💡", description="Concept icon")


class InteractiveQuestionResponse(BaseModel):
    """Interactive question"""
    question: str = Field(..., description="Question")
    hint: Optional[str] = Field(None, description="Hint")
    emoji: str = Field(default="🤔", description="Question icon")


class KidsDailyTextRequest(BaseModel):
    """Kids Daily text conversion request (simple mode)"""
    child_id: str = Field(..., min_length=1, max_length=100, description="Child unique identifier")
    age_group: AgeGroup = Field(..., description="Age group")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="News category")
    news_url: Optional[str] = Field(None, description="News URL")
    news_text: Optional[str] = Field(None, description="News original text")
    enable_audio: bool = Field(default=True, description="Whether to generate audio")
    voice: Optional[VoiceType] = Field(default=VoiceType.FABLE, description="Voice type")


class KidsDailyTextResponse(BaseModel):
    """Kids Daily text conversion response"""
    conversion_id: str = Field(..., description="Conversion ID")
    kid_title: str = Field(..., description="Kid-friendly title")
    kid_content: str = Field(..., description="Kid-friendly content")
    why_care: str = Field(..., description="Why it matters")
    key_concepts: List[KeyConceptResponse] = Field(default_factory=list, description="Key concepts")
    interactive_questions: List[InteractiveQuestionResponse] = Field(default_factory=list, description="Interactive questions")
    category: NewsCategory = Field(..., description="News category")
    age_group: AgeGroup = Field(..., description="Age group")
    audio_url: Optional[str] = Field(None, description="Audio URL")
    original_url: Optional[str] = Field(None, description="Original news URL")
    is_degraded: bool = Field(default=False, description="Whether degraded/fallback content")
    degraded_reason: Optional[str] = Field(None, description="Degradation reason")
    created_at: datetime = Field(default_factory=datetime.now, description="Created at")


# ============================================================================
# Inspiration Daily API Models (#405)
# ============================================================================


class InspirationCategory(str, Enum):
    """Creative project category for Inspiration Daily (PRD §3.10)"""
    ART_PROJECT = "art_project"
    INVENTION = "invention"
    RECYCLING = "recycling"
    SCIENCE_CRAFT = "science_craft"
    PERFORMANCE = "performance"


class CtaType(str, Enum):
    """Call-to-action type determining where the child is routed"""
    DRAW = "draw"
    STORY = "story"
    EXPLORE = "explore"


class AgeAdaptation(BaseModel):
    """Age-adapted text variant for an inspiration card"""
    summary: str = Field(..., description="Age-appropriate summary")
    creative_prompt: str = Field(..., description="Age-appropriate creative prompt")


class InspirationCard(BaseModel):
    """Single daily inspiration card (PRD §3.10.2)"""
    id: str = Field(..., description="Stable slug ID, e.g. 'bubble-painting-brazil'")
    title: str = Field(..., description="Short, exciting headline")
    summary: str = Field(..., description="1-2 sentence description (default 6-8)")
    source_hint: str = Field(..., description="Anonymized origin, e.g. 'A school in São Paulo'")
    creative_prompt: str = Field(..., description="Actionable try-this instruction (default 6-8)")
    category: InspirationCategory = Field(..., description="Project category")
    illustration_emoji: str = Field(..., description="Emoji visual representation")
    cta_type: CtaType = Field(..., description="CTA routing type")
    cta_route: str = Field(..., description="Target page path, e.g. '/upload'")
    age_adaptations: Dict[str, AgeAdaptation] = Field(
        ..., description="Age-adapted variants keyed by '3-5', '6-8', '9-12'"
    )


class InspirationDailyResponse(BaseModel):
    """Response for GET /api/v1/inspiration-daily"""
    card: InspirationCard = Field(..., description="Today's inspiration card")
    age_group: str = Field(..., description="Age group used for adaptation")
    adapted_summary: str = Field(..., description="Age-adapted summary text")
    adapted_prompt: str = Field(..., description="Age-adapted creative prompt")


# ============================================================================
# Kids Daily API Models (#44)
# ============================================================================

ALLOWED_DIALOGUE_ROLES = {"curious_kid", "fun_expert", "guest"}
ALLOWED_ANIMATION_TYPES = {"pan", "zoom", "ken_burns"}


class DialogueLine(BaseModel):
    """Kids Daily dialogue line"""
    role: str = Field(..., description="Role: curious_kid | fun_expert | guest")
    text: str = Field(..., min_length=1, description="Dialogue content")
    display_name: Optional[str] = Field(None, description="Role display name (Mimi / Duo)")
    timestamp_start: float = Field(..., ge=0.0, description="Start time (seconds)")
    timestamp_end: float = Field(..., ge=0.0, description="End time (seconds)")

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ALLOWED_DIALOGUE_ROLES:
            raise ValueError("role must be one of curious_kid | fun_expert | guest")
        return value

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.timestamp_end <= self.timestamp_start:
            raise ValueError("timestamp_end must be greater than timestamp_start")
        return self


class DialogueScript(BaseModel):
    """Kids Daily dialogue script"""
    lines: List[DialogueLine] = Field(default_factory=list, description="Dialogue lines")
    total_duration: float = Field(..., ge=0.0, description="Total duration (seconds)")
    guest_character: Optional[str] = Field(None, description="Guest character name (optional)")

    @model_validator(mode="after")
    def validate_total_duration(self):
        if self.lines:
            latest_end = max(line.timestamp_end for line in self.lines)
            if self.total_duration < latest_end:
                raise ValueError("total_duration must cover the final line timestamp")
        return self


class EpisodeIllustration(BaseModel):
    """Kids Daily illustration metadata"""
    url: str = Field(..., min_length=1, description="Illustration URL")
    description: str = Field(..., min_length=1, description="Illustration description")
    display_order: int = Field(..., ge=0, description="Display order")
    animation_type: str = Field(..., description="Animation type: pan | zoom | ken_burns")

    @field_validator("animation_type")
    @classmethod
    def validate_animation_type(cls, value: str) -> str:
        if value not in ALLOWED_ANIMATION_TYPES:
            raise ValueError("animation_type must be one of pan | zoom | ken_burns")
        return value


class KidsDailyEpisode(BaseModel):
    """Kids Daily complete episode data"""
    episode_id: str = Field(..., description="Episode unique ID")
    child_id: str = Field(..., description="Child ID")
    age_group: AgeGroup = Field(..., description="Age group")
    category: NewsCategory = Field(..., description="Topic category")
    kid_title: str = Field(..., description="Child-friendly title")
    kid_content: str = Field(..., description="Child-friendly content")
    why_care: str = Field(..., description="Why it matters")
    key_concepts: List[KeyConceptResponse] = Field(default_factory=list, description="Key concepts")
    interactive_questions: List[InteractiveQuestionResponse] = Field(default_factory=list, description="Interactive questions")
    dialogue_script: DialogueScript = Field(..., description="Multi-character dialogue script")
    illustrations: List[EpisodeIllustration] = Field(default_factory=list, description="Illustrations list")
    audio_urls: Dict[str, str] = Field(default_factory=dict, description="Audio URL mapping (line_index -> url)")
    story_type: Literal["kids_daily"] = Field(default="kids_daily", description="Content type")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Total episode duration (seconds)")
    is_played: bool = Field(default=False, description="Whether played")
    is_new: bool = Field(default=True, description="Whether new content")
    is_degraded: bool = Field(default=False, description="Whether degraded/fallback generated content")
    degraded_reason: Optional[str] = Field(None, description="Degradation reason")
    created_at: datetime = Field(default_factory=datetime.now, description="Created at")


class KidsDailyRequest(BaseModel):
    """Kids Daily generation request"""
    news_url: Optional[str] = Field(None, description="News URL")
    news_text: Optional[str] = Field(None, description="News body text")
    age_group: AgeGroup = Field(..., description="Age group")
    child_id: Optional[str] = Field(None, description="Child ID (optional)")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="Topic category")


class KidsDailyOnDemandRequest(BaseModel):
    """On-demand Kids Daily generation request (#304)"""
    child_id: str = Field(..., min_length=1, max_length=100, description="Child ID")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="Topic category")
    age_group: AgeGroup = Field(..., description="Age group")


class KidsDailyRateLimitResponse(BaseModel):
    """Rate limit response (#305)"""
    message: str = Field(..., description="Friendly prompt message")
    retry_after: int = Field(..., ge=0, description="Seconds until next generation allowed")


class KidsDailyGenerationMetadata(BaseModel):
    """Kids Daily generation metadata"""
    generation_id: str = Field(..., description="Generation task ID")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Content safety score")
    used_mock: bool = Field(default=False, description="Whether mock fallback was used")
    is_degraded: bool = Field(default=False, description="Whether degraded/fallback generated content")
    degraded_reason: Optional[str] = Field(None, description="Degradation reason")
    created_at: datetime = Field(default_factory=datetime.now, description="Generated at")


class KidsDailyResponse(BaseModel):
    """Kids Daily generation response"""
    episode: KidsDailyEpisode = Field(..., description="Episode data")
    metadata: KidsDailyGenerationMetadata = Field(..., description="Generation metadata")


class PaginatedKidsDailyResponse(BaseModel):
    """Kids Daily episode list response"""
    items: List[KidsDailyEpisode] = Field(default_factory=list, description="Episode list")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset")


class TopicSubscription(BaseModel):
    """Topic subscription record"""
    child_id: str = Field(..., description="Child ID")
    topic: NewsCategory = Field(..., description="Subscribed topic")
    subscribed_at: datetime = Field(default_factory=datetime.now, description="Subscribed at")
    is_active: bool = Field(default=True, description="Whether subscription is active")


class SubscriptionRequest(BaseModel):
    """Create subscription request"""
    child_id: str = Field(..., min_length=1, max_length=100, description="Child ID")
    topic: NewsCategory = Field(..., description="Subscription topic")


class SubscriptionResponse(TopicSubscription):
    """Subscription operation response"""
    message: str = Field(default="ok", description="Operation result message")


class SubscriptionListResponse(BaseModel):
    """Subscription list response"""
    items: List[TopicSubscription] = Field(default_factory=list, description="Subscription list")
    total: int = Field(..., description="Total subscriptions")


class KidsDailyEmailSubscriptionRequest(BaseModel):
    """Public Kids Daily preview email subscription request"""
    email: str = Field(..., min_length=5, max_length=254, description="Email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        normalized = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", normalized):
            raise ValueError("Invalid email format")
        return normalized


class KidsDailyEmailSubscriptionResponse(BaseModel):
    """Public Kids Daily preview email subscription response"""
    email: str = Field(..., description="Subscribed email address")
    subscribed_at: datetime = Field(..., description="Subscription timestamp")
    message: str = Field(default="subscribed", description="Operation result message")


class KidsDailyTrackEvent(str, Enum):
    """Kids Daily playback event type"""
    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ABANDON = "abandon"


class KidsDailyTrackRequest(BaseModel):
    """Kids Daily playback tracking request"""
    child_id: str = Field(..., min_length=1, max_length=100, description="Child ID")
    episode_id: str = Field(..., min_length=1, description="Episode ID")
    topic: NewsCategory = Field(..., description="Episode topic")
    event_type: KidsDailyTrackEvent = Field(..., description="Event type")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Playback progress 0-1")
    played_seconds: Optional[float] = Field(default=None, ge=0.0, description="Seconds played")
    event_at: datetime = Field(default_factory=datetime.now, description="Event time")


class KidsDailyTrackResponse(BaseModel):
    """Kids Daily tracking response"""
    status: str = Field(..., description="Status")
    topic_score: float = Field(..., description="Current topic engagement score")
    profile_updated_at: datetime = Field(default_factory=datetime.now, description="Preference updated at")


# ============================================================================
# Error Response Models
# ============================================================================

class ErrorDetail(BaseModel):
    """Error details"""
    field: Optional[str] = Field(None, description="Error field")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Error time"
    )


# ============================================================================
# Health Check Models
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Check time"
    )
    services: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dependent service statuses"
    )


# ============================================================================
# Video Generation API Models
# ============================================================================

class VideoJobRequest(BaseModel):
    """Video generation request"""
    story_id: str = Field(..., description="Story ID")
    style: VideoStyle = Field(
        default=VideoStyle.GENTLE_ANIMATION,
        description="Video style"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Video provider adapter name"
    )
    model: Optional[str] = Field(
        default=None,
        description="Provider video model identifier"
    )
    include_audio: bool = Field(
        default=True,
        description="Whether to include audio narration"
    )
    duration_seconds: int = Field(
        default=10,
        ge=5,
        le=30,
        description="Video duration (seconds)"
    )


class VideoJobResponse(BaseModel):
    """Video generation job response"""
    job_id: str = Field(..., description="Job ID")
    story_id: str = Field(..., description="Story ID")
    status: VideoStatus = Field(..., description="Job status")
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Created at"
    )


class VideoJobStatusResponse(BaseModel):
    """Video job status response"""
    job_id: str = Field(..., description="Job ID")
    status: VideoStatus = Field(..., description="Job status")
    progress_percent: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage"
    )
    video_url: Optional[str] = Field(None, description="Video URL")
    error_message: Optional[str] = Field(None, description="Error message")
    created_at: datetime = Field(..., description="Created at")
    completed_at: Optional[datetime] = Field(None, description="Completed at")


# ============================================================================
# User Authentication API Models
# ============================================================================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username"
    )
    email: str = Field(
        ...,
        description="Email address"
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Password, at least 6 characters"
    )
    display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Display name"
    )
    referral_code: Optional[str] = Field(
        None,
        max_length=8,
        description="Referral code from share link (optional)"
    )
    role: Literal["parent", "child"] = Field(
        default="parent",
        description="Who is setting up the account. Parent is the primary supported path.",
    )
    parent_email: Optional[str] = Field(
        None,
        description="Required when a child starts registration without a parent account.",
    )
    child_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Configured child profile id for parent-owned setup.",
    )
    child_name: Optional[str] = Field(
        None,
        max_length=80,
        description="Parent-provided child profile nickname.",
    )
    child_age_group: Optional[AgeGroup] = Field(
        None,
        description="Parent-selected age group for the initial child profile.",
    )
    child_interests: List[str] = Field(
        default_factory=list,
        max_length=8,
        description="Parent-selected interests for the initial child profile.",
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator('parent_email')
    @classmethod
    def validate_parent_email(cls, v):
        if v is None or v == "":
            return None
        if "@" not in v or "." not in v:
            raise ValueError("Invalid parent email format")
        return v.lower()

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v.lower()

    @field_validator('child_name')
    @classmethod
    def validate_child_name(cls, v):
        if v is None or v == "":
            return None
        return _validate_child_nickname(v)

    @model_validator(mode="after")
    def validate_child_signup_parent_email(self):
        if self.role == "child" and not self.parent_email:
            raise ValueError("A parent/guardian email is required for child sign-up")
        return self


_NICKNAME_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_NICKNAME_PHONE_RE = re.compile(r"(?:\+?\d[\s().-]*){7,}")


def _validate_child_nickname(value: str) -> str:
    nickname = value.strip()
    if not nickname:
        raise ValueError("Child nickname is required")
    if _NICKNAME_EMAIL_RE.search(nickname) or _NICKNAME_PHONE_RE.search(nickname):
        raise ValueError("Child nickname cannot include email addresses or phone numbers")
    return nickname


class ChildProfileCreateRequest(BaseModel):
    """Create a child profile under the current parent account."""
    name: str = Field(..., min_length=1, max_length=80)
    age_group: AgeGroup = Field(default=AgeGroup.AGE_6_8)
    interests: List[str] = Field(default_factory=list, max_length=8)
    avatar: Optional[str] = Field(default=None, max_length=120)
    child_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_default: bool = Field(default=False)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return _validate_child_nickname(v)


class ChildProfileUpdateRequest(BaseModel):
    """Patch editable child profile fields."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    age_group: Optional[AgeGroup] = None
    interests: Optional[List[str]] = Field(default=None, max_length=8)
    avatar: Optional[str] = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return None
        return _validate_child_nickname(v)


class ChildProfileResponse(BaseModel):
    """Child profile API response."""
    child_id: str
    user_id: str
    name: str
    age_group: str
    interests: List[str] = Field(default_factory=list)
    avatar: Optional[str] = None
    is_default: bool = False
    archived_at: Optional[datetime] = None
    camera_consent: bool = False
    microphone_consent: bool = False
    voice_conversation_consent: bool = False
    voice_persona: str = "buddy_default"
    voice_session_quota_seconds: int = 0
    created_at: datetime
    updated_at: datetime


class ChildProfileConsentUpdateRequest(BaseModel):
    """Patch consent + voice fields on a child profile (#587, #612).

    Camera + microphone consent shipped with #587. The voice fields land
    in #612 to support PRD §3.16 Talk to Buddy:
      - voice_conversation_consent — gates the realtime voice channel
      - voice_persona — selects the buddy's TTS voice preset
      - voice_session_quota_seconds — per-day quota cap (per-age in §3.16.6)

    At least one field must be supplied; supplying multiple is allowed.
    """
    camera_consent: Optional[bool] = None
    microphone_consent: Optional[bool] = None
    voice_conversation_consent: Optional[bool] = None
    voice_persona: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    voice_session_quota_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        le=24 * 60 * 60,  # at most one day
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if all(
            value is None
            for value in (
                self.camera_consent,
                self.microphone_consent,
                self.voice_conversation_consent,
                self.voice_persona,
                self.voice_session_quota_seconds,
            )
        ):
            raise ValueError(
                "At least one consent or voice field must be provided"
            )
        return self


class ChildProfileListResponse(BaseModel):
    """GET /child-profiles response envelope."""
    items: List[ChildProfileResponse] = Field(default_factory=list)


# ============================================================================
# Talk to Buddy — Realtime Voice (#611 / epic #605, PRD §3.16)
# ============================================================================

class VoiceSessionStartRequest(BaseModel):
    """POST /api/v1/me/agent/voice/session — initiate a realtime voice session.

    Child profile is the consent + quota anchor. Backend mints an ephemeral
    token + WS URL; the browser opens the WebSocket directly. Audio bytes
    flow over the WS — never through this REST envelope.
    """
    child_id: str = Field(..., min_length=1, max_length=100)
    persona: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Override the buddy's voice persona for this session. "
                    "Falls back to child_profile.voice_persona.",
    )


class VoiceProviderConfig(BaseModel):
    """Sub-shape of VoiceSessionStartResponse — provider-specific runtime hints."""
    provider: Literal["mock", "hybrid", "openai_realtime"] = Field(
        ..., description="Which RealtimeVoiceProvider impl backs this session."
    )
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    audio_format: Literal["pcm16", "opus"] = Field(default="pcm16")


class VoiceSessionStartResponse(BaseModel):
    """REST response — what the client needs to open the WS handshake.

    Returns 501 in the foundation PR (#611). Real implementation lands in
    sub-story #606.5 once the broker is wired. In #645 we add the OpenAI
    Realtime client secret + transport hint so E4 (#647 WebRTC) can
    layer in without breaking the contract.
    """
    session_id: str
    ephemeral_token: str = Field(..., min_length=20, max_length=512)
    expires_at: datetime
    ws_url: str = Field(..., description="Absolute or relative WebSocket URL")
    provider_config: VoiceProviderConfig
    openai_realtime_client_secret: Optional[str] = Field(
        default=None,
        description=(
            "Ephemeral OpenAI Realtime client secret. Populated only when "
            "the OpenAI Realtime provider backs the session. The frontend "
            "stores it for E4's WebRTC transport — for E2's server-relay "
            "(WS) path it's unused."
        ),
    )
    transport: Literal["ws", "webrtc"] = Field(
        default="ws",
        description=(
            "Selected client transport. ``ws`` = server-relay broker (E2, "
            "default). ``webrtc`` = browser-direct RTCPeerConnection against "
            "OpenAI Realtime (E4 / #647) — opt-in via the ``prefer_webrtc`` "
            "query parameter. Non-OpenAI providers always degrade to ``ws``."
        ),
    )


# ── WS Event envelopes ───────────────────────────────────────────────────────
# Discriminated unions on `type`. Pydantic resolves by literal match.

class VoiceWSAudioChunkEvent(BaseModel):
    """Client → Server: a chunk of captured PCM/opus from the browser mic."""
    type: Literal["audio_chunk"]
    seq: int = Field(..., ge=0, description="Monotonic sequence number")
    audio_b64: str = Field(..., description="Base64-encoded audio bytes")


class VoiceWSVadEndEvent(BaseModel):
    """Client → Server: VAD detected end-of-utterance; finalize transcription."""
    type: Literal["vad_end"]
    seq: int = Field(..., ge=0)


class VoiceWSClientDoneEvent(BaseModel):
    """Client → Server: user tapped End; close the session gracefully."""
    type: Literal["client_done"]


# Discriminated union of every legal client → server WS event.
VoiceWSClientEvent = Union[
    VoiceWSAudioChunkEvent,
    VoiceWSVadEndEvent,
    VoiceWSClientDoneEvent,
]


class VoiceWSPartialTranscriptEvent(BaseModel):
    """Server → Client: streaming partial transcript while the child is speaking."""
    type: Literal["partial_transcript"]
    text: str
    seq: int = Field(..., ge=0)


class VoiceWSFinalTranscriptEvent(BaseModel):
    """Server → Client: safety-passed final transcript for one child utterance."""
    type: Literal["final_transcript"]
    text: str
    safety_passed: bool = Field(default=True)


class VoiceWSAssistantTextEvent(BaseModel):
    """Server → Client: a delta of the buddy's reply text (pre-TTS)."""
    type: Literal["assistant_text"]
    delta: str
    is_final: bool = Field(default=False)


class VoiceWSAudioChunkServerEvent(BaseModel):
    """Server → Client: a chunk of synthesized buddy speech."""
    type: Literal["audio_chunk"]
    seq: int = Field(..., ge=0)
    audio_b64: str


class VoiceWSSafetyBlockEvent(BaseModel):
    """Server → Client: the proposed reply or transcript failed safety; replaced."""
    type: Literal["safety_block"]
    direction: Literal["utterance", "reply"]
    fallback_text: str = Field(
        ..., description="The kid-friendly redirect that will be spoken instead."
    )


class VoiceWSQuotaExhaustedEvent(BaseModel):
    """Server → Client: daily voice quota is spent; session closing."""
    type: Literal["quota_exhausted"]
    seconds_remaining: int = Field(default=0)


class VoiceWSErrorEvent(BaseModel):
    """Server → Client: terminal error; session will close after this frame."""
    type: Literal["error"]
    code: str = Field(..., description="Stable error code (e.g. 'not_implemented').")
    message: str = Field(default="")


# Discriminated union of every legal server → client WS event.
VoiceWSServerEvent = Union[
    VoiceWSPartialTranscriptEvent,
    VoiceWSFinalTranscriptEvent,
    VoiceWSAssistantTextEvent,
    VoiceWSAudioChunkServerEvent,
    VoiceWSSafetyBlockEvent,
    VoiceWSQuotaExhaustedEvent,
    VoiceWSErrorEvent,
]


class ParentApprovalTokenRequest(BaseModel):
    """Approve a child-started account with a signed parent token."""
    token: str = Field(..., min_length=20, description="Signed parent approval token")


class ParentApprovalResponse(BaseModel):
    """Parent approval result."""
    status: str = Field(..., description="Approval operation status")
    user_id: str = Field(..., description="Approved child user id")
    consent_status: str = Field(..., description="Updated consent status")


class ParentApprovalStatusResponse(BaseModel):
    """Pending approval resend/status response."""
    status: str = Field(..., description="Approval status")
    parent_email: Optional[str] = Field(None, description="Parent/guardian email")
    approval_token: Optional[str] = Field(None, description="Development/test approval token")
    approval_url: Optional[str] = Field(None, description="Development/test approval URL")


class UserLoginRequest(BaseModel):
    """User login request"""
    username_or_email: str = Field(
        ...,
        description="Username or email"
    )
    password: str = Field(
        ...,
        description="Password"
    )


class PublicUserResponse(BaseModel):
    """Public user profile — safe for unauthenticated access"""
    user_id: str = Field(..., description="User unique ID")
    username: str = Field(..., description="Username")
    display_name: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    created_at: datetime = Field(..., description="Registered at")


class UserResponse(BaseModel):
    """User info response"""
    user_id: str = Field(..., description="User unique ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email")
    display_name: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    is_active: bool = Field(..., description="Whether active")
    is_verified: bool = Field(..., description="Whether verified")
    role: str = Field(default="child", description="User role: 'child' or 'parent'")
    parent_email: Optional[str] = Field(None, description="Parent/guardian email for child-started accounts")
    consent_status: str = Field(default="not_required", description="Parent consent status")
    membership_tier: str = Field(default="free", description="Membership tier: 'free' or 'plus'")
    referral_code: str = Field(default="", description="User's unique referral code")
    created_at: datetime = Field(..., description="Registered at")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")
    # Onboarding + agent fields (#439, depends on #438 schema)
    has_agent: bool = Field(default=False, description="Whether the user has a configured agent persona")
    onboarded_at: Optional[datetime] = Field(None, description="When onboarding finished")
    nickname: Optional[str] = Field(None, description="Friendly name shown in UI")
    default_child_id: Optional[str] = Field(None, description="Active child profile bound to the agent")
    parent_consent_at: Optional[datetime] = Field(None, description="When parent granted consent")


class AgentResponse(BaseModel):
    """Agent persona info (PRD §3.11.3)."""
    agent_id: str = Field(..., description="Stable surrogate ID of the agent persona")
    user_id: str = Field(..., description="Owner user ID")
    child_id: str = Field(..., description="Child profile this agent is bound to")
    agent_name: str = Field(..., description="Agent display name")
    agent_avatar_id: str = Field(..., description="Avatar identifier (e.g. 'emoji:🦊')")
    agent_title: str = Field(..., description="Agent title (curated or free-text)")
    tone: str = Field(default="warm_curious", description="Guided tone preset")
    interaction_style: str = Field(default="guided_playful", description="Guided interaction style preset")
    enabled_skills: List[str] = Field(default_factory=list, description="Enabled My Agent skill IDs")
    favorite_topics: List[str] = Field(default_factory=list, description="Topics the buddy should favor")
    learning_goals: List[str] = Field(default_factory=list, description="Parent-selected learning goals")
    custom_instructions: str = Field(default="", max_length=500, description="Parent-approved custom guidance")
    created_at: datetime = Field(..., description="When the agent was first created")
    updated_at: datetime = Field(..., description="When the agent was last updated")


class UpsertAgentRequest(BaseModel):
    """PUT /me/agent body — create-or-update an agent persona."""
    agent_name: str = Field(..., min_length=1, max_length=32, description="Agent display name")
    agent_avatar_id: str = Field(..., min_length=1, description="Avatar identifier from the whitelist")
    agent_title: str = Field(..., min_length=1, max_length=32, description="Agent title")
    child_id: str = Field(..., min_length=1, description="Child profile this agent is bound to")
    tone: str = Field(default="warm_curious", min_length=1, max_length=40)
    interaction_style: str = Field(default="guided_playful", min_length=1, max_length=40)
    enabled_skills: List[str] = Field(default_factory=list)
    favorite_topics: List[str] = Field(default_factory=list, max_length=8)
    learning_goals: List[str] = Field(default_factory=list, max_length=8)
    custom_instructions: str = Field(default="", max_length=500)


class AgentChatRequest(BaseModel):
    """JSON body for POST /me/agent/chat/stream."""
    child_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, min_length=1)
    age_group: Optional[str] = Field(None, description="Active child age group, e.g. 6-8")
    interests: List[str] = Field(default_factory=list, max_length=8)


class CompleteOnboardingRequest(BaseModel):
    """POST /me/onboarding/complete body — gates onboarding completion behind parent consent (#440)."""
    parent_consent: bool = Field(..., description="True iff a parent has granted consent for the child's buddy persona to be shown publicly when sharing")
    child_id: str = Field(..., min_length=1, description="Child profile being onboarded")


# ---------------------------------------------------------------------------
# My Agent — multi-topic chat sessions (#565 §3.11.8)
# ---------------------------------------------------------------------------


class AgentChatSessionSummary(BaseModel):
    """One row in the sessions sidebar (#567)."""
    session_id: str = Field(..., description="Stable session identifier")
    child_id: str = Field(..., description="Child profile this session belongs to")
    title: str = Field(default="", description="Auto-generated or renamed session title")
    last_message_preview: str = Field(default="", description="Truncated last assistant reply")
    archived_at: Optional[str] = Field(None, description="ISO timestamp when archived, else null")
    created_at: str = Field(..., description="When the session was created")
    updated_at: str = Field(..., description="When the session was last active")


class AgentChatSessionListResponse(BaseModel):
    """GET /me/agent/sessions response."""
    sessions: List[AgentChatSessionSummary] = Field(default_factory=list)


class AgentChatMessageItem(BaseModel):
    """One chat message in a session's history (#567)."""
    message_id: str = Field(..., description="Stable message identifier")
    role: str = Field(..., description="'user' or 'assistant'")
    text: str = Field(..., description="Message text")
    input_modality: Literal["text", "voice"] = Field(default="text")
    output_modality: Literal["text", "voice"] = Field(default="text")
    result_metadata: dict = Field(default_factory=dict, description="Structured launch/result payload, if any")
    created_at: str = Field(..., description="When the message was stored")


class AgentChatMessagesResponse(BaseModel):
    """GET /me/agent/sessions/{id}/messages response."""
    session_id: str = Field(..., description="Session whose history this is")
    messages: List[AgentChatMessageItem] = Field(default_factory=list)


class CreateAgentChatSessionRequest(BaseModel):
    """POST /me/agent/sessions body — start a fresh empty session (#568)."""
    child_id: str = Field(..., min_length=1, description="Child profile this session belongs to")
    title: Optional[str] = Field(None, max_length=60, description="Optional initial title")


class UpdateAgentChatSessionRequest(BaseModel):
    """PATCH /me/agent/sessions/{id} body — rename and/or archive (#568)."""
    title: Optional[str] = Field(None, max_length=60, description="New title; safety-checked when present")
    archived: Optional[bool] = Field(None, description="Set true to archive, false to restore")


# ---------------------------------------------------------------------------
# Content Hub — groups (#448)
# ---------------------------------------------------------------------------


class CreateGroupRequest(BaseModel):
    """POST /hub/groups body."""
    name: str = Field(..., min_length=1, max_length=80, description="Group display name")
    visibility: str = Field(..., description="public | private")
    description: Optional[str] = Field(None, max_length=500)
    theme: Optional[str] = Field(None, max_length=50, description="Optional theme tag, e.g. 'fantasy'")


class JoinByInviteRequest(BaseModel):
    """POST /hub/groups/join-by-invite body."""
    invite_token: str = Field(..., min_length=1, max_length=200)


class GroupResponse(BaseModel):
    """Group payload returned to clients.

    invite_token is intentionally Optional — it is included ONLY in the
    create-response (to the owner) or in get-by-id when the caller IS
    the group's owner. List/get responses to non-owners must scrub it.
    """
    group_id: str
    slug: str
    name: str
    description: Optional[str] = None
    theme: Optional[str] = None
    visibility: str
    invite_token: Optional[str] = None
    created_at: str
    member_count: int


class ListGroupsResponse(BaseModel):
    """GET /hub/groups response."""
    items: List[GroupResponse]
    total: int


class JoinGroupResponse(BaseModel):
    """POST /hub/groups/{id}/join response."""
    group_id: str
    role: str
    joined_at: str


# ---------------------------------------------------------------------------
# Content Hub — posts (#449)
# ---------------------------------------------------------------------------


class CreatePostRequest(BaseModel):
    """POST /hub/groups/{id}/posts body."""
    source_artifact_type: str = Field(..., description="art_story | interactive_story | kids_daily")
    source_id: str = Field(..., min_length=1, description="ID of the source story / session")
    caption: Optional[str] = Field(None, max_length=280, description="Optional caption shown above the story")


class HubPostResponse(BaseModel):
    """COPPA-safe post payload — projects ONLY hub_posts columns.

    The fields below are deliberately the persona snapshot (not a JOIN
    against users / user_agents). Adding any users-table column here
    will break the contract test in #450.
    """
    post_id: str
    group_id: str
    agent_name: str
    agent_avatar_id: str
    agent_title: str
    source_artifact_type: str
    source_id: str
    caption: Optional[str] = None
    created_at: str


class HubPostCursor(BaseModel):
    cursor_created_at: str
    cursor_post_id: str


class ListHubPostsResponse(BaseModel):
    items: List[HubPostResponse]
    next_cursor: Optional[HubPostCursor] = None


# ---------------------------------------------------------------------------
# Admin Hub moderation (#456)
# ---------------------------------------------------------------------------


class RemoveHubPostRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=200, description="Free-text moderation reason captured on hub_posts.removed_reason")


class RemoveHubPostResponse(BaseModel):
    post_id: str
    removed_at: str
    removed_reason: Optional[str] = None
    already_removed: bool = False


# ---------------------------------------------------------------------------
# Content Hub — reactions (#454)
# ---------------------------------------------------------------------------


class ReactionToggleRequest(BaseModel):
    reaction_type: str = Field(..., description="heart | star | wow")


class ReactionToggleResponse(BaseModel):
    post_id: str
    reaction_type: str
    active: bool = Field(..., description="True = was inserted; False = was removed")
    counts: Dict[str, int]
    viewer_reactions: List[str]


class HubReactionResponse(BaseModel):
    post_id: str
    counts: Dict[str, int]
    viewer_reactions: List[str]


class ReferralStatusResponse(BaseModel):
    """Referral progress and membership tier status (PRD §3.9.4)"""
    referral_code: str = Field(..., description="User's unique referral code")
    share_url: str = Field(..., description="Shareable referral link")
    qualified_count: int = Field(0, description="Verified referrals count")
    total_count: int = Field(0, description="Total referrals count")
    upgrade_threshold: int = Field(10, description="Qualified referrals needed for Plus")
    membership_tier: str = Field("free", description="Current membership tier")


class UserWithStatsResponse(UserResponse):
    """User info with content statistics"""
    story_count: int = Field(0, description="Total stories created")
    session_count: int = Field(0, description="Total interactive sessions")
    art_story_count: int = Field(0, description="Stories from image-to-story")
    interactive_count: int = Field(0, description="Interactive story sessions")
    news_count: int = Field(0, description="News-to-kids and morning show stories")


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time (seconds)")


class AuthResponse(BaseModel):
    """Authentication response (login/register)"""
    user: UserResponse = Field(..., description="User info")
    token: TokenResponse = Field(..., description="Access token")


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str = Field(..., description="Old password")
    new_password: str = Field(
        ...,
        min_length=6,
        description="New password, at least 6 characters"
    )


class UpdateProfileRequest(BaseModel):
    """Update profile request"""
    display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Display name"
    )
    avatar_url: Optional[str] = Field(
        None,
        description="Avatar URL — emoji:🐼 format or https:// URL"
    )

    @field_validator('avatar_url', mode='before')
    @classmethod
    def validate_avatar_url(cls, v: Any) -> Any:
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError('avatar_url must be a string')
        if v.startswith('https://'):
            return v
        if v.startswith('emoji:'):
            emoji_part = v[6:]
            if emoji_part and re.match(r'^[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0000200D]{1,7}$', emoji_part):
                return v
            raise ValueError('emoji: prefix must be followed by a valid emoji character')
        raise ValueError('avatar_url must be emoji:🐼 format or a valid https:// URL')


# ============================================================================
# Library API Models (#49 My Library)
# ============================================================================

class LibraryItemType(str, Enum):
    """Library content type.

    NEWS, MORNING_SHOW, and KIDS_NEWS are legacy aliases kept for API
    backward compatibility; internally they all resolve to KIDS_DAILY.
    """
    ART_STORY = "art-story"
    INTERACTIVE = "interactive"
    KIDS_DAILY = "kids-daily"
    # Legacy aliases (still accepted as query params)
    NEWS = "news"
    MORNING_SHOW = "morning-show"
    KIDS_NEWS = "kids-news"


class LibrarySortOrder(str, Enum):
    """Library sort order (#83)"""
    NEWEST = "newest"
    OLDEST = "oldest"
    WORD_COUNT = "word_count"
    FAVORITE_FIRST = "favorite_first"


class LibraryItem(BaseModel):
    """Unified library item returned by the library API."""
    id: str = Field(..., description="Item ID")
    type: LibraryItemType = Field(..., description="Content type")
    title: str = Field(..., description="Display title")
    preview: str = Field(..., description="Content preview (first ~100 chars)")
    image_url: Optional[str] = Field(None, description="Thumbnail/cover image URL")
    thumbnail_url: Optional[str] = Field(None, description="Artifact thumbnail URL (preferred over image_url)")
    audio_url: Optional[str] = Field(None, description="Audio narration URL")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    is_favorited: bool = Field(False, description="Whether user has favorited this item")
    # Art-story specific
    safety_score: Optional[float] = Field(None, description="Content safety score")
    word_count: Optional[int] = Field(None, description="Story word count")
    themes: Optional[List[str]] = Field(None, description="Story themes")
    # Interactive specific
    progress: Optional[int] = Field(None, description="Story progress percentage")
    status: Optional[str] = Field(None, description="Session status")
    # News specific
    category: Optional[str] = Field(None, description="News category")
    # Kids Daily specific
    duration_seconds: Optional[int] = Field(None, description="Episode duration in seconds")
    is_new: Optional[bool] = Field(None, description="Whether the episode is unplayed/new")


class LibraryResponse(BaseModel):
    """Paginated library response."""
    items: List[LibraryItem] = Field(..., description="Library items")
    total: int = Field(..., description="Total items matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Current offset")


class FavoriteRequest(BaseModel):
    """Add/remove favorite request."""
    item_id: str = Field(..., description="ID of the item")
    item_type: LibraryItemType = Field(..., description="Type of the item")


class FavoriteResponse(BaseModel):
    """Add favorite response."""
    status: str = Field(..., description="Result status")
    item_id: str = Field(..., description="Item ID")
    item_type: str = Field(..., description="Item type")


class LibraryStatsGroupBy(str, Enum):
    """Grouping period for library stats (#133)"""
    WEEK = "week"
    MONTH = "month"


class LibraryStatsPeriod(BaseModel):
    """A single time period with creation count (#133)."""
    period: str = Field(..., description="Period label (YYYY-Www or YYYY-MM)")
    count: int = Field(..., description="Number of creations in this period")


class LibraryStatsResponse(BaseModel):
    """Library creation stats response (#133)."""
    periods: List[LibraryStatsPeriod] = Field(..., description="Creation counts by period")


class RichStatsPeriod(BaseModel):
    """A single period with multi-dimensional growth metrics (#356)."""
    period: str = Field(..., description="Period label (YYYY-Www or YYYY-MM)")
    creation_count: int = Field(0, description="Total creations")
    total_words: int = Field(0, description="Sum of word counts from stories")
    unique_themes: int = Field(0, description="Distinct themes explored")
    completion_rate: float = Field(0.0, description="Interactive session completion rate (0-1)")
    story_type_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count per story type")


class ParentDashboardTheme(BaseModel):
    """Parent dashboard theme summary without child/user identifiers (#532)."""
    theme: str = Field(..., description="Theme label")
    count: int = Field(..., description="Number of safe creations using this theme")


class ParentDashboardRecentCreation(BaseModel):
    """Parent-safe recent creation summary (#532)."""
    id: str = Field(..., description="Creation identifier")
    type: str = Field(..., description="Library content type")
    title: str = Field(..., description="Display title")
    created_at: str = Field(..., description="Creation timestamp")
    thumbnail_url: Optional[str] = Field(None, description="Optional thumbnail URL")


class RichStatsResponse(BaseModel):
    """Rich growth dashboard stats (#356)."""
    periods: List[RichStatsPeriod] = Field(..., description="Per-period growth metrics")
    streak_days: int = Field(0, description="Deprecated compatibility field; always 0")
    top_themes: List[ParentDashboardTheme] = Field(
        default_factory=list,
        description="Parent dashboard safe theme summary",
    )
    recent_creations: List[ParentDashboardRecentCreation] = Field(
        default_factory=list,
        description="Parent dashboard recent safe creations",
    )


class PaginatedNewsResponse(BaseModel):
    """Paginated news history response (#69)."""
    items: List[Dict[str, Any]] = Field(..., description="News story items")
    total: int = Field(..., description="Total matching items")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Current offset")
