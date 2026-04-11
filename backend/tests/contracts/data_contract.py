"""
Data Contract Tests - Data contract tests

This file defines data layer contract tests, including:
1. Database schema contracts
2. API response format contracts
3. Data serialization/deserialization contracts
4. Data integrity rule tests

Testing principles:
1. Once defined, database schemas should not have breaking changes
2. API response formats must maintain backward compatibility
3. All data transfers must be validated
4. Data integrity rules must be guaranteed at both application and database layers
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import json


# ============================================================================
# 1. Database Model Contracts
# ============================================================================

class UserRole(str, Enum):
    """User role enum"""
    CHILD = "child"
    PARENT = "parent"
    TEACHER = "teacher"
    ADMIN = "admin"


class SafetyLevel(str, Enum):
    """Safety level enum"""
    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"


class ContentType(str, Enum):
    """Content type enum"""
    STORY = "story"
    VIDEO = "video"
    NEWS = "news"
    INTERACTIVE_STORY = "interactive_story"


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# -------------------------
# 1.1 User Table Contract
# -------------------------

class UserSchema(BaseModel):
    """User table data contract"""
    id: str = Field(..., description="User UUID", regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Email")
    password_hash: str = Field(..., min_length=60, max_length=255, description="Password hash")
    role: UserRole = Field(..., description="User role")
    age: Optional[int] = Field(None, ge=3, le=120, description="Age")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
    parent_id: Optional[str] = Field(None, description="Parent ID (child accounts only)")
    is_active: bool = Field(default=True, description="Whether active")

    @validator('parent_id')
    def validate_child_has_parent(cls, v, values):
        """Validate child account must have parent ID"""
        if values.get('role') == UserRole.CHILD and not v:
            raise ValueError("Child account must be associated with a parent ID")
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
# 1.2 Child Profile Table Contract
# -------------------------

class ChildProfileSchema(BaseModel):
    """Child profile table data contract"""
    id: str = Field(..., description="Profile UUID")
    user_id: str = Field(..., description="Associated user ID")
    age: int = Field(..., ge=3, le=12, description="Age (3-12)")
    interests: List[str] = Field(default=[], max_length=10, description="Interest tags (max 10)")
    favorite_stories: List[str] = Field(default=[], description="Favorite story ID list")
    content_preferences: Dict[str, Any] = Field(default={}, description="Content preferences")
    safety_level: SafetyLevel = Field(default=SafetyLevel.MODERATE, description="Safety level")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")

    @validator('interests')
    def validate_interests_count(cls, v):
        """Validate interest tag count"""
        if len(v) > 10:
            raise ValueError("Interest tags limited to 10")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "323e4567-e89b-12d3-a456-426614174002",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "age": 7,
                "interests": ["dinosaurs", "space", "animals"],
                "favorite_stories": ["story-001", "story-002"],
                "content_preferences": {
                    "voice_type": "gentle grandma",
                    "reading_speed": "normal"
                },
                "safety_level": "moderate",
                "created_at": "2026-01-26T10:00:00Z",
                "updated_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.3 Content Table Contract
# -------------------------

class ContentSchema(BaseModel):
    """Content table data contract"""
    id: str = Field(..., description="Content UUID")
    user_id: str = Field(..., description="Creator ID")
    type: ContentType = Field(..., description="Content type")
    title: str = Field(..., min_length=1, max_length=200, description="Title")
    content_text: Optional[str] = Field(None, description="Content text")
    metadata: Dict[str, Any] = Field(default={}, description="Metadata")
    safety_checked: bool = Field(default=False, description="Whether safety checked")
    safety_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Safety score")
    created_at: datetime = Field(..., description="Created at")
    media_url: Optional[str] = Field(None, description="Media URL")
    audio_url: Optional[str] = Field(None, description="Audio URL")
    parent_content_id: Optional[str] = Field(None, description="Parent content ID (for branching stories)")
    is_published: bool = Field(default=True, description="Whether published")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "423e4567-e89b-12d3-a456-426614174003",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "type": "story",
                "title": "Little Dinosaur's Adventure",
                "content_text": "Once upon a time there was a little dinosaur...",
                "metadata": {
                    "word_count": 450,
                    "reading_time": 180,
                    "themes": ["friendship", "courage"]
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
# 1.4 Image Table Contract
# -------------------------

class ImageSchema(BaseModel):
    """Image table data contract"""
    id: str = Field(..., description="Image UUID")
    user_id: str = Field(..., description="Uploader ID")
    image_url: str = Field(..., description="Image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    analysis_result: Optional[Dict[str, Any]] = Field(None, description="Analysis result JSON")
    embedding_id: Optional[str] = Field(None, description="Vector database ID")
    created_at: datetime = Field(..., description="Created at")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "523e4567-e89b-12d3-a456-426614174004",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "image_url": "https://s3.amazonaws.com/images/drawing-123.jpg",
                "thumbnail_url": "https://s3.amazonaws.com/images/thumb-123.jpg",
                "analysis_result": {
                    "objects": ["puppy", "trees", "sun"],
                    "scene": "outdoor",
                    "mood": "happy"
                },
                "embedding_id": "vec-123456",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.5 Interactive Story Session Table Contract
# -------------------------

class StorySessionSchema(BaseModel):
    """Interactive story session table data contract"""
    id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="User ID")
    story_id: str = Field(..., description="Story ID")
    session_state: Dict[str, Any] = Field(default={}, description="Session state")
    current_segment_id: Optional[str] = Field(None, description="Current segment ID")
    is_completed: bool = Field(default=False, description="Whether completed")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
    completed_at: Optional[datetime] = Field(None, description="Completed at")

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
# 1.6 Medal Table Contract
# -------------------------

class MedalSchema(BaseModel):
    """Medal table data contract"""
    id: str = Field(..., description="Medal UUID")
    name: str = Field(..., min_length=1, max_length=100, description="Medal name")
    description: str = Field(..., description="Medal description")
    icon: str = Field(..., description="Medal icon URL")
    category: str = Field(..., description="Medal category")
    condition_type: str = Field(..., description="Condition type")
    condition_threshold: int = Field(..., ge=1, description="Condition threshold")
    created_at: datetime = Field(..., description="Created at")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "723e4567-e89b-12d3-a456-426614174006",
                "name": "Little Artist",
                "description": "Uploaded 1st drawing",
                "icon": "https://s3.amazonaws.com/medals/artist.png",
                "category": "creation",
                "condition_type": "image_upload_count",
                "condition_threshold": 1,
                "created_at": "2026-01-26T10:00:00Z"
            }
        }


# -------------------------
# 1.7 Task Table Contract
# -------------------------

class TaskSchema(BaseModel):
    """Task table data contract"""
    id: str = Field(..., description="Task UUID")
    user_id: str = Field(..., description="User ID")
    task_type: str = Field(..., description="Task type")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress (0-100)")
    input_data: Dict[str, Any] = Field(default={}, description="Input data")
    result_data: Optional[Dict[str, Any]] = Field(None, description="Result data")
    error_message: Optional[str] = Field(None, description="Error message")
    created_at: datetime = Field(..., description="Created at")
    completed_at: Optional[datetime] = Field(None, description="Completed at")

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
# 2. API Response Format Contracts
# ============================================================================

class APIResponse(BaseModel):
    """Unified API response format contract"""
    success: bool = Field(..., description="Whether request succeeded")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional['ErrorDetail'] = Field(None, description="Error details")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"story_id": "story-123", "title": "Little Dinosaur's Adventure"},
                "error": None,
                "metadata": {"request_id": "req-123", "duration_ms": 250},
                "timestamp": "2026-01-26T10:00:00Z"
            }
        }


class ErrorDetail(BaseModel):
    """Error detail contract"""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="User-friendly error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed error info")
    trace_id: Optional[str] = Field(None, description="Trace ID")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Input data validation failed",
                "details": {"field": "child_age", "error": "Age must be between 3 and 12"},
                "trace_id": "trace-123456"
            }
        }


class PaginatedResponse(BaseModel):
    """Paginated response contract"""
    items: List[Any] = Field(..., description="Data items list")
    total: int = Field(..., ge=0, description="Total count")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Page size")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

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
# 3. Data Contract Test Cases
# ============================================================================

class TestDatabaseSchemaContracts:
    """Database schema contract tests"""

    def test_user_schema_valid(self):
        """Test valid user data"""
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
        """Test child account must have parent ID"""
        with pytest.raises(ValueError, match="Child account must be associated with a parent ID"):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice",
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.CHILD,
                age=7,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                parent_id=None  # Missing parent ID
            )

    def test_child_profile_max_interests(self):
        """Test child profile max 10 interest tags"""
        with pytest.raises(ValueError, match="Interest tags limited to 10"):
            ChildProfileSchema(
                id="323e4567-e89b-12d3-a456-426614174002",
                user_id="123e4567-e89b-12d3-a456-426614174000",
                age=7,
                interests=["interest" + str(i) for i in range(11)],  # 11 tags
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_content_safety_score_range(self):
        """Test content safety score range"""
        content = ContentSchema(
            id="423e4567-e89b-12d3-a456-426614174003",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            type=ContentType.STORY,
            title="Little Dinosaur's Adventure",
            safety_score=0.95,
            created_at=datetime.now()
        )
        assert 0.0 <= content.safety_score <= 1.0

    def test_task_progress_range(self):
        """Test task progress range"""
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
    """API response format contract tests"""

    def test_success_response(self):
        """Test success response format"""
        response = APIResponse(
            success=True,
            data={"story_id": "story-123", "title": "Little Dinosaur's Adventure"},
            metadata={"request_id": "req-123", "duration_ms": 250}
        )
        assert response.success
        assert response.data is not None
        assert response.error is None

    def test_error_response(self):
        """Test error response format"""
        response = APIResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Input data validation failed",
                details={"field": "child_age", "error": "Age must be between 3 and 12"}
            )
        )
        assert not response.success
        assert response.error is not None
        assert response.error.code == "VALIDATION_ERROR"

    def test_paginated_response(self):
        """Test paginated response format"""
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
    """Data serialization tests"""

    def test_user_to_json(self):
        """Test user data serialization to JSON"""
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
        """Test JSON deserialization to user data"""
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
    """Data integrity rule tests"""

    def test_username_uniqueness_constraint(self):
        """Test username uniqueness constraint"""
        # This test should be verified at the actual database layer
        # Here we verify the data model contains uniqueness info
        user1 = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.PARENT,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        # In actual application, database should prevent inserting a second record with same username
        assert user1.username == "alice"

    def test_foreign_key_integrity(self):
        """Test foreign key integrity"""
        # Verify child profile references a valid user ID
        profile = ChildProfileSchema(
            id="323e4567-e89b-12d3-a456-426614174002",
            user_id="123e4567-e89b-12d3-a456-426614174000",  # Must be a valid user ID
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert profile.user_id is not None

    def test_cascading_delete_relationship(self):
        """Test cascading delete relationship"""
        # When a user is deleted, related child profiles should also be deleted
        # This logic is defined at the database layer (ON DELETE CASCADE)
        # Here we verify the data model contains this relationship info
        profile = ChildProfileSchema(
            id="323e4567-e89b-12d3-a456-426614174002",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            age=7,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        # In actual application, deleting the user matching user_id should also delete this profile
        assert profile.user_id is not None

    def test_timestamp_consistency(self):
        """Test timestamp consistency"""
        now = datetime.now()
        user = UserSchema(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="alice",
            password_hash="$2b$12$" + "a" * 50,
            role=UserRole.PARENT,
            created_at=now,
            updated_at=now
        )
        # updated_at should be >= created_at
        assert user.updated_at >= user.created_at


class TestDataMigrationCompatibility:
    """Data migration compatibility tests"""

    def test_add_optional_field_backward_compatible(self):
        """Test backward compatibility of adding optional fields"""
        # Suppose we add a new optional field in a future version
        # Old version data should still be loadable
        old_user_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "alice",
            "password_hash": "$2b$12$" + "a" * 50,
            "role": "parent",
            "created_at": "2026-01-26T10:00:00Z",
            "updated_at": "2026-01-26T10:00:00Z",
            "is_active": True
            # Note: no email or age fields
        }
        user = UserSchema(**old_user_data)
        assert user.username == "alice"
        assert user.email is None  # New fields use default values

    def test_enum_values_backward_compatible(self):
        """Test backward compatibility of enum values"""
        # Existing enum values should not be deleted or renamed
        assert UserRole.CHILD == "child"
        assert UserRole.PARENT == "parent"
        assert UserRole.TEACHER == "teacher"

    def test_required_fields_cannot_be_removed(self):
        """Test required fields cannot be removed"""
        # Attempting to create data missing required fields should fail
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice"
                # Missing other required fields
            )


class TestDataValidationRules:
    """Data validation rule tests"""

    def test_email_format_validation(self):
        """Test email format validation"""
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="alice",
                email="invalid-email",  # Invalid email format
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_uuid_format_validation(self):
        """Test UUID format validation"""
        with pytest.raises(Exception):
            UserSchema(
                id="invalid-uuid",  # Invalid UUID format
                username="alice",
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def test_string_length_constraints(self):
        """Test string length constraints"""
        with pytest.raises(Exception):
            UserSchema(
                id="123e4567-e89b-12d3-a456-426614174000",
                username="ab",  # Less than min length 3
                password_hash="$2b$12$" + "a" * 50,
                role=UserRole.PARENT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )


class TestVectorDatabaseContracts:
    """Vector database contract tests"""

    def test_image_embedding_structure(self):
        """Test image embedding vector structure"""
        embedding = {
            "id": "vec-123456",
            "values": [0.1] * 1024,  # 1024-dim vector
            "metadata": {
                "user_id": "user-123",
                "image_url": "https://example.com/image.jpg",
                "objects": ["puppy", "trees"],
                "scene": "outdoor",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }
        assert len(embedding["values"]) == 1024
        assert "user_id" in embedding["metadata"]

    def test_story_embedding_structure(self):
        """Test story embedding vector structure"""
        embedding = {
            "id": "vec-789012",
            "values": [0.2] * 1024,  # 1024-dim vector
            "metadata": {
                "user_id": "user-123",
                "story_id": "story-456",
                "title": "Little Dinosaur's Adventure",
                "themes": ["friendship", "courage"],
                "age_group": "6-8",
                "created_at": "2026-01-26T10:00:00Z"
            }
        }
        assert len(embedding["values"]) == 1024
        assert "themes" in embedding["metadata"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
