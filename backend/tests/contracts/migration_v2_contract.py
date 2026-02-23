"""
Migration v2 Contract Tests

Defines expected behavior for the enhanced backfill migration:
- Per-record status tracking with resume/retry
- Checksum dedup to prevent duplicate artifacts
- File metadata population (mime_type, file_size)
- Migration report generation

These contracts are tested against real in-memory SQLite.
"""

import pytest
import uuid
import hashlib
from datetime import datetime, timezone

from src.services.database.connection import DatabaseManager
from src.services.database.schema import init_schema
from src.services.database.artifact_repository import (
    ArtifactRepository, MigrationStatusRepository
)
from src.services.models.artifact_models import (
    ArtifactCreate, ArtifactType, MigrationStatusEnum
)


@pytest.fixture
async def db(tmp_path):
    """Create in-memory test database with full schema"""
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path=db_path)
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


# ============================================================================
# Migration Status Tracking
# ============================================================================

class TestMigrationStatusTracking:
    """Contract: Per-record migration status with resume/retry"""

    @pytest.mark.asyncio
    async def test_create_migration_record(self, db):
        """Contract: upsert() creates a new migration status record"""
        repo = MigrationStatusRepository(db)

        migration_id = await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-001",
            status="in_progress",
        )

        assert isinstance(migration_id, str)
        assert len(migration_id) == 36  # UUID

        record = await repo.get("stories_to_artifacts_v2", "story", "story-001")
        assert record is not None
        assert record.status == MigrationStatusEnum.IN_PROGRESS
        assert record.retry_count == 0

    @pytest.mark.asyncio
    async def test_status_transitions(self, db):
        """Contract: Records transition pending → in_progress → completed/failed"""
        repo = MigrationStatusRepository(db)

        # Create with in_progress
        await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-002",
            status="in_progress",
        )

        # Transition to completed
        await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-002",
            status="completed",
            artifacts_created=3,
            links_created=2,
        )

        record = await repo.get("stories_to_artifacts_v2", "story", "story-002")
        assert record.status == MigrationStatusEnum.COMPLETED
        assert record.artifacts_created == 3
        assert record.links_created == 2
        assert record.completed_at is not None

    @pytest.mark.asyncio
    async def test_resume_skips_completed(self, db):
        """Contract: Completed records are skipped on resume"""
        repo = MigrationStatusRepository(db)

        # Mark as completed
        await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-003",
            status="completed",
            artifacts_created=2,
            links_created=1,
        )

        # Check: completed records not in pending/failed lists
        pending = await repo.list_by_status("stories_to_artifacts_v2", "pending")
        failed = await repo.list_failed("stories_to_artifacts_v2")
        assert all(r.source_id != "story-003" for r in pending)
        assert all(r.source_id != "story-003" for r in failed)

    @pytest.mark.asyncio
    async def test_retry_increments_count(self, db):
        """Contract: increment_retry() bumps retry_count and resets status"""
        repo = MigrationStatusRepository(db)

        await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-004",
            status="failed",
            error_message="Connection timeout",
        )

        success = await repo.increment_retry(
            "stories_to_artifacts_v2", "story", "story-004"
        )
        assert success is True

        record = await repo.get("stories_to_artifacts_v2", "story", "story-004")
        assert record.retry_count == 1
        assert record.status == MigrationStatusEnum.IN_PROGRESS
        assert record.error_message is None

    @pytest.mark.asyncio
    async def test_idempotent_upsert(self, db):
        """Contract: UNIQUE(migration_name, source_type, source_id) prevents duplicates"""
        repo = MigrationStatusRepository(db)

        id1 = await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-005",
            status="in_progress",
        )

        # Second upsert for same source updates instead of inserting
        id2 = await repo.upsert(
            migration_name="stories_to_artifacts_v2",
            source_type="story",
            source_id="story-005",
            status="completed",
            artifacts_created=2,
            links_created=1,
        )

        assert id1 == id2  # Same migration_id returned


# ============================================================================
# Checksum Dedup
# ============================================================================

class TestMigrationChecksumDedup:
    """Contract: Duplicate detection via content_hash"""

    @pytest.mark.asyncio
    async def test_duplicate_detection_by_hash(self, db):
        """Contract: get_by_content_hash() finds existing artifact"""
        repo = ArtifactRepository(db)

        text_content = "Once upon a time in a magical forest..."
        content_hash = hashlib.sha256(text_content.encode()).hexdigest()

        # Create artifact with payload (hash auto-computed)
        artifact_id = await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload=text_content,
            description="Story text"
        ))

        # Lookup by hash should find it
        existing = await repo.get_by_content_hash(content_hash)
        assert existing is not None
        assert existing.artifact_id == artifact_id

    @pytest.mark.asyncio
    async def test_no_false_positive_dedup(self, db):
        """Contract: Different content produces different hashes"""
        repo = ArtifactRepository(db)

        await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Story A"
        ))

        different_hash = hashlib.sha256("Story B".encode()).hexdigest()
        existing = await repo.get_by_content_hash(different_hash)
        assert existing is None  # No match


# ============================================================================
# File Metadata
# ============================================================================

class TestMigrationFileMetadata:
    """Contract: mime_type and file_size population"""

    @pytest.mark.asyncio
    async def test_create_artifact_with_metadata(self, db):
        """Contract: New columns stored and retrieved correctly"""
        repo = ArtifactRepository(db)

        artifact_id = await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.AUDIO,
            artifact_path="./data/audio/story.mp3",
            mime_type="audio/mpeg",
            file_size=1024000,
            safety_score=0.95,
            created_by_agent="story_agent",
        ))

        artifact = await repo.get_by_id(artifact_id)
        assert artifact.mime_type == "audio/mpeg"
        assert artifact.file_size == 1024000
        assert artifact.safety_score == 0.95
        assert artifact.created_by_agent == "story_agent"

    @pytest.mark.asyncio
    async def test_backward_compat_without_new_columns(self, db):
        """Contract: Artifacts without new columns still work"""
        repo = ArtifactRepository(db)

        artifact_id = await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Story text"
        ))

        artifact = await repo.get_by_id(artifact_id)
        assert artifact.mime_type is None
        assert artifact.file_size is None
        assert artifact.safety_score is None
        assert artifact.created_by_agent is None

    @pytest.mark.asyncio
    async def test_list_safety_flagged(self, db):
        """Contract: list_safety_flagged() returns low-score artifacts"""
        repo = ArtifactRepository(db)

        # Create artifacts with different safety scores
        await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Safe content",
            safety_score=0.95,
        ))
        flagged_id = await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="Flagged content",
            safety_score=0.60,
        ))

        flagged = await repo.list_safety_flagged()
        assert len(flagged) == 1
        assert flagged[0].artifact_id == flagged_id
        assert flagged[0].safety_score == 0.60

    @pytest.mark.asyncio
    async def test_list_by_type_and_state(self, db):
        """Contract: list_by_type_and_state() uses compound index"""
        repo = ArtifactRepository(db)

        await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.AUDIO,
            artifact_path="./audio1.mp3"
        ))
        await repo.create(ArtifactCreate(
            artifact_type=ArtifactType.TEXT,
            artifact_payload="text"
        ))

        results = await repo.list_by_type_and_state("audio", "intermediate")
        assert len(results) == 1
        assert results[0].artifact_type.value == "audio"


# ============================================================================
# Migration Report
# ============================================================================

class TestMigrationReport:
    """Contract: Migration report generation"""

    @pytest.mark.asyncio
    async def test_report_success_rate(self, db):
        """Contract: Report calculates correct success rate"""
        repo = MigrationStatusRepository(db)

        # Create mixed results
        for i in range(7):
            await repo.upsert(
                migration_name="test_migration",
                source_type="story",
                source_id=f"story-{i}",
                status="completed",
                artifacts_created=2,
                links_created=1,
            )

        for i in range(3):
            await repo.upsert(
                migration_name="test_migration",
                source_type="story",
                source_id=f"story-fail-{i}",
                status="failed",
                error_message=f"Error {i}",
            )

        report = await repo.get_report("test_migration")
        assert report.total_records == 10
        assert report.completed == 7
        assert report.failed == 3
        assert report.success_rate == pytest.approx(0.7)
        assert report.total_artifacts_created == 14
        assert report.total_links_created == 7

    @pytest.mark.asyncio
    async def test_report_unresolved_records(self, db):
        """Contract: Report lists failed/pending records"""
        repo = MigrationStatusRepository(db)

        await repo.upsert(
            migration_name="test_migration",
            source_type="story",
            source_id="story-ok",
            status="completed",
        )
        await repo.upsert(
            migration_name="test_migration",
            source_type="story",
            source_id="story-fail",
            status="failed",
            error_message="DB error",
        )

        report = await repo.get_report("test_migration")
        assert len(report.unresolved_records) == 1
        assert report.unresolved_records[0].source_id == "story-fail"
        assert report.unresolved_records[0].error_message == "DB error"
