"""
API Request/Response Models

Pydantic models defining request and response formats for all API endpoints
"""

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
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
    progress: float = Field(..., ge=0.0, le=1.0, description="Completion progress 0-1")
    total_segments: int = Field(..., description="Total segments")
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
    """Kids Daily 完整节目数据"""
    episode_id: str = Field(..., description="节目唯一 ID")
    child_id: str = Field(..., description="儿童 ID")
    age_group: AgeGroup = Field(..., description="年龄组")
    category: NewsCategory = Field(..., description="话题分类")
    kid_title: str = Field(..., description="儿童友好标题")
    kid_content: str = Field(..., description="儿童友好正文")
    why_care: str = Field(..., description="为什么重要")
    key_concepts: List[KeyConceptResponse] = Field(default_factory=list, description="关键概念")
    interactive_questions: List[InteractiveQuestionResponse] = Field(default_factory=list, description="互动问题")
    dialogue_script: DialogueScript = Field(..., description="多角色对话脚本")
    illustrations: List[EpisodeIllustration] = Field(default_factory=list, description="插画列表")
    audio_urls: Dict[str, str] = Field(default_factory=dict, description="音频 URL 映射（line_index -> url）")
    story_type: Literal["kids_daily"] = Field(default="kids_daily", description="内容类型")
    duration_seconds: Optional[int] = Field(None, ge=0, description="节目总时长（秒）")
    is_played: bool = Field(default=False, description="是否已播放")
    is_new: bool = Field(default=True, description="是否新内容")
    is_degraded: bool = Field(default=False, description="是否为降级/回退生成内容")
    degraded_reason: Optional[str] = Field(None, description="降级原因")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class KidsDailyRequest(BaseModel):
    """Kids Daily 生成请求"""
    news_url: Optional[str] = Field(None, description="新闻 URL")
    news_text: Optional[str] = Field(None, description="新闻正文")
    age_group: AgeGroup = Field(..., description="年龄组")
    child_id: Optional[str] = Field(None, description="儿童 ID（可选）")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="话题分类")


class KidsDailyOnDemandRequest(BaseModel):
    """按需生成 Kids Daily 请求 (#304)"""
    child_id: str = Field(..., min_length=1, max_length=100, description="儿童 ID")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="话题分类")
    age_group: AgeGroup = Field(..., description="年龄组")


class KidsDailyRateLimitResponse(BaseModel):
    """速率限制响应 (#305)"""
    message: str = Field(..., description="友好提示消息")
    retry_after: int = Field(..., ge=0, description="距下次允许生成的秒数")


class KidsDailyGenerationMetadata(BaseModel):
    """Kids Daily 生成元数据"""
    generation_id: str = Field(..., description="生成任务 ID")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="内容安全分数")
    used_mock: bool = Field(default=False, description="是否使用 mock fallback")
    is_degraded: bool = Field(default=False, description="是否为降级/回退生成内容")
    degraded_reason: Optional[str] = Field(None, description="降级原因")
    created_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class KidsDailyResponse(BaseModel):
    """Kids Daily 生成响应"""
    episode: KidsDailyEpisode = Field(..., description="节目数据")
    metadata: KidsDailyGenerationMetadata = Field(..., description="生成元数据")


class PaginatedKidsDailyResponse(BaseModel):
    """Kids Daily 节目列表响应"""
    items: List[KidsDailyEpisode] = Field(default_factory=list, description="节目列表")
    total: int = Field(..., description="总数")
    limit: int = Field(..., description="分页大小")
    offset: int = Field(..., description="偏移量")


class TopicSubscription(BaseModel):
    """话题订阅记录"""
    child_id: str = Field(..., description="儿童 ID")
    topic: NewsCategory = Field(..., description="订阅话题")
    subscribed_at: datetime = Field(default_factory=datetime.now, description="订阅时间")
    is_active: bool = Field(default=True, description="是否有效订阅")


class SubscriptionRequest(BaseModel):
    """创建订阅请求"""
    child_id: str = Field(..., min_length=1, max_length=100, description="儿童 ID")
    topic: NewsCategory = Field(..., description="订阅话题")


class SubscriptionResponse(TopicSubscription):
    """订阅操作响应"""
    message: str = Field(default="ok", description="操作结果消息")


class SubscriptionListResponse(BaseModel):
    """订阅列表响应"""
    items: List[TopicSubscription] = Field(default_factory=list, description="订阅列表")
    total: int = Field(..., description="订阅总数")


class KidsDailyTrackEvent(str, Enum):
    """Kids Daily 播放事件类型"""
    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ABANDON = "abandon"


class KidsDailyTrackRequest(BaseModel):
    """Kids Daily 播放行为跟踪请求"""
    child_id: str = Field(..., min_length=1, max_length=100, description="儿童 ID")
    episode_id: str = Field(..., min_length=1, description="节目 ID")
    topic: NewsCategory = Field(..., description="节目话题")
    event_type: KidsDailyTrackEvent = Field(..., description="事件类型")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="播放进度 0-1")
    played_seconds: Optional[float] = Field(default=None, ge=0.0, description="已播放秒数")
    event_at: datetime = Field(default_factory=datetime.now, description="事件时间")


class KidsDailyTrackResponse(BaseModel):
    """Kids Daily 跟踪响应"""
    status: str = Field(..., description="状态")
    topic_score: float = Field(..., description="当前话题参与度分数")
    profile_updated_at: datetime = Field(default_factory=datetime.now, description="偏好更新时间")


# ============================================================================
# 错误响应 Models
# ============================================================================

class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = Field(None, description="错误字段")
    message: str = Field(..., description="错误消息")
    code: Optional[str] = Field(None, description="错误代码")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="详细错误信息"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="错误时间"
    )


# ============================================================================
# 健康检查 Models
# ============================================================================

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="API版本")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="检查时间"
    )
    services: Dict[str, Any] = Field(
        default_factory=dict,
        description="依赖服务状态"
    )


# ============================================================================
# 视频生成 API Models
# ============================================================================

class VideoJobRequest(BaseModel):
    """视频生成请求"""
    story_id: str = Field(..., description="故事ID")
    style: VideoStyle = Field(
        default=VideoStyle.GENTLE_ANIMATION,
        description="视频风格"
    )
    include_audio: bool = Field(
        default=True,
        description="是否包含音频旁白"
    )
    duration_seconds: int = Field(
        default=10,
        ge=5,
        le=30,
        description="视频时长（秒）"
    )


class VideoJobResponse(BaseModel):
    """视频生成任务响应"""
    job_id: str = Field(..., description="任务ID")
    story_id: str = Field(..., description="故事ID")
    status: VideoStatus = Field(..., description="任务状态")
    estimated_completion: Optional[datetime] = Field(
        None,
        description="预计完成时间"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )


class VideoJobStatusResponse(BaseModel):
    """视频任务状态响应"""
    job_id: str = Field(..., description="任务ID")
    status: VideoStatus = Field(..., description="任务状态")
    progress_percent: int = Field(
        default=0,
        ge=0,
        le=100,
        description="进度百分比"
    )
    video_url: Optional[str] = Field(None, description="视频URL")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


# ============================================================================
# 用户认证 API Models
# ============================================================================

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名"
    )
    email: str = Field(
        ...,
        description="邮箱地址"
    )
    password: str = Field(
        ...,
        min_length=6,
        description="密码，至少6个字符"
    )
    display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="显示名称"
    )
    referral_code: Optional[str] = Field(
        None,
        max_length=8,
        description="Referral code from share link (optional)"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("邮箱格式不正确")
        return v.lower()

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.lower()


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    username_or_email: str = Field(
        ...,
        description="用户名或邮箱"
    )
    password: str = Field(
        ...,
        description="密码"
    )


class PublicUserResponse(BaseModel):
    """Public user profile — safe for unauthenticated access"""
    user_id: str = Field(..., description="用户唯一ID")
    username: str = Field(..., description="用户名")
    display_name: Optional[str] = Field(None, description="显示名称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    created_at: datetime = Field(..., description="注册时间")


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str = Field(..., description="用户唯一ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    display_name: Optional[str] = Field(None, description="显示名称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    is_active: bool = Field(..., description="是否激活")
    is_verified: bool = Field(..., description="是否已验证")
    role: str = Field(default="child", description="User role: 'child' or 'parent'")
    created_at: datetime = Field(..., description="注册时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")


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
    """令牌响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class AuthResponse(BaseModel):
    """认证响应（登录/注册）"""
    user: UserResponse = Field(..., description="用户信息")
    token: TokenResponse = Field(..., description="访问令牌")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(
        ...,
        min_length=6,
        description="新密码，至少6个字符"
    )


class UpdateProfileRequest(BaseModel):
    """更新资料请求"""
    display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="显示名称"
    )
    avatar_url: Optional[str] = Field(
        None,
        description="头像URL — emoji:🐼 格式或 https:// URL"
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


class RichStatsResponse(BaseModel):
    """Rich growth dashboard stats (#356)."""
    periods: List[RichStatsPeriod] = Field(..., description="Per-period growth metrics")
    streak_days: int = Field(0, description="Current consecutive creation days")


class PaginatedNewsResponse(BaseModel):
    """Paginated news history response (#69)."""
    items: List[Dict[str, Any]] = Field(..., description="News story items")
    total: int = Field(..., description="Total matching items")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Current offset")
