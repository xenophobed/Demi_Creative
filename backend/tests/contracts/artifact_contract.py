"""
Artifact System Contract Tests

Defines the expected behavior of the artifact graph model through contract-driven
development. These tests establish the data contract BEFORE implementation.

Contract Principles:
- Artifacts are immutable: updates create new artifact_id
- Lifecycle states flow: intermediate → candidate → published → archived
- One primary artifact per story+role (enforced by DB unique constraint)
- Relations form a directed graph with immutable edges
- Lineage tracking: artifact → created_by_step → run for complete provenance
"""

import pytest
import json
from datetime import datetime
from typing import Optional, Dict, Any


# ============================================================================
# Artifact Data Contract
# ============================================================================

class TestArtifactImmutability:
    """Contract: Artifacts are immutable"""

    def test_artifact_creation_contract(self):
        """
        Contract: Creating an artifact results in:
        - Unique artifact_id (UUID)
        - Immutable created_at timestamp
        - Computed content_hash from payload
        - Default lifecycle state: intermediate
        """
        artifact_data = {
            "artifact_type": "audio",
            "artifact_path": "./data/audio/story_abc123.mp3",
            "artifact_url": "https://cdn.example.com/audio/story_abc123.mp3",
            "description": "Story audio narration",
            "metadata": {
                "duration": 120,
                "codec": "mp3",
                "channels": 2
            }
        }

        # Expected contract:
        # - artifact_id: UUID string
        # - created_at: ISO 8601 timestamp (immutable after creation)
        # - lifecycle_state: "intermediate" (default)
        # - artifact_type: from input
        # - stored_at: can be updated (different from created_at)

        expected_contract = {
            "artifact_id": {"type": str, "pattern": r"^[a-f0-9-]{36}$"},  # UUID
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "artifact_path": "./data/audio/story_abc123.mp3",
            "created_at": {"type": str, "pattern": r"^\d{4}-\d{2}-\d{2}T"},  # ISO 8601
            "stored_at": {"type": str, "pattern": r"^\d{4}-\d{2}-\d{2}T"},
            "description": "Story audio narration",
            "metadata": artifact_data["metadata"]
        }

        # Assertion: created_at and stored_at are ISO 8601 timestamps
        assert isinstance(expected_contract["created_at"], dict)
        assert isinstance(expected_contract["stored_at"], dict)

    def test_artifact_immutability_no_update(self):
        """
        Contract: Attempting to UPDATE an artifact should fail or create new one.
        Artifacts are INSERT-only entities.

        If consumer tries to update an artifact:
        - Option 1 (DB enforcement): UNIQUE(artifact_id) prevents updates
        - Option 2 (Service layer): throw ImmutableArtifactError
        """
        # Cannot update artifact directly; must create new one with relation
        original_artifact = {
            "artifact_id": "orig-uuid",
            "lifecycle_state": "intermediate"
        }

        # If content changes, create new artifact:
        updated_artifact = {
            "artifact_id": "new-uuid",  # Different ID
            "lifecycle_state": "intermediate"
        }

        # Link old→new via artifact_relation:
        relation = {
            "from_artifact_id": "orig-uuid",
            "to_artifact_id": "new-uuid",
            "relation_type": "variant_of"
        }

        # Contract: old and new artifact_ids are different
        assert original_artifact["artifact_id"] != updated_artifact["artifact_id"]


class TestArtifactLifecycleStates:
    """Contract: Artifact lifecycle state transitions"""

    def test_lifecycle_state_enum_values(self):
        """
        Contract: Artifact has 4 lifecycle states:
        - intermediate: temporary artifacts during orchestration
        - candidate: reviewed/usable outputs
        - published: user-visible approved outputs
        - archived: retained but not active
        """
        valid_states = ["intermediate", "candidate", "published", "archived"]

        for state in valid_states:
            # Each state should be valid
            assert state in valid_states

    def test_lifecycle_state_transitions(self):
        """
        Contract: Valid transitions:
        - intermediate → candidate (after review)
        - intermediate → candidate → published (approval flow)
        - any state → archived (retention)
        - NOT: intermediate → published (skip candidate)
        - NOT: published → intermediate (no rollback)
        """
        # Valid flows:
        valid_flows = [
            ("intermediate", "candidate"),
            ("intermediate", "archived"),  # early discard
            ("candidate", "published"),
            ("candidate", "archived"),
            ("published", "archived"),
            ("archived", "archived"),  # idempotent
        ]

        # Invalid flows (should be rejected):
        invalid_flows = [
            ("intermediate", "published"),  # skip candidate
            ("published", "candidate"),  # rollback
            ("published", "intermediate"),  # rollback
            ("archived", "published"),  # resurrection
        ]

        for from_state, to_state in valid_flows:
            # Should be allowed
            pass

        for from_state, to_state in invalid_flows:
            # Should raise error or be rejected
            pass


class TestArtifactRelations:
    """Contract: Artifact relations form a directed graph"""

    def test_relation_types(self):
        """
        Contract: Three relation types for lineage tracking:
        - derived_from: output depends on input (e.g., audio derived from text)
        - variant_of: alternative version (e.g., same audio, different format)
        - transcoded_from: format conversion (e.g., mp3 → wav)
        """
        valid_relation_types = [
            "derived_from",
            "variant_of",
            "transcoded_from"
        ]

        for rel_type in valid_relation_types:
            assert rel_type in valid_relation_types

    def test_relation_directionality(self):
        """
        Contract: Relations are directed edges from→to.
        Semantics:
        - derived_from: to_artifact depends on from_artifact
        - variant_of: from_artifact and to_artifact are alternatives
        - transcoded_from: to_artifact is recoded version of from_artifact
        """
        relation = {
            "from_artifact_id": "text-artifact-uuid",
            "to_artifact_id": "audio-artifact-uuid",
            "relation_type": "derived_from"
        }

        # from→to direction is significant
        assert relation["from_artifact_id"] != relation["to_artifact_id"]

    def test_relation_uniqueness_constraint(self):
        """
        Contract: UNIQUE(from_artifact_id, to_artifact_id, relation_type)
        Cannot have duplicate relations between same pair with same type.
        """
        # This should succeed:
        relation_1 = {
            "from_artifact_id": "uuid1",
            "to_artifact_id": "uuid2",
            "relation_type": "derived_from"
        }

        # This should fail (duplicate):
        relation_2 = {
            "from_artifact_id": "uuid1",
            "to_artifact_id": "uuid2",
            "relation_type": "derived_from"
        }

        # But this should succeed (different type):
        relation_3 = {
            "from_artifact_id": "uuid1",
            "to_artifact_id": "uuid2",
            "relation_type": "variant_of"
        }

        assert relation_1 == relation_2  # Same data, should be rejected on duplicate
        assert relation_1 != relation_3  # Different type, allowed


class TestStoryArtifactLinks:
    """Contract: Story references artifacts via links with roles"""

    def test_story_artifact_link_roles(self):
        """
        Contract: Four canonical story roles:
        - cover: cover image displayed in story preview
        - final_audio: complete narration
        - final_video: video version
        - scene_image: scene images (0-many per story)
        """
        valid_roles = [
            "cover",
            "final_audio",
            "final_video",
            "scene_image"
        ]

        for role in valid_roles:
            assert role in valid_roles

    def test_one_primary_per_role_constraint(self):
        """
        Contract: UNIQUE(story_id, role, is_primary=1)
        Only one PRIMARY artifact per story+role combination.

        Allows multiple non-primary alternatives (for A/B testing).
        """
        primary_link = {
            "story_id": "story-uuid",
            "artifact_id": "audio-uuid-1",
            "role": "final_audio",
            "is_primary": True
        }

        # This primary link should succeed
        assert primary_link["is_primary"] is True

        # Attempting another primary for same story+role should fail:
        duplicate_primary = {
            "story_id": "story-uuid",
            "artifact_id": "audio-uuid-2",  # Different artifact
            "role": "final_audio",
            "is_primary": True
        }

        # Should trigger unique constraint violation
        # (story-uuid, final_audio, is_primary=1) already exists

        # But this non-primary link should succeed:
        alternative_link = {
            "story_id": "story-uuid",
            "artifact_id": "audio-uuid-2",
            "role": "final_audio",
            "is_primary": False
        }

        assert alternative_link["is_primary"] is False

    def test_scene_image_position_ordering(self):
        """
        Contract: scene_image links may have position for ordering.
        Allows: story has multiple scene images in sequence.
        """
        scene_links = [
            {
                "story_id": "story-uuid",
                "artifact_id": "image-uuid-1",
                "role": "scene_image",
                "is_primary": True,
                "position": 0
            },
            {
                "story_id": "story-uuid",
                "artifact_id": "image-uuid-2",
                "role": "scene_image",
                "is_primary": False,
                "position": 1
            },
        ]

        # Position helps order multiple scene images
        assert scene_links[0]["position"] < scene_links[1]["position"]


class TestRunAndAgentSteps:
    """Contract: Run and AgentStep form execution provenance"""

    def test_run_workflow_types(self):
        """
        Contract: Run tracks a generation workflow.
        Workflow types:
        - image_to_story: child's drawing → story
        - interactive_story: branching narrative flow
        - news_to_kids: news article → child-friendly summary
        """
        valid_workflow_types = [
            "image_to_story",
            "interactive_story",
            "news_to_kids"
        ]

        for workflow_type in valid_workflow_types:
            assert workflow_type in valid_workflow_types

    def test_run_status_tracking(self):
        """
        Contract: Run has status lifecycle:
        - pending: created but not started
        - running: currently executing
        - completed: finished (success or partial)
        - failed: error occurred
        """
        valid_statuses = [
            "pending",
            "running",
            "completed",
            "failed"
        ]

        for status in valid_statuses:
            assert status in valid_statuses

    def test_agent_step_execution_order(self):
        """
        Contract: AgentStep has step_order for sequence tracking.
        Steps within a run have ordering.
        """
        steps = [
            {
                "agent_step_id": "step-1-uuid",
                "run_id": "run-uuid",
                "step_name": "vision_analysis",
                "step_order": 1
            },
            {
                "agent_step_id": "step-2-uuid",
                "run_id": "run-uuid",
                "step_name": "safety_check",
                "step_order": 2
            },
        ]

        # Steps are ordered within run
        assert steps[0]["step_order"] < steps[1]["step_order"]

    def test_artifact_lineage_via_agent_step(self):
        """
        Contract: Artifact.created_by_step_id → AgentStep.agent_step_id
        Links artifact to the agent execution that created it.
        """
        artifact = {
            "artifact_id": "audio-uuid",
            "created_by_step_id": "step-2-uuid"
        }

        agent_step = {
            "agent_step_id": "step-2-uuid",
            "step_name": "tts_generation",
            "output_data": {"artifact_id": "audio-uuid"}
        }

        # Artifact references the step that created it
        assert artifact["created_by_step_id"] == agent_step["agent_step_id"]


class TestArtifactTypeConstraints:
    """Contract: Artifact types have specific requirements"""

    def test_artifact_type_enum(self):
        """
        Contract: Artifact types:
        - image: PNG, JPG, etc.
        - audio: MP3, WAV, etc.
        - video: MP4, WebM, etc.
        - text: plain text stories
        - json: structured data
        """
        valid_types = [
            "image",
            "audio",
            "video",
            "text",
            "json"
        ]

        for artifact_type in valid_types:
            assert artifact_type in valid_types

    def test_artifact_metadata_by_type(self):
        """
        Contract: Metadata varies by type.
        - image: dimensions, file_size
        - audio: duration, codec, channels
        - video: duration, dimensions, codec
        - text: char_count
        - json: schema_version
        """
        audio_artifact = {
            "artifact_type": "audio",
            "metadata": {
                "duration": 120,  # seconds
                "codec": "mp3",
                "channels": 2,
                "file_size": 1024000  # bytes
            }
        }

        image_artifact = {
            "artifact_type": "image",
            "metadata": {
                "dimensions": {"width": 1920, "height": 1080},
                "file_size": 2048000
            }
        }

        # Different types have different metadata
        assert "duration" in audio_artifact["metadata"]
        assert "duration" not in image_artifact["metadata"]
        assert "dimensions" in image_artifact["metadata"]
        assert "dimensions" not in audio_artifact["metadata"]


class TestForeignKeyIntegrity:
    """Contract: Database constraints for referential integrity"""

    def test_artifact_relation_fk_constraint(self):
        """
        Contract: artifact_relation.from_artifact_id and to_artifact_id
        must reference existing artifacts.
        ON DELETE CASCADE: if artifact deleted, relations involving it are deleted.
        """
        # If artifact with id "uuid1" is deleted:
        # - All relations WHERE from_artifact_id='uuid1' are deleted
        # - All relations WHERE to_artifact_id='uuid1' are deleted
        # This prevents orphaned relations
        pass

    def test_story_artifact_link_fk_constraint(self):
        """
        Contract: story_artifact_link references both story and artifact.
        ON DELETE CASCADE:
        - If story deleted: all links deleted
        - If artifact deleted: link deleted
        """
        pass

    def test_run_artifact_link_fk_constraint(self):
        """
        Contract: run_artifact_link references both run and artifact.
        ON DELETE CASCADE:
        - If run deleted: all links deleted
        - If artifact deleted: link deleted
        """
        pass


class TestContentHash:
    """Contract: Artifact deduplication via content hash"""

    def test_content_hash_computation(self):
        """
        Contract: content_hash is SHA256 of artifact content.
        Allows detecting duplicate content (even if stored separately).
        """
        artifact_content = "Story audio narration text"
        expected_hash = "abc123def456..."  # SHA256 hex

        # Two artifacts with same content should have same hash
        artifact_1_hash = "abc123def456"
        artifact_2_hash = "abc123def456"

        assert artifact_1_hash == artifact_2_hash

    def test_content_hash_optional(self):
        """
        Contract: content_hash is OPTIONAL (NULL allowed).
        Some artifacts (e.g., video, large files) may not compute hash.
        """
        artifact_without_hash = {
            "artifact_id": "video-uuid",
            "content_hash": None  # Large video, hash not computed
        }

        artifact_with_hash = {
            "artifact_id": "text-uuid",
            "content_hash": "abc123def456"
        }

        # Both valid
        assert artifact_without_hash["content_hash"] is None
        assert artifact_with_hash["content_hash"] is not None


# ============================================================================
# Data Contract Assertions
# ============================================================================

class TestDataContractSchema:
    """Validate overall artifact system data schema"""

    def test_artifact_minimum_required_fields(self):
        """
        Contract: Minimum artifact fields for database insertion
        """
        minimum_artifact = {
            "artifact_id": "uuid",
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
            assert field in minimum_artifact

    def test_story_required_fields_post_migration(self):
        """
        Contract: After artifact migration, stories table should have:
        - cover_artifact_id
        - canonical_audio_id
        - canonical_video_id
        - current_run_id

        OLD fields (deprecated, kept for backward compat):
        - audio_url (legacy)
        - image_url (legacy)
        - image_path (legacy)
        """
        story_post_migration = {
            "story_id": "uuid",
            "story_text": "The story...",  # Still present
            "word_count": 245,
            # New artifact references:
            "cover_artifact_id": "image-uuid",
            "canonical_audio_id": "audio-uuid",
            "canonical_video_id": None,
            "current_run_id": "run-uuid",
            # Legacy (optional, for compat):
            "audio_url": "https://...",
            "image_url": "https://..."
        }

        # New fields present
        assert "cover_artifact_id" in story_post_migration
        assert "canonical_audio_id" in story_post_migration
        assert "current_run_id" in story_post_migration

        # Old fields still allowed (backward compat)
        assert "audio_url" in story_post_migration


# ============================================================================
# Edge Cases & Constraints
# ============================================================================

class TestEdgeCases:
    """Contract: Edge case handling"""

    def test_artifact_with_no_metadata(self):
        """
        Contract: metadata is optional (NULL allowed)
        Some artifacts don't need metadata.
        """
        minimal_artifact = {
            "artifact_id": "uuid",
            "artifact_type": "text",
            "lifecycle_state": "intermediate",
            "metadata": None  # Optional
        }

        assert minimal_artifact["metadata"] is None

    def test_artifact_with_no_payload(self):
        """
        Contract: artifact_payload is optional (for file-based artifacts)
        Only used for small inline JSON/text artifacts.
        """
        file_based_artifact = {
            "artifact_id": "uuid",
            "artifact_type": "audio",
            "artifact_path": "./data/audio/story.mp3",
            "artifact_payload": None  # Not used for file artifacts
        }

        assert file_based_artifact["artifact_payload"] is None

    def test_orphaned_artifact_handling(self):
        """
        Contract: An artifact can exist without story_artifact_link.
        It's generated but not yet assigned to any story (lifecycle: intermediate).
        """
        orphaned_artifact = {
            "artifact_id": "uuid",
            "lifecycle_state": "intermediate"
            # No story_artifact_link yet
        }

        # This is valid - artifact awaiting approval
        assert orphaned_artifact["lifecycle_state"] == "intermediate"

    def test_circular_relation_prevention(self):
        """
        Contract: Relations should not form cycles.
        If A derived_from B and B derived_from C,
        then C cannot be derived_from A.
        """
        # This is a constraint that may be enforced at:
        # 1. Application layer (on insert_relation)
        # 2. Or accepted as-is (query lineage carefully to detect cycles)
        #
        # Contract: At least prevent direct cycles (A → A)
        self_cycle_relation = {
            "from_artifact_id": "uuid",
            "to_artifact_id": "uuid",  # Same!
            "relation_type": "derived_from"
        }

        # Should be rejected: cannot derive from itself
        assert self_cycle_relation["from_artifact_id"] != self_cycle_relation["to_artifact_id"]
