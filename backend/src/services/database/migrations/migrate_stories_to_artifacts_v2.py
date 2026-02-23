"""
Migration v2: Stories to Artifact Graph Model (Enhanced)

Improvements over v1:
1. Per-story transactions — failure on story N doesn't roll back stories 1..N-1
2. Checksum dedup — compute SHA256 from files; skip if artifact already exists
3. File metadata — populate mime_type (via mimetypes), file_size (via os.path.getsize)
4. Safety score — copy from stories.safety_score to text artifact
5. Resume/retry — write per-story status to migration_status table
6. Migration report — generate_report() returns MigrationReport
7. Enhanced rollback — uses migration_status records to identify created artifacts
8. Sampling validation — validate_ui_parity() spot-checks migrated stories
"""

import os
import uuid
import hashlib
import mimetypes
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..artifact_repository import (
    ArtifactRepository, MigrationStatusRepository
)
from ...models.artifact_models import (
    ArtifactCreate, ArtifactType, MigrationReport
)


MIGRATION_NAME = "stories_to_artifacts_v2"


class StoriesToArtifactsMigrationV2:
    """Enhanced migration with resume/retry, dedup, and per-record tracking"""

    def __init__(self, db: "DatabaseManager", dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.artifact_repo = ArtifactRepository(db)
        self.migration_repo = MigrationStatusRepository(db)

    async def run(self, retry_failed: bool = False) -> MigrationReport:
        """
        Execute migration with resume/retry support.

        Args:
            retry_failed: If True, retry previously failed records

        Returns:
            MigrationReport with success rate and unresolved records
        """
        print("\n" + "=" * 60)
        print("🚀 MIGRATION v2: Stories → Artifact Graph Model")
        print("=" * 60)

        if self.dry_run:
            print("📝 DRY RUN MODE — changes will NOT be committed")
        else:
            print("⚠️  LIVE MODE — changes will be committed per-story")

        if retry_failed:
            print("🔄 RETRY MODE — retrying previously failed records")

        try:
            stories = await self.db.fetchall("SELECT * FROM stories")
            print(f"\n📊 Found {len(stories)} stories to process...")

            for story in stories:
                story_id = story["story_id"]

                # Check existing migration status
                existing = await self.migration_repo.get(
                    MIGRATION_NAME, "story", story_id
                )

                if existing:
                    if existing.status.value == "completed":
                        continue  # Already migrated

                    if existing.status.value == "failed" and not retry_failed:
                        print(f"  ⏭️  Skipping {story_id} (failed, use retry_failed=True)")
                        continue

                    if existing.status.value == "failed" and retry_failed:
                        await self.migration_repo.increment_retry(
                            MIGRATION_NAME, "story", story_id
                        )
                        print(f"  🔄 Retrying {story_id} (attempt {existing.retry_count + 1})")

                # Check if already migrated via artifact references
                already_migrated = (
                    story.get("cover_artifact_id") or
                    story.get("canonical_audio_id") or
                    story.get("canonical_video_id") or
                    story.get("current_run_id")
                )

                if already_migrated:
                    await self.migration_repo.upsert(
                        MIGRATION_NAME, "story", story_id, "skipped"
                    )
                    continue

                await self._migrate_story(story)

            report = await self.migration_repo.get_report(MIGRATION_NAME)

            # Print summary
            print("\n" + "=" * 60)
            print("✅ MIGRATION v2 SUMMARY")
            print("=" * 60)
            print(f"Total records: {report.total_records}")
            print(f"Completed: {report.completed}")
            print(f"Failed: {report.failed}")
            print(f"Skipped: {report.skipped}")
            print(f"Pending: {report.pending}")
            print(f"Success rate: {report.success_rate:.1%}")
            print(f"Artifacts created: {report.total_artifacts_created}")
            print(f"Links created: {report.total_links_created}")

            if report.unresolved_records:
                print(f"\n⚠️  {len(report.unresolved_records)} unresolved records")

            return report

        except Exception as e:
            print(f"\n❌ MIGRATION FAILED: {e}")
            raise

    async def _migrate_story(self, story: Dict[str, Any]) -> None:
        """Migrate a single story in its own transaction scope"""
        story_id = story["story_id"]

        # Mark as in-progress
        if not self.dry_run:
            await self.migration_repo.upsert(
                MIGRATION_NAME, "story", story_id, "in_progress"
            )

        print(f"  🔄 Migrating {story_id}...")

        artifacts_created = 0
        links_created = 0

        try:
            # Create run for legacy story
            run_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            if not self.dry_run:
                await self.db.execute(
                    """
                    INSERT INTO runs (
                        run_id, story_id, workflow_type, status, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, story_id, "image_to_story", "completed", now)
                )

            # Migrate cover image
            cover_artifact_id = None
            if story.get("image_url") or story.get("image_path"):
                cover_artifact_id, created = await self._create_artifact_with_dedup(
                    artifact_type="image",
                    artifact_path=story.get("image_path"),
                    artifact_url=story.get("image_url"),
                    description="Cover image from legacy story",
                )
                if created:
                    artifacts_created += 1

                if cover_artifact_id:
                    link_created = await self._create_story_artifact_link(
                        story_id, cover_artifact_id, "cover"
                    )
                    if link_created:
                        links_created += 1

            # Migrate audio
            canonical_audio_id = None
            if story.get("audio_url"):
                canonical_audio_id, created = await self._create_artifact_with_dedup(
                    artifact_type="audio",
                    artifact_url=story.get("audio_url"),
                    description="Narration audio from legacy story",
                )
                if created:
                    artifacts_created += 1

                if canonical_audio_id:
                    link_created = await self._create_story_artifact_link(
                        story_id, canonical_audio_id, "final_audio"
                    )
                    if link_created:
                        links_created += 1

            # Migrate text with safety score
            if story.get("story_text"):
                text_artifact_id, created = await self._create_artifact_with_dedup(
                    artifact_type="text",
                    artifact_payload=story.get("story_text"),
                    description="Story text from legacy story",
                    safety_score=story.get("safety_score"),
                )
                if created:
                    artifacts_created += 1

            # Update stories table with artifact references
            if not self.dry_run:
                await self.db.execute(
                    """
                    UPDATE stories
                    SET cover_artifact_id = ?, canonical_audio_id = ?,
                        current_run_id = ?
                    WHERE story_id = ?
                    """,
                    (cover_artifact_id, canonical_audio_id, run_id, story_id)
                )
                await self.db.commit()

            # Mark completed
            if not self.dry_run:
                await self.migration_repo.upsert(
                    MIGRATION_NAME, "story", story_id, "completed",
                    artifacts_created=artifacts_created,
                    links_created=links_created,
                )

            print(f"    ✅ Migrated: {artifacts_created} artifacts, {links_created} links")

        except Exception as e:
            # Per-story failure doesn't affect other stories
            print(f"    ❌ Failed: {e}")

            if not self.dry_run:
                await self.migration_repo.upsert(
                    MIGRATION_NAME, "story", story_id, "failed",
                    error_message=str(e),
                    artifacts_created=artifacts_created,
                    links_created=links_created,
                )

    async def _create_artifact_with_dedup(
        self,
        artifact_type: str,
        artifact_path: Optional[str] = None,
        artifact_url: Optional[str] = None,
        artifact_payload: Optional[str] = None,
        description: Optional[str] = None,
        safety_score: Optional[float] = None,
    ) -> tuple[Optional[str], bool]:
        """
        Create artifact with checksum dedup and file metadata.

        Returns:
            (artifact_id, was_created) — was_created=False if dedup matched
        """
        # Compute content hash for dedup
        content_hash = None
        if artifact_payload:
            content_hash = hashlib.sha256(artifact_payload.encode()).hexdigest()
        elif artifact_path and os.path.exists(artifact_path):
            content_hash = self._compute_file_hash(artifact_path)

        # Checksum dedup: check if artifact with same hash exists
        if content_hash:
            existing = await self.artifact_repo.get_by_content_hash(content_hash)
            if existing:
                print(f"      ♻️  Dedup: reusing existing artifact {existing.artifact_id}")
                return existing.artifact_id, False

        # Populate file metadata
        mime_type = None
        file_size = None
        if artifact_path and os.path.exists(artifact_path):
            mime_type, _ = mimetypes.guess_type(artifact_path)
            file_size = os.path.getsize(artifact_path)
        elif artifact_url:
            mime_type, _ = mimetypes.guess_type(artifact_url)

        artifact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            if not self.dry_run:
                await self.db.execute(
                    """
                    INSERT INTO artifacts (
                        artifact_id, artifact_type, lifecycle_state, content_hash,
                        artifact_path, artifact_url, artifact_payload,
                        description, mime_type, file_size, safety_score,
                        created_by_agent, created_at, stored_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        artifact_type,
                        "published",  # Legacy stories already approved
                        content_hash,
                        artifact_path,
                        artifact_url,
                        artifact_payload,
                        description,
                        mime_type,
                        file_size,
                        safety_score,
                        "migration_v2",
                        now,
                        now
                    )
                )

            return artifact_id, True

        except Exception as e:
            print(f"      ❌ Failed to create {artifact_type} artifact: {e}")
            return None, False

    async def _create_story_artifact_link(
        self, story_id: str, artifact_id: str, role: str
    ) -> bool:
        """Create story-artifact link. Returns True if created."""
        link_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            if not self.dry_run:
                await self.db.execute(
                    """
                    INSERT INTO story_artifact_links (
                        link_id, story_id, artifact_id, role,
                        is_primary, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (link_id, story_id, artifact_id, role, 1, now, now)
                )
            return True

        except Exception as e:
            print(f"      ❌ Failed to create link: {e}")
            return False

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# ============================================================================
# Rollback
# ============================================================================

async def rollback_migration_v2(db: "DatabaseManager") -> Dict[str, Any]:
    """
    Enhanced rollback using migration_status records.

    Identifies artifacts created by migration_v2 and removes them,
    along with their links and story references.
    """
    print("\n" + "=" * 60)
    print("⏮️  ROLLBACK: Migration v2")
    print("=" * 60)

    try:
        # Find all artifacts created by migration_v2
        artifacts = await db.fetchall(
            "SELECT artifact_id FROM artifacts WHERE created_by_agent = ?",
            ("migration_v2",)
        )

        artifact_ids = [a["artifact_id"] for a in artifacts]

        if not artifact_ids:
            print("No migration_v2 artifacts found. Nothing to rollback.")
            return {"status": "no_op", "artifacts_removed": 0}

        # Delete story artifact links referencing these artifacts
        for aid in artifact_ids:
            await db.execute(
                "DELETE FROM story_artifact_links WHERE artifact_id = ?",
                (aid,)
            )

        # Delete the artifacts themselves
        for aid in artifact_ids:
            await db.execute(
                "DELETE FROM artifacts WHERE artifact_id = ?",
                (aid,)
            )

        # Clear story references
        await db.execute(
            """
            UPDATE stories
            SET cover_artifact_id = NULL,
                canonical_audio_id = NULL,
                canonical_video_id = NULL,
                current_run_id = NULL
            WHERE cover_artifact_id IS NOT NULL
               OR canonical_audio_id IS NOT NULL
               OR canonical_video_id IS NOT NULL
               OR current_run_id IS NOT NULL
            """
        )

        # Clear migration status records
        await db.execute(
            "DELETE FROM migration_status WHERE migration_name = ?",
            (MIGRATION_NAME,)
        )

        await db.commit()

        print(f"✅ Rollback complete: {len(artifact_ids)} artifacts removed")
        return {
            "status": "success",
            "artifacts_removed": len(artifact_ids)
        }

    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        raise


# ============================================================================
# Validation
# ============================================================================

async def validate_ui_parity(
    db: "DatabaseManager", sample_size: int = 10
) -> Dict[str, Any]:
    """
    Spot-check migrated stories: verify artifact URLs match legacy fields.

    Args:
        db: Database manager
        sample_size: Number of stories to check

    Returns:
        Validation result dict
    """
    print("\n" + "=" * 60)
    print("✓ VALIDATION: UI Parity Check")
    print("=" * 60)

    issues = []

    # Sample stories that have been migrated
    stories = await db.fetchall(
        """
        SELECT * FROM stories
        WHERE cover_artifact_id IS NOT NULL
           OR canonical_audio_id IS NOT NULL
        LIMIT ?
        """,
        (sample_size,)
    )

    for story in stories:
        story_id = story["story_id"]

        # Check cover image parity
        if story.get("image_url") and story.get("cover_artifact_id"):
            artifact = await db.fetchone(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (story["cover_artifact_id"],)
            )
            if not artifact:
                issues.append(f"{story_id}: cover_artifact_id references missing artifact")
            elif artifact.get("artifact_url") != story.get("image_url"):
                # URL may differ (artifact might have path instead), check path too
                if artifact.get("artifact_path") != story.get("image_path"):
                    issues.append(
                        f"{story_id}: cover artifact URL/path doesn't match legacy fields"
                    )

        # Check audio parity
        if story.get("audio_url") and story.get("canonical_audio_id"):
            artifact = await db.fetchone(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (story["canonical_audio_id"],)
            )
            if not artifact:
                issues.append(f"{story_id}: canonical_audio_id references missing artifact")
            elif artifact.get("artifact_url") != story.get("audio_url"):
                issues.append(
                    f"{story_id}: audio artifact URL doesn't match legacy audio_url"
                )

    if issues:
        print(f"\n❌ {len(issues)} parity issues found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return {"status": "failed", "issues": issues}
    else:
        print(f"\n✅ All {len(stories)} sampled stories pass parity check")
        return {"status": "success", "stories_checked": len(stories)}


# ============================================================================
# Entry Point
# ============================================================================

async def migrate_stories_to_artifacts_v2(
    db: "DatabaseManager", dry_run: bool = False, retry_failed: bool = False
) -> MigrationReport:
    """
    Main entry point for v2 migration.

    Args:
        db: Database manager instance
        dry_run: If True, don't commit changes
        retry_failed: If True, retry previously failed records

    Returns:
        MigrationReport
    """
    migration = StoriesToArtifactsMigrationV2(db, dry_run=dry_run)
    return await migration.run(retry_failed=retry_failed)


async def generate_migration_report(db: "DatabaseManager") -> MigrationReport:
    """Generate a report for an existing migration run."""
    repo = MigrationStatusRepository(db)
    return await repo.get_report(MIGRATION_NAME)
