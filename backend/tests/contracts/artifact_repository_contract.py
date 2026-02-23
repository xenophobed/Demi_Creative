"""
Artifact Repository Contract Tests

Defines the expected interface and behavior of artifact repositories
before implementation. Tests repository CRUD operations and constraints.

Repository Pattern:
- All database access goes through repositories (never direct queries)
- Repositories enforce business logic and constraints
- Enable testability through mock implementations
"""

import pytest
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


# ============================================================================
# Artifact Repository Contract
# ============================================================================

class TestArtifactRepositoryCreate:
    """Contract: Creating artifacts"""

    def test_create_artifact_returns_id(self):
        """
        Contract: create_artifact() returns artifact_id.

        Method signature:
        async def create_artifact(artifact_data: Dict[str, Any]) -> str

        Returns: artifact_id (UUID string)
        """
        artifact_data = {
            "artifact_type": "audio",
            "artifact_path": "./data/audio/story.mp3",
            "artifact_url": "https://cdn.example.com/audio/story.mp3",
            "metadata": {"duration": 120},
            "description": "Story narration"
        }

        # Expected behavior:
        # - Validates artifact_data
        # - Generates artifact_id (UUID)
        # - Sets created_at to now
        # - Sets stored_at to now
        # - Computes content_hash if applicable
        # - Inserts into artifacts table
        # - Returns artifact_id string

        expected_return_type = str
        artifact_id_length = 36  # UUID length with dashes

    def test_create_artifact_sets_lifecycle_state(self):
        """
        Contract: New artifacts default to lifecycle_state='intermediate'.
        """
        artifact_data = {
            "artifact_type": "audio",
            "artifact_path": "./data/audio/story.mp3"
        }

        # Expected: lifecycle_state defaults to "intermediate" if not provided
        expected_default_state = "intermediate"

    def test_create_artifact_generates_uuid(self):
        """
        Contract: artifact_id is generated as UUID (not sequential).
        Supports distributed systems without coordination.
        """
        # Two calls should generate different IDs
        artifact_id_1 = "550e8400-e29b-41d4-a716-446655440000"
        artifact_id_2 = "550e8400-e29b-41d4-a716-446655440001"

        assert artifact_id_1 != artifact_id_2
        assert len(artifact_id_1) == 36

    def test_create_artifact_with_optional_fields(self):
        """
        Contract: Can create artifact with or without optional fields.
        """
        minimal_artifact = {
            "artifact_type": "text",
            "artifact_payload": "Story text content..."
        }

        full_artifact = {
            "artifact_type": "audio",
            "artifact_path": "./data/audio/story.mp3",
            "artifact_url": "https://cdn.example.com/audio/story.mp3",
            "metadata": {"duration": 120},
            "description": "Story narration",
            "created_by_step_id": "step-uuid"
        }

        # Both should be accepted


class TestArtifactRepositoryRead:
    """Contract: Reading artifacts"""

    def test_get_artifact_by_id(self):
        """
        Contract: get_by_id(artifact_id) returns Artifact or None.

        Method signature:
        async def get_by_id(artifact_id: str) -> Optional[Artifact]
        """
        # Artifact found
        artifact_id = "550e8400-e29b-41d4-a716-446655440000"
        expected_artifact = {
            "artifact_id": artifact_id,
            "artifact_type": "audio",
            "lifecycle_state": "intermediate",
            "created_at": "2026-02-23T10:00:00Z",
            "stored_at": "2026-02-23T10:00:00Z"
        }

        # Artifact not found
        missing_artifact_id = "550e8400-e29b-41d4-a716-446655440099"
        # Should return None

    def test_list_artifacts_by_lifecycle_state(self):
        """
        Contract: list_by_lifecycle_state(state, limit) returns List[Artifact].

        Method signature:
        async def list_by_lifecycle_state(
            state: str, limit: int = 100
        ) -> List[Artifact]
        """
        # Should use indexed query on lifecycle_state column
        # Should respect limit parameter
        # Should return in descending created_at order (newest first)

        expected_states = ["intermediate", "candidate", "published", "archived"]

    def test_list_artifacts_by_created_by_step(self):
        """
        Contract: list_by_created_by_step(step_id) returns artifacts produced by step.

        Method signature:
        async def list_by_created_by_step(step_id: str) -> List[Artifact]

        Use case: Lineage tracking - what did this step produce?
        """
        step_id = "step-uuid"
        # Should query WHERE created_by_step_id = ?
        # Should use index on created_by_step_id

    def test_list_artifacts_pagination(self):
        """
        Contract: list operations support limit/offset pagination.
        """
        # list_by_lifecycle_state(state, limit=10, offset=0)
        # Returns first 10 results

        # list_by_lifecycle_state(state, limit=10, offset=10)
        # Returns next 10 results


class TestArtifactRepositoryUpdate:
    """Contract: Updating artifact state"""

    def test_update_lifecycle_state(self):
        """
        Contract: update_lifecycle_state(artifact_id, new_state) -> bool.

        Method signature:
        async def update_lifecycle_state(
            artifact_id: str,
            new_state: str
        ) -> bool

        Returns: True if successful, False if artifact not found

        Use case: Approve artifact (intermediate→candidate→published)
        """
        artifact_id = "550e8400-e29b-41d4-a716-446655440000"

        # Valid transitions
        valid_transitions = [
            ("intermediate", "candidate"),
            ("candidate", "published"),
            ("published", "archived"),
            ("intermediate", "archived"),
            ("candidate", "archived")
        ]

        # Invalid transitions (should be rejected)
        invalid_transitions = [
            ("published", "candidate"),  # Rollback
            ("intermediate", "published"),  # Skip
            ("archived", "published")  # Resurrection
        ]


class TestArtifactRelationRepository:
    """Contract: Managing artifact relations"""

    def test_create_relation(self):
        """
        Contract: create_relation(from_id, to_id, rel_type, metadata) -> str.

        Method signature:
        async def create_relation(
            from_artifact_id: str,
            to_artifact_id: str,
            relation_type: str,
            metadata: Optional[Dict] = None
        ) -> str  # Returns relation_id
        """
        from_artifact_id = "550e8400-e29b-41d4-a716-446655440000"
        to_artifact_id = "550e8400-e29b-41d4-a716-446655440001"
        relation_type = "derived_from"

        # Expected behavior:
        # - Validates relation_type enum
        # - Prevents self-relations (from == to)
        # - Prevents duplicate relations (UNIQUE constraint)
        # - Generates relation_id
        # - Sets created_at to now
        # - Inserts into artifact_relations table
        # - Returns relation_id

    def test_create_relation_prevents_self_reference(self):
        """
        Contract: Cannot create relation from artifact to itself.
        """
        artifact_id = "550e8400-e29b-41d4-a716-446655440000"

        # Should fail:
        # create_relation(artifact_id, artifact_id, "derived_from")

    def test_create_relation_prevents_duplicates(self):
        """
        Contract: UNIQUE(from_artifact_id, to_artifact_id, relation_type).
        Cannot insert duplicate relation.
        """
        # First insert succeeds
        # create_relation("uuid1", "uuid2", "derived_from")

        # Second insert with same data fails
        # create_relation("uuid1", "uuid2", "derived_from")  # Duplicate!

        # But different type succeeds
        # create_relation("uuid1", "uuid2", "variant_of")  # OK

    def test_get_artifact_lineage(self):
        """
        Contract: get_artifact_lineage(artifact_id) -> Dict with ancestors/descendants.

        Method signature:
        async def get_artifact_lineage(artifact_id: str) -> Dict[str, Any]

        Returns dict with:
        - ancestors: List[Artifact] (recursive traversal of incoming relations)
        - descendants: List[Artifact] (recursive traversal of outgoing relations)
        - relations: List[ArtifactRelation] (all relations in lineage)

        Use case: Trace derivation chain (where did this artifact come from?)
        """
        artifact_id = "artifact-uuid-5"

        # Example lineage:
        # artifact-1 --derived_from--> artifact-2
        # artifact-2 --variant_of--> artifact-3
        # artifact-3 --transcoded_from--> artifact-4
        # artifact-4 --derived_from--> artifact-5

        expected_lineage = {
            "artifact_id": "artifact-5",
            "ancestors": [
                {"artifact_id": "artifact-4"},
                {"artifact_id": "artifact-3"},
                {"artifact_id": "artifact-2"},
                {"artifact_id": "artifact-1"}
            ],
            "descendants": [],  # No outgoing relations
            "relations": [
                {"from": "artifact-4", "to": "artifact-5", "type": "derived_from"}
            ]
        }


class TestStoryArtifactLinkRepository:
    """Contract: Linking artifacts to stories"""

    def test_upsert_story_artifact_link(self):
        """
        Contract: upsert_link(story_id, artifact_id, role, is_primary) -> str.

        Method signature:
        async def upsert_link(
            story_id: str,
            artifact_id: str,
            role: str,
            is_primary: bool = True
        ) -> str  # Returns link_id

        Behavior:
        - If link already exists: UPDATE (update stored_at, is_primary)
        - If link doesn't exist: INSERT
        - Enforces UNIQUE(story_id, role, is_primary=1) constraint
        """
        story_id = "story-uuid"
        artifact_id = "artifact-uuid"
        role = "final_audio"
        is_primary = True

        # Expected: returns link_id (UUID string)

    def test_enforce_one_primary_per_role(self):
        """
        Contract: Only one PRIMARY artifact per story+role.

        Scenario 1: Create link with is_primary=True
        - Succeeds

        Scenario 2: Create another link with same story, role, is_primary=True
        - Should fail (UNIQUE constraint violation)
        - OR automatically update first link to is_primary=False (upsert logic)
        """
        story_id = "story-uuid"

        # First primary link
        link_1 = {
            "story_id": story_id,
            "artifact_id": "audio-uuid-1",
            "role": "final_audio",
            "is_primary": True
        }

        # Attempting second primary for same story+role
        link_2 = {
            "story_id": story_id,
            "artifact_id": "audio-uuid-2",
            "role": "final_audio",
            "is_primary": True
        }

        # Implementation choice:
        # Option A: Reject link_2 with error
        # Option B: Set link_1.is_primary=False, set link_2.is_primary=True

    def test_get_canonical_artifact(self):
        """
        Contract: get_canonical_artifact(story_id, role) -> Optional[Artifact].

        Method signature:
        async def get_canonical_artifact(
            story_id: str,
            role: str
        ) -> Optional[Artifact]

        Returns the PRIMARY artifact for given story+role, or None if not found.
        """
        story_id = "story-uuid"
        role = "final_audio"

        # Expected: Returns Artifact where:
        # - story_artifact_link.story_id = story_id
        # - story_artifact_link.role = role
        # - story_artifact_link.is_primary = True
        # - WITH artifact details

    def test_list_artifacts_by_story(self):
        """
        Contract: list_artifacts_by_story(story_id) -> List[StoryArtifactLink].

        Method signature:
        async def list_artifacts_by_story(story_id: str) -> List[StoryArtifactLink]

        Returns all artifacts linked to story (both primary and non-primary).
        """
        story_id = "story-uuid"

        # Expected:
        # - JOINs story_artifact_links and artifacts tables
        # - Returns all links for story
        # - Ordered by role, then is_primary DESC (primary first)

    def test_list_stories_by_artifact(self):
        """
        Contract: list_stories_by_artifact(artifact_id) -> List[StoryArtifactLink].

        Use case: Reverse lookup - which stories use this artifact?
        """
        artifact_id = "artifact-uuid"

        # Returns all story links for this artifact


class TestRunRepository:
    """Contract: Managing runs (execution workflows)"""

    def test_create_run(self):
        """
        Contract: create_run(run_data) -> str.

        Method signature:
        async def create_run(run_data: Dict[str, Any]) -> str  # Returns run_id

        Required fields:
        - story_id
        - workflow_type (image_to_story|interactive_story|news_to_kids)

        Optional fields:
        - session_id (for interactive stories)
        """
        run_data = {
            "story_id": "story-uuid",
            "workflow_type": "image_to_story",
            "status": "pending"
        }

        # Expected: returns run_id (UUID string)

    def test_update_run_status(self):
        """
        Contract: update_status(run_id, status) -> bool.

        Method signature:
        async def update_status(run_id: str, status: str) -> bool

        Valid statuses: pending, running, completed, failed
        """
        run_id = "run-uuid"
        new_status = "running"

        # Expected: returns True if successful, False if run not found

    def test_get_run_by_id(self):
        """
        Contract: get_by_id(run_id) -> Optional[Run].

        Returns run with all fields including result_summary.
        """
        run_id = "run-uuid"

        # Expected:
        # - Returns Run object
        # - Or None if not found

    def test_list_runs_by_story(self):
        """
        Contract: list_by_story(story_id) -> List[Run].

        Returns all runs for a story in reverse chronological order.
        """
        story_id = "story-uuid"


class TestAgentStepRepository:
    """Contract: Managing agent steps"""

    def test_create_agent_step(self):
        """
        Contract: create_step(step_data) -> str.

        Method signature:
        async def create_step(step_data: Dict[str, Any]) -> str  # Returns agent_step_id

        Required fields:
        - run_id
        - step_name
        - step_order

        Optional fields:
        - input_data (JSON)
        - output_data (JSON)
        """
        step_data = {
            "run_id": "run-uuid",
            "step_name": "vision_analysis",
            "step_order": 1,
            "input_data": {"image_path": "./data/uploads/drawing.png"}
        }

        # Expected: returns agent_step_id (UUID string)

    def test_list_steps_by_run(self):
        """
        Contract: list_by_run(run_id) -> List[AgentStep].

        Returns all steps for a run in step_order sequence.
        """
        run_id = "run-uuid"

        # Expected: steps ordered by step_order ASC

    def test_complete_step(self):
        """
        Contract: complete_step(agent_step_id, output_data, status) -> bool.

        Method signature:
        async def complete_step(
            agent_step_id: str,
            output_data: Dict[str, Any],
            status: str
        ) -> bool

        Sets:
        - output_data (JSON)
        - status (completed|failed)
        - completed_at (current timestamp)
        """
        agent_step_id = "step-uuid"
        output_data = {
            "artifact_id": "audio-uuid",
            "duration": 120,
            "status": "generated"
        }
        status = "completed"

        # Expected: returns True if successful


class TestTransactionSupport:
    """Contract: Transactional operations for consistency"""

    def test_create_artifact_with_run_and_steps(self):
        """
        Contract: Creating artifact with run+steps should be transactional.

        Scenario:
        1. Create run
        2. Create agent_step
        3. Create artifact
        4. Create run_artifact_link

        If any step fails: rollback all (atomicity)
        """
        # This is a multi-step operation
        # Either all succeed or all rollback


class TestIndexing:
    """Contract: Repository uses database indexes"""

    def test_artifacts_indexed_by_lifecycle_state(self):
        """
        Contract: artifacts table has:
        INDEX idx_artifact_lifecycle_state (lifecycle_state)

        Enables fast queries like:
        SELECT * FROM artifacts WHERE lifecycle_state='candidate'
        """

    def test_artifacts_indexed_by_created_by_step(self):
        """
        Contract: artifacts table has:
        INDEX idx_artifact_created_by_step (created_by_step_id)
        """

    def test_artifacts_indexed_by_type(self):
        """
        Contract: artifacts table has:
        INDEX idx_artifact_type (artifact_type)
        """

    def test_relations_indexed_by_direction(self):
        """
        Contract: artifact_relations table has:
        INDEX idx_relation_from (from_artifact_id)
        INDEX idx_relation_to (to_artifact_id)

        Enables fast lineage traversal.
        """

    def test_links_indexed_by_story(self):
        """
        Contract: story_artifact_links table has:
        INDEX idx_link_story (story_id)

        Enables fast lookup of artifacts for a story.
        """


class TestErrorHandling:
    """Contract: Repository error conditions"""

    def test_create_artifact_with_invalid_data(self):
        """
        Contract: create_artifact() validates input.

        Should reject:
        - Missing artifact_type
        - Missing created_at/stored_at (auto-generated, but validate format)
        - Invalid lifecycle_state
        """

    def test_create_relation_with_nonexistent_artifact(self):
        """
        Contract: create_relation() validates foreign keys.

        Should reject:
        - from_artifact_id doesn't exist
        - to_artifact_id doesn't exist
        """

    def test_update_nonexistent_artifact(self):
        """
        Contract: update_lifecycle_state() returns False if artifact not found.

        Doesn't throw exception, returns False.
        Allows client to handle gracefully.
        """

    def test_get_nonexistent_artifact(self):
        """
        Contract: get_by_id() returns None if not found.

        Doesn't throw exception, returns None.
        """


class TestImmutabilityEnforcement:
    """Contract: Repository enforces artifact immutability"""

    def test_cannot_update_artifact_id(self):
        """
        Contract: artifact_id is immutable.
        Database PRIMARY KEY prevents changes.
        """

    def test_cannot_update_created_at(self):
        """
        Contract: created_at is immutable.
        Repository should reject attempts to update it.
        """

    def test_can_update_stored_at(self):
        """
        Contract: stored_at CAN be updated.
        Tracks when artifact was last saved/replicated to storage.
        """

    def test_can_update_lifecycle_state(self):
        """
        Contract: lifecycle_state CAN be updated.
        But only via update_lifecycle_state() with validation.
        """
