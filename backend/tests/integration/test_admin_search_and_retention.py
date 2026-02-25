"""
Integration Tests: Admin Search, Lineage Explorer & Retention Cleanup

Tests the full stack: repository → service → models.
Uses an in-memory SQLite database.

Issue #16: Admin search, story lineage, lineage export, safety audit.
Issue #19: Retention cleanup, storage stats, safeguards.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.artifact_repository import (
    ArtifactRepository,
    ArtifactRelationRepository,
    StoryArtifactLinkRepository,
    RunRepository,
    AgentStepRepository,
    RunArtifactLinkRepository,
)
from src.services.models.artifact_models import (
    ArtifactCreate,
    ArtifactType,
    LifecycleState,
    ArtifactRelationCreate,
    RelationType,
    StoryArtifactLinkCreate,
    StoryArtifactRole,
    RunCreate,
    WorkflowType,
    AgentStepCreate,
    RunArtifactLinkCreate,
    RunArtifactStage,
    RetentionPolicy,
)
from src.services.retention_service import RetentionService
from src.services.provenance_tracker import ProvenanceTracker


@pytest.fixture
async def db(tmp_path):
    """Create test database with full schema."""
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path=db_path)
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


async def create_test_story(db, story_id: str = None) -> str:
    """Helper: create a minimal story record."""
    sid = story_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db.execute(
        """
        INSERT INTO stories (
            story_id, child_id, age_group, story_text, word_count,
            created_at, stored_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, "child-1", "6-8", "Test story text.", 3, now, now),
    )
    await db.commit()
    return sid


async def create_full_provenance_chain(db) -> dict:
    """
    Helper: build a full story → run → step → artifact chain.
    Returns dict with story_id, run_id, step_ids, artifact_ids.
    """
    tracker = ProvenanceTracker(db)
    story_id = await create_test_story(db)

    run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)

    # Step 1: vision analysis → image artifact
    step1_id = await tracker.start_step(run_id, "vision_analysis", 1)
    image_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_path="./data/uploads/drawing.png",
        description="Child drawing",
        mime_type="image/png",
        file_size=50000,
        safety_score=0.95,
        agent_name="vision_agent",
    )
    await tracker.complete_step(step1_id, output_data={"artifact_id": image_id})

    # Step 2: story generation → text artifact (derived from image)
    step2_id = await tracker.start_step(run_id, "story_generation", 2)
    text_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Once upon a time...",
        description="Generated story",
        safety_score=0.92,
        agent_name="story_agent",
        input_artifact_ids=[image_id],
    )
    await tracker.complete_step(step2_id, output_data={"artifact_id": text_id})

    # Step 3: TTS → audio artifact (derived from text)
    step3_id = await tracker.start_step(run_id, "tts_generation", 3)
    audio_id = await tracker.record_artifact(
        step3_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/story.mp3",
        description="Story narration",
        mime_type="audio/mpeg",
        file_size=200000,
        safety_score=0.98,
        agent_name="tts_agent",
        input_artifact_ids=[text_id],
    )
    await tracker.complete_step(step3_id, output_data={"artifact_id": audio_id})

    await tracker.complete_run(run_id, result_summary={"artifacts": 3})

    # Link to story
    await tracker.link_to_story(story_id, image_id, StoryArtifactRole.COVER)
    await tracker.link_to_story(story_id, audio_id, StoryArtifactRole.FINAL_AUDIO)

    return {
        "story_id": story_id,
        "run_id": run_id,
        "step_ids": [step1_id, step2_id, step3_id],
        "artifact_ids": [image_id, text_id, audio_id],
        "image_id": image_id,
        "text_id": text_id,
        "audio_id": audio_id,
    }


# ============================================================================
# Admin Search Tests (Issue #16)
# ============================================================================


@pytest.mark.asyncio
async def test_search_by_artifact_id(db):
    """Search finds exact artifact by ID."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    result = await repo.search(artifact_id=chain["image_id"])

    assert result.total_count == 1
    assert result.artifacts[0].artifact_id == chain["image_id"]
    assert result.query["artifact_id"] == chain["image_id"]


@pytest.mark.asyncio
async def test_search_by_story_id(db):
    """Search by story_id finds all linked artifacts."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    result = await repo.search(story_id=chain["story_id"])

    # image and audio are linked to story (cover + final_audio)
    assert result.total_count == 2
    found_ids = {a.artifact_id for a in result.artifacts}
    assert chain["image_id"] in found_ids
    assert chain["audio_id"] in found_ids


@pytest.mark.asyncio
async def test_search_by_run_id(db):
    """Search by run_id finds all artifacts produced in that run."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    result = await repo.search(run_id=chain["run_id"])

    assert result.total_count == 3  # image, text, audio
    found_ids = {a.artifact_id for a in result.artifacts}
    assert chain["image_id"] in found_ids
    assert chain["text_id"] in found_ids
    assert chain["audio_id"] in found_ids


@pytest.mark.asyncio
async def test_search_empty_with_no_fields(db):
    """Search with no fields returns empty result."""
    repo = ArtifactRepository(db)
    result = await repo.search()
    assert result.total_count == 0
    assert result.artifacts == []


# ============================================================================
# Story Lineage Tests (Issue #16)
# ============================================================================


@pytest.mark.asyncio
async def test_story_lineage_full_chain(db):
    """Story lineage shows all runs, steps, and artifacts."""
    chain = await create_full_provenance_chain(db)
    run_repo = RunRepository(db)

    runs = await run_repo.list_by_story(chain["story_id"])
    assert len(runs) == 1
    assert runs[0].run_id == chain["run_id"]


@pytest.mark.asyncio
async def test_artifact_lineage_export(db):
    """Artifact lineage export includes ancestors and safety flags."""
    chain = await create_full_provenance_chain(db)
    relation_repo = ArtifactRelationRepository(db)

    # Get lineage from the audio artifact (should trace back to text → image)
    lineage = await relation_repo.get_artifact_lineage(chain["audio_id"])

    assert lineage.artifact_id == chain["audio_id"]
    assert len(lineage.ancestors) >= 1  # at least text_id
    ancestor_ids = {a.artifact_id for a in lineage.ancestors}
    assert chain["text_id"] in ancestor_ids

    # Check that relations are included
    assert len(lineage.relations) >= 1


@pytest.mark.asyncio
async def test_safety_flagged_artifacts(db):
    """Safety audit returns artifacts below threshold."""
    repo = ArtifactRepository(db)

    # Create a low-safety artifact
    aid = await repo.create(
        ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Scary story...",
            description="Low safety artifact",
            safety_score=0.50,
        )
    )

    # Create a safe artifact
    await repo.create(
        ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Happy story!",
            description="Safe artifact",
            safety_score=0.95,
        )
    )

    flagged = await repo.list_safety_flagged()
    assert len(flagged) == 1
    assert flagged[0].artifact_id == aid
    assert flagged[0].safety_score == 0.50


# ============================================================================
# Storage Stats Tests (Issue #19)
# ============================================================================


@pytest.mark.asyncio
async def test_storage_stats(db):
    """Storage stats returns correct counts and sizes."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    stats = await repo.get_storage_stats()

    assert stats.total_artifacts == 3
    assert "intermediate" in stats.by_state
    assert stats.by_state["intermediate"] == 3
    assert "image" in stats.by_type
    assert "text" in stats.by_type
    assert "audio" in stats.by_type
    # image (50000) + audio (200000) = 250000
    assert stats.total_file_size_bytes == 250000


# ============================================================================
# Retention Cleanup Tests (Issue #19)
# ============================================================================


@pytest.mark.asyncio
async def test_retention_dry_run(db):
    """Dry run reports candidates without making changes."""
    # Create old intermediate artifacts
    repo = ArtifactRepository(db)
    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat().replace("+00:00", "Z")

    for i in range(3):
        aid = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO artifacts (
                artifact_id, artifact_type, lifecycle_state,
                created_at, stored_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (aid, "text", "intermediate", old_date, old_date),
        )
    await db.commit()

    service = RetentionService(db)
    report = await service.run_cleanup(dry_run=True)

    assert report.dry_run is True
    assert report.candidates_found >= 3
    assert report.archived_count >= 3  # Would archive 3

    # Verify no state changes
    artifacts = await repo.list_by_lifecycle_state("intermediate")
    assert len(artifacts) >= 3  # Still intermediate


@pytest.mark.asyncio
async def test_retention_archives_expired_intermediate(db):
    """Cleanup archives intermediate artifacts past TTL."""
    repo = ArtifactRepository(db)
    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat().replace("+00:00", "Z")

    aid = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO artifacts (
            artifact_id, artifact_type, lifecycle_state,
            created_at, stored_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (aid, "text", "intermediate", old_date, old_date),
    )
    await db.commit()

    service = RetentionService(db)
    report = await service.run_cleanup(dry_run=False)

    assert report.dry_run is False
    assert report.archived_count >= 1

    # Verify state changed
    artifact = await repo.get_by_id(aid)
    assert artifact.lifecycle_state == LifecycleState.ARCHIVED


@pytest.mark.asyncio
async def test_retention_never_touches_published(db):
    """Published artifacts are never archived or deleted."""
    repo = ArtifactRepository(db)
    old_date = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat().replace("+00:00", "Z")

    aid = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO artifacts (
            artifact_id, artifact_type, lifecycle_state,
            created_at, stored_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (aid, "text", "published", old_date, old_date),
    )
    await db.commit()

    service = RetentionService(db)
    report = await service.run_cleanup(dry_run=False)

    # Published should still be published
    artifact = await repo.get_by_id(aid)
    assert artifact.lifecycle_state == LifecycleState.PUBLISHED


@pytest.mark.asyncio
async def test_retention_protects_canonical_artifacts(db):
    """Canonical (primary story-linked) artifacts are safeguarded."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    # Make image artifact old
    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat().replace("+00:00", "Z")
    await db.execute(
        "UPDATE artifacts SET created_at = ? WHERE artifact_id = ?",
        (old_date, chain["image_id"]),
    )
    await db.commit()

    # Verify it's canonical
    assert await repo.is_canonical(chain["image_id"])

    service = RetentionService(db)
    report = await service.run_cleanup(dry_run=False)

    assert report.safeguarded_count >= 1

    # Canonical artifact should NOT be archived
    artifact = await repo.get_by_id(chain["image_id"])
    assert artifact.lifecycle_state == LifecycleState.INTERMEDIATE


@pytest.mark.asyncio
async def test_retention_cleanup_is_idempotent(db):
    """Running cleanup twice yields same result."""
    repo = ArtifactRepository(db)
    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat().replace("+00:00", "Z")

    aid = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO artifacts (
            artifact_id, artifact_type, lifecycle_state,
            created_at, stored_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (aid, "text", "intermediate", old_date, old_date),
    )
    await db.commit()

    service = RetentionService(db)

    # First run
    report1 = await service.run_cleanup(dry_run=False)
    assert report1.archived_count >= 1

    # Second run — should find nothing to archive
    report2 = await service.run_cleanup(dry_run=False)
    # The artifact is now archived; with 7-day TTL it won't be expired yet
    assert report2.archived_count == 0


@pytest.mark.asyncio
async def test_is_canonical(db):
    """is_canonical correctly identifies primary story artifacts."""
    chain = await create_full_provenance_chain(db)
    repo = ArtifactRepository(db)

    # image_id is canonical (cover)
    assert await repo.is_canonical(chain["image_id"]) is True

    # text_id is NOT canonical (not linked to story)
    assert await repo.is_canonical(chain["text_id"]) is False


@pytest.mark.asyncio
async def test_bulk_archive(db):
    """bulk_archive transitions multiple artifacts to archived."""
    repo = ArtifactRepository(db)

    aids = []
    for _ in range(3):
        aid = await repo.create(
            ArtifactCreate(
                artifact_type=ArtifactType.TEXT,
                artifact_payload="temp text",
            )
        )
        aids.append(aid)

    count = await repo.bulk_archive(aids)
    assert count == 3

    for aid in aids:
        a = await repo.get_by_id(aid)
        assert a.lifecycle_state == LifecycleState.ARCHIVED
