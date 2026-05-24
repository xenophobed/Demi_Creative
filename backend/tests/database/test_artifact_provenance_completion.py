"""Focused coverage for issue #528 provenance completion gaps."""

import uuid
from datetime import datetime, timezone

import pytest

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.artifact_repository import (
    AgentStepRepository,
    ArtifactCharacterLinkRepository,
    ArtifactRepository,
    RunRepository,
    StoryArtifactLinkRepository,
)
from src.services.models.artifact_models import (
    ArtifactCharacterLinkCreate,
    ArtifactCreate,
    ArtifactMetadata,
    ArtifactType,
    LifecycleState,
    RunCreate,
    StoryArtifactRole,
    StoryArtifactLinkCreate,
    WorkflowType,
)
from src.services.provenance_tracker import ProvenanceTracker


@pytest.fixture
async def db(tmp_path):
    manager = DatabaseManager(db_path=str(tmp_path / "provenance_completion.db"))
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


async def create_test_story(db, *, story_id: str | None = None) -> str:
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


async def create_test_session(db, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db.execute(
        """
        INSERT INTO sessions (
            session_id, child_id, age_group, story_title, theme,
            created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, "child-1", "6-8", "Branching Tale", "space", now, now, now),
    )
    await db.commit()


async def create_test_character(db, character_name: str = "Luna") -> int:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db.execute(
        """
        INSERT INTO characters (
            user_id, child_id, name, description, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("user-1", "child-1", character_name, "A recurring friend", now, now),
    )
    await db.commit()
    row = await db.fetchone(
        "SELECT id FROM characters WHERE user_id = ? AND child_id = ? AND name = ?",
        ("user-1", "child-1", character_name),
    )
    return row["id"]


@pytest.mark.asyncio
async def test_interactive_session_run_can_exist_before_story_is_saved(db):
    """Branch text/audio provenance can be attached to a session-only run."""
    session_id = "session-before-save"
    await create_test_session(db, session_id)

    tracker = ProvenanceTracker(db)
    run_id = await tracker.start_run(
        None,
        WorkflowType.INTERACTIVE_STORY,
        session_id=session_id,
    )
    step_id = await tracker.start_step(run_id, "story_opening", 1)
    text_id = await tracker.record_artifact(
        step_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Luna found a glowing map.",
        agent_name="interactive_story",
        metadata=ArtifactMetadata(word_count=6),
    )
    audio_id = await tracker.record_artifact(
        step_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_url="/data/audio/branch.mp3",
        agent_name="tts_generation",
        input_artifact_ids=[text_id],
    )
    await tracker.complete_step(
        step_id,
        output_data={"text_artifact_id": text_id, "audio_artifact_id": audio_id},
    )

    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id)
    assert run.story_id is None
    assert run.session_id == session_id

    session_runs = await run_repo.list_by_session(session_id)
    assert [r.run_id for r in session_runs] == [run_id]

    artifacts = await ArtifactRepository(db).get_by_ids([text_id, audio_id])
    assert {a.created_by_step_id for a in artifacts} == {step_id}
    assert {a.artifact_type for a in artifacts} == {
        ArtifactType.TEXT,
        ArtifactType.AUDIO,
    }


@pytest.mark.asyncio
async def test_story_text_artifact_links_to_character_record(db):
    """Story text artifacts can be associated with known character records."""
    story_id = await create_test_story(db)
    character_id = await create_test_character(db)
    artifact_repo = ArtifactRepository(db)
    link_repo = ArtifactCharacterLinkRepository(db)

    text_id = await artifact_repo.create(
        ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Luna helped save the moon garden.",
            description="Story text",
        )
    )
    await artifact_repo.update_lifecycle_state(text_id, "candidate")
    await artifact_repo.update_lifecycle_state(text_id, "published")
    await StoryArtifactLinkRepository(db).upsert(
        StoryArtifactLinkCreate(
            story_id=story_id,
            artifact_id=text_id,
            role=StoryArtifactRole.STORY_TEXT,
        )
    )

    link_id = await link_repo.upsert(
        ArtifactCharacterLinkCreate(
            artifact_id=text_id,
            character_id=character_id,
            story_id=story_id,
            relationship="features",
            role="main_character",
        )
    )

    links = await link_repo.list_by_artifact(text_id)
    assert len(links) == 1
    assert links[0].link_id == link_id
    assert links[0].character_id == character_id
    assert links[0].relationship == "features"
    assert links[0].role == "main_character"


@pytest.mark.asyncio
async def test_kids_daily_script_image_and_audio_artifacts_publish_and_link(db):
    """Kids Daily visible outputs use published lifecycle with run/step lineage."""
    story_id = await create_test_story(db)
    tracker = ProvenanceTracker(db)
    run_id = await tracker.start_run(story_id, WorkflowType.KIDS_DAILY)

    script_step_id = await tracker.start_step(run_id, "dialogue_script", 1)
    script_id = await tracker.record_artifact(
        script_step_id,
        ArtifactType.TEXT,
        run_id=run_id,
        artifact_payload="Anchor: Today we explore coral reefs!",
        agent_name="kids_daily",
        metadata=ArtifactMetadata(custom={"script_format": "dialogue"}),
    )
    await tracker.complete_step(script_step_id, {"text_artifact_id": script_id})

    audio_step_id = await tracker.start_step(run_id, "audio_segments", 2)
    audio_id = await tracker.record_artifact(
        audio_step_id,
        ArtifactType.AUDIO,
        run_id=run_id,
        artifact_url="/data/audio/kids_daily_line_1.mp3",
        agent_name="tts_generation",
        input_artifact_ids=[script_id],
    )
    await tracker.complete_step(audio_step_id, {"audio_artifact_ids": [audio_id]})

    image_step_id = await tracker.start_step(run_id, "illustrations", 3)
    image_id = await tracker.record_artifact(
        image_step_id,
        ArtifactType.IMAGE,
        run_id=run_id,
        artifact_url="/data/uploads/kids_daily_reef.png",
        agent_name="illustration_generation",
        input_artifact_ids=[script_id],
    )
    await tracker.complete_step(image_step_id, {"image_artifact_ids": [image_id]})

    artifact_repo = ArtifactRepository(db)
    for artifact_id, role in [
        (script_id, StoryArtifactRole.STORY_TEXT),
        (audio_id, StoryArtifactRole.FINAL_AUDIO),
        (image_id, StoryArtifactRole.COVER),
    ]:
        await artifact_repo.update_lifecycle_state(artifact_id, "candidate")
        await tracker.publish_artifact(artifact_id, story_id, role)

    script = await artifact_repo.get_by_id(script_id)
    audio = await artifact_repo.get_by_id(audio_id)
    image = await artifact_repo.get_by_id(image_id)
    assert script.lifecycle_state == LifecycleState.PUBLISHED
    assert audio.lifecycle_state == LifecycleState.PUBLISHED
    assert image.lifecycle_state == LifecycleState.PUBLISHED

    steps = await AgentStepRepository(db).list_by_run(run_id)
    assert [step.step_name for step in steps] == [
        "dialogue_script",
        "audio_segments",
        "illustrations",
    ]
    assert all(step.completed_at is not None for step in steps)

    story_links = await StoryArtifactLinkRepository(db).list_by_story(story_id)
    assert {link.role for link in story_links} == {
        StoryArtifactRole.STORY_TEXT,
        StoryArtifactRole.FINAL_AUDIO,
        StoryArtifactRole.COVER,
    }
