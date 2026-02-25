"""
Retention Service

Implements lifecycle-based retention policies for artifact cleanup.
Ensures canonical/published artifacts are never deleted.

Issue #19: Lifecycle policies + TTL cleanup for intermediates.

Default Policies:
    - published:    indefinite (never delete)
    - candidate:    90 days
    - intermediate: 30 days
    - archived:     7 days (final cleanup)
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from .database.connection import DatabaseManager
from .database.artifact_repository import (
    ArtifactRepository,
    StoryArtifactLinkRepository,
)
from .models.artifact_models import (
    Artifact,
    LifecycleState,
    RetentionPolicy,
    RetentionCandidate,
    RetentionReport,
)

logger = logging.getLogger(__name__)

# Default retention policies by lifecycle state
DEFAULT_POLICIES: List[RetentionPolicy] = [
    RetentionPolicy(
        lifecycle_state=LifecycleState.PUBLISHED,
        retention_days=-1,
        description="Published artifacts are retained indefinitely",
    ),
    RetentionPolicy(
        lifecycle_state=LifecycleState.CANDIDATE,
        retention_days=90,
        description="Candidate artifacts retained for 90 days before archival",
    ),
    RetentionPolicy(
        lifecycle_state=LifecycleState.INTERMEDIATE,
        retention_days=30,
        description="Intermediate artifacts retained for 30 days before archival",
    ),
    RetentionPolicy(
        lifecycle_state=LifecycleState.ARCHIVED,
        retention_days=7,
        description="Archived artifacts retained for 7 days before deletion",
    ),
]


class RetentionService:
    """
    Applies lifecycle retention policies to artifacts.

    Safeguards:
        - Published artifacts are NEVER archived or deleted.
        - Canonical (primary story-linked) artifacts are NEVER deleted.
        - Dry-run mode reports impact without making changes.
    """

    def __init__(
        self,
        db: DatabaseManager,
        policies: Optional[List[RetentionPolicy]] = None,
    ):
        self.db = db
        self._artifact_repo = ArtifactRepository(db)
        self._link_repo = StoryArtifactLinkRepository(db)
        self.policies = policies or DEFAULT_POLICIES

    async def run_cleanup(
        self,
        dry_run: bool = True,
        candidate_limit: int = 500,
    ) -> RetentionReport:
        """
        Execute retention cleanup based on configured policies.

        Args:
            dry_run: If True, report only — no state changes.
            candidate_limit: Max artifacts to process per state.

        Returns:
            RetentionReport with details of what was (or would be) done.
        """
        now = datetime.now(timezone.utc)
        all_candidates: List[RetentionCandidate] = []
        archive_ids: List[str] = []
        delete_ids: List[str] = []
        by_type: dict = {}
        safeguarded_count = 0

        for policy in self.policies:
            if policy.retention_days < 0:
                # Indefinite — skip
                continue

            state = policy.lifecycle_state.value
            expired = await self._artifact_repo.list_expired(
                state, policy.retention_days, limit=candidate_limit
            )

            for artifact in expired:
                canonical = await self._artifact_repo.is_canonical(
                    artifact.artifact_id
                )
                # Safeguard: never touch published or canonical artifacts
                protected = (
                    artifact.lifecycle_state == LifecycleState.PUBLISHED
                    or canonical
                )

                candidate = RetentionCandidate(
                    artifact=artifact,
                    reason=f"{state} artifact older than {policy.retention_days} days",
                    is_canonical=canonical,
                    safeguarded=protected,
                )
                all_candidates.append(candidate)

                if protected:
                    safeguarded_count += 1
                    continue

                art_type = artifact.artifact_type.value
                by_type[art_type] = by_type.get(art_type, 0) + 1

                if state == LifecycleState.ARCHIVED.value:
                    # Archived past TTL → schedule for deletion
                    delete_ids.append(artifact.artifact_id)
                else:
                    # intermediate/candidate past TTL → archive
                    archive_ids.append(artifact.artifact_id)

        archived_count = 0
        deleted_count = 0

        if not dry_run:
            # Archive expired intermediate/candidate artifacts
            if archive_ids:
                archived_count = await self._artifact_repo.bulk_archive(
                    archive_ids
                )
                logger.info("Archived %d artifacts", archived_count)

            # Delete expired archived artifacts (remove files + rows)
            if delete_ids:
                deleted_count = await self._delete_artifacts(delete_ids)
                logger.info("Deleted %d artifacts", deleted_count)

        return RetentionReport(
            dry_run=dry_run,
            policies_applied=[
                p for p in self.policies if p.retention_days >= 0
            ],
            candidates_found=len(all_candidates),
            safeguarded_count=safeguarded_count,
            archived_count=archived_count if not dry_run else len(archive_ids),
            deleted_count=deleted_count if not dry_run else len(delete_ids),
            by_type=by_type,
            candidates=all_candidates[:100],  # Cap detail list
            executed_at=now,
        )

    async def _delete_artifacts(self, artifact_ids: List[str]) -> int:
        """
        Delete artifacts: delete DB row first (with commit), then remove file.

        Order matters for crash safety: if the process dies after DB delete
        but before file removal, we get an orphan file (harmless) rather than
        a DB row pointing to a missing file (broken reference).

        Only deletes artifacts that are:
            - In 'archived' state
            - NOT canonical for any story
        """
        deleted = 0
        for aid in artifact_ids:
            artifact = await self._artifact_repo.get_by_id(aid)
            if not artifact:
                continue

            # Final safeguard check
            if artifact.lifecycle_state != LifecycleState.ARCHIVED:
                logger.warning(
                    "Skipping non-archived artifact %s (state=%s)",
                    aid,
                    artifact.lifecycle_state.value,
                )
                continue

            if await self._artifact_repo.is_canonical(aid):
                logger.warning("Skipping canonical artifact %s", aid)
                continue

            file_path = artifact.artifact_path

            # Delete DB row first via repository (CASCADE removes relations and links)
            was_deleted = await self._artifact_repo.delete(aid)
            if not was_deleted:
                continue
            deleted += 1

            # Then remove file from disk (orphan file is harmless on failure)
            if file_path:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.debug("Removed file: %s", file_path)
                except OSError as e:
                    logger.error(
                        "Failed to remove file %s: %s", file_path, e
                    )

        return deleted
