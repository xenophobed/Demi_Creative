"""
Admin Artifact Routes — Internal Lineage Explorer & Audit Tooling

Issue #16: Lineage explorer, admin search, safety audit, export.
Issue #19: Retention policies, TTL cleanup, storage monitoring.

All endpoints are prefixed with /api/v1/admin/artifacts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone

from ...services.database.connection import DatabaseManager, db_manager
from ...services.database.artifact_repository import (
    ArtifactRepository,
    ArtifactRelationRepository,
    StoryArtifactLinkRepository,
    RunRepository,
    AgentStepRepository,
    RunArtifactLinkRepository,
)
from ...services.models.artifact_models import (
    Artifact,
    ArtifactSearchResult,
    StoryLineage,
    LineageExport,
    StorageStats,
    RetentionPolicy,
    RetentionReport,
    RunWithArtifacts,
    LifecycleState,
)
from ...services.retention_service import RetentionService, DEFAULT_POLICIES

router = APIRouter(prefix="/api/v1/admin/artifacts", tags=["admin-artifacts"])


def get_db() -> DatabaseManager:
    """Dependency that provides the singleton DatabaseManager."""
    return db_manager


# ============================================================================
# Admin Search (Issue #16)
# ============================================================================

@router.get("/search", response_model=ArtifactSearchResult)
async def search_artifacts(
    artifact_id: Optional[str] = Query(None, description="Exact artifact UUID"),
    content_hash: Optional[str] = Query(None, description="SHA256 content hash"),
    story_id: Optional[str] = Query(None, description="Story UUID (via story-artifact links)"),
    run_id: Optional[str] = Query(None, description="Run UUID (via run-artifact links)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: DatabaseManager = Depends(get_db),
):
    """
    Multi-field admin search across artifacts.

    Supports search by artifact_id, content_hash, story_id, or run_id.
    At least one search field must be provided.
    """
    if not any([artifact_id, content_hash, story_id, run_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one search field is required (artifact_id, content_hash, story_id, run_id)",
        )

    repo = ArtifactRepository(db)
    result = await repo.search(
        artifact_id=artifact_id,
        content_hash=content_hash,
        story_id=story_id,
        run_id=run_id,
        limit=limit,
        offset=offset,
    )
    return result


# ============================================================================
# Story Lineage Explorer (Issue #16)
# ============================================================================

@router.get("/stories/{story_id}/lineage", response_model=StoryLineage)
async def get_story_lineage(
    story_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """
    Full story → run → step → artifact lineage chain.

    Traces all runs for a story, each with its agent steps and generated artifacts.
    Also includes direct story-artifact links with canonical roles.
    """
    run_repo = RunRepository(db)
    step_repo = AgentStepRepository(db)
    link_repo = RunArtifactLinkRepository(db)
    artifact_repo = ArtifactRepository(db)
    story_link_repo = StoryArtifactLinkRepository(db)

    # Get all runs for story
    runs = await run_repo.list_by_story(story_id)

    if not runs:
        # Still return story artifact links even if no runs
        story_artifacts = await story_link_repo.list_by_story(story_id)
        return StoryLineage(
            story_id=story_id,
            runs=[],
            story_artifacts=story_artifacts,
            total_artifacts=0,
            total_runs=0,
        )

    # Build RunWithArtifacts for each run
    runs_with_artifacts: List[RunWithArtifacts] = []
    total_artifacts = 0

    for run in runs:
        steps = await step_repo.list_by_run(run.run_id)
        run_links = await link_repo.list_by_run(run.run_id)

        artifacts = []
        for rl in run_links:
            artifact = await artifact_repo.get_by_id(rl.artifact_id)
            if artifact:
                artifacts.append(artifact)

        total_artifacts += len(artifacts)

        runs_with_artifacts.append(
            RunWithArtifacts(
                run=run,
                steps=steps,
                artifacts=artifacts,
                links=run_links,
            )
        )

    story_artifacts = await story_link_repo.list_by_story(story_id)

    return StoryLineage(
        story_id=story_id,
        runs=runs_with_artifacts,
        story_artifacts=story_artifacts,
        total_artifacts=total_artifacts,
        total_runs=len(runs),
    )


# ============================================================================
# Lineage Export for Incident Review (Issue #16)
# ============================================================================

@router.get("/{artifact_id}/export", response_model=LineageExport)
async def export_artifact_lineage(
    artifact_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """
    Export complete artifact lineage for incident review.

    Includes the full lineage graph, run context (if available),
    and any safety-flagged artifacts in the chain.
    """
    relation_repo = ArtifactRelationRepository(db)
    artifact_repo = ArtifactRepository(db)

    # Get full lineage
    try:
        lineage = await relation_repo.get_artifact_lineage(artifact_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Find the run that produced this artifact (via created_by_step_id → agent_steps → runs)
    run_context = None
    artifact = lineage.artifact

    if artifact.created_by_step_id:
        step_repo = AgentStepRepository(db)
        run_repo = RunRepository(db)
        link_repo = RunArtifactLinkRepository(db)

        step_row = await db.fetchone(
            "SELECT run_id FROM agent_steps WHERE agent_step_id = ?",
            (artifact.created_by_step_id,),
        )
        if step_row:
            run_id = step_row["run_id"]
            run = await run_repo.get_by_id(run_id)
            if run:
                steps = await step_repo.list_by_run(run_id)
                run_links = await link_repo.list_by_run(run_id)
                run_artifacts = []
                for rl in run_links:
                    a = await artifact_repo.get_by_id(rl.artifact_id)
                    if a:
                        run_artifacts.append(a)

                run_context = RunWithArtifacts(
                    run=run,
                    steps=steps,
                    artifacts=run_artifacts,
                    links=run_links,
                )

    # Collect safety-flagged artifacts in the lineage
    all_lineage_artifacts = [lineage.artifact] + lineage.ancestors + lineage.descendants
    safety_flags = [
        a for a in all_lineage_artifacts
        if a.safety_score is not None and a.safety_score < 0.85
    ]

    return LineageExport(
        artifact_id=artifact_id,
        lineage=lineage,
        run_context=run_context,
        safety_flags=safety_flags,
        exported_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Safety Audit (Issue #16)
# ============================================================================

@router.get("/safety-flagged", response_model=List[Artifact])
async def list_safety_flagged_artifacts(
    limit: int = Query(100, ge=1, le=1000),
    db: DatabaseManager = Depends(get_db),
):
    """
    List all artifacts with safety scores below the 0.85 threshold.

    Supports incident review and safety audit workflows.
    """
    repo = ArtifactRepository(db)
    return await repo.list_safety_flagged(limit)


# ============================================================================
# Storage Monitoring (Issue #19)
# ============================================================================

@router.get("/storage-stats", response_model=StorageStats)
async def get_storage_stats(
    db: DatabaseManager = Depends(get_db),
):
    """
    Get artifact storage usage statistics.

    Returns counts by lifecycle state, artifact type, and total file sizes.
    """
    repo = ArtifactRepository(db)
    return await repo.get_storage_stats()


# ============================================================================
# Retention Policies (Issue #19)
# ============================================================================

@router.get("/retention/policies", response_model=List[RetentionPolicy])
async def get_retention_policies():
    """
    Get current retention policies.

    Returns the configured TTL for each lifecycle class.
    """
    return DEFAULT_POLICIES


@router.post("/retention/run", response_model=RetentionReport)
async def run_retention_cleanup(
    dry_run: bool = Query(True, description="If true, report only — no changes"),
    candidate_limit: int = Query(500, ge=1, le=5000, description="Max artifacts per state"),
    db: DatabaseManager = Depends(get_db),
):
    """
    Execute retention cleanup.

    Applies lifecycle retention policies:
    - intermediate artifacts older than 30 days → archived
    - candidate artifacts older than 90 days → archived
    - archived artifacts older than 7 days → deleted
    - published artifacts are NEVER touched

    Dry-run mode (default) reports impact without making changes.
    """
    service = RetentionService(db)
    return await service.run_cleanup(
        dry_run=dry_run,
        candidate_limit=candidate_limit,
    )
