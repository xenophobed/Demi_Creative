"""
Artifact System Pydantic v2 Models

Defines the data contracts for the artifact graph system.
Uses Pydantic v2 for validation, serialization, and OpenAPI documentation.

Design Principles:
- All IDs are opaque UUID strings at API boundaries
- Timestamps are ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- Enums use lowercase string values
- All models are immutable by default (except for state transition models)
- Flexible metadata for different artifact types
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# Enumerations
# ============================================================================

class LifecycleState(str, Enum):
    """Artifact lifecycle states"""
    INTERMEDIATE = "intermediate"
    CANDIDATE = "candidate"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArtifactType(str, Enum):
    """Types of artifacts"""
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    JSON = "json"


class RelationType(str, Enum):
    """Artifact relation types"""
    DERIVED_FROM = "derived_from"
    VARIANT_OF = "variant_of"
    TRANSCODED_FROM = "transcoded_from"


class StoryArtifactRole(str, Enum):
    """Story canonical artifact roles"""
    COVER = "cover"
    FINAL_AUDIO = "final_audio"
    FINAL_VIDEO = "final_video"
    SCENE_IMAGE = "scene_image"


class RunStatus(str, Enum):
    """Run execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowType(str, Enum):
    """Run workflow types"""
    IMAGE_TO_STORY = "image_to_story"
    INTERACTIVE_STORY = "interactive_story"
    NEWS_TO_KIDS = "news_to_kids"


class AgentStepStatus(str, Enum):
    """Agent step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunArtifactStage(str, Enum):
    """Run artifact generation stages"""
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FAILED = "failed"


# ============================================================================
# Metadata Models
# ============================================================================

class ArtifactMetadata(BaseModel):
    """
    Flexible metadata for different artifact types.
    All fields optional to support various artifact types.
    """
    # Audio/Video metadata
    duration: Optional[int] = Field(None, description="Duration in seconds")
    codec: Optional[str] = Field(None, description="Media codec (mp3, h264, etc)")
    channels: Optional[int] = Field(None, description="Audio channels")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate (Hz)")

    # Image/Video metadata
    dimensions: Optional[Dict[str, int]] = Field(
        None, description="Dimensions: {width, height}"
    )
    format: Optional[str] = Field(None, description="File format (png, jpg, mp4, etc)")

    # File metadata
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")

    # Text metadata
    char_count: Optional[int] = Field(None, description="Character count")
    word_count: Optional[int] = Field(None, description="Word count")

    # Custom metadata
    custom: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "duration": 120,
                "codec": "mp3",
                "channels": 2,
                "file_size": 1024000
            }
        }


# ============================================================================
# Core Artifact Models
# ============================================================================

class Artifact(BaseModel):
    """
    Immutable artifact entity.

    Once created, artifact_id and created_at never change.
    Updates create new artifacts with new artifact_id.
    """
    artifact_id: str = Field(..., description="Unique UUID identifier")
    artifact_type: ArtifactType = Field(..., description="Type of artifact")
    lifecycle_state: LifecycleState = Field(
        default=LifecycleState.INTERMEDIATE,
        description="Lifecycle state"
    )
    content_hash: Optional[str] = Field(
        None, description="SHA256 hash of content for dedup"
    )
    artifact_path: Optional[str] = Field(
        None, description="Local file system path"
    )
    artifact_url: Optional[str] = Field(
        None, description="CDN/cloud storage URL"
    )
    artifact_payload: Optional[str] = Field(
        None, description="Inline JSON/text payload (for small artifacts)"
    )
    metadata: Optional[ArtifactMetadata] = Field(
        None, description="Type-specific metadata"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description"
    )
    created_by_step_id: Optional[str] = Field(
        None, description="Agent step that created this artifact"
    )
    created_at: datetime = Field(..., description="Immutable creation timestamp")
    stored_at: datetime = Field(..., description="Storage update timestamp")

    class Config:
        """Pydantic config"""
        frozen = False  # Allow setting fields during creation
        json_schema_extra = {
            "example": {
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "artifact_type": "audio",
                "lifecycle_state": "intermediate",
                "artifact_path": "./data/audio/story_abc123.mp3",
                "artifact_url": "https://cdn.example.com/audio/story_abc123.mp3",
                "metadata": {"duration": 120, "codec": "mp3"},
                "description": "Story narration",
                "created_at": "2026-02-23T10:00:00Z",
                "stored_at": "2026-02-23T10:00:00Z"
            }
        }

    @validator("created_at", "stored_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class ArtifactCreate(BaseModel):
    """
    Input model for creating artifacts.
    Excludes artifact_id, created_at, stored_at (auto-generated).
    """
    artifact_type: ArtifactType
    artifact_path: Optional[str] = None
    artifact_url: Optional[str] = None
    artifact_payload: Optional[str] = None
    metadata: Optional[ArtifactMetadata] = None
    description: Optional[str] = None
    created_by_step_id: Optional[str] = None

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "artifact_type": "audio",
                "artifact_path": "./data/audio/story_abc123.mp3",
                "metadata": {"duration": 120},
                "description": "Story narration"
            }
        }


class ArtifactUpdateState(BaseModel):
    """
    Input model for updating artifact lifecycle state.
    Only allows state transitions, not content changes.
    """
    new_state: LifecycleState = Field(..., description="New lifecycle state")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {"new_state": "published"}
        }


# ============================================================================
# Artifact Relation Models
# ============================================================================

class ArtifactRelation(BaseModel):
    """
    Directed edge in artifact lineage graph.
    Immutable once created (INSERT-only).
    """
    relation_id: str = Field(..., description="Unique UUID identifier")
    from_artifact_id: str = Field(..., description="Source artifact UUID")
    to_artifact_id: str = Field(..., description="Target artifact UUID")
    relation_type: RelationType = Field(..., description="Relation type")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Relation metadata (confidence, algorithm, etc)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    @validator("created_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @validator("from_artifact_id", "to_artifact_id")
    def validate_different_artifacts(cls, v, values):
        """Prevent self-references"""
        if "from_artifact_id" in values and v == values["from_artifact_id"]:
            raise ValueError("Cannot create relation from artifact to itself")
        return v

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "relation_id": "550e8400-e29b-41d4-a716-446655440001",
                "from_artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "to_artifact_id": "550e8400-e29b-41d4-a716-446655440002",
                "relation_type": "derived_from",
                "created_at": "2026-02-23T10:00:00Z"
            }
        }


class ArtifactRelationCreate(BaseModel):
    """
    Input model for creating artifact relations.
    Excludes relation_id and created_at (auto-generated).
    """
    from_artifact_id: str
    to_artifact_id: str
    relation_type: RelationType
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "from_artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "to_artifact_id": "550e8400-e29b-41d4-a716-446655440002",
                "relation_type": "derived_from"
            }
        }


# ============================================================================
# Story Artifact Link Models
# ============================================================================

class StoryArtifactLink(BaseModel):
    """
    Maps artifacts to stories with canonical roles.
    Enforces one primary artifact per story+role.
    """
    link_id: str = Field(..., description="Unique UUID identifier")
    story_id: str = Field(..., description="Story UUID")
    artifact_id: str = Field(..., description="Artifact UUID")
    role: StoryArtifactRole = Field(..., description="Canonical role")
    is_primary: bool = Field(default=True, description="Is primary for this role")
    position: Optional[int] = Field(
        None, description="Position (for scene_image ordering)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @validator("created_at", "updated_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "link_id": "550e8400-e29b-41d4-a716-446655440003",
                "story_id": "story-uuid-1",
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "final_audio",
                "is_primary": True,
                "created_at": "2026-02-23T10:00:00Z",
                "updated_at": "2026-02-23T10:00:00Z"
            }
        }


class StoryArtifactLinkCreate(BaseModel):
    """
    Input model for creating story-artifact links.
    """
    story_id: str
    artifact_id: str
    role: StoryArtifactRole
    is_primary: bool = True
    position: Optional[int] = None

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "story_id": "story-uuid-1",
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "final_audio",
                "is_primary": True
            }
        }


# ============================================================================
# Run and Agent Step Models
# ============================================================================

class Run(BaseModel):
    """
    Execution workflow for multi-agent generation.
    Tracks a generation run (image→story, branching narrative, etc).
    """
    run_id: str = Field(..., description="Unique UUID identifier")
    story_id: str = Field(..., description="Story UUID")
    session_id: Optional[str] = Field(
        None, description="Session UUID (for interactive stories)"
    )
    workflow_type: WorkflowType = Field(..., description="Workflow type")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Execution status")
    result_summary: Optional[Dict[str, Any]] = Field(
        None, description="Execution summary (counts, messages, etc)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    @validator("created_at", "started_at", "completed_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if v is None:
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440004",
                "story_id": "story-uuid-1",
                "workflow_type": "image_to_story",
                "status": "pending",
                "created_at": "2026-02-23T10:00:00Z"
            }
        }


class RunCreate(BaseModel):
    """
    Input model for creating runs.
    """
    story_id: str
    session_id: Optional[str] = None
    workflow_type: WorkflowType

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "story_id": "story-uuid-1",
                "workflow_type": "image_to_story"
            }
        }


class AgentStep(BaseModel):
    """
    Unit of work within a run.
    Represents a single step in agent orchestration (e.g., vision_analysis, safety_check).
    """
    agent_step_id: str = Field(..., description="Unique UUID identifier")
    run_id: str = Field(..., description="Parent run UUID")
    step_name: str = Field(..., description="Step name (vision_analysis, etc)")
    step_order: int = Field(..., description="Execution order within run")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Step input (JSON)")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Step output (JSON)")
    status: AgentStepStatus = Field(
        default=AgentStepStatus.PENDING, description="Execution status"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    @validator("created_at", "completed_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if v is None:
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "agent_step_id": "550e8400-e29b-41d4-a716-446655440005",
                "run_id": "550e8400-e29b-41d4-a716-446655440004",
                "step_name": "vision_analysis",
                "step_order": 1,
                "status": "pending",
                "created_at": "2026-02-23T10:00:00Z"
            }
        }


class AgentStepCreate(BaseModel):
    """
    Input model for creating agent steps.
    """
    run_id: str
    step_name: str
    step_order: int
    input_data: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440004",
                "step_name": "vision_analysis",
                "step_order": 1,
                "input_data": {"image_path": "./data/uploads/drawing.png"}
            }
        }


class AgentStepComplete(BaseModel):
    """
    Input model for completing agent steps.
    """
    output_data: Dict[str, Any] = Field(..., description="Step output")
    status: AgentStepStatus = Field(
        default=AgentStepStatus.COMPLETED, description="Completion status"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "output_data": {"artifact_id": "550e8400-e29b-41d4-a716-446655440000"},
                "status": "completed"
            }
        }


# ============================================================================
# Run Artifact Link Models
# ============================================================================

class RunArtifactLink(BaseModel):
    """
    Maps artifacts to run stages.
    Tracks which artifacts were produced/reviewed/approved in a run.
    """
    link_id: str = Field(..., description="Unique UUID identifier")
    run_id: str = Field(..., description="Run UUID")
    artifact_id: str = Field(..., description="Artifact UUID")
    stage: RunArtifactStage = Field(..., description="Generation stage")
    created_at: datetime = Field(..., description="Creation timestamp")

    @validator("created_at", pre=True)
    def parse_datetime(cls, v):
        """Parse ISO 8601 datetime strings"""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "link_id": "550e8400-e29b-41d4-a716-446655440006",
                "run_id": "550e8400-e29b-41d4-a716-446655440004",
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "stage": "generated",
                "created_at": "2026-02-23T10:00:00Z"
            }
        }


class RunArtifactLinkCreate(BaseModel):
    """
    Input model for creating run-artifact links.
    """
    run_id: str
    artifact_id: str
    stage: RunArtifactStage

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440004",
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "stage": "generated"
            }
        }


# ============================================================================
# Complex Response Models
# ============================================================================

class ArtifactLineage(BaseModel):
    """
    Complete artifact lineage (ancestry, descendants, relations).
    Returned by GET /artifacts/{artifact_id}/lineage
    """
    artifact_id: str
    artifact: Artifact
    ancestors: List[Artifact] = Field(default_factory=list, description="Parent artifacts")
    descendants: List[Artifact] = Field(default_factory=list, description="Child artifacts")
    relations: List[ArtifactRelation] = Field(
        default_factory=list, description="All relations in lineage"
    )
    total_count: int = Field(..., description="Total artifacts in lineage")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "description": "Complete artifact lineage with ancestry and descendants"
        }


class RunWithArtifacts(BaseModel):
    """
    Run with all generated artifacts.
    Returned by GET /runs/{run_id}
    """
    run: Run
    steps: List[AgentStep] = Field(default_factory=list, description="Execution steps")
    artifacts: List[Artifact] = Field(default_factory=list, description="Generated artifacts")
    links: List[RunArtifactLink] = Field(
        default_factory=list, description="Run-artifact mappings"
    )

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "description": "Run with complete execution context and artifacts"
        }
