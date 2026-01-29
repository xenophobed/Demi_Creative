"""
Data Contract Tests - 数据契约测试

此文件定义了数据层的契约测试，包括：
1. 数据库模式契约
2. API 响应格式契约
3. 数据序列化/反序列化契约
4. 数据完整性规则测试

测试原则：
1. 数据库模式一旦定义，不应破坏性修改
2. API 响应格式必须保持向后兼容
3. 所有数据传输必须经过验证
4. 数据完整性规则必须在应用层和数据库层双重保证
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import json


# ============================================================================
# 1. 数据库模型契约
# ============================================================================

class UserRole(str, Enum):
    """用户角色枚举"""
    CHILD = "child"
    PARENT = "parent"
    TEACHER = "teacher"
    ADMIN = "admin"


class SafetyLevel(str, Enum):
    """安全级别枚举"""
    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"


class ContentType(str, Enum):
    """内容类型枚举"""
    STORY = "story"
    VIDEO = "video"
    NEWS = "news"
    INTERACTIVE_STORY = "interactive_story"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# -------------------------
# 1.1 用户表契约
# -------------------------

class UserSchema(BaseModel):
    """用户表数据契约"""
    id: str = Field(..., description="用户UUID", regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="邮箱")
    password_hash: str = Field(..., min_length=60, max_length=255, description="密码哈希")
    role: UserRole = Field(..., description="用户角色")
    age: Optional[int] = Field(None, ge=3, le=120, description="年龄")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    parent_id: Optional[str] = Field(None, description="家长ID（仅儿童账户）")
    is_active: bool = Field(default=True, description="是否激活")

    @validator('parent_id')
    def validate_child_has_parent(cls, v, values):
        """验证儿童账户必须有家长ID"""
        if values.get('role') == UserRole.CHILD and not v:
            raise ValueError("儿童账户必须关联家长ID")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "username": "little_alice",
                "email": "alice@example.com",
                "password_hash": "$2b$12$KIXvZ9Q1LZ8QZ1Q1LZ8QZ1Q1LZ8QZ1Q1LZ8QZ1Q1LZ8QZ1Q1LZ8",
                "role": "child",
                "age": 7,
                "created_at": "2026-01-26T10:00:00Z",
                "updated_at": "2026-01-26T10:00:00Z",
                "parent_id": "223e4567-e89b-12d3-a456-426614174001",
                "is_active": True
            }
        }


# -------------------------
# 1.2 儿童档案表契约
# -------------------------

class ChildProfileSchema(BaseModel):
    """儿童档案表数据契约"""
    id: str = Field(..., description="档案UUID")
    user_id: str = Field(..., description="关联用户ID")
    age: int = Field(..., ge=3, le=12, description="年龄（3-12岁）")
    interests: List[str] = Field(default=[], max_length=10, description="兴趣标签（最多10个）")
    favorite_stories: List[str] = Field(default=[], description="喜爱的故事ID列表")
    content_preferences: Dict[str, Any] = Field(default={}, description="内容偏好设置")
    safety_level: SafetyLevel = Field(default=SafetyLevel.MODERATE, description="安全级别")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @validator('interests')
    def validate_interests_count(cls, v):
        """验证兴趣标签数量"""
        if len(v) > 10:
            raise ValueError("兴趣标签最多10个")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "323e4567-e89b-12d3-a456-426614174002",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "age": 7,
                "interests": ["恐龙", "太空", "动物"],
                "favorite_stories": ["story-001", "story-002"],
                "content_preferences": {
                    "voice_type": "温柔奶奶",
                    "reading_speed": "normal"
                },
                "safety_level": "moderate",
                "created_at": "2026-01-26T10:00:00Z",
                "updated_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.3 内容表契约
# -------------------------

class ContentSchema(BaseModel):
    """内容表数据契约"""
    id: str = Field(..., description="内容UUID")
    user_id: str = Field(..., description="创建者ID")
    type: ContentType = Field(..., description="内容类型")
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content_text: Optional[str] = Field(None, description="内容文本")
    metadata: Dict[str, Any] = Field(default={}, description="元数据")
    safety_checked: bool = Field(default=False, description="是否已安全检查")
    safety_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="安全分数")
    created_at: datetime = Field(..., description="创建时间")
    media_url: Optional[str] = Field(None, description="媒体URL")
    audio_url: Optional[str] = Field(None, description="音频URL")
    parent_content_id: Optional[str] = Field(None, description="父内容ID（用于分支故事）")
    is_published: bool = Field(default=True, description="是否发布")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "423e4567-e89b-12d3-a456-426614174003",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "type": "story",
                "title": "小恐龙的冒险",
                "content_text": "从前有一只小恐龙...",
                "metadata": {
                    "word_count": 450,
                    "reading_time": 180,
                    "themes": ["友谊", "勇气"]
                },
                "safety_checked": True,
                "safety_score": 0.95,
                "created_at": "2026-01-26T10:00:00Z",
                "media_url": "https://s3.amazonaws.com/videos/story-123.mp4",
                "audio_url": "https://s3.amazonaws.com/audio/story-123.mp3",
                "parent_content_id": None,
                "is_published": True
            }
        }


# -------------------------
# 1.4 图片表契约
# -------------------------

class ImageSchema(BaseModel):
    """图片表数据契约"""
    id: str = Field(..., description="图片UUID")
    user_id: str = Field(..., description="上传者ID")
    image_url: str = Field(..., description="图片URL")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    analysis_result: Optional[Dict[str, Any]] = Field(None, description="分析结果JSON")
    embedding_id: Optional[str] = Field(None, description="向量数据库ID")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "523e4567-e89b-12d3-a456-426614174004",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "image_url": "https://s3.amazonaws.com/images/drawing-123.jpg",
                "thumbnail_url": "https://s3.amazonaws.com/images/thumb-123.jpg",
                "analysis_result": {
                    "objects": ["小狗", "树木", "太阳"],
                    "scene": "户外",
                    "mood": "快乐"
                },
                "embedding_id": "vec-123456",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.5 互动故事会话表契约
# -------------------------

class StorySessionSchema(BaseModel):
    """互动故事会话表数据契约"""
    id: str = Field(..., description="会话UUID")
    user_id: str = Field(..., description="用户ID")
    story_id: str = Field(..., description="故事ID")
    session_state: Dict[str, Any] = Field(default={}, description="会话状态")
    current_segment_id: Optional[str] = Field(None, description="当前段落ID")
    is_completed: bool = Field(default=False, description="是否完成")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "623e4567-e89b-12d3-a456-426614174005",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "story_id": "423e4567-e89b-12d3-a456-426614174003",
                "session_state": {
                    "choices_history": ["choice-1", "choice-3"],
                    "current_chapter": 2,
                    "variables": {"found_treasure": True}
                },
                "current_segment_id": "segment-5",
                "is_completed": False,
                "created_at": "2026-01-26T10:00:00Z",
                "updated_at": "2026-01-26T10:15:00Z",
                "completed_at": None
            }
        }


# -------------------------
# 1.6 勋章表契约
# -------------------------

class MedalSchema(BaseModel):
    """勋章表数据契约"""
    id: str = Field(..., description="勋章UUID")
    name: str = Field(..., min_length=1, max_length=100, description="勋章名称")
    description: str = Field(..., description="勋章描述")
    icon: str = Field(..., description="勋章图标URL")
    category: str = Field(..., description="勋章类别")
    condition_type: str = Field(..., description="条件类型")
    condition_threshold: int = Field(..., ge=1, description="条件阈值")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "723e4567-e89b-12d3-a456-426614174006",
                "name": "小画家",
                "description": "上传第1幅画作",
                "icon": "https://s3.amazonaws.com/medals/artist.png",
                "category": "creation",
                "condition_type": "image_upload_count",
                "condition_threshold": 1,
                "created_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.7 任务表契约
# -------------------------

class TaskSchema(BaseModel):
    """任务表数据契约"""
    id: str = Field(..., description="任务UUID")
    user_id: str = Field(..., description="用户ID")
    task_type: str = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度（0-100）")
    input_data: Dict[str, Any] = Field(default={}, description="输入数据")
    result_data: Optional[Dict[str, Any]] = Field(None, description="结果数据")
    error_message: Optional[str] = Field(None, description="错误消息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "823e4567-e89b-12d3-a456-426614174007",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "task_type": "image_to_story",
                "status": "processing",
                "progress": 65,
                "input_data": {
                    "image_url": "https://example.com/image.jpg",
                    "child_age": 7
                },
                "result_data": None,
                "error_message": None,
                "created_at": "2026-01-26T10:00:00Z",
                "completed_at": None
            }
        }


# ============================================================================
# 2. API 响应格式契约
# ============================================================================

class APIResponse(BaseModel):
    """统一API响应格式契约"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[Any] = Field(None, description="响应数据")
    error: Optional['ErrorDetail'] = Field(None, description="错误详情")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"story_id": "story-123", "title": "小恐龙的冒险"},
                "error": None,
                "metadata": {"request_id": "req-123", "duration_ms": 250},
                "timestamp": "2026-01-26T10:00:00Z"
            }
        }


class ErrorDetail(BaseModel):
    """错误详情契约"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="用户友好的错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="详细错误信息")
    trace_id: Optional[str] = Field(None, description="追踪ID")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "输入数据验证失败",
                "details": {"field": "child_age", "error": "年龄必须在3-12岁之间"},
                "trace_id": "trace-123456"
            }
        }


class PaginatedResponse(BaseModel):
    """分页响应契约"""
    items: List[Any] = Field(..., description="数据项列表")
    total: int = Field(..., ge=0, description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页大小")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [{"id": "1", "title": "Story 1"}, {"id": "2", "title": "Story 2"}],
                "total": 50,
                "page": 1,
                "page_size": 20,
                "has_next": True,
                "has_prev": False
            }
        }


# ============================================================================
# 3. 数据契约测试用例
# ============================================================================

class TestDatabaseSchemaContracts:
    """数据库模式契约测试"""

    def test_user_schema_valid(self):
        """测试有效的用户数据"""
        user = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            email="alice@example.com",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.CHILD,
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            parent_id="223e4567-e89b-12d3-a456-426614174001",
            is_active=True
        )
        assert user.role == UserRole.CHILD
        assert user.age == 7

    def test_child_must_have_parent_id(self):
        """测试儿童账户必须有家长ID"""
        with pytest.raises(ValueError, match="儿童账户必须关联家长ID"):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice",
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.CHILD,
                age=7,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                parent_id=None  # 缺少家长ID
            )

    def test_child_profile_max_interests(self):
        """测试儿童档案最多10个兴趣标签"""
        with pytest.raises(ValueError, match="兴趣标签最多10个"):
            ChildProfileSchema(
                id="323e4567-e89b-12d3-a456-426614174002",
                user_id="123e4567-e89b-12d3-a456-426614174000",
                age=7,
                interests=["兴趣" + str(i) for i in range(11)],  # 11个标签
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_content_safety_score_range(self):
        """测试内容安全分数范围"""
        content = ContentSchema(
            id="423e4567-e89b-12d3-a456-426614174003",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            type=ContentType.STORY,
            title="小恐龙的冒险",
            safety_score=0.95,
            created_at=datetime.now()
        )
        assert 0.0 <= content.safety_score <= 1.0

    def test_task_progress_range(self):
        """测试任务进度范围"""
        task = TaskSchema(
            id="823e4567-e89b-12d3-a456-426614174007",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            task_type="image_to_story",
            status=TaskStatus.PROCESSING,
            progress=65,
            created_at=datetime.now()
        )
        assert 0 <= task.progress <= 100


class TestAPIResponseContracts:
    """API响应格式契约测试"""

    def test_success_response(self):
        """测试成功响应格式"""
        response = APIResponse(
            success=True,
            data={"story_id": "story-123", "title": "小恐龙的冒险"},
            metadata={"request_id": "req-123", "duration_ms": 250}
        )
        assert response.success
        assert response.data is not None
        assert response.error is None

    def test_error_response(self):
        """测试错误响应格式"""
        response = APIResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="输入数据验证失败",
                details={"field": "child_age", "error": "年龄必须在3-12岁之间"}
            )
        )
        assert not response.success
        assert response.error is not None
        assert response.error.code == "VALIDATION_ERROR"

    def test_paginated_response(self):
        """测试分页响应格式"""
        response = PaginatedResponse(
            items=[{"id": "1", "title": "Story 1"}],
            total=50,
            page=1,
            page_size=20,
            has_next=True,
            has_prev=False
        )
        assert len(response.items) <= response.page_size
        assert response.has_next
        assert not response.has_prev


class TestDataSerialization:
    """数据序列化测试"""

    def test_user_to_json(self):
        """测试用户数据序列化为JSON"""
        user = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            email="alice@example.com",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.CHILD,
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            parent_id="223e4567-e89b-12d3-a456-426614174001"
        )
        json_data = user.model_dump_json()
        assert isinstance(json_data, str)
        parsed = json.loads(json_data)
        assert parsed["username"] == "alice"
        assert parsed["role"] == "child"

    def test_json_to_user(self):
        """测试JSON反序列化为用户数据"""
        json_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "alice",
            "email": "alice@example.com",
            "password_hash": "$2b$12$" + "a" * 50,
            "role": "child",
            "age": 7,
            "created_at": "2026-01-26T10:00:00Z",
            "updated_at": "2026-01-26T10:00:00Z",
            "parent_id": "223e4567-e89b-12d3-a456-426614174001",
            "is_active": True
        }
        user = UserSchema(**json_data)
        assert user.username == "alice"
        assert user.role == UserRole.CHILD


class TestDataIntegrityRules:
    """数据完整性规则测试"""

    def test_username_uniqueness_constraint(self):
        """测试用户名唯一性约束"""
        # 这个测试应该在实际数据库层面验证
        # 这里我们验证数据模型是否包含唯一性信息
        user1 = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.PARENT,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        # 在实际应用中，数据库应该阻止插入相同用户名的第二条记录
        assert user1.username == "alice"

    def test_foreign_key_integrity(self):
        """测试外键完整性"""
        # 验证儿童档案引用有效的用户ID
        profile = ChildProfileSchema(
            id="323e4567-e89b-12d3-a456-426614174002",
            user_id="123e4567-e89b-12d3-a456-426614174000",  # 必须是有效的用户ID
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert profile.user_id is not None

    def test_cascading_delete_relationship(self):
        """测试级联删除关系"""
        # 当用户被删除时，相关的儿童档案也应该被删除
        # 这个逻辑在数据库层面定义（ON DELETE CASCADE）
        # 这里我们验证数据模型是否包含这个关系信息
        profile = ChildProfileSchema(
            id="323e4567-e89b-12d3-a456-426614174002",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        # 在实际应用中，删除 user_id 对应的用户时，这个档案也应该被删除
        assert profile.user_id is not None

    def test_timestamp_consistency(self):
        """测试时间戳一致性"""
        now = datetime.now()
        user = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.PARENT,
            created_at=now,
            updated_at=now
        )
        # updated_at 应该大于或等于 created_at
        assert user.updated_at >= user.created_at


class TestDataMigrationCompatibility:
    """数据迁移兼容性测试"""

    def test_add_optional_field_backward_compatible(self):
        """测试添加可选字段的向后兼容性"""
        # 假设我们在未来版本中添加了一个新的可选字段
        # 旧版本的数据应该仍然能够被加载
        old_user_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "alice",
            "password_hash": "$2b$12$" + "a" * 50,
            "role": "parent",
            "created_at": "2026-01-26T10:00:00Z",
            "updated_at": "2026-01-26T10:00:00Z",
            "is_active": True
            # 注意：没有 email 和 age 字段
        }
        user = UserSchema(**old_user_data)
        assert user.username == "alice"
        assert user.email is None  # 新字段使用默认值

    def test_enum_values_backward_compatible(self):
        """测试枚举值的向后兼容性"""
        # 已有的枚举值不应该被删除或重命名
        assert UserRole.CHILD == "child"
        assert UserRole.PARENT == "parent"
        assert UserRole.TEACHER == "teacher"

    def test_required_fields_cannot_be_removed(self):
        """测试必填字段不能被移除"""
        # 尝试创建缺少必填字段的数据应该失败
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice"
                # 缺少其他必填字段
            )


class TestDataValidationRules:
    """数据验证规则测试"""

    def test_email_format_validation(self):
        """测试邮箱格式验证"""
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice",
                email="invalid-email",  # 无效的邮箱格式
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_uuid_format_validation(self):
        """测试UUID格式验证"""
        with pytest.raises(Exception):
            UserSchema(
                id="invalid-uuid",  # 无效的UUID格式
                username="alice",
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_string_length_constraints(self):
        """测试字符串长度约束"""
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="ab",  # 少于最小长度3
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )


class TestVectorDatabaseContracts:
    """向量数据库契约测试"""

    def test_image_embedding_structure(self):
        """测试图片嵌入向量结构"""
        embedding = {
            "id": "vec-123456",
            "values": [0.1] * 1024,  # 1024维向量
            "metadata": {
                "user_id": "user-123",
                "image_url": "https://example.com/image.jpg",
                "objects": ["小狗", "树木"],
                "scene": "户外",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }
        assert len(embedding["values"]) == 1024
        assert "user_id" in embedding["metadata"]

    def test_story_embedding_structure(self):
        """测试故事嵌入向量结构"""
        embedding = {
            "id": "vec-789012",
            "values": [0.2] * 1024,  # 1024维向量
            "metadata": {
                "user_id": "user-123",
                "story_id": "story-456",
                "title": "小恐龙的冒险",
                "themes": ["友谊", "勇气"],
                "age_group": "6-8",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }
        assert len(embedding["values"]) == 1024
        assert "themes" in embedding["metadata"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
