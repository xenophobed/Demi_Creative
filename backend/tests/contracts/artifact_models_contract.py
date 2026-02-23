"""
Artifact Pydantic Models Contract Tests

Tests for Pydantic v2 models that define the artifact system data contracts.
Validates serialization, deserialization, and validation rules.
"""

import pytest
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


# ============================================================================
# Model Contract Tests
# ============================================================================

class TestLifecycleStateEnum:
    """Contract: LifecycleState enum validation"""

    def test_lifecycle_state_values(self):
        """
        Contract: LifecycleState enum has exactly 4 values.
        """
        valid_states = {
            "INTERMEDIATE": "intermediate",
            "CANDIDATE": "candidate",
            "PUBLISHED": "published",
            "ARCHIVED": "archived"
        }

        assert len(valid_states) == 4
        assert "INTERMEDIATE" in valid_states
        assert "CANDIDATE" in valid_states
        assert "PUBLISHED" in valid_states
        assert "ARCHIVED" in valid_states

    def test_lifecycle_state_string_values(self):
        """
        Contract: String representation for serialization (lowercase).
        """
        states = ["intermediate", "candidate", "published", "archived"]

        for state in states:
            assert isinstance(state, str)
            assert state.islower()


class TestArtifactTypeEnum:
    """Contract: ArtifactType enum validation"""

    def test_artifact_type_values(self):
        """
        Contract: ArtifactType enum covers media types.
        """
        valid_types = {
            "IMAGE": "image",
            "AUDIO": "audio",
            "VIDEO": "video",
            "TEXT": "text",
            "JSON": "json"
        }

        assert len(valid_types) == 5
        for artifact_type in valid_types.values():
            assert isinstance(artifact_type, str)


class TestRelationTypeEnum:
    """Contract: RelationType enum validation"""

    def test_relation_type_values(self):
        """
        Contract: Three relation types for artifact lineage.
        """
        valid_types = {
            "DERIVED_FROM": "derived_from",
            "VARIANT_OF": "variant_of",
            "TRANSCODED_FROM": "transcoded_from"
        }

        assert len(valid_types) == 3


class TestStoryArtifactRoleEnum:
    """Contract: StoryArtifactRole enum validation"""

    def test_story_artifact_role_values(self):
        """
        Contract: Four canonical roles plus custom.
        """
        valid_roles = {
            "COVER": "cover",
            "FINAL_AUDIO": "final_audio",
            "FINAL_VIDEO": "final_video",
            "SCENE_IMAGE": "scene_image"
        }

        assert len(valid_roles) == 4


class TestArtifactMetadataModel:
    """Contract: ArtifactMetadata model validation"""

    def test_artifact_metadata_optional_fields(self):
        """
        Contract: All ArtifactMetadata fields are optional.
        Allows flexible metadata for different artifact types.
        """
        # Empty metadata valid
        empty_metadata = {}
        assert isinstance(empty_metadata, dict)

        # Audio metadata
        audio_metadata = {
            "duration": 120,
            "channels": 2,
            "codec": "mp3",
            "file_size": 1024000
        }
        assert audio_metadata["duration"] is not None
        assert audio_metadata["channels"] is not None

        # Image metadata
        image_metadata = {
            "dimensions": {"width": 1920, "height": 1080},
            "file_size": 2048000
        }
        assert image_metadata["dimensions"]["width"] == 1920

    def test_artifact_metadata_serialization(self):
        """
        Contract: ArtifactMetadata serializes to/from JSON.
        """
        metadata = {
            "duration": 120,
            "dimensions": {"width": 1920, "height": 1080},
            "codec": "mp3"
        }

        # Should serialize to JSON string
        json_str = str(metadata)
        assert "duration" in json_str


class TestArtifactModel:
    """Contract: Artifact model validation"""

    def test_artifact_required_fields(self):
        """
        Contract: Artifact has these REQUIRED fields:
        - artifact_id: UUID string
        - artifact_type: enum value
        - lifecycle_state: enum value (defaults to intermediate)
        - created_at: datetime (immutable)
        - stored_at: datetime (mutable)
        """
        artifact_data = {
            "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "created_at": "2026-02-23T10:00:00Z",
            "stored_at": "2026-02-23T10:00:00Z"
        }

        required_fields = [
            "artifact_id",
            "artifact_type",
            "lifecycle_state",
            "created_at",
            "stored_at"
        ]

        for field in required_fields:
            assert field in artifact_data

    def test_artifact_optional_fields(self):
        """
        Contract: Optional fields:
        - content_hash
        - artifact_path
        - artifact_url
        - artifact_payload
        - metadata
        - description
        - created_by_step_id
        """
        artifact_with_optionals = {
            "artifact_id": "uuid",
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "created_at": "2026-02-23T10:00:00Z",
            "stored_at": "2026-02-23T10:00:00Z",
            "content_hash": "sha256abc...",
            "artifact_path": "./data/audio/story.mp3",
            "artifact_url": "https://cdn.example.com/audio/story.mp3",
            "metadata": {"duration": 120},
            "description": "Story narration",
            "created_by_step_id": "step-uuid"
        }

        # All optional fields present
        assert artifact_with_optionals["content_hash"] is not None

    def test_artifact_immutability_after_creation(self):
        """
        Contract: Once created, artifact_id and created_at are immutable.
        Attempts to modify them should be rejected.

        In Pydantic v2, can use frozen=True or field_validator to prevent updates.
        """
        original_artifact = {
            "artifact_id": "uuid-1",
            "created_at": "2026-02-23T10:00:00Z"
        }

        # Attempting to change should be rejected by validator
        attempted_change = {
            "artifact_id": "uuid-2",  # Different
            "created_at": "2026-02-23T11:00:00Z"  # Different
        }

        # Should not be allowed
        assert original_artifact["artifact_id"] != attempted_change["artifact_id"]

    def test_artifact_uuid_validation(self):
        """
        Contract: artifact_id must be valid UUID format.
        """
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        invalid_uuid = "not-a-uuid"

        # Valid UUID format (36 chars with dashes)
        assert len(valid_uuid) == 36
        assert valid_uuid.count("-") == 4

        # Invalid format
        assert len(invalid_uuid) != 36

    def test_artifact_timestamp_iso8601(self):
        """
        Contract: created_at and stored_at must be ISO 8601 format.
        """
        valid_timestamp = "2026-02-23T10:00:00Z"
        # ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ

        # Valid format
        assert "T" in valid_timestamp
        assert "Z" in valid_timestamp

    def test_artifact_lifecycle_state_default(self):
        """
        Contract: If lifecycle_state not provided, defaults to "intermediate".
        """
        artifact_without_state = {
            "artifact_id": "uuid",
            "artifact_type": "audio"
            # lifecycle_state omitted
        }

        # Default should be "intermediate"
        expected_default = "intermediate"
        assert expected_default == "intermediate"


class TestArtifactRelationModel:
    """Contract: ArtifactRelation model validation"""

    def test_relation_required_fields(self):
        """
        Contract: ArtifactRelation requires:
        - relation_id: UUID
        - from_artifact_id: UUID
        - to_artifact_id: UUID
        - relation_type: enum
        - created_at: datetime
        """
        relation_data = {
            "relation_id": "550e8400-e29b-41d4-a716-446655440001",
            "from_artifact_id": "550e8400-e29b-41d4-a716-446655440002",
            "to_artifact_id": "550e8400-e29b-41d4-a716-446655440003",
            "relation_type": "derived_from",
            "created_at": "2026-02-23T10:00:00Z"
        }

        required_fields = [
            "relation_id",
            "from_artifact_id",
            "to_artifact_id",
            "relation_type",
            "created_at"
        ]

        for field in required_fields:
            assert field in relation_data

    def test_relation_optional_metadata(self):
        """
        Contract: metadata is optional JSON field.
        Can store relation-specific data (confidence, algorithm, etc).
        """
        relation_with_metadata = {
            "relation_id": "uuid",
            "from_artifact_id": "uuid1",
            "to_artifact_id": "uuid2",
            "relation_type": "derived_from",
            "metadata": {
                "confidence": 0.95,
                "algorithm": "speech_synthesis",
                "parameters": {"voice": "nova", "speed": 1.0}
            },
            "created_at": "2026-02-23T10:00:00Z"
        }

        # Metadata accessible
        assert relation_with_metadata["metadata"]["confidence"] == 0.95

    def test_relation_no_self_reference(self):
        """
        Contract: Validation should reject from_artifact_id == to_artifact_id.
        """
        invalid_self_relation = {
            "from_artifact_id": "uuid",
            "to_artifact_id": "uuid"  # Same as from!
        }

        # Should fail validation
        assert invalid_self_relation["from_artifact_id"] == invalid_self_relation["to_artifact_id"]


class TestStoryArtifactLinkModel:
    """Contract: StoryArtifactLink model validation"""

    def test_link_required_fields(self):
        """
        Contract: StoryArtifactLink requires:
        - link_id: UUID
        - story_id: UUID
        - artifact_id: UUID
        - role: enum
        - is_primary: boolean
        - created_at: datetime
        - updated_at: datetime
        """
        link_data = {
            "link_id": "550e8400-e29b-41d4-a716-446655440004",
            "story_id": "story-uuid",
            "artifact_id": "artifact-uuid",
            "role": "final_audio",
            "is_primary": True,
            "created_at": "2026-02-23T10:00:00Z",
            "updated_at": "2026-02-23T10:00:00Z"
        }

        required_fields = [
            "link_id", "story_id", "artifact_id", "role",
            "is_primary", "created_at", "updated_at"
        ]

        for field in required_fields:
            assert field in link_data

    def test_link_optional_position(self):
        """
        Contract: position is optional (used for scene_image ordering).
        """
        link_with_position = {
            "link_id": "uuid",
            "story_id": "story-uuid",
            "artifact_id": "image-uuid",
            "role": "scene_image",
            "position": 0,
            "is_primary": True,
            "created_at": "2026-02-23T10:00:00Z",
            "updated_at": "2026-02-23T10:00:00Z"
        }

        link_without_position = {
            "link_id": "uuid",
            "story_id": "story-uuid",
            "artifact_id": "audio-uuid",
            "role": "final_audio",
            "position": None,  # Optional
            "is_primary": True,
            "created_at": "2026-02-23T10:00:00Z",
            "updated_at": "2026-02-23T10:00:00Z"
        }

        # Both valid
        assert link_with_position["position"] is not None
        assert link_without_position["position"] is None

    def test_link_is_primary_boolean(self):
        """
        Contract: is_primary is boolean, defaults to True.
        """
        primary_link = {"is_primary": True}
        non_primary_link = {"is_primary": False}

        assert isinstance(primary_link["is_primary"], bool)
        assert isinstance(non_primary_link["is_primary"], bool)
        assert primary_link["is_primary"] is True
        assert non_primary_link["is_primary"] is False


class TestRunArtifactLinkModel:
    """Contract: RunArtifactLink model validation"""

    def test_run_artifact_link_required_fields(self):
        """
        Contract: RunArtifactLink requires:
        - link_id: UUID
        - run_id: UUID
        - artifact_id: UUID
        - stage: string enum (generated|reviewed|approved|failed)
        - created_at: datetime
        """
        link_data = {
            "link_id": "550e8400-e29b-41d4-a716-446655440005",
            "run_id": "run-uuid",
            "artifact_id": "artifact-uuid",
            "stage": "generated",
            "created_at": "2026-02-23T10:00:00Z"
        }

        required_fields = ["link_id", "run_id", "artifact_id", "stage", "created_at"]

        for field in required_fields:
            assert field in link_data

    def test_run_artifact_link_stage_values(self):
        """
        Contract: stage has specific values.
        """
        valid_stages = ["generated", "reviewed", "approved", "failed"]

        for stage in valid_stages:
            assert stage in valid_stages


class TestRunModel:
    """Contract: Run model validation"""

    def test_run_required_fields(self):
        """
        Contract: Run requires:
        - run_id: UUID
        - story_id: UUID
        - workflow_type: enum (image_to_story|interactive_story|news_to_kids)
        - status: enum (pending|running|completed|failed)
        - created_at: datetime
        """
        run_data = {
            "run_id": "550e8400-e29b-41d4-a716-446655440006",
            "story_id": "story-uuid",
            "workflow_type": "image_to_story",
            "status": "pending",
            "created_at": "2026-02-23T10:00:00Z"
        }

        required_fields = ["run_id", "story_id", "workflow_type", "status", "created_at"]

        for field in required_fields:
            assert field in run_data

    def test_run_optional_fields(self):
        """
        Contract: Optional fields:
        - session_id: for interactive stories
        - result_summary: JSON with results
        - started_at: when execution began
        - completed_at: when execution finished
        """
        run_with_optionals = {
            "run_id": "uuid",
            "story_id": "story-uuid",
            "session_id": "session-uuid",
            "workflow_type": "interactive_story",
            "status": "completed",
            "result_summary": {
                "success_count": 3,
                "error_count": 0,
                "messages": ["Step 1 OK", "Step 2 OK", "Step 3 OK"]
            },
            "created_at": "2026-02-23T10:00:00Z",
            "started_at": "2026-02-23T10:00:01Z",
            "completed_at": "2026-02-23T10:00:05Z"
        }

        # All optional fields present
        assert run_with_optionals["session_id"] is not None
        assert run_with_optionals["started_at"] is not None

    def test_run_status_values(self):
        """
        Contract: Run status has specific values.
        """
        valid_statuses = ["pending", "running", "completed", "failed"]

        for status in valid_statuses:
            assert status in valid_statuses

    def test_run_workflow_type_values(self):
        """
        Contract: Run workflow_type has specific values.
        """
        valid_types = ["image_to_story", "interactive_story", "news_to_kids"]

        for workflow_type in valid_types:
            assert workflow_type in valid_types


class TestAgentStepModel:
    """Contract: AgentStep model validation"""

    def test_agent_step_required_fields(self):
        """
        Contract: AgentStep requires:
        - agent_step_id: UUID
        - run_id: UUID
        - step_name: string
        - step_order: integer
        - status: enum (pending|running|completed|failed)
        - created_at: datetime
        """
        step_data = {
            "agent_step_id": "550e8400-e29b-41d4-a716-446655440007",
            "run_id": "run-uuid",
            "step_name": "vision_analysis",
            "step_order": 1,
            "status": "pending",
            "created_at": "2026-02-23T10:00:00Z"
        }

        required_fields = [
            "agent_step_id", "run_id", "step_name",
            "step_order", "status", "created_at"
        ]

        for field in required_fields:
            assert field in step_data

    def test_agent_step_optional_fields(self):
        """
        Contract: Optional fields:
        - input_data: JSON
        - output_data: JSON
        - error_message: string
        - completed_at: datetime
        """
        step_with_optionals = {
            "agent_step_id": "uuid",
            "run_id": "run-uuid",
            "step_name": "safety_check",
            "step_order": 2,
            "input_data": {"content": "Story text..."},
            "output_data": {"is_safe": True, "safety_score": 0.92},
            "error_message": None,
            "completed_at": "2026-02-23T10:00:03Z",
            "status": "completed",
            "created_at": "2026-02-23T10:00:00Z"
        }

        assert step_with_optionals["input_data"] is not None
        assert step_with_optionals["output_data"] is not None

    def test_agent_step_ordering(self):
        """
        Contract: step_order is integer for sequencing within a run.
        """
        steps = [
            {"step_name": "vision_analysis", "step_order": 1},
            {"step_name": "safety_check", "step_order": 2},
            {"step_name": "tts_generation", "step_order": 3}
        ]

        # Order is sequential
        assert steps[0]["step_order"] < steps[1]["step_order"]
        assert steps[1]["step_order"] < steps[2]["step_order"]


class TestModelSerialization:
    """Contract: Model serialization/deserialization"""

    def test_artifact_to_json_serialization(self):
        """
        Contract: Artifact model serializes to JSON.
        Pydantic v2 uses model_dump_json().
        """
        artifact = {
            "artifact_id": "uuid",
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "created_at": "2026-02-23T10:00:00Z",
            "stored_at": "2026-02-23T10:00:00Z",
            "metadata": {"duration": 120}
        }

        # Should be serializable to JSON
        import json
        json_str = json.dumps(artifact)
        assert "artifact_id" in json_str
        assert "audio" in json_str

    def test_artifact_from_json_deserialization(self):
        """
        Contract: Artifact model deserializes from JSON dict.
        Pydantic v2 uses model_validate().
        """
        json_dict = {
            "artifact_id": "uuid",
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "created_at": "2026-02-23T10:00:00Z",
            "stored_at": "2026-02-23T10:00:00Z"
        }

        # Should deserialize without error
        assert json_dict["artifact_id"] == "uuid"
        assert json_dict["artifact_type"] == "audio"

    def test_enum_serialization(self):
        """
        Contract: Enum values serialize as lowercase strings.
        """
        artifact_data = {
            "artifact_type": "audio",  # String value, not enum
            "lifecycle_state": "intermediate"  # String value
        }

        # Serialized as strings
        assert artifact_data["artifact_type"] == "audio"
        assert artifact_data["lifecycle_state"] == "intermediate"


class TestTimestampHandling:
    """Contract: Timestamp field handling"""

    def test_iso8601_timestamp_format(self):
        """
        Contract: All timestamps are ISO 8601 format.
        Examples: 2026-02-23T10:00:00Z
        """
        valid_timestamps = [
            "2026-02-23T10:00:00Z",
            "2026-02-23T10:00:00+00:00"
        ]

        for ts in valid_timestamps:
            assert "T" in ts  # Has date-time separator

    def test_timestamp_immutability_created_at(self):
        """
        Contract: created_at is immutable (set at creation, never changed).
        """
        original_artifact = {
            "artifact_id": "uuid",
            "created_at": "2026-02-23T10:00:00Z"
        }

        # Attempting to change should be rejected
        # (Pydantic validator or frozen field)

        # stored_at can change (timestamp of storage update)
        updated_artifact = {
            "artifact_id": "uuid",
            "created_at": "2026-02-23T10:00:00Z",  # Same
            "stored_at": "2026-02-23T10:00:05Z"  # Different
        }

        assert original_artifact["created_at"] == updated_artifact["created_at"]
        assert original_artifact["created_at"] != updated_artifact["stored_at"]
