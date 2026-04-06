"""
API Package

FastAPI 应用模块
"""

from .models import (
    # 枚举
    AgeGroup,
    VoiceType,
    StoryMode,
    SessionStatus,
    # 画作转故事
    ImageToStoryRequest,
    ImageToStoryResponse,
    StoryContent,
    EducationalValue,
    CharacterMemory,
    # 互动故事
    InteractiveStoryStartRequest,
    InteractiveStoryStartResponse,
    ChoiceRequest,
    ChoiceResponse,
    SessionStatusResponse,
    SaveInteractiveStoryResponse,
    StorySegment,
    StoryChoice,
    # Kids Daily
    NewsCategory,
    KidsDailyTextRequest,
    KidsDailyTextResponse,
    KeyConceptResponse,
    InteractiveQuestionResponse,
    DialogueLine,
    DialogueScript,
    EpisodeIllustration,
    KidsDailyEpisode,
    KidsDailyRequest,
    KidsDailyResponse,
    KidsDailyGenerationMetadata,
    PaginatedKidsDailyResponse,
    TopicSubscription,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionListResponse,
    KidsDailyTrackEvent,
    KidsDailyTrackRequest,
    KidsDailyTrackResponse,
    # 错误处理
    ErrorResponse,
    ErrorDetail,
    # 健康检查
    HealthCheckResponse,
)

__all__ = [
    # 枚举
    "AgeGroup",
    "VoiceType",
    "StoryMode",
    "SessionStatus",
    # 画作转故事
    "ImageToStoryRequest",
    "ImageToStoryResponse",
    "StoryContent",
    "EducationalValue",
    "CharacterMemory",
    # 互动故事
    "InteractiveStoryStartRequest",
    "InteractiveStoryStartResponse",
    "ChoiceRequest",
    "ChoiceResponse",
    "SessionStatusResponse",
    "SaveInteractiveStoryResponse",
    "StorySegment",
    "StoryChoice",
    # Kids Daily
    "NewsCategory",
    "KidsDailyTextRequest",
    "KidsDailyTextResponse",
    "KeyConceptResponse",
    "InteractiveQuestionResponse",
    "DialogueLine",
    "DialogueScript",
    "EpisodeIllustration",
    "KidsDailyEpisode",
    "KidsDailyRequest",
    "KidsDailyResponse",
    "KidsDailyGenerationMetadata",
    "PaginatedKidsDailyResponse",
    "TopicSubscription",
    "SubscriptionRequest",
    "SubscriptionResponse",
    "SubscriptionListResponse",
    "KidsDailyTrackEvent",
    "KidsDailyTrackRequest",
    "KidsDailyTrackResponse",
    # 错误处理
    "ErrorResponse",
    "ErrorDetail",
    # 健康检查
    "HealthCheckResponse",
]
