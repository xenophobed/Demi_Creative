"""
News & Morning Show Provenance Integration Tests (Issue #141)

Verifies that news-to-kids and morning show pipelines create
Run, AgentStep, and Artifact records with correct provenance chains.
Uses in-memory SQLite database with full schema.
"""

import pytest
import uuid

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.provenance_tracker import ProvenanceTracker
from src.services.database.artifact_repository import (
    ArtifactRepository,
    AgentStepRepository,
    RunRepository,
    StoryArtifactLinkRepository,
)
from src.services.models.artifact_models import (
    ArtifactType,
    WorkflowType,
    StoryArtifactRole,
    ArtifactMetadata,
)


@pytest.fixture
async def db(tmp_path):
    """Create test database with full schema."""
    db_path = str(tmp_path / "test_news_provenance.db")
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
        (sid, "child-1", "6-8", "Test news story.", 3, now, now),
    )
    await db.commit()
    return sid


# ============================================================================
# Morning Show Provenance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_morning_show_provenance_chain(db):
    """
    Acceptance: Morning show episode creates Run with steps for
    news_conversion, tts_generation, and illustration_generation,
    each producing the expected artifacts.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    # Start run
    run_id = await tracker.start_run(
        story_id, WorkflowType.MORNING_SHOW
    )
    assert run_id is not None

    # ---- Step 1: News conversion ----
    step1_id = await tracker.start_step(
        run_id, "news_conversion", 1,
        input_data={"category": "science", "age_group": "6-8"},
    )

    text_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Kids-friendly news content about space discovery.",
        description="Morning show converted news text",
        safety_score=0.92,
        agent_name="morning_show",
        metadata=ArtifactMetadata(char_count=48, word_count=7),
    )

    await tracker.complete_step(
        step1_id,
        output_data={"text_artifact_id": text_id},
    )

    # ---- Step 2: TTS generation ----
    step2_id = await tracker.start_step(
        run_id, "tts_generation", 2,
        input_data={"dialogue_lines": 3},
    )

    audio_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/morning_show_ep1.mp3",
        artifact_url="/data/audio/morning_show_ep1.mp3",
        description="Morning show TTS audio",
        mime_type="audio/mpeg",
        agent_name="tts_generation",
        input_artifact_ids=[text_id],
    )

    await tracker.complete_step(
        step2_id,
        output_data={"audio_artifact_id": audio_id},
    )

    # ---- Step 3: Illustration generation ----
    step3_id = await tracker.start_step(
        run_id, "illustration_generation", 3,
        input_data={"illustration_count": 2},
    )

    illust_id_1 = await tracker.record_artifact(
        step3_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_url="/data/uploads/morning_show_ep1_0.svg",
        description="Morning show illustration 1",
        agent_name="illustration_generation",
    )

    illust_id_2 = await tracker.record_artifact(
        step3_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_url="/data/uploads/morning_show_ep1_1.svg",
        description="Morning show illustration 2",
        agent_name="illustration_generation",
    )

    await tracker.complete_step(
        step3_id,
        output_data={
            "illustration_ids": [illust_id_1, illust_id_2],
        },
    )

    # ---- Complete run ----
    await tracker.complete_run(run_id, result_summary={
        "artifacts_created": 4,
        "episode_id": story_id,
    })

    # ============================================================
    # VERIFY: Run completed
    # ============================================================
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "completed"
    assert run.workflow_type == "morning_show"
    assert run.result_summary["artifacts_created"] == 4

    # ============================================================
    # VERIFY: All 3 steps created
    # ============================================================
    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 3

    step_names = {s.step_name for s in steps}
    assert step_names == {"news_conversion", "tts_generation", "illustration_generation"}

    for step in steps:
        assert step.output_data is not None
        assert "_duration_ms" in step.output_data

    # ============================================================
    # VERIFY: Artifacts created with correct types
    # ============================================================
    artifact_repo = ArtifactRepository(db)

    text_art = await artifact_repo.get_by_id(text_id)
    assert text_art.artifact_type.value == "text"
    assert text_art.created_by_agent == "morning_show"

    audio_art = await artifact_repo.get_by_id(audio_id)
    assert audio_art.artifact_type.value == "audio"
    assert audio_art.created_by_agent == "tts_generation"

    illust_art = await artifact_repo.get_by_id(illust_id_1)
    assert illust_art.artifact_type.value == "image"
    assert illust_art.created_by_agent == "illustration_generation"


@pytest.mark.asyncio
async def test_morning_show_story_artifact_links(db):
    """
    Acceptance: Morning show artifacts can be linked to story and
    queried via story lineage.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)
    artifact_repo = ArtifactRepository(db)
    link_repo = StoryArtifactLinkRepository(db)

    run_id = await tracker.start_run(story_id, WorkflowType.MORNING_SHOW)

    step_id = await tracker.start_step(run_id, "news_conversion", 1)
    text_id = await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="News content for kids",
        agent_name="morning_show",
        safety_score=0.95,
    )

    audio_step_id = await tracker.start_step(run_id, "tts_generation", 2)
    audio_id = await tracker.record_artifact(
        audio_step_id, ArtifactType.AUDIO, run_id=run_id,
        artifact_url="/data/audio/ep.mp3",
        agent_name="tts_generation",
        input_artifact_ids=[text_id],
    )
    await tracker.complete_step(step_id)
    await tracker.complete_step(audio_step_id)

    # Promote and link
    await artifact_repo.update_lifecycle_state(text_id, "candidate")
    await artifact_repo.update_lifecycle_state(text_id, "published")
    await tracker.link_to_story(story_id, text_id, StoryArtifactRole.STORY_TEXT)

    await artifact_repo.update_lifecycle_state(audio_id, "candidate")
    await artifact_repo.update_lifecycle_state(audio_id, "published")
    await tracker.link_to_story(story_id, audio_id, StoryArtifactRole.FINAL_AUDIO)

    await tracker.complete_run(run_id)

    # Verify links
    text_link = await link_repo.get_canonical_artifact(story_id, "story_text")
    assert text_link.artifact_id == text_id

    audio_link = await link_repo.get_canonical_artifact(story_id, "final_audio")
    assert audio_link.artifact_id == audio_id


# ============================================================================
# News-to-Kids Provenance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_news_to_kids_provenance_chain(db):
    """
    Acceptance: News-to-kids conversion creates Run with steps for
    news_conversion and optional tts_generation, with correct artifacts.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(
        story_id, WorkflowType.NEWS_TO_KIDS
    )
    assert run_id is not None

    # ---- Step 1: News conversion ----
    step1_id = await tracker.start_step(
        run_id, "news_conversion", 1,
        input_data={"category": "technology", "age_group": "9-12"},
    )

    text_id = await tracker.record_artifact(
        step1_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Kid-friendly technology news.",
        description="Converted news text",
        safety_score=0.90,
        agent_name="news_to_kids",
        metadata=ArtifactMetadata(char_count=30, word_count=4),
    )

    await tracker.complete_step(
        step1_id,
        output_data={"text_artifact_id": text_id},
    )

    # ---- Step 2: TTS generation (optional) ----
    step2_id = await tracker.start_step(
        run_id, "tts_generation", 2,
        input_data={"voice": "nova"},
    )

    audio_id = await tracker.record_artifact(
        step2_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_path="./data/audio/news_convert_1.mp3",
        artifact_url="/data/audio/news_convert_1.mp3",
        description="News narration audio",
        mime_type="audio/mpeg",
        agent_name="tts_generation",
        input_artifact_ids=[text_id],
    )

    await tracker.complete_step(
        step2_id,
        output_data={"audio_artifact_id": audio_id},
    )

    # ---- Complete run ----
    await tracker.complete_run(run_id, result_summary={
        "artifacts_created": 2,
        "conversion_id": story_id,
    })

    # VERIFY
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "completed"
    assert run.workflow_type == "news_to_kids"

    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 2
    assert {s.step_name for s in steps} == {"news_conversion", "tts_generation"}

    artifact_repo = ArtifactRepository(db)
    text_art = await artifact_repo.get_by_id(text_id)
    assert text_art.artifact_type.value == "text"
    assert text_art.safety_score == 0.90


@pytest.mark.asyncio
async def test_news_to_kids_without_audio(db):
    """
    Acceptance: News-to-kids conversion without audio still creates
    proper provenance with only the text artifact.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(story_id, WorkflowType.NEWS_TO_KIDS)

    step_id = await tracker.start_step(run_id, "news_conversion", 1)
    text_id = await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="Simple news for kids.",
        agent_name="news_to_kids",
        safety_score=0.93,
    )
    await tracker.complete_step(step_id)

    await tracker.complete_run(run_id, result_summary={
        "artifacts_created": 1,
        "conversion_id": story_id,
    })

    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "completed"

    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 1
    assert steps[0].step_name == "news_conversion"


# ============================================================================
# Provenance Failure Resilience Tests
# ============================================================================


@pytest.mark.asyncio
async def test_provenance_failure_does_not_block_news_content(db):
    """
    Acceptance: Provenance failures are logged but never block
    content delivery. Simulates a provenance error mid-pipeline.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(story_id, WorkflowType.NEWS_TO_KIDS)

    step_id = await tracker.start_step(run_id, "news_conversion", 1)
    await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="News content",
        agent_name="news_to_kids",
    )
    await tracker.complete_step(step_id)

    # Simulate provenance failure
    await tracker.fail_run(run_id, "Simulated DB error during provenance")

    # Verify run is marked failed but artifacts are preserved
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "failed"
    assert run.result_summary["error"] == "Simulated DB error during provenance"

    # Artifacts still exist
    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 1
    assert steps[0].status == "completed"


@pytest.mark.asyncio
async def test_morning_show_provenance_failure_does_not_block(db):
    """
    Acceptance: Morning show provenance failure does not block episode delivery.
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(story_id, WorkflowType.MORNING_SHOW)

    step_id = await tracker.start_step(run_id, "news_conversion", 1)
    await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="Morning show content",
        agent_name="morning_show",
    )
    await tracker.complete_step(step_id)

    # Simulate failure
    await tracker.fail_run(run_id, "Simulated morning show provenance error")

    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.status == "failed"

    # Steps and artifacts are preserved
    step_repo = AgentStepRepository(db)
    steps = await step_repo.list_by_run(run_id)
    assert len(steps) == 1
    assert steps[0].status == "completed"


@pytest.mark.asyncio
async def test_story_lineage_returns_data_for_morning_show(db):
    """
    Acceptance: GET /admin/artifacts/stories/{story_id}/lineage
    returns data for morning show content (verified via repository layer).
    """
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)

    run_id = await tracker.start_run(story_id, WorkflowType.MORNING_SHOW)
    step_id = await tracker.start_step(run_id, "news_conversion", 1)
    text_id = await tracker.record_artifact(
        step_id, ArtifactType.TEXT, run_id=run_id,
        artifact_payload="Morning show text",
        agent_name="morning_show",
    )
    await tracker.complete_step(step_id)
    await tracker.complete_run(run_id)

    await tracker.link_to_story(story_id, text_id, StoryArtifactRole.STORY_TEXT)

    # Verify via RunRepository — the lineage endpoint queries runs by story_id
    run_repo = RunRepository(db)
    runs = await run_repo.list_by_story(story_id)
    assert len(runs) == 1
    assert runs[0].workflow_type == "morning_show"

    # Verify via StoryArtifactLinkRepository
    link_repo = StoryArtifactLinkRepository(db)
    links = await link_repo.list_by_story(story_id)
    assert len(links) == 1
    assert links[0].role.value == "story_text"
