"""
Legacy Support for Artifact System

Provides backward-compatible wrappers for existing code that still uses
denormalized story fields (audio_url, image_url, etc).

Allows gradual migration: new code uses artifact system, old code continues
to work via these compatibility functions.

Migration Path:
1. Existing code continues to work (uses legacy_support)
2. New code uses artifact repositories directly
3. Eventually deprecate these wrappers (v2.0)
"""

from typing import Optional
from .artifact_repository import ArtifactRepository, StoryArtifactLinkRepository
from .connection import DatabaseManager


async def get_story_audio_url(
    db: DatabaseManager, story_id: str
) -> Optional[str]:
    """
    Get story audio URL (backward-compatible).

    Tries new artifact system first, falls back to denormalized field.

    Args:
        db: Database manager
        story_id: Story UUID

    Returns:
        Audio URL or None
    """
    # Try new artifact system first
    link_repo = StoryArtifactLinkRepository(db)
    artifact = await link_repo.get_canonical_artifact(story_id, "final_audio")

    if artifact:
        return artifact.artifact_url or artifact.artifact_path

    # Fall back to legacy denormalized field
    story = await db.fetchone(
        "SELECT audio_url FROM stories WHERE story_id = ?",
        (story_id,)
    )

    if story:
        return story.get("audio_url")

    return None


async def get_story_image_url(
    db: DatabaseManager, story_id: str
) -> Optional[str]:
    """
    Get story cover image URL (backward-compatible).

    Tries new artifact system first, falls back to denormalized field.

    Args:
        db: Database manager
        story_id: Story UUID

    Returns:
        Image URL or None
    """
    # Try new artifact system first
    link_repo = StoryArtifactLinkRepository(db)
    artifact = await link_repo.get_canonical_artifact(story_id, "cover")

    if artifact:
        return artifact.artifact_url or artifact.artifact_path

    # Fall back to legacy denormalized field
    story = await db.fetchone(
        "SELECT image_url, image_path FROM stories WHERE story_id = ?",
        (story_id,)
    )

    if story:
        return story.get("image_url") or story.get("image_path")

    return None


async def get_story_image_path(
    db: DatabaseManager, story_id: str
) -> Optional[str]:
    """
    Get story cover image path (backward-compatible).

    Tries new artifact system first, falls back to denormalized field.

    Args:
        db: Database manager
        story_id: Story UUID

    Returns:
        Image path or None
    """
    # Try new artifact system first
    link_repo = StoryArtifactLinkRepository(db)
    artifact = await link_repo.get_canonical_artifact(story_id, "cover")

    if artifact:
        return artifact.artifact_path

    # Fall back to legacy denormalized field
    story = await db.fetchone(
        "SELECT image_path FROM stories WHERE story_id = ?",
        (story_id,)
    )

    if story:
        return story.get("image_path")

    return None


async def get_story_with_artifacts(
    db: DatabaseManager, story_id: str
) -> Optional[dict]:
    """
    Get story with all artifact data.

    Combines denormalized story fields with artifact system for backward
    compatibility and richness.

    Args:
        db: Database manager
        story_id: Story UUID

    Returns:
        Story dict with artifact URLs included
    """
    story = await db.fetchone(
        "SELECT * FROM stories WHERE story_id = ?",
        (story_id,)
    )

    if not story:
        return None

    # Enrich with artifact URLs if available
    audio_url = await get_story_audio_url(db, story_id)
    image_url = await get_story_image_url(db, story_id)

    if audio_url:
        story["audio_url"] = audio_url

    if image_url:
        story["image_url"] = image_url

    # Add artifact IDs for new code to use
    story_dict = dict(story) if hasattr(story, 'items') else story

    # Get artifact references
    run_result = await db.fetchone(
        "SELECT run_id FROM runs WHERE story_id = ? AND workflow_type != 'legacy_story' LIMIT 1",
        (story_id,)
    )

    if run_result:
        story_dict["current_run_id"] = run_result.get("run_id")

    return story_dict


async def list_stories_with_artifacts(
    db: DatabaseManager, limit: int = 100, offset: int = 0
) -> list:
    """
    List stories with all artifact data.

    Args:
        db: Database manager
        limit: Max results
        offset: Pagination offset

    Returns:
        List of story dicts with artifact URLs
    """
    stories = await db.fetchall(
        """
        SELECT * FROM stories
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )

    # Enrich each story with artifact data
    enriched = []
    for story in stories:
        enriched_story = await get_story_with_artifacts(
            db, story["story_id"]
        )
        if enriched_story:
            enriched.append(enriched_story)

    return enriched


# ============================================================================
# Story Creation with Artifacts
# ============================================================================

async def create_story_with_artifacts(
    db: DatabaseManager,
    story_data: dict,
    audio_artifact_id: Optional[str] = None,
    image_artifact_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> str:
    """
    Create story with artifact support.

    New-style story creation that:
    1. Creates story record
    2. Links artifacts with canonical roles
    3. Creates run for execution tracking

    Args:
        db: Database manager
        story_data: Story fields (story_id required, rest optional)
        audio_artifact_id: Audio artifact to link
        image_artifact_id: Cover image artifact to link
        run_id: Run ID for this story (optional)

    Returns:
        story_id

    Usage:
        story_id = await create_story_with_artifacts(
            db,
            story_data={
                "story_id": "uuid",
                "story_text": "...",
                "word_count": 245,
                ...
            },
            audio_artifact_id="audio-uuid",
            image_artifact_id="image-uuid",
            run_id="run-uuid"
        )
    """
    import uuid
    from datetime import datetime

    story_id = story_data.get("story_id") or str(uuid.uuid4())

    # Create story record
    now = datetime.utcnow().isoformat() + "Z"

    # Build insert statement with all provided fields
    fields = ["story_id", "created_at", "stored_at"]
    values = [story_id, now, now]

    for key, value in story_data.items():
        if key != "story_id":
            fields.append(key)
            values.append(value)

    # Add artifact references if provided
    if image_artifact_id:
        if "cover_artifact_id" not in fields:
            fields.append("cover_artifact_id")
            values.append(image_artifact_id)

    if audio_artifact_id:
        if "canonical_audio_id" not in fields:
            fields.append("canonical_audio_id")
            values.append(audio_artifact_id)

    if run_id:
        if "current_run_id" not in fields:
            fields.append("current_run_id")
            values.append(run_id)

    # Create story
    placeholders = ", ".join(["?"] * len(fields))
    field_names = ", ".join(fields)

    await db.execute(
        f"INSERT INTO stories ({field_names}) VALUES ({placeholders})",
        tuple(values)
    )

    await db.commit()

    # Create story-artifact links if artifacts provided
    link_repo = StoryArtifactLinkRepository(db)

    if image_artifact_id:
        from ..models.artifact_models import StoryArtifactLinkCreate
        link_data = StoryArtifactLinkCreate(
            story_id=story_id,
            artifact_id=image_artifact_id,
            role="cover",
            is_primary=True
        )
        await link_repo.upsert(link_data)

    if audio_artifact_id:
        from ..models.artifact_models import StoryArtifactLinkCreate
        link_data = StoryArtifactLinkCreate(
            story_id=story_id,
            artifact_id=audio_artifact_id,
            role="final_audio",
            is_primary=True
        )
        await link_repo.upsert(link_data)

    return story_id


# ============================================================================
# Migration Utilities
# ============================================================================

async def get_unmigrated_stories(db: DatabaseManager) -> list:
    """
    Get stories that haven't been migrated to artifact system yet.

    Returns:
        List of stories with legacy data but no artifact references
    """
    stories = await db.fetchall(
        """
        SELECT * FROM stories
        WHERE (audio_url IS NOT NULL OR image_url IS NOT NULL)
          AND (canonical_audio_id IS NULL AND cover_artifact_id IS NULL)
        """
    )

    return stories


async def get_migrated_stories(db: DatabaseManager) -> list:
    """
    Get stories that have been migrated to artifact system.

    Returns:
        List of stories with artifact references
    """
    stories = await db.fetchall(
        """
        SELECT * FROM stories
        WHERE canonical_audio_id IS NOT NULL OR cover_artifact_id IS NOT NULL
        """
    )

    return stories


async def get_migration_status(db: DatabaseManager) -> dict:
    """
    Get migration status summary.

    Returns:
        Dict with migration statistics
    """
    total_stories = await db.fetchone(
        "SELECT COUNT(*) as count FROM stories"
    )

    unmigrated = await db.fetchone(
        """
        SELECT COUNT(*) as count FROM stories
        WHERE (audio_url IS NOT NULL OR image_url IS NOT NULL)
          AND (canonical_audio_id IS NULL AND cover_artifact_id IS NULL)
        """
    )

    migrated = await db.fetchone(
        """
        SELECT COUNT(*) as count FROM stories
        WHERE canonical_audio_id IS NOT NULL OR cover_artifact_id IS NOT NULL
        """
    )

    total = total_stories["count"] if total_stories else 0
    unmigrated_count = unmigrated["count"] if unmigrated else 0
    migrated_count = migrated["count"] if migrated else 0

    return {
        "total_stories": total,
        "migrated_stories": migrated_count,
        "unmigrated_stories": unmigrated_count,
        "migration_percentage": (
            (migrated_count / total) * 100 if total > 0 else 0
        ),
        "status": "complete" if unmigrated_count == 0 else "in_progress"
    }
