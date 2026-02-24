"""
Provenance Chain Integration Test (Issue #17)

End-to-end test verifying lineage chain across 3+ agent rounds.
Uses in-memory SQLite database with full schema.
"""

import pytest
import uuid

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.provenance_tracker import ProvenanceTracker
from src.services.database.artifact_repository import (
    ArtifactRepository,
    ArtifactRelationRepository,
    StoryArtifactLinkRepository,
)
from src.services.models.artifact_models import (
    ArtifactType,
    WorkflowType,
    LifecycleState,
    StoryArtifactRole,
    ArtifactMetadata,
)


@pytest.fixture
async def db(tmp_path):
    """Create test database with full schema."""
    db_path = str(tmp_path / "test_provenance.db")
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
        (sid, "child-1", "6-8", "Test story text.", 3, now, now),
    )
    await db.commit()
    return sid


@pytest.mark.asyncio
async def test_three_round_provenance_chain(db):
    """
    Acceptance criterion: End-to-end test verifies lineage chain
    across at least 3 agent rounds.

    Simulates:
    Round 1 (image_upload): Upload drawing → image artifact
    Round 2 (story_generation): Generate story → text artifact (derived_from image)
    Round 3 (tts_generation): Generate audio → audio artifact (derived_from text)

    Verifies:
    - All 3 artifacts have created_by_step_id
    - Relations form image → text → audio chain
    - Lineage query returns full ancestry
    - Each step has duration_ms
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    # Start run
    run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)
    assert run_id is not None

    # ---- Round 1: Image upload ----
    step1_id = await tracker.start_step(
        run_id,
        "image_upload",
        1,
        input_data={"image_path": "./data/uploads/drawing.png"},
        model_name="upload_handler",
    )

    image_artifact_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_path="./data/uploads/drawing.png",
        description="Uploaded child drawing",
        mime_type="image/png",
        file_size=50000,
        agent_name="image_upload",
    )

    await tracker.complete_step(step1_id, output_data={"artifact_id": image_artifact_id})

    # ---- Round 2: Story generation ----
    step2_id = await tracker.start_step(
        run_id,
        "story_generation",
        2,
        input_data={"child_age": 7, "interests": ["animals"]},
        model_name="claude-agent-sdk",
        prompt_hash=ProvenanceTracker.compute_prompt_hash("image_to_story:child-1:7"),
    )

    text_artifact_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Once upon a time a little dog...",
        description="Generated story text",
        safety_score=0.95,
        agent_name="story_generation",
        input_artifact_ids=[image_artifact_id],
        metadata=ArtifactMetadata(char_count=32, word_count=7),
    )

    await tracker.complete_step(step2_id, output_data={"artifact_id": text_artifact_id})

    # ---- Round 3: TTS generation ----
    step3_id = await tracker.start_step(
        run_id,
        "tts_generation",
        3,
        input_data={"voice": "nova", "speed": 0.9},
        model_name="openai-tts",
    )

    audio_artifact_id = await tracker.record_artifact(
        step3_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/story_123.mp3",
        artifact_url="/data/audio/story_123.mp3",
        description="TTS narration",
        mime_type="audio/mpeg",
        agent_name="tts_generation",
        input_artifact_ids=[text_artifact_id],
        metadata=ArtifactMetadata(duration=30, codec="mp3"),
    )

    await tracker.complete_step(step3_id, output_data={"artifact_id": audio_artifact_id})

    # ---- Complete run ----
    await tracker.complete_run(run_id, result_summary={
        "artifacts_created": 3,
        "story_id": story_id,
    })

    # ============================================================
    # VERIFY: All artifacts have provenance metadata
    # ============================================================

    artifact_repo = ArtifactRepository(db)

    image = await artifact_repo.get_by_id(image_artifact_id)
    assert image.created_by_step_id == step1_id
    assert image.created_by_agent == "image_upload"

    text = await artifact_repo.get_by_id(text_artifact_id)
    assert text.created_by_step_id == step2_id
    assert text.created_by_agent == "story_generation"

    audio = await artifact_repo.get_by_id(audio_artifact_id)
    assert audio.created_by_step_id == step3_id
    assert audio.created_by_agent == "tts_generation"

    # ============================================================
    # VERIFY: Lineage chain (image → text → audio)
    # ============================================================

    relation_repo = ArtifactRelationRepository(db)

    # Audio lineage should include text and image as ancestors
    audio_lineage = await relation_repo.get_artifact_lineage(audio_artifact_id)
    assert audio_lineage.artifact_id == audio_artifact_id
    ancestor_ids = {a.artifact_id for a in audio_lineage.ancestors}
    assert text_artifact_id in ancestor_ids
    assert image_artifact_id in ancestor_ids
    assert len(audio_lineage.ancestors) >= 2

    # Image lineage should include text and audio as descendants
    image_lineage = await relation_repo.get_artifact_lineage(image_artifact_id)
    descendant_ids = {d.artifact_id for d in image_lineage.descendants}
    assert text_artifact_id in descendant_ids
    assert audio_artifact_id in descendant_ids

    # Relations should include both edges
    assert len(audio_lineage.relations) >= 2

    # ============================================================
    # VERIFY: Steps have duration_ms in output_data
    # ============================================================

    from src.services.database.artifact_repository import AgentStepRepository

    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 3

    for step in steps:
        assert step.output_data is not None
        assert "_duration_ms" in step.output_data
        assert isinstance(step.output_data["_duration_ms"], int)
        assert step.output_data["_duration_ms"] >= 0

    # ============================================================
    # VERIFY: Steps have provenance model/prompt_hash in input_data
    # ============================================================

    # Step 2 should have model and prompt hash
    step2 = [s for s in steps if s.step_name == "story_generation"][0]
    assert step2.input_data is not None
    assert "_provenance_model" in step2.input_data
    assert step2.input_data["_provenance_model"] == "claude-agent-sdk"
    assert "_provenance_prompt_hash" in step2.input_data
    assert len(step2.input_data["_provenance_prompt_hash"]) == 16

    # ============================================================
    # VERIFY: Run completed with summary
    # ============================================================

    from src.services.database.artifact_repository import RunRepository

    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "completed"
    assert run.started_at is not None
    assert run.completed_at is not None
    assert run.result_summary is not None
    assert run.result_summary["artifacts_created"] == 3


@pytest.mark.asyncio
async def test_failed_step_preserves_history(db):
    """
    Acceptance criterion: Failed/retried steps preserve history
    without mutating old artifacts.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)

    # Step 1: Succeed
    step1_id = await tracker.start_step(run_id, "image_upload", 1)
    image_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_path="./test.png",
        agent_name="upload",
    )
    await tracker.complete_step(step1_id, output_data={"artifact_id": image_id})

    # Step 2: Fail (TTS timeout)
    step2_id = await tracker.start_step(run_id, "tts_generation", 2)
    await tracker.complete_step(
        step2_id,
        error_message="TTS service timeout after 30s",
    )

    # Step 3: Retry TTS (new step, not mutation)
    step3_id = await tracker.start_step(run_id, "tts_generation_retry", 3)
    audio_id = await tracker.record_artifact(
        step3_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./test.mp3",
        agent_name="tts_retry",
        input_artifact_ids=[image_id],
    )
    await tracker.complete_step(step3_id, output_data={"artifact_id": audio_id})

    await tracker.complete_run(run_id)

    # Verify: All 3 steps exist
    from src.services.database.artifact_repository import AgentStepRepository

    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 3

    # Step 2 is failed with error
    failed = [s for s in steps if s.step_name == "tts_generation"][0]
    assert failed.status == "failed"
    assert failed.error_message == "TTS service timeout after 30s"

    # Step 3 succeeded
    retry = [s for s in steps if s.step_name == "tts_generation_retry"][0]
    assert retry.status == "completed"

    # Image artifact is untouched
    artifact_repo = ArtifactRepository(db)
    image = await artifact_repo.get_by_id(image_id)
    assert image.lifecycle_state == LifecycleState.INTERMEDIATE
    assert image.created_by_agent == "upload"


@pytest.mark.asyncio
async def test_publish_workflow_integration(db):
    """
    Integration test for Issue #18: Artifact publishing workflow.

    Simulates:
    1. Create artifacts (intermediate)
    2. Promote to candidate
    3. Publish (candidate → published) with story linking
    4. Verify curated story artifacts
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)
    artifact_repo = ArtifactRepository(db)
    link_repo = StoryArtifactLinkRepository(db)

    run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)

    # Create image artifact
    step1_id = await tracker.start_step(run_id, "upload", 1)
    image_id = await tracker.record_artifact(
        step1_id, ArtifactType.IMAGE, run_id=run_id,
        artifact_path="./test.png", agent_name="upload",
    )
    await tracker.complete_step(step1_id)

    # Create audio artifact
    step2_id = await tracker.start_step(run_id, "tts", 2)
    audio_id = await tracker.record_artifact(
        step2_id, ArtifactType.AUDIO, run_id=run_id,
        artifact_path="./test.mp3", agent_name="tts",
    )
    await tracker.complete_step(step2_id)

    # Promote to candidate
    await artifact_repo.update_lifecycle_state(image_id, "candidate")
    await artifact_repo.update_lifecycle_state(audio_id, "candidate")

    # Publish with story linking
    await tracker.publish_artifact(image_id, story_id, StoryArtifactRole.COVER)
    await tracker.publish_artifact(audio_id, story_id, StoryArtifactRole.FINAL_AUDIO)

    # Verify published state
    image = await artifact_repo.get_by_id(image_id)
    assert image.lifecycle_state == LifecycleState.PUBLISHED

    audio = await artifact_repo.get_by_id(audio_id)
    assert audio.lifecycle_state == LifecycleState.PUBLISHED

    # Verify story links
    cover = await link_repo.get_canonical_artifact(story_id, "cover")
    assert cover.artifact_id == image_id

    final_audio = await link_repo.get_canonical_artifact(story_id, "final_audio")
    assert final_audio.artifact_id == audio_id

    # Verify cannot publish intermediate directly
    step3_id = await tracker.start_step(run_id, "extra", 3)
    extra_id = await tracker.record_artifact(
        step3_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="draft", agent_name="test",
    )
    await tracker.complete_step(step3_id)

    with pytest.raises(ValueError, match="Only candidate artifacts can be published"):
        await tracker.publish_artifact(extra_id)

    # Verify cannot rollback published → candidate
    with pytest.raises(ValueError, match="Invalid state transition"):
        await artifact_repo.update_lifecycle_state(image_id, "candidate")
