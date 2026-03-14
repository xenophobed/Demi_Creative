"""
API Request/Response Models

Pydantic 模型定义所有 API 端点的请求和响应格式
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# 枚举类型
# ============================================================================

class AgeGroup(str, Enum):
    """年龄组 (PRD §2.1 canonical: 3-5, 6-8, 9-12)"""
    AGE_3_5 = "3-5"
    AGE_6_8 = "6-8"
    AGE_9_12 = "9-12"


class TTSProviderEnum(str, Enum):
    """TTS provider selection (#149)"""
    OPENAI = "openai"
    REPLICATE = "replicate"


class EmotionType(str, Enum):
    """Allowed TTS emotions (#149). Age-filtered at service layer."""
    HAPPY = "happy"
    SAD = "sad"
    NEUTRAL = "neutral"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"


class VoiceType(str, Enum):
    """语音类型"""
    NOVA = "nova"           # 温柔女性
    SHIMMER = "shimmer"     # 活泼女性
    ALLOY = "alloy"         # 中性
    ECHO = "echo"           # 男性
    FABLE = "fable"         # 故事讲述者
    ONYX = "onyx"           # 深沉男性


class StoryMode(str, Enum):
    """故事模式"""
    LINEAR = "linear"           # 线性故事
    INTERACTIVE = "interactive" # 互动故事


class SessionStatus(str, Enum):
    """会话状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class VideoStyle(str, Enum):
    """视频风格"""
    GENTLE_ANIMATION = "gentle_animation"  # 温和动画，通用儿童友好风格
    PLAYFUL = "playful"                    # 活泼风格
    STORYBOOK = "storybook"                # 绘本风格


class VideoStatus(str, Enum):
    """视频生成状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NewsCategory(str, Enum):
    """新闻分类"""
    SCIENCE = "science"
    NATURE = "nature"
    TECHNOLOGY = "technology"
    SPACE = "space"
    ANIMALS = "animals"
    SPORTS = "sports"
    CULTURE = "culture"
    GENERAL = "general"


# ============================================================================
# 画作转故事 API Models
# ============================================================================

class ImageToStoryRequest(BaseModel):
    """画作转故事请求"""
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="儿童唯一标识符"
    )
    age_group: AgeGroup = Field(
        ...,
        description="年龄组：3-5, 6-9, 10-12"
    )
    interests: Optional[List[str]] = Field(
        default=None,
        max_length=5,
        description="兴趣标签，最多5个"
    )
    voice: VoiceType = Field(
        default=VoiceType.NOVA,
        description="语音类型"
    )
    enable_audio: bool = Field(
        default=True,
        description="是否生成语音"
    )

    @field_validator('interests')
    @classmethod
    def validate_interests(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("最多只能有5个兴趣标签")
        return v


class StoryContent(BaseModel):
    """故事内容"""
    text: str = Field(..., description="故事文本")
    word_count: int = Field(..., description="字数")
    age_adapted: bool = Field(..., description="是否经过年龄适配")


class EducationalValue(BaseModel):
    """教育价值"""
    themes: List[str] = Field(..., description="主题（如：友谊、勇气）")
    concepts: List[str] = Field(..., description="概念（如：颜色、数字）")
    moral: Optional[str] = Field(None, description="道德寓意")


class CharacterMemory(BaseModel):
    """角色记忆"""
    character_name: str = Field(..., description="角色名称")
    description: str = Field(..., description="角色描述")
    appearances: int = Field(..., description="出现次数")


class ImageToStoryResponse(BaseModel):
    """画作转故事响应"""
    story_id: str = Field(..., description="故事唯一ID")
    story: StoryContent = Field(..., description="故事内容")
    image_url: Optional[str] = Field(None, description="画作图片URL")
    audio_url: Optional[str] = Field(None, description="语音文件URL")
    video_url: Optional[str] = Field(None, description="视频文件URL")
    video_job_id: Optional[str] = Field(None, description="视频生成任务ID")
    educational_value: EducationalValue = Field(..., description="教育价值")
    characters: List[CharacterMemory] = Field(
        default_factory=list,
        description="识别到的角色"
    )
    analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="画作分析结果"
    )
    safety_score: float = Field(..., ge=0.0, le=1.0, description="安全评分")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )


# ============================================================================
# 互动故事 API Models
# ============================================================================

class InteractiveStoryStartRequest(BaseModel):
    """开始互动故事请求"""
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="儿童唯一标识符"
    )
    age_group: AgeGroup = Field(..., description="年龄组")
    interests: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="兴趣标签，1-5个"
    )
    theme: Optional[str] = Field(
        None,
        description="故事主题（可选）"
    )
    voice: VoiceType = Field(
        default=VoiceType.FABLE,
        description="语音类型"
    )
    enable_audio: bool = Field(
        default=True,
        description="是否生成语音"
    )

    @field_validator('interests')
    @classmethod
    def validate_interests(cls, v):
        if len(v) < 1 or len(v) > 5:
            raise ValueError("兴趣标签数量必须在1-5之间")
        return v


class StoryChoice(BaseModel):
    """故事选项"""
    choice_id: str = Field(..., description="选项ID")
    text: str = Field(..., description="选项文本")
    emoji: str = Field(..., description="选项图标")


class StorySegment(BaseModel):
    """故事段落"""
    segment_id: int = Field(..., description="段落序号")
    text: str = Field(..., description="段落文本")
    audio_url: Optional[str] = Field(None, description="语音URL")
    choices: List[StoryChoice] = Field(
        default_factory=list,
        description="可选择的分支"
    )
    is_ending: bool = Field(
        default=False,
        description="是否为结局"
    )
    # Optional content support for age-based behavior
    primary_mode: str = Field(
        default="both",
        description="主要内容模式: 'audio' | 'text' | 'both'"
    )
    optional_content_available: bool = Field(
        default=False,
        description="是否有可选内容按钮"
    )
    optional_content_type: Optional[str] = Field(
        None,
        description="可选内容类型: 'text' (3-5岁显示文字) | 'audio' (10-12岁播放语音)"
    )


class InteractiveStoryStartResponse(BaseModel):
    """开始互动故事响应"""
    session_id: str = Field(..., description="会话ID")
    story_title: str = Field(..., description="故事标题")
    opening: StorySegment = Field(..., description="开场段落")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )


class ChoiceRequest(BaseModel):
    """选择分支请求"""
    choice_id: str = Field(..., description="选择的选项ID")


class ChoiceResponse(BaseModel):
    """选择分支响应"""
    session_id: str = Field(..., description="会话ID")
    next_segment: StorySegment = Field(..., description="下一段落")
    choice_history: List[str] = Field(..., description="选择历史")
    progress: float = Field(..., ge=0.0, le=1.0, description="进度（0-1）")


class SessionStatusResponse(BaseModel):
    """会话状态响应"""
    session_id: str = Field(..., description="会话ID")
    status: SessionStatus = Field(..., description="会话状态")
    child_id: str = Field(..., description="儿童ID")
    story_title: str = Field(..., description="故事标题")
    current_segment: int = Field(..., description="当前段落序号")
    total_segments: int = Field(..., description="总段落数")
    choice_history: List[str] = Field(..., description="选择历史")
    educational_summary: Optional[EducationalValue] = Field(
        None,
        description="教育总结（完成后）"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    expires_at: datetime = Field(..., description="过期时间")


class SessionResumeResponse(BaseModel):
    """Resume an in-progress interactive story session."""
    session_id: str = Field(..., description="会话ID")
    status: SessionStatus = Field(..., description="会话状态")
    story_title: str = Field(..., description="故事标题")
    age_group: AgeGroup = Field(..., description="年龄组")
    segments: List[StorySegment] = Field(..., description="所有已生成段落")
    choice_history: List[str] = Field(..., description="选择历史")
    progress: float = Field(..., ge=0.0, le=1.0, description="完成进度 0-1")
    total_segments: int = Field(..., description="总段落数")
    educational_summary: Optional[EducationalValue] = Field(None, description="教育总结")


class SaveInteractiveStoryResponse(BaseModel):
    """保存互动故事响应"""
    story_id: str = Field(..., description="保存后的故事ID")
    session_id: str = Field(..., description="互动会话ID")
    message: str = Field(..., description="操作结果消息")


class KeyConceptResponse(BaseModel):
    """新闻关键概念"""
    term: str = Field(..., description="概念词")
    explanation: str = Field(..., description="儿童友好解释")
    emoji: str = Field(default="💡", description="概念图标")


class InteractiveQuestionResponse(BaseModel):
    """互动提问"""
    question: str = Field(..., description="问题")
    hint: Optional[str] = Field(None, description="提示")
    emoji: str = Field(default="🤔", description="问题图标")


class NewsToKidsRequest(BaseModel):
    """新闻转儿童内容请求"""
    child_id: str = Field(..., min_length=1, max_length=100, description="儿童唯一标识符")
    age_group: AgeGroup = Field(..., description="年龄组")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="新闻分类")
    news_url: Optional[str] = Field(None, description="新闻URL")
    news_text: Optional[str] = Field(None, description="新闻原文")
    enable_audio: bool = Field(default=True, description="是否生成音频")
    voice: Optional[VoiceType] = Field(default=VoiceType.FABLE, description="语音类型")


class NewsToKidsResponse(BaseModel):
    """新闻转儿童内容响应"""
    conversion_id: str = Field(..., description="转换ID")
    kid_title: str = Field(..., description="儿童版标题")
    kid_content: str = Field(..., description="儿童版正文")
    why_care: str = Field(..., description="为什么重要")
    key_concepts: List[KeyConceptResponse] = Field(default_factory=list, description="关键概念")
    interactive_questions: List[InteractiveQuestionResponse] = Field(default_factory=list, description="互动问题")
    category: NewsCategory = Field(..., description="新闻分类")
    age_group: AgeGroup = Field(..., description="年龄组")
    audio_url: Optional[str] = Field(None, description="音频URL")
    original_url: Optional[str] = Field(None, description="原始新闻URL")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


# ============================================================================
# Morning Show API Models (#44)
# ============================================================================

ALLOWED_DIALOGUE_ROLES = {"curious_kid", "fun_expert", "guest"}
ALLOWED_ANIMATION_TYPES = {"pan", "zoom", "ken_burns"}


class DialogueLine(BaseModel):
    """Morning Show 对话行"""
    role: str = Field(..., description="角色: curious_kid | fun_expert | guest")
    text: str = Field(..., min_length=1, description="对话内容")
    timestamp_start: float = Field(..., ge=0.0, description="开始时间（秒）")
    timestamp_end: float = Field(..., ge=0.0, description="结束时间（秒）")

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
    """Morning Show 对话脚本"""
    lines: List[DialogueLine] = Field(default_factory=list, description="对话行列表")
    total_duration: float = Field(..., ge=0.0, description="总时长（秒）")
    guest_character: Optional[str] = Field(None, description="嘉宾角色名（可选）")

    @model_validator(mode="after")
    def validate_total_duration(self):
        if self.lines:
            latest_end = max(line.timestamp_end for line in self.lines)
            if self.total_duration < latest_end:
                raise ValueError("total_duration must cover the final line timestamp")
        return self


class EpisodeIllustration(BaseModel):
    """Morning Show 插画元数据"""
    url: str = Field(..., min_length=1, description="插画 URL")
    description: str = Field(..., min_length=1, description="插画描述")
    display_order: int = Field(..., ge=0, description="显示顺序")
    animation_type: str = Field(..., description="动画类型: pan | zoom | ken_burns")

    @field_validator("animation_type")
    @classmethod
    def validate_animation_type(cls, value: str) -> str:
        if value not in ALLOWED_ANIMATION_TYPES:
            raise ValueError("animation_type must be one of pan | zoom | ken_burns")
        return value


class MorningShowEpisode(BaseModel):
    """Morning Show 完整节目数据"""
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
    story_type: Literal["morning_show"] = Field(default="morning_show", description="内容类型")
    duration_seconds: Optional[int] = Field(None, ge=0, description="节目总时长（秒）")
    is_played: bool = Field(default=False, description="是否已播放")
    is_new: bool = Field(default=True, description="是否新内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class MorningShowRequest(BaseModel):
    """Morning Show 生成请求"""
    news_url: Optional[str] = Field(None, description="新闻 URL")
    news_text: Optional[str] = Field(None, description="新闻正文")
    age_group: AgeGroup = Field(..., description="年龄组")
    child_id: Optional[str] = Field(None, description="儿童 ID（可选）")
    category: NewsCategory = Field(default=NewsCategory.GENERAL, description="话题分类")


class MorningShowGenerationMetadata(BaseModel):
    """Morning Show 生成元数据"""
    generation_id: str = Field(..., description="生成任务 ID")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="内容安全分数")
    used_mock: bool = Field(default=False, description="是否使用 mock fallback")
    created_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class MorningShowResponse(BaseModel):
    """Morning Show 生成响应"""
    episode: MorningShowEpisode = Field(..., description="节目数据")
    metadata: MorningShowGenerationMetadata = Field(..., description="生成元数据")


class PaginatedMorningShowResponse(BaseModel):
    """Morning Show 节目列表响应"""
    items: List[MorningShowEpisode] = Field(default_factory=list, description="节目列表")
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


class MorningShowTrackEvent(str, Enum):
    """Morning Show 播放事件类型"""
    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ABANDON = "abandon"


class MorningShowTrackRequest(BaseModel):
    """Morning Show 播放行为跟踪请求"""
    child_id: str = Field(..., min_length=1, max_length=100, description="儿童 ID")
    episode_id: str = Field(..., min_length=1, description="节目 ID")
    topic: NewsCategory = Field(..., description="节目话题")
    event_type: MorningShowTrackEvent = Field(..., description="事件类型")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="播放进度 0-1")
    played_seconds: Optional[float] = Field(default=None, ge=0.0, description="已播放秒数")
    event_at: datetime = Field(default_factory=datetime.now, description="事件时间")


class MorningShowTrackResponse(BaseModel):
    """Morning Show 跟踪响应"""
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
    services: Dict[str, str] = Field(
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


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str = Field(..., description="用户唯一ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    display_name: Optional[str] = Field(None, description="显示名称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    is_active: bool = Field(..., description="是否激活")
    is_verified: bool = Field(..., description="是否已验证")
    created_at: datetime = Field(..., description="注册时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")


class UserWithStatsResponse(UserResponse):
    """User info with content statistics"""
    story_count: int = Field(0, description="Total stories created")
    session_count: int = Field(0, description="Total interactive sessions")


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
        description="头像URL"
    )


# ============================================================================
# Library API Models (#49 My Library)
# ============================================================================

class LibraryItemType(str, Enum):
    """Library content type"""
    ART_STORY = "art-story"
    INTERACTIVE = "interactive"
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
    # Morning Show specific
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


class PaginatedNewsResponse(BaseModel):
    """Paginated news history response (#69)."""
    items: List[Dict[str, Any]] = Field(..., description="News story items")
    total: int = Field(..., description="Total matching items")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Current offset")
