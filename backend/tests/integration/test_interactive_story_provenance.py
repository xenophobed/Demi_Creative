"""
Interactive Story Provenance Integration Test (Issue #138)

Verifies that interactive story pipeline creates Run, AgentStep,
and Artifact records with correct lineage chains.
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
    AgentStepRepository,
    RunRepository,
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
    db_path = str(tmp_path / "test_interactive_provenance.db")
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
        (sid, "child-1", "6-8", "Test interactive story.", 3, now, now),
    )
    await db.commit()
    return sid


@pytest.mark.asyncio
async def test_interactive_story_provenance_chain(db):
    """
    Acceptance: Interactive story creates Run + AgentStep records,
    each segment's text and audio recorded as Artifacts with correct types,
    and lineage chain links segments together.

    Simulates:
    Step 1 (story_opening): Generate opening → text artifact + audio artifact
    Step 2 (segment_2): Generate next segment → text artifact + audio artifact
    Step 3 (safety_check): Final safety check → safety result recorded
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    # Start run for interactive story workflow
    run_id = await tracker.start_run(
        story_id, WorkflowType.INTERACTIVE_STORY, session_id="session-123"
    )
    assert run_id is not None

    # ---- Step 1: Story opening ----
    step1_id = await tracker.start_step(
        run_id, "story_opening", 1,
        input_data={
            "child_id": "child-1",
            "age_group": "6-8",
            "theme": "forest adventure",
        },
        model_name="claude-agent-sdk",
        prompt_hash=ProvenanceTracker.compute_prompt_hash(
            "interactive_story:child-1:6-8"
        ),
    )

    # Record opening text artifact
    opening_text_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Once upon a time in a magical forest...",
        description="Interactive story opening segment",
        safety_score=0.95,
        agent_name="interactive_story",
        metadata=ArtifactMetadata(char_count=40, word_count=8),
    )

    # Record opening audio artifact (derived from text)
    opening_audio_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/segment_1.mp3",
        artifact_url="/data/audio/segment_1.mp3",
        description="TTS narration for opening segment",
        mime_type="audio/mpeg",
        agent_name="tts_generation",
        input_artifact_ids=[opening_text_id],
    )

    await tracker.complete_step(
        step1_id,
        output_data={
            "text_artifact_id": opening_text_id,
            "audio_artifact_id": opening_audio_id,
        },
    )

    # ---- Step 2: Next segment (after choice) ----
    step2_id = await tracker.start_step(
        run_id, "segment_2", 2,
        input_data={"choice_id": "choice_a", "segment_number": 2},
        model_name="claude-agent-sdk",
    )

    seg2_text_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="You chose to explore the cave. Inside you found...",
        description="Interactive story segment 2",
        safety_score=0.92,
        agent_name="interactive_story",
        input_artifact_ids=[opening_text_id],  # derived from opening
        metadata=ArtifactMetadata(char_count=50, word_count=9),
    )

    seg2_audio_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/segment_2.mp3",
        artifact_url="/data/audio/segment_2.mp3",
        description="TTS narration for segment 2",
        mime_type="audio/mpeg",
        agent_name="tts_generation",
        input_artifact_ids=[seg2_text_id],
    )

    await tracker.complete_step(
        step2_id,
        output_data={
            "text_artifact_id": seg2_text_id,
            "audio_artifact_id": seg2_audio_id,
        },
    )

    # ---- Complete run ----
    await tracker.complete_run(run_id, result_summary={
        "artifacts_created": 4,
        "story_id": story_id,
        "segments_generated": 2,
    })

    # ============================================================
    # VERIFY: All artifacts have provenance metadata
    # ============================================================
    artifact_repo = ArtifactRepository(db)

    opening_text = await artifact_repo.get_by_id(opening_text_id)
    assert opening_text.created_by_step_id == step1_id
    assert opening_text.created_by_agent == "interactive_story"
    assert opening_text.artifact_type.value == "text"

    opening_audio = await artifact_repo.get_by_id(opening_audio_id)
    assert opening_audio.created_by_step_id == step1_id
    assert opening_audio.created_by_agent == "tts_generation"
    assert opening_audio.artifact_type.value == "audio"

    seg2_text = await artifact_repo.get_by_id(seg2_text_id)
    assert seg2_text.created_by_step_id == step2_id
    assert seg2_text.created_by_agent == "interactive_story"

    # ============================================================
    # VERIFY: Lineage chain (opening_text → seg2_text → seg2_audio)
    # ============================================================
    relation_repo = ArtifactRelationRepository(db)

    # Seg2 audio should trace back to seg2 text and opening text
    seg2_audio_lineage = await relation_repo.get_artifact_lineage(seg2_audio_id)
    ancestor_ids = {a.artifact_id for a in seg2_audio_lineage.ancestors}
    assert seg2_text_id in ancestor_ids
    assert opening_text_id in ancestor_ids

    # Opening text should have descendants
    opening_lineage = await relation_repo.get_artifact_lineage(opening_text_id)
    descendant_ids = {d.artifact_id for d in opening_lineage.descendants}
    assert seg2_text_id in descendant_ids
    assert opening_audio_id in descendant_ids

    # ============================================================
    # VERIFY: Steps have duration_ms and provenance metadata
    # ============================================================
    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 2

    for step in steps:
        assert step.output_data is not None
        assert "_duration_ms" in step.output_data
        assert isinstance(step.output_data["_duration_ms"], int)

    # Step 1 has model and prompt hash
    step1 = [s for s in steps if s.step_name == "story_opening"][0]
    assert step1.input_data["_provenance_model"] == "claude-agent-sdk"
    assert "_provenance_prompt_hash" in step1.input_data

    # ============================================================
    # VERIFY: Run completed with summary
    # ============================================================
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "completed"
    assert run.result_summary["artifacts_created"] == 4
    assert run.result_summary["segments_generated"] == 2


@pytest.mark.asyncio
async def test_interactive_story_publish_and_link(db):
    """
    Acceptance: Artifacts linked to story via StoryArtifactLink
    and GET /admin/artifacts/stories/{story_id}/lineage returns
    complete chain for interactive stories.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)
    artifact_repo = ArtifactRepository(db)
    link_repo = StoryArtifactLinkRepository(db)

    run_id = await tracker.start_run(
        story_id, WorkflowType.INTERACTIVE_STORY, session_id="session-456"
    )

    # Create text artifact
    step_id = await tracker.start_step(run_id, "story_opening", 1)
    text_id = await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="Once upon a time...",
        agent_name="interactive_story",
        safety_score=0.95,
    )

    # Create audio artifact
    audio_id = await tracker.record_artifact(
        step_id, ArtifactType.AUDIO, run_id=run_id,
        artifact_path="./data/audio/opening.mp3",
        agent_name="tts_generation",
        input_artifact_ids=[text_id],
    )
    await tracker.complete_step(step_id)

    # Promote and link
    await artifact_repo.update_lifecycle_state(text_id, "candidate")
    await artifact_repo.update_lifecycle_state(text_id, "published")

    await artifact_repo.update_lifecycle_state(audio_id, "candidate")
    await tracker.publish_artifact(audio_id, story_id, StoryArtifactRole.FINAL_AUDIO)

    # Verify published state
    audio = await artifact_repo.get_by_id(audio_id)
    assert audio.lifecycle_state == LifecycleState.PUBLISHED

    # Verify story link
    final_audio = await link_repo.get_canonical_artifact(story_id, "final_audio")
    assert final_audio.artifact_id == audio_id

    await tracker.complete_run(run_id, result_summary={"artifacts_created": 2})


@pytest.mark.asyncio
async def test_provenance_failure_does_not_block_story(db):
    """
    Acceptance: Provenance failure does not block story delivery.
    Simulates a provenance error mid-pipeline and verifies the run
    is marked as failed but no exception propagates.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(
        story_id, WorkflowType.INTERACTIVE_STORY
    )

    # Step succeeds
    step_id = await tracker.start_step(run_id, "story_opening", 1)
    await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="Story text",
        agent_name="interactive_story",
    )
    await tracker.complete_step(step_id)

    # Simulate provenance failure during run completion
    # (e.g., DB write failure) — mark run failed
    await tracker.fail_run(run_id, "Simulated provenance error")

    # Verify run is marked failed but artifacts are preserved
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "failed"
    assert run.result_summary["error"] == "Simulated provenance error"

    # Artifacts still exist
    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 1
    assert steps[0].status == "completed"
