"""
Artifact System API Routes

REST endpoints for artifact graph system:
- GET/POST artifacts with pagination & filtering
- Publish workflow (candidate -> published)
- GET artifact lineage (provenance graph)
- GET runs and execution steps
- GET/POST story-artifact links with role filtering
- GET curated story artifacts (published/canonical only)

Security:
- All mutation endpoints require authentication via Depends(get_current_user)
- All read endpoints require authentication
- Public responses use PublicArtifactResponse to redact internal fields
- /health endpoint remains public
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from ..deps import get_current_user
from ...services.user_service import UserData
from ...services.database.connection import DatabaseManager, db_manager
from ...services.database.artifact_repository import (
    ArtifactRepository, ArtifactRelationRepository,
    StoryArtifactLinkRepository, RunRepository,
    AgentStepRepository, RunArtifactLinkRepository
)
from ...services.models.artifact_models import (
    Artifact, ArtifactCreate, ArtifactType, LifecycleState,
    Run, RunCreate, AgentStep, StoryArtifactRole,
    StoryArtifactLink, StoryArtifactLinkCreate,
    ArtifactLineage, RunWithArtifacts
)
from ...services.provenance_tracker import ProvenanceTracker

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


# ============================================================================
# Public-Safe Response Models
# ============================================================================


class PublicArtifactResponse(BaseModel):
    """
    Public-safe artifact response that excludes internal fields.

    Omits: content_hash, artifact_path, created_by_step_id
    """

    artifact_id: str
    artifact_type: str
    lifecycle_state: str
    artifact_url: Optional[str] = None
    artifact_payload: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    safety_score: Optional[float] = None
    created_by_agent: Optional[str] = None
    created_at: datetime
    stored_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_artifact(cls, artifact) -> "PublicArtifactResponse":
        """Create a public response from an internal Artifact model."""
        data = (
            artifact.model_dump(mode="json")
            if hasattr(artifact, "model_dump")
            else dict(artifact)
        )
        # Remove internal fields
        data.pop("content_hash", None)
        data.pop("artifact_path", None)
        data.pop("created_by_step_id", None)
        # Convert enums to strings
        if hasattr(data.get("artifact_type", ""), "value"):
            data["artifact_type"] = data["artifact_type"].value
        if hasattr(data.get("lifecycle_state", ""), "value"):
            data["lifecycle_state"] = data["lifecycle_state"].value
        return cls(**data)


def get_db() -> DatabaseManager:
    """Dependency that provides the singleton DatabaseManager."""
    return db_manager


# ============================================================================
# Health Check (must be before /{artifact_id} to avoid path conflicts)
# ============================================================================


@router.get("/health")
async def health():
    """
    Health check for artifact system.

    Returns:
        Service status
    """
    return {
        "status": "healthy",
        "service": "artifacts",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Artifact Endpoints
# ============================================================================


@router.get("/{artifact_id}", response_model=PublicArtifactResponse)
async def get_artifact(
    artifact_id: str,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Get artifact by ID (public-safe fields only).

    Returns:
        Artifact object with internal fields redacted
    """
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id)

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return PublicArtifactResponse.from_artifact(artifact)


@router.post("", response_model=PublicArtifactResponse)
async def create_artifact(
    artifact_data: ArtifactCreate,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Create a new artifact. Requires authentication.

    Args:
        artifact_data: Artifact creation data

    Returns:
        Created artifact with auto-generated ID and timestamps
    """
    repo = ArtifactRepository(db)
    artifact_id = await repo.create(artifact_data)
    artifact = await repo.get_by_id(artifact_id)

    if not artifact:
        raise HTTPException(status_code=500, detail="Failed to create artifact")

    return PublicArtifactResponse.from_artifact(artifact)


@router.get("", response_model=List[PublicArtifactResponse])
async def list_artifacts(
    state: Optional[str] = Query(None, description="Filter by lifecycle state"),
    artifact_type: Optional[str] = Query(
        None, description="Filter by type"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    List artifacts with optional filters.

    Query Parameters:
        state: intermediate|candidate|published|archived
        artifact_type: image|audio|video|text|json
        limit: Max results (default 100)
        offset: Pagination offset

    Returns:
        List of artifacts
    """
    repo = ArtifactRepository(db)

    filter_state = state or "published"

    if artifact_type:
        # Filter by both state and type
        artifacts = await repo.list_by_lifecycle_state_and_type(
            filter_state, artifact_type, limit, offset
        )
    else:
        artifacts = await repo.list_by_lifecycle_state(
            filter_state, limit, offset
        )

    return [PublicArtifactResponse.from_artifact(a) for a in artifacts]


@router.patch("/{artifact_id}/state")
async def update_artifact_state(
    artifact_id: str,
    new_state: str = Query(..., description="New lifecycle state"),
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Update artifact lifecycle state. Requires authentication.

    Args:
        artifact_id: Artifact UUID
        new_state: New state (intermediate|candidate|published|archived)

    Returns:
        Success message
    """
    repo = ArtifactRepository(db)

    try:
        success = await repo.update_lifecycle_state(artifact_id, new_state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not success:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return {"status": "success", "message": f"State updated to {new_state}"}


class PublishRequest(BaseModel):
    """Request body for publishing an artifact."""

    story_id: Optional[str] = None
    role: Optional[StoryArtifactRole] = None


@router.post("/{artifact_id}/publish")
async def publish_artifact(
    artifact_id: str,
    body: Optional[PublishRequest] = None,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Publish a candidate artifact. Requires authentication.

    Validates the artifact is in 'candidate' state, transitions to 'published',
    and optionally links it as the canonical artifact for a story role.

    Args:
        artifact_id: Artifact UUID
        body: Optional story_id and role for canonical linking

    Returns:
        Published artifact
    """
    tracker = ProvenanceTracker(db)

    story_id = body.story_id if body else None
    role = body.role if body else None

    try:
        success = await tracker.publish_artifact(artifact_id, story_id, role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to publish artifact"
        )

    artifact = await ArtifactRepository(db).get_by_id(artifact_id)
    return PublicArtifactResponse.from_artifact(artifact)


@router.get("/{artifact_id}/lineage", response_model=ArtifactLineage)
async def get_artifact_lineage(
    artifact_id: str,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Get complete artifact lineage (ancestors, descendants, relations).

    Returns:
        ArtifactLineage with full provenance graph
    """
    repo = ArtifactRelationRepository(db)

    try:
        lineage = await repo.get_artifact_lineage(artifact_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return lineage


# ============================================================================
# Run Endpoints
# ============================================================================


@router.get("/runs/{run_id}", response_model=RunWithArtifacts)
async def get_run(
    run_id: str,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Get run with all generated artifacts and steps.

    Returns:
        Run with complete execution context
    """
    run_repo = RunRepository(db)
    step_repo = AgentStepRepository(db)
    link_repo = RunArtifactLinkRepository(db)
    artifact_repo = ArtifactRepository(db)

    run = await run_repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get steps
    steps = await step_repo.list_by_run(run_id)

    # Get artifact links
    links = await link_repo.list_by_run(run_id)

    # Get artifacts
    artifacts = []
    for link in links:
        artifact = await artifact_repo.get_by_id(link.artifact_id)
        if artifact:
            artifacts.append(artifact)

    return RunWithArtifacts(
        run=run,
        steps=steps,
        artifacts=artifacts,
        links=links,
    )


@router.post("/runs", response_model=Run)
async def create_run(
    run_data: RunCreate,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Create a new run (execution workflow). Requires authentication.

    Args:
        run_data: Run creation data (story_id, workflow_type required)

    Returns:
        Created run
    """
    repo = RunRepository(db)
    run_id = await repo.create(run_data)
    run = await repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=500, detail="Failed to create run")

    return run


# ============================================================================
# Story Artifact Link Endpoints
# ============================================================================


@router.get(
    "/stories/{story_id}/artifacts",
    response_model=List[StoryArtifactLink],
)
async def list_story_artifacts(
    story_id: str,
    role: Optional[str] = Query(
        None,
        description="Filter by role (cover|final_audio|final_video|scene_image)",
    ),
    state: Optional[str] = Query(
        None,
        description="Filter by artifact lifecycle state",
    ),
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Get artifacts linked to a story, with optional role/state filtering.

    Query Parameters:
        role: Filter by canonical role
        state: Filter by artifact lifecycle state (e.g. published)

    Returns:
        List of story-artifact links with canonical roles
    """
    link_repo = StoryArtifactLinkRepository(db)
    links = await link_repo.list_by_story(story_id)

    if role:
        links = [link for link in links if link.role.value == role]

    if state:
        artifact_repo = ArtifactRepository(db)
        filtered = []
        for link in links:
            artifact = await artifact_repo.get_by_id(link.artifact_id)
            if artifact and artifact.lifecycle_state.value == state:
                filtered.append(link)
        links = filtered

    return links


@router.get("/stories/{story_id}/curated")
async def get_story_curated_artifacts(
    story_id: str,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get only curated (published/canonical) artifacts for a story.

    Returns a map of role -> primary artifact for the story,
    including only published artifacts by default.

    Returns:
        Dict with role keys and Artifact values
    """
    link_repo = StoryArtifactLinkRepository(db)

    curated: Dict[str, Any] = {"story_id": story_id, "artifacts": {}}

    for role in StoryArtifactRole:
        artifact = await link_repo.get_canonical_artifact(
            story_id, role.value
        )
        if artifact and artifact.lifecycle_state in (
            LifecycleState.PUBLISHED,
            LifecycleState.CANDIDATE,
        ):
            curated["artifacts"][role.value] = (
                PublicArtifactResponse.from_artifact(artifact).model_dump(
                    mode="json"
                )
            )

    return curated


@router.get(
    "/stories/{story_id}/artifacts/{role}",
    response_model=PublicArtifactResponse,
)
async def get_story_canonical_artifact(
    story_id: str,
    role: str,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Get primary (canonical) artifact for a story role.

    Args:
        story_id: Story UUID
        role: Artifact role (cover|final_audio|final_video|scene_image)

    Returns:
        Artifact or 404 if not found
    """
    repo = StoryArtifactLinkRepository(db)
    artifact = await repo.get_canonical_artifact(story_id, role)

    if not artifact:
        raise HTTPException(
            status_code=404,
            detail=f"No {role} artifact found for story {story_id}",
        )

    return PublicArtifactResponse.from_artifact(artifact)


@router.post(
    "/stories/{story_id}/artifacts",
    response_model=StoryArtifactLink,
)
async def link_story_artifact(
    story_id: str,
    link_data: StoryArtifactLinkCreate,
    user: UserData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Link an artifact to a story with a canonical role. Requires authentication.

    Args:
        story_id: Story UUID (also in link_data.story_id)
        link_data: Link creation data

    Returns:
        Created/updated link
    """
    repo = StoryArtifactLinkRepository(db)

    # Override story_id to match path parameter
    link_data.story_id = story_id

    try:
        link_id = await repo.upsert(link_data)
        # Fetch and return the created link
        links = await repo.list_by_story(story_id)
        for link in links:
            if link.link_id == link_id:
                return link
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raise HTTPException(status_code=500, detail="Failed to create link")
