"""
API Request/Response Models

Pydantic 模型定义所有 API 端点的请求和响应格式
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 枚举类型
# ============================================================================

class AgeGroup(str, Enum):
    """年龄组"""
    AGE_3_5 = "3-5"
    AGE_6_8 = "6-8"
    AGE_9_12 = "9-12"


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
        description="年龄组：3-5, 6-8, 9-12"
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
    audio_url: Optional[str] = Field(None, description="语音文件URL")
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
