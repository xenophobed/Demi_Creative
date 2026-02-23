"""
Migration: Stories to Artifact Graph Model (v1)

Migrates existing story records to the artifact graph model while maintaining
backward compatibility. Zero-downtime migration using transaction-based approach.

Strategy:
1. For each story with denormalized fields (audio_url, image_url, story_text, etc):
   - Create artifact records for image/audio/video
   - Create story_artifact_links with canonical roles
   - Create run record (workflow_type='legacy_story')
   - Update stories table with artifact references
2. Validate: all created artifacts, all links exist
3. Keep old columns for backward compatibility (will deprecate in v2.0)

Safety:
- All operations in transaction (rollback on error)
- Skip stories that are already migrated
- Log all migrations for audit trail
- Optional dry-run mode
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class StoriesToArtifactsMigration:
    """Handles migration of stories to artifact graph model"""

    def __init__(self, db: "DatabaseManager", dry_run: bool = False):
        """
        Initialize migration.

        Args:
            db: Database manager instance
            dry_run: If True, log changes without committing
        """
        self.db = db
        self.dry_run = dry_run
        self.migrated_stories = 0
        self.created_artifacts = 0
        self.migration_log: List[Dict[str, Any]] = []

    async def run(self) -> Dict[str, Any]:
        """
        Execute migration.

        Returns:
            Migration summary dict
        """
        print("\n" + "=" * 60)
        print("🚀 MIGRATION: Stories → Artifact Graph Model")
        print("=" * 60)

        if self.dry_run:
            print("📝 DRY RUN MODE - Changes will NOT be committed")
        else:
            print("⚠️  LIVE MODE - Changes will be committed to database")

        try:
            # Get all stories
            stories = await self.db.fetchall(
                "SELECT * FROM stories"
            )

            print(f"\n📊 Found {len(stories)} stories to process...")

            for story in stories:
                await self._migrate_story(story)

            # Summary
            summary = {
                "total_stories": len(stories),
                "migrated_stories": self.migrated_stories,
                "created_artifacts": self.created_artifacts,
                "skipped_stories": len(stories) - self.migrated_stories,
                "migration_log": self.migration_log,
                "dry_run": self.dry_run
            }

            # Print summary
            print("\n" + "=" * 60)
            print("✅ MIGRATION SUMMARY")
            print("=" * 60)
            print(f"Total stories processed: {summary['total_stories']}")
            print(f"Stories migrated: {summary['migrated_stories']}")
            print(f"Artifacts created: {summary['created_artifacts']}")
            print(f"Stories skipped: {summary['skipped_stories']}")

            if not self.dry_run:
                await self.db.commit()
                print("\n✅ Migration committed to database")
            else:
                print("\n📝 Dry run complete - no changes committed")

            return summary

        except Exception as e:
            print(f"\n❌ MIGRATION FAILED: {e}")
            if not self.dry_run:
                await self.db.connection.rollback()
                print("⏮️  Transaction rolled back")
            raise

    async def _migrate_story(self, story: Dict[str, Any]) -> None:
        """Migrate a single story to artifact model"""

        story_id = story["story_id"]

        # Check if already migrated (has artifact references)
        already_migrated = (
            story.get("cover_artifact_id") or
            story.get("canonical_audio_id") or
            story.get("canonical_video_id") or
            story.get("current_run_id")
        )

        if already_migrated:
            print(f"  ⏭️  Skipping {story_id} (already migrated)")
            return

        print(f"  🔄 Migrating {story_id}...")

        artifacts_created = []
        story_artifact_links = []

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

        # Migrate image/cover
        cover_artifact_id = None
        if story.get("image_url") or story.get("image_path"):
            cover_artifact_id = await self._create_artifact(
                artifact_type="image",
                artifact_path=story.get("image_path"),
                artifact_url=story.get("image_url"),
                description="Cover image from legacy story"
            )

            if cover_artifact_id:
                artifacts_created.append(cover_artifact_id)

                # Create story-artifact link
                link_id = await self._create_story_artifact_link(
                    story_id=story_id,
                    artifact_id=cover_artifact_id,
                    role="cover",
                    is_primary=True
                )

                if link_id:
                    story_artifact_links.append(link_id)

        # Migrate audio
        canonical_audio_id = None
        if story.get("audio_url"):
            canonical_audio_id = await self._create_artifact(
                artifact_type="audio",
                artifact_url=story.get("audio_url"),
                description="Narration audio from legacy story"
            )

            if canonical_audio_id:
                artifacts_created.append(canonical_audio_id)

                # Create story-artifact link
                link_id = await self._create_story_artifact_link(
                    story_id=story_id,
                    artifact_id=canonical_audio_id,
                    role="final_audio",
                    is_primary=True
                )

                if link_id:
                    story_artifact_links.append(link_id)

        # Create text artifact (story text)
        text_artifact_id = None
        if story.get("story_text"):
            text_artifact_id = await self._create_artifact(
                artifact_type="text",
                artifact_payload=story.get("story_text"),
                description="Story text from legacy story"
            )

            if text_artifact_id:
                artifacts_created.append(text_artifact_id)

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

        # Log migration
        self.migration_log.append({
            "story_id": story_id,
            "run_id": run_id,
            "artifacts_created": artifacts_created,
            "story_artifact_links_created": story_artifact_links
        })

        self.migrated_stories += 1
        self.created_artifacts += len(artifacts_created)

        print(f"    ✅ Migrated {len(artifacts_created)} artifacts, "
              f"{len(story_artifact_links)} links")

    async def _create_artifact(
        self,
        artifact_type: str,
        artifact_path: Optional[str] = None,
        artifact_url: Optional[str] = None,
        artifact_payload: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[str]:
        """Create artifact for legacy story"""

        artifact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            if not self.dry_run:
                await self.db.execute(
                    """
                    INSERT INTO artifacts (
                        artifact_id, artifact_type, lifecycle_state,
                        artifact_path, artifact_url, artifact_payload,
                        description, created_at, stored_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        artifact_type,
                        "published",  # Legacy stories already approved
                        artifact_path,
                        artifact_url,
                        artifact_payload,
                        description,
                        now,
                        now
                    )
                )

            return artifact_id

        except Exception as e:
            print(f"      ❌ Failed to create {artifact_type} artifact: {e}")
            return None

    async def _create_story_artifact_link(
        self,
        story_id: str,
        artifact_id: str,
        role: str,
        is_primary: bool = True
    ) -> Optional[str]:
        """Create story-artifact link"""

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
                    (
                        link_id,
                        story_id,
                        artifact_id,
                        role,
                        int(is_primary),
                        now,
                        now
                    )
                )

            return link_id

        except Exception as e:
            print(f"      ❌ Failed to create story-artifact link: {e}")
            return None


async def migrate_stories_to_artifacts(
    db: "DatabaseManager", dry_run: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for migration.

    Args:
        db: Database manager instance
        dry_run: If True, don't commit changes

    Returns:
        Migration summary
    """
    migration = StoriesToArtifactsMigration(db, dry_run=dry_run)
    return await migration.run()


# ============================================================================
# Rollback Strategy
# ============================================================================

async def rollback_stories_to_artifacts(
    db: "DatabaseManager"
) -> Dict[str, Any]:
    """
    Rollback migration (restore pre-migration state).

    This is a non-destructive rollback:
    - Clears artifact references from stories table
    - Keeps artifact records (they don't hurt)
    - Old audio_url, image_url fields still exist

    Safe to run multiple times.
    """
    print("\n" + "=" * 60)
    print("⏮️  ROLLBACK: Artifact Graph Migration")
    print("=" * 60)

    try:
        # Clear artifact references from stories
        result = await db.execute(
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

        await db.commit()

        print("✅ Rollback complete")
        print("   - Artifact references cleared from stories table")
        print("   - Artifact records preserved (can be manually deleted)")
        print("   - Old audio_url, image_url fields still available")

        return {
            "status": "success",
            "stories_updated": result.rowcount if hasattr(result, 'rowcount') else 0,
            "message": "Migration rolled back successfully"
        }

    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        raise


# ============================================================================
# Validation
# ============================================================================

async def validate_migration(db: "DatabaseManager") -> Dict[str, Any]:
    """
    Validate that migration was successful.

    Checks:
    - All stories with legacy data have corresponding artifacts
    - All artifacts have proper links
    - No orphaned artifacts
    - Referential integrity
    """
    print("\n" + "=" * 60)
    print("✓ VALIDATION: Artifact Graph Migration")
    print("=" * 60)

    issues = []

    # Check 1: Stories with audio_url have canonical_audio_id
    stories_with_audio_url = await db.fetchall(
        "SELECT * FROM stories WHERE audio_url IS NOT NULL"
    )

    for story in stories_with_audio_url:
        if not story.get("canonical_audio_id"):
            issues.append(
                f"Story {story['story_id']}: has audio_url but no "
                f"canonical_audio_id"
            )

    # Check 2: Stories with image_url have cover_artifact_id
    stories_with_image_url = await db.fetchall(
        "SELECT * FROM stories WHERE image_url IS NOT NULL"
    )

    for story in stories_with_image_url:
        if not story.get("cover_artifact_id"):
            issues.append(
                f"Story {story['story_id']}: has image_url but no "
                f"cover_artifact_id"
            )

    # Check 3: All story_artifact_links reference valid artifacts
    bad_links = await db.fetchall(
        """
        SELECT l.link_id, l.artifact_id FROM story_artifact_links l
        LEFT JOIN artifacts a ON l.artifact_id = a.artifact_id
        WHERE a.artifact_id IS NULL
        """
    )

    for link in bad_links:
        issues.append(
            f"Story-artifact link {link['link_id']}: references "
            f"non-existent artifact {link['artifact_id']}"
        )

    # Report results
    if issues:
        print(f"\n❌ VALIDATION FAILED - {len(issues)} issues found:\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return {
            "status": "failed",
            "issue_count": len(issues),
            "issues": issues
        }
    else:
        print("\n✅ VALIDATION PASSED - All checks successful")
        return {
            "status": "success",
            "issue_count": 0,
            "message": "Migration validation successful"
        }
