"""
Provenance Tracker Service

Wraps agent execution with artifact-level provenance tracking.
Creates Run, AgentStep, Artifact, and Relation records for every
generated output during orchestration.

Issue #17: Pipeline provenance — every artifact traceable to run/step/agent.
"""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .database.connection import DatabaseManager
from .database.artifact_repository import (
    ArtifactRepository,
    ArtifactRelationRepository,
    StoryArtifactLinkRepository,
    RunRepository,
    AgentStepRepository,
    RunArtifactLinkRepository,
)
from .models.artifact_models import (
    ArtifactCreate,
    ArtifactType,
    ArtifactRelationCreate,
    RelationType,
    StoryArtifactLinkCreate,
    StoryArtifactRole,
    RunCreate,
    WorkflowType,
    AgentStepCreate,
    AgentStepComplete,
    AgentStepStatus,
    RunArtifactLinkCreate,
    RunArtifactStage,
    ArtifactMetadata,
)


class ProvenanceTracker:
    """
    Tracks multi-agent run provenance for artifact lineage.

    Usage:
        tracker = ProvenanceTracker(db)
        run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)

        step_id = await tracker.start_step(run_id, "vision_analysis", 1, input_data={...})
        artifact_id = await tracker.record_artifact(step_id, ArtifactType.IMAGE, ...)
        await tracker.complete_step(step_id, output_data={...})

        await tracker.complete_run(run_id, result_summary={...})
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._artifact_repo = ArtifactRepository(db)
        self._relation_repo = ArtifactRelationRepository(db)
        self._link_repo = StoryArtifactLinkRepository(db)
        self._run_repo = RunRepository(db)
        self._step_repo = AgentStepRepository(db)
        self._run_artifact_repo = RunArtifactLinkRepository(db)
        self._step_start_times: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    async def start_run(
        self,
        story_id: str,
        workflow_type: WorkflowType,
        session_id: Optional[str] = None,
    ) -> str:
        """Create a Run record and mark it running."""
        run_id = await self._run_repo.create(
            RunCreate(
                story_id=story_id,
                session_id=session_id,
                workflow_type=workflow_type,
            )
        )
        await self._run_repo.update_status(run_id, "running")
        return run_id

    async def complete_run(
        self,
        run_id: str,
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a Run as completed with optional summary."""
        if result_summary:
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            import json

            await self.db.execute(
                "UPDATE runs SET result_summary = ?, completed_at = ?, status = ? WHERE run_id = ?",
                (json.dumps(result_summary), now, "completed", run_id),
            )
            await self.db.commit()
        else:
            await self._run_repo.update_status(run_id, "completed")

    async def fail_run(
        self,
        run_id: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a Run as failed."""
        import json

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        summary = {"error": error_message} if error_message else None
        await self.db.execute(
            "UPDATE runs SET result_summary = ?, completed_at = ?, status = ? WHERE run_id = ?",
            (json.dumps(summary) if summary else None, now, "failed", run_id),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Step lifecycle
    # ------------------------------------------------------------------

    async def start_step(
        self,
        run_id: str,
        step_name: str,
        step_order: int,
        input_data: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        prompt_hash: Optional[str] = None,
    ) -> str:
        """Create an AgentStep and mark it running.

        Provenance metadata (model_name, prompt_hash) is stored in input_data.
        """
        enriched_input = dict(input_data or {})
        if model_name:
            enriched_input["_provenance_model"] = model_name
        if prompt_hash:
            enriched_input["_provenance_prompt_hash"] = prompt_hash

        step_id = await self._step_repo.create(
            AgentStepCreate(
                run_id=run_id,
                step_name=step_name,
                step_order=step_order,
                input_data=enriched_input if enriched_input else None,
            )
        )

        # Track wall-clock start for duration_ms
        self._step_start_times[step_id] = time.monotonic()

        # Mark running
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.db.execute(
            "UPDATE agent_steps SET status = ? WHERE agent_step_id = ?",
            ("running", step_id),
        )
        await self.db.commit()

        return step_id

    async def complete_step(
        self,
        step_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Complete a step with output and timing metadata."""
        status = AgentStepStatus.FAILED if error_message else AgentStepStatus.COMPLETED

        enriched_output = dict(output_data or {})

        # Calculate duration
        start = self._step_start_times.pop(step_id, None)
        if start is not None:
            enriched_output["_duration_ms"] = int(
                (time.monotonic() - start) * 1000
            )

        await self._step_repo.complete(
            step_id,
            AgentStepComplete(
                output_data=enriched_output,
                status=status,
                error_message=error_message,
            ),
        )

    # ------------------------------------------------------------------
    # Artifact recording
    # ------------------------------------------------------------------

    async def record_artifact(
        self,
        step_id: str,
        artifact_type: ArtifactType,
        *,
        run_id: Optional[str] = None,
        artifact_path: Optional[str] = None,
        artifact_url: Optional[str] = None,
        artifact_payload: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[ArtifactMetadata] = None,
        mime_type: Optional[str] = None,
        file_size: Optional[int] = None,
        safety_score: Optional[float] = None,
        agent_name: Optional[str] = None,
        stage: RunArtifactStage = RunArtifactStage.GENERATED,
        input_artifact_ids: Optional[List[str]] = None,
    ) -> str:
        """
        Create an artifact linked to an agent step and (optionally) a run.

        Args:
            step_id: Agent step that produced this artifact
            artifact_type: Type of artifact
            run_id: If provided, also creates a run-artifact link
            input_artifact_ids: Artifacts this one was derived from (creates relations)
            stage: Stage in the run lifecycle

        Returns:
            artifact_id
        """
        artifact_id = await self._artifact_repo.create(
            ArtifactCreate(
                artifact_type=artifact_type,
                artifact_path=artifact_path,
                artifact_url=artifact_url,
                artifact_payload=artifact_payload,
                description=description,
                metadata=metadata,
                created_by_step_id=step_id,
                mime_type=mime_type,
                file_size=file_size,
                safety_score=safety_score,
                created_by_agent=agent_name,
            )
        )

        # Link to run
        if run_id:
            await self._run_artifact_repo.create(
                RunArtifactLinkCreate(
                    run_id=run_id,
                    artifact_id=artifact_id,
                    stage=stage,
                )
            )

        # Create derived_from relations for input artifacts
        if input_artifact_ids:
            for input_id in input_artifact_ids:
                try:
                    await self._relation_repo.create(
                        ArtifactRelationCreate(
                            from_artifact_id=input_id,
                            to_artifact_id=artifact_id,
                            relation_type=RelationType.DERIVED_FROM,
                        )
                    )
                except ValueError:
                    pass  # Relation already exists or invalid

        return artifact_id

    # ------------------------------------------------------------------
    # Story linking
    # ------------------------------------------------------------------

    async def link_to_story(
        self,
        story_id: str,
        artifact_id: str,
        role: StoryArtifactRole,
        is_primary: bool = True,
        position: Optional[int] = None,
    ) -> str:
        """Link an artifact to a story with a canonical role."""
        return await self._link_repo.upsert(
            StoryArtifactLinkCreate(
                story_id=story_id,
                artifact_id=artifact_id,
                role=role,
                is_primary=is_primary,
                position=position,
            )
        )

    # ------------------------------------------------------------------
    # Publish workflow
    # ------------------------------------------------------------------

    async def publish_artifact(
        self,
        artifact_id: str,
        story_id: Optional[str] = None,
        role: Optional[StoryArtifactRole] = None,
    ) -> bool:
        """
        Publish a candidate artifact and optionally link as canonical.

        Validates the artifact is in candidate state, transitions to published,
        and links to a story role if provided.
        """
        artifact = await self._artifact_repo.get_by_id(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        if artifact.lifecycle_state.value != "candidate":
            raise ValueError(
                f"Only candidate artifacts can be published "
                f"(current: {artifact.lifecycle_state.value})"
            )

        success = await self._artifact_repo.update_lifecycle_state(
            artifact_id, "published"
        )

        if success and story_id and role:
            await self.link_to_story(story_id, artifact_id, role)

        return success

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_prompt_hash(prompt_text: str) -> str:
        """Compute a redacted-safe SHA256 hash of the prompt."""
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
