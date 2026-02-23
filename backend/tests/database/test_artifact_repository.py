"""
Artifact Repository Unit Tests

Tests for artifact repository implementation based on contracts.
Uses in-memory SQLite database for fast test execution.
"""

import pytest
import uuid
from datetime import datetime

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.artifact_repository import (
    ArtifactRepository, ArtifactRelationRepository,
    StoryArtifactLinkRepository, RunRepository,
    AgentStepRepository, MigrationStatusRepository
)
from src.services.models.artifact_models import (
    ArtifactCreate, ArtifactType, LifecycleState,
    ArtifactRelationCreate, RelationType,
    StoryArtifactLinkCreate, StoryArtifactRole,
    RunCreate, WorkflowType,
    AgentStepCreate, AgentStepComplete, AgentStepStatus,
    RunArtifactLinkCreate, RunArtifactStage
)


@pytest.fixture
async def db(tmp_path):
    """Create test database with full schema"""
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path=db_path)
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


async def create_test_story(db, story_id: str = None) -> str:
    """Helper: insert a minimal story record to satisfy FK constraints."""
    from datetime import datetime, timezone
    sid = story_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db.execute(
        """
        INSERT INTO stories (
            story_id, child_id, age_group, story_text, word_count,
            created_at, stored_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, "child-1", "6-8", "Test story text.", 3, now, now)
    )
    await db.commit()
    return sid


@pytest.mark.asyncio
async def test_artifact_create(db):
    """Test creating an artifact"""
    repo = ArtifactRepository(db)

    artifact_data = ArtifactCreate(
        artifact_type=ArtifactType.AUDIO,
        artifact_path="./data/audio/story.mp3",
        artifact_url="https://cdn.example.com/audio/story.mp3",
        description="Test audio artifact",
        metadata=None
    )

    artifact_id = await repo.create(artifact_data)

    # Verify artifact_id is UUID format
    assert isinstance(artifact_id, str)
    assert len(artifact_id) == 36  # UUID with dashes

    # Verify artifact can be retrieved
    artifact = await repo.get_by_id(artifact_id)
    assert artifact is not None
    assert artifact.artifact_id == artifact_id
    assert artifact.artifact_type == ArtifactType.AUDIO
    assert artifact.lifecycle_state == LifecycleState.INTERMEDIATE


@pytest.mark.asyncio
async def test_artifact_immutability(db):
    """Test that artifact_id and created_at are immutable"""
    repo = ArtifactRepository(db)

    artifact_data = ArtifactCreate(
        artifact_type=ArtifactType.TEXT,
        artifact_payload="Story text content"
    )

    artifact_id = await repo.create(artifact_data)
    artifact = await repo.get_by_id(artifact_id)

    # Verify created_at doesn't change
    created_at_1 = artifact.created_at

    # Simulate time passing
    import time
    time.sleep(0.1)

    artifact = await repo.get_by_id(artifact_id)
    created_at_2 = artifact.created_at

    assert created_at_1 == created_at_2  # Immutable


@pytest.mark.asyncio
async def test_artifact_lifecycle_state_transition(db):
    """Test artifact state transitions"""
    repo = ArtifactRepository(db)

    artifact_data = ArtifactCreate(
        artifact_type=ArtifactType.AUDIO
    )

    artifact_id = await repo.create(artifact_data)

    # Valid transition: intermediate → candidate
    success = await repo.update_lifecycle_state(artifact_id, "candidate")
    assert success is True

    artifact = await repo.get_by_id(artifact_id)
    assert artifact.lifecycle_state == LifecycleState.CANDIDATE

    # Valid transition: candidate → published
    success = await repo.update_lifecycle_state(artifact_id, "published")
    assert success is True

    # Invalid transition: published → intermediate
    with pytest.raises(ValueError):
        await repo.update_lifecycle_state(artifact_id, "intermediate")


@pytest.mark.asyncio
async def test_artifact_list_by_lifecycle_state(db):
    """Test listing artifacts by state"""
    repo = ArtifactRepository(db)

    # Create multiple artifacts
    for i in range(3):
        await repo.create(
            ArtifactCreate(artifact_type=ArtifactType.IMAGE)
        )

    # All should be in intermediate state by default
    intermediate = await repo.list_by_lifecycle_state("intermediate")
    assert len(intermediate) == 3

    # List published (should be empty)
    published = await repo.list_by_lifecycle_state("published")
    assert len(published) == 0


@pytest.mark.asyncio
async def test_artifact_relation_create(db):
    """Test creating artifact relations"""
    artifact_repo = ArtifactRepository(db)
    relation_repo = ArtifactRelationRepository(db)

    # Create two artifacts
    artifact_1_id = await artifact_repo.create(
        ArtifactCreate(artifact_type=ArtifactType.TEXT)
    )
    artifact_2_id = await artifact_repo.create(
        ArtifactCreate(artifact_type=ArtifactType.AUDIO)
    )

    # Create relation
    relation_data = ArtifactRelationCreate(
        from_artifact_id=artifact_1_id,
        to_artifact_id=artifact_2_id,
        relation_type=RelationType.DERIVED_FROM
    )

    relation_id = await relation_repo.create(relation_data)
    assert isinstance(relation_id, str)
    assert len(relation_id) == 36


@pytest.mark.asyncio
async def test_artifact_relation_prevents_self_reference(db):
    """Test that self-referencing relations are rejected"""
    artifact_repo = ArtifactRepository(db)
    relation_repo = ArtifactRelationRepository(db)

    artifact_id = await artifact_repo.create(
        ArtifactCreate(artifact_type=ArtifactType.TEXT)
    )

    # Try to create self-reference
    relation_data = ArtifactRelationCreate(
        from_artifact_id=artifact_id,
        to_artifact_id=artifact_id,
        relation_type=RelationType.DERIVED_FROM
    )

    with pytest.raises(ValueError, match="Cannot create relation from artifact to itself"):
        await relation_repo.create(relation_data)


@pytest.mark.asyncio
async def test_story_artifact_link_one_primary_per_role(db):
    """Test that only one primary artifact per story+role"""
    artifact_repo = ArtifactRepository(db)
    link_repo = StoryArtifactLinkRepository(db)

    # Create artifacts
    artifact_1_id = await artifact_repo.create(
        ArtifactCreate(artifact_type=ArtifactType.AUDIO)
    )
    artifact_2_id = await artifact_repo.create(
        ArtifactCreate(artifact_type=ArtifactType.AUDIO)
    )

    story_id = await create_test_story(db)

    # Create first primary link
    link_data_1 = StoryArtifactLinkCreate(
        story_id=story_id,
        artifact_id=artifact_1_id,
        role=StoryArtifactRole.FINAL_AUDIO,
        is_primary=True
    )

    link_id_1 = await link_repo.upsert(link_data_1)

    # Create second link with same role and is_primary
    # Should demote first link
    link_data_2 = StoryArtifactLinkCreate(
        story_id=story_id,
        artifact_id=artifact_2_id,
        role=StoryArtifactRole.FINAL_AUDIO,
        is_primary=True
    )

    link_id_2 = await link_repo.upsert(link_data_2)

    # Both links should exist, but only one should be primary
    links = await link_repo.list_by_story(story_id)
    assert len(links) == 2

    primary_links = [l for l in links if l.is_primary]
    assert len(primary_links) == 1
    assert primary_links[0].artifact_id == artifact_2_id


@pytest.mark.asyncio
async def test_run_creation_and_status_tracking(db):
    """Test run creation and status updates"""
    run_repo = RunRepository(db)

    story_id = await create_test_story(db)

    run_data = RunCreate(
        story_id=story_id,
        workflow_type=WorkflowType.IMAGE_TO_STORY
    )

    run_id = await run_repo.create(run_data)
    assert isinstance(run_id, str)

    # Verify run created with pending status
    run = await run_repo.get_by_id(run_id)
    assert run.status == "pending"

    # Update to running
    success = await run_repo.update_status(run_id, "running")
    assert success is True

    run = await run_repo.get_by_id(run_id)
    assert run.status == "running"
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_agent_step_creation_and_completion(db):
    """Test agent step execution"""
    run_repo = RunRepository(db)
    step_repo = AgentStepRepository(db)

    # Create run first (needs a story for FK)
    story_id = await create_test_story(db)
    run_data = RunCreate(
        story_id=story_id,
        workflow_type=WorkflowType.IMAGE_TO_STORY
    )
    run_id = await run_repo.create(run_data)

    # Create step
    step_data = AgentStepCreate(
        run_id=run_id,
        step_name="vision_analysis",
        step_order=1,
        input_data={"image_path": "./data/uploads/drawing.png"}
    )

    step_id = await step_repo.create(step_data)
    assert isinstance(step_id, str)

    # Complete step
    completion = AgentStepComplete(
        output_data={"objects": ["dog", "house"], "scene": "day"},
        status=AgentStepStatus.COMPLETED
    )

    success = await step_repo.complete(step_id, completion)
    assert success is True

    # Verify step state
    step = await step_repo.list_by_run(run_id)
    assert len(step) == 1
    assert step[0].status == AgentStepStatus.COMPLETED.value


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_end_to_end_artifact_workflow(db):
    """Test complete artifact workflow: create, link, run"""
    artifact_repo = ArtifactRepository(db)
    link_repo = StoryArtifactLinkRepository(db)
    run_repo = RunRepository(db)
    step_repo = AgentStepRepository(db)

    # 1. Create run (needs a story for FK)
    story_id = await create_test_story(db)
    run_data = RunCreate(
        story_id=story_id,
        workflow_type=WorkflowType.IMAGE_TO_STORY
    )
    run_id = await run_repo.create(run_data)

    # 2. Create agent step
    step_data = AgentStepCreate(
        run_id=run_id,
        step_name="tts_generation",
        step_order=1
    )
    step_id = await step_repo.create(step_data)

    # 3. Create artifact (with step reference)
    artifact_data = ArtifactCreate(
        artifact_type=ArtifactType.AUDIO,
        artifact_url="https://cdn.example.com/audio/story.mp3",
        created_by_step_id=step_id
    )
    artifact_id = await artifact_repo.create(artifact_data)

    # 4. Link artifact to story
    link_data = StoryArtifactLinkCreate(
        story_id=story_id,
        artifact_id=artifact_id,
        role=StoryArtifactRole.FINAL_AUDIO,
        is_primary=True
    )
    await link_repo.upsert(link_data)

    # 5. Verify complete chain
    artifact = await artifact_repo.get_by_id(artifact_id)
    assert artifact.created_by_step_id == step_id

    canonical = await link_repo.get_canonical_artifact(
        story_id, StoryArtifactRole.FINAL_AUDIO.value
    )
    assert canonical.artifact_id == artifact_id

    # 6. Complete step and transition artifact
    completion = AgentStepComplete(
        output_data={"artifact_id": artifact_id},
        status=AgentStepStatus.COMPLETED
    )
    await step_repo.complete(step_id, completion)

    # Transition through valid states: intermediate → candidate → published
    success = await artifact_repo.update_lifecycle_state(
        artifact_id, LifecycleState.CANDIDATE.value
    )
    assert success is True

    success = await artifact_repo.update_lifecycle_state(
        artifact_id, LifecycleState.PUBLISHED.value
    )
    assert success is True

    final_artifact = await artifact_repo.get_by_id(artifact_id)
    assert final_artifact.lifecycle_state == LifecycleState.PUBLISHED


# ============================================================================
# New Column Tests (Issue #14)
# ============================================================================

@pytest.mark.asyncio
async def test_artifact_create_with_new_columns(db):
    """Test creating artifacts with mime_type, file_size, safety_score, created_by_agent"""
    repo = ArtifactRepository(db)

    artifact_data = ArtifactCreate(
        artifact_type=ArtifactType.AUDIO,
        artifact_path="./data/audio/story.mp3",
        mime_type="audio/mpeg",
        file_size=512000,
        safety_score=0.92,
        created_by_agent="tts_agent",
    )

    artifact_id = await repo.create(artifact_data)
    artifact = await repo.get_by_id(artifact_id)

    assert artifact.mime_type == "audio/mpeg"
    assert artifact.file_size == 512000
    assert artifact.safety_score == 0.92
    assert artifact.created_by_agent == "tts_agent"


@pytest.mark.asyncio
async def test_artifact_new_columns_default_none(db):
    """Test new columns default to None when not provided"""
    repo = ArtifactRepository(db)

    artifact_id = await repo.create(ArtifactCreate(
        artifact_type=ArtifactType.TEXT,
        artifact_payload="test"
    ))

    artifact = await repo.get_by_id(artifact_id)
    assert artifact.mime_type is None
    assert artifact.file_size is None
    assert artifact.safety_score is None
    assert artifact.created_by_agent is None


@pytest.mark.asyncio
async def test_get_by_content_hash(db):
    """Test dedup lookup by content hash"""
    repo = ArtifactRepository(db)

    artifact_id = await repo.create(ArtifactCreate(
        artifact_type=ArtifactType.TEXT,
        artifact_payload="unique story text"
    ))

    artifact = await repo.get_by_id(artifact_id)
    existing = await repo.get_by_content_hash(artifact.content_hash)
    assert existing is not None
    assert existing.artifact_id == artifact_id

    # Non-existent hash returns None
    none_result = await repo.get_by_content_hash("nonexistent_hash")
    assert none_result is None


@pytest.mark.asyncio
async def test_list_by_type_and_state(db):
    """Test compound index query: type + lifecycle state"""
    repo = ArtifactRepository(db)

    await repo.create(ArtifactCreate(artifact_type=ArtifactType.AUDIO))
    await repo.create(ArtifactCreate(artifact_type=ArtifactType.TEXT, artifact_payload="t"))
    await repo.create(ArtifactCreate(artifact_type=ArtifactType.AUDIO))

    results = await repo.list_by_type_and_state("audio", "intermediate")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_list_safety_flagged(db):
    """Test partial index query: safety flagged artifacts"""
    repo = ArtifactRepository(db)

    await repo.create(ArtifactCreate(
        artifact_type=ArtifactType.TEXT,
        artifact_payload="safe",
        safety_score=0.95,
    ))
    await repo.create(ArtifactCreate(
        artifact_type=ArtifactType.TEXT,
        artifact_payload="flagged",
        safety_score=0.50,
    ))

    flagged = await repo.list_safety_flagged()
    assert len(flagged) == 1
    assert flagged[0].safety_score == 0.50


# ============================================================================
# Migration Status Repository Tests (Issue #15)
# ============================================================================

@pytest.mark.asyncio
async def test_migration_status_upsert_and_get(db):
    """Test migration status record creation and retrieval"""
    repo = MigrationStatusRepository(db)

    migration_id = await repo.upsert(
        migration_name="v2",
        source_type="story",
        source_id="s1",
        status="completed",
        artifacts_created=3,
        links_created=2,
    )

    record = await repo.get("v2", "story", "s1")
    assert record is not None
    assert record.migration_id == migration_id
    assert record.artifacts_created == 3


@pytest.mark.asyncio
async def test_migration_status_report(db):
    """Test migration report generation"""
    repo = MigrationStatusRepository(db)

    for i in range(5):
        await repo.upsert("v2", "story", f"s{i}", "completed", artifacts_created=1)
    await repo.upsert("v2", "story", "sfail", "failed", error_message="err")

    report = await repo.get_report("v2")
    assert report.completed == 5
    assert report.failed == 1
    assert report.success_rate == pytest.approx(5 / 6)
