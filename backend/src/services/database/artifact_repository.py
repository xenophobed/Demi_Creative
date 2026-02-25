"""
Artifact Repository

Implements CRUD operations and business logic for artifacts and their relations.
Uses repository pattern to abstract database access from services.

Key Principles:
- Artifacts are immutable (INSERT-only)
- All IDs are generated as UUIDs (not sequential)
- Timestamps are in ISO 8601 format
- Constraints enforced at DB level (unique, foreign keys)
- Indexes optimize common query patterns
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .connection import DatabaseManager
from ...services.models.artifact_models import (
    Artifact, ArtifactCreate, ArtifactRelation, ArtifactRelationCreate,
    StoryArtifactLink, StoryArtifactLinkCreate, Run, RunCreate,
    AgentStep, AgentStepCreate, AgentStepComplete, RunArtifactLink,
    RunArtifactLinkCreate, ArtifactLineage, RunWithArtifacts,
    MigrationRecord, MigrationStatusEnum, MigrationReport,
    ArtifactSearchResult, StorageStats,
)


# ============================================================================
# Artifact Repository
# ============================================================================

class ArtifactRepository:
    """Repository for artifact CRUD operations"""

    def __init__(self, db: DatabaseManager):
        """
        Initialize artifact repository.

        Args:
            db: Database manager instance
        """
        self.db = db

    async def create(self, artifact_data: ArtifactCreate) -> str:
        """
        Create an immutable artifact.

        Args:
            artifact_data: Artifact creation data

        Returns:
            artifact_id (UUID string)
        """
        artifact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Compute content hash if payload provided
        content_hash = None
        if artifact_data.artifact_payload:
            content_hash = hashlib.sha256(
                artifact_data.artifact_payload.encode()
            ).hexdigest()

        # Serialize metadata
        metadata_json = None
        if artifact_data.metadata:
            metadata_json = artifact_data.metadata.model_dump_json()

        # Insert artifact
        await self.db.execute(
            """
            INSERT INTO artifacts (
                artifact_id, artifact_type, lifecycle_state, content_hash,
                artifact_path, artifact_url, artifact_payload, metadata,
                description, created_by_step_id,
                mime_type, file_size, safety_score, created_by_agent,
                created_at, stored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                artifact_data.artifact_type.value,
                "intermediate",  # Default lifecycle state
                content_hash,
                artifact_data.artifact_path,
                artifact_data.artifact_url,
                artifact_data.artifact_payload,
                metadata_json,
                artifact_data.description,
                artifact_data.created_by_step_id,
                artifact_data.mime_type,
                artifact_data.file_size,
                artifact_data.safety_score,
                artifact_data.created_by_agent,
                now,
                now
            )
        )

        await self.db.commit()
        return artifact_id

    async def get_by_id(self, artifact_id: str) -> Optional[Artifact]:
        """
        Get artifact by ID.

        Args:
            artifact_id: Artifact UUID

        Returns:
            Artifact object or None if not found
        """
        result = await self.db.fetchone(
            "SELECT * FROM artifacts WHERE artifact_id = ?",
            (artifact_id,)
        )

        if not result:
            return None

        return self._row_to_artifact(result)

    async def list_by_lifecycle_state(
        self, state: str, limit: int = 100, offset: int = 0
    ) -> List[Artifact]:
        """
        List artifacts by lifecycle state.

        Args:
            state: Lifecycle state
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of artifacts
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE lifecycle_state = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (state, limit, offset)
        )

        return [self._row_to_artifact(row) for row in results]

    async def list_by_lifecycle_state_and_type(
        self, state: str, artifact_type: str, limit: int = 100, offset: int = 0
    ) -> List[Artifact]:
        """
        List artifacts by lifecycle state and artifact type.

        Args:
            state: Lifecycle state
            artifact_type: Artifact type
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of artifacts
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE lifecycle_state = ? AND artifact_type = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (state, artifact_type, limit, offset)
        )

        return [self._row_to_artifact(row) for row in results]

    async def list_by_created_by_step(
        self, step_id: str, limit: int = 100
    ) -> List[Artifact]:
        """
        List artifacts created by a specific agent step.

        Args:
            step_id: Agent step UUID
            limit: Maximum results

        Returns:
            List of artifacts
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE created_by_step_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (step_id, limit)
        )

        return [self._row_to_artifact(row) for row in results]

    async def update_lifecycle_state(self, artifact_id: str, new_state: str) -> bool:
        """
        Update artifact lifecycle state.

        Args:
            artifact_id: Artifact UUID
            new_state: New state (intermediate|candidate|published|archived)

        Returns:
            True if successful, False if not found
        """
        # Check if artifact exists
        artifact = await self.get_by_id(artifact_id)
        if not artifact:
            return False

        # Validate transition
        valid_transitions = {
            "intermediate": ["candidate", "archived"],
            "candidate": ["published", "archived"],
            "published": ["archived"],
            "archived": ["archived"]  # Idempotent
        }

        current_state = artifact.lifecycle_state.value
        if new_state not in valid_transitions.get(current_state, []):
            raise ValueError(
                f"Invalid state transition: {current_state} → {new_state}"
            )

        # Update state and stored_at timestamp
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.db.execute(
            "UPDATE artifacts SET lifecycle_state = ?, stored_at = ? WHERE artifact_id = ?",
            (new_state, now, artifact_id)
        )

        await self.db.commit()
        return True

    def _row_to_artifact(self, row: Dict[str, Any]) -> Artifact:
        """Convert database row to Artifact model"""
        metadata = None
        if row["metadata"]:
            metadata = json.loads(row["metadata"])

        return Artifact(
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            lifecycle_state=row["lifecycle_state"],
            content_hash=row["content_hash"],
            artifact_path=row["artifact_path"],
            artifact_url=row["artifact_url"],
            artifact_payload=row["artifact_payload"],
            metadata=metadata,
            description=row["description"],
            created_by_step_id=row["created_by_step_id"],
            mime_type=row.get("mime_type"),
            file_size=row.get("file_size"),
            safety_score=row.get("safety_score"),
            created_by_agent=row.get("created_by_agent"),
            created_at=row["created_at"],
            stored_at=row["stored_at"]
        )

    async def get_by_content_hash(self, content_hash: str) -> Optional[Artifact]:
        """
        Get artifact by content hash (for checksum dedup).

        Args:
            content_hash: SHA256 hash of content

        Returns:
            Artifact object or None if not found
        """
        result = await self.db.fetchone(
            "SELECT * FROM artifacts WHERE content_hash = ?",
            (content_hash,)
        )

        if not result:
            return None

        return self._row_to_artifact(result)

    async def list_by_type_and_state(
        self, artifact_type: str, lifecycle_state: str,
        limit: int = 100, offset: int = 0
    ) -> List[Artifact]:
        """
        List artifacts by type and lifecycle state (uses compound index).

        Args:
            artifact_type: Artifact type
            lifecycle_state: Lifecycle state
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of artifacts
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE artifact_type = ? AND lifecycle_state = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (artifact_type, lifecycle_state, limit, offset)
        )

        return [self._row_to_artifact(row) for row in results]

    async def list_safety_flagged(self, limit: int = 100) -> List[Artifact]:
        """
        List artifacts with safety scores below threshold (uses partial index).

        Returns:
            List of artifacts with safety_score < 0.85
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE safety_score IS NOT NULL AND safety_score < 0.85
            ORDER BY safety_score ASC
            LIMIT ?
            """,
            (limit,)
        )

        return [self._row_to_artifact(row) for row in results]

    # ------------------------------------------------------------------
    # Admin Search (Issue #16)
    # ------------------------------------------------------------------

    async def search(
        self,
        artifact_id: Optional[str] = None,
        content_hash: Optional[str] = None,
        story_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ArtifactSearchResult:
        """
        Multi-field admin search across artifacts.

        Searches by artifact_id (exact), content_hash (exact),
        story_id (via story_artifact_links), or run_id (via run_artifact_links).

        Returns:
            ArtifactSearchResult with matching artifacts and total count.
        """
        query_info = {}
        conditions = []
        params: list = []
        joins = []

        if artifact_id:
            conditions.append("a.artifact_id = ?")
            params.append(artifact_id)
            query_info["artifact_id"] = artifact_id

        if content_hash:
            conditions.append("a.content_hash = ?")
            params.append(content_hash)
            query_info["content_hash"] = content_hash

        if story_id:
            joins.append(
                "JOIN story_artifact_links sal ON a.artifact_id = sal.artifact_id"
            )
            conditions.append("sal.story_id = ?")
            params.append(story_id)
            query_info["story_id"] = story_id

        if run_id:
            joins.append(
                "JOIN run_artifact_links ral ON a.artifact_id = ral.artifact_id"
            )
            conditions.append("ral.run_id = ?")
            params.append(run_id)
            query_info["run_id"] = run_id

        if not conditions:
            # No filters — return empty
            return ArtifactSearchResult(
                artifacts=[], total_count=0, query=query_info
            )

        join_clause = " ".join(joins)
        where_clause = " AND ".join(conditions)

        # Count query
        count_sql = f"""
            SELECT COUNT(DISTINCT a.artifact_id)
            FROM artifacts a {join_clause}
            WHERE {where_clause}
        """
        count_row = await self.db.fetchone(count_sql, tuple(params))
        total_count = list(count_row.values())[0] if count_row else 0

        # Data query
        data_sql = f"""
            SELECT DISTINCT a.* FROM artifacts a {join_clause}
            WHERE {where_clause}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
        """
        results = await self.db.fetchall(
            data_sql, tuple(params) + (limit, offset)
        )

        artifacts = [self._row_to_artifact(row) for row in results]

        return ArtifactSearchResult(
            artifacts=artifacts,
            total_count=total_count,
            query=query_info,
        )

    # ------------------------------------------------------------------
    # Storage Stats (Issue #19)
    # ------------------------------------------------------------------

    async def get_storage_stats(self) -> StorageStats:
        """
        Compute storage usage statistics across all artifacts.

        Returns:
            StorageStats with counts by state/type and file sizes.
        """
        # Total count
        total_row = await self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM artifacts"
        )
        total = total_row["cnt"] if total_row else 0

        # Count by state
        state_rows = await self.db.fetchall(
            "SELECT lifecycle_state, COUNT(*) as cnt FROM artifacts GROUP BY lifecycle_state"
        )
        by_state = {row["lifecycle_state"]: row["cnt"] for row in state_rows}

        # Count by type
        type_rows = await self.db.fetchall(
            "SELECT artifact_type, COUNT(*) as cnt FROM artifacts GROUP BY artifact_type"
        )
        by_type = {row["artifact_type"]: row["cnt"] for row in type_rows}

        # Total file size
        size_row = await self.db.fetchone(
            "SELECT COALESCE(SUM(file_size), 0) as total FROM artifacts WHERE file_size IS NOT NULL"
        )
        total_size = size_row["total"] if size_row else 0

        # File size by state
        state_size_rows = await self.db.fetchall(
            """
            SELECT lifecycle_state, COALESCE(SUM(file_size), 0) as total
            FROM artifacts
            WHERE file_size IS NOT NULL
            GROUP BY lifecycle_state
            """
        )
        by_state_size = {row["lifecycle_state"]: row["total"] for row in state_size_rows}

        return StorageStats(
            total_artifacts=total,
            by_state=by_state,
            by_type=by_type,
            total_file_size_bytes=total_size,
            by_state_size=by_state_size,
        )

    # ------------------------------------------------------------------
    # Retention Queries (Issue #19)
    # ------------------------------------------------------------------

    async def list_expired(
        self, state: str, older_than_days: int, limit: int = 1000
    ) -> List[Artifact]:
        """
        List artifacts in a given state older than N days.

        Args:
            state: Lifecycle state to filter
            older_than_days: Age threshold in days
            limit: Max results

        Returns:
            Artifacts past their retention period.
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM artifacts
            WHERE lifecycle_state = ?
              AND created_at < datetime('now', ? || ' days')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (state, f"-{older_than_days}", limit),
        )

        return [self._row_to_artifact(row) for row in results]

    async def is_canonical(self, artifact_id: str) -> bool:
        """
        Check if an artifact is the primary/canonical artifact for any story.

        Returns:
            True if the artifact is linked as primary to any story.
        """
        row = await self.db.fetchone(
            """
            SELECT 1 FROM story_artifact_links
            WHERE artifact_id = ? AND is_primary = 1
            LIMIT 1
            """,
            (artifact_id,),
        )
        return row is not None

    async def bulk_archive(self, artifact_ids: List[str]) -> int:
        """
        Transition a batch of artifacts to 'archived' state.

        Only transitions artifacts currently in intermediate or candidate state.

        Returns:
            Number of artifacts actually archived.
        """
        if not artifact_ids:
            return 0

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        placeholders = ", ".join(["?"] * len(artifact_ids))

        cursor = await self.db.execute(
            f"""
            UPDATE artifacts
            SET lifecycle_state = 'archived', stored_at = ?
            WHERE artifact_id IN ({placeholders})
              AND lifecycle_state IN ('intermediate', 'candidate')
            """,
            (now, *artifact_ids),
        )

        await self.db.commit()
        return cursor.rowcount


# ============================================================================
# Artifact Relation Repository
# ============================================================================

class ArtifactRelationRepository:
    """Repository for artifact relations"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create(self, relation_data: ArtifactRelationCreate) -> str:
        """
        Create artifact relation (directed edge in lineage graph).

        Args:
            relation_data: Relation creation data

        Returns:
            relation_id (UUID string)

        Raises:
            ValueError: If self-reference or validation fails
        """
        # Validate no self-reference
        if relation_data.from_artifact_id == relation_data.to_artifact_id:
            raise ValueError("Cannot create relation from artifact to itself")

        # Verify artifacts exist
        from_exists = await self.db.fetchone(
            "SELECT artifact_id FROM artifacts WHERE artifact_id = ?",
            (relation_data.from_artifact_id,)
        )
        to_exists = await self.db.fetchone(
            "SELECT artifact_id FROM artifacts WHERE artifact_id = ?",
            (relation_data.to_artifact_id,)
        )

        if not from_exists or not to_exists:
            raise ValueError("Source or target artifact does not exist")

        # Create relation
        relation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        metadata_json = None
        if relation_data.metadata:
            metadata_json = json.dumps(relation_data.metadata)

        try:
            await self.db.execute(
                """
                INSERT INTO artifact_relations (
                    relation_id, from_artifact_id, to_artifact_id,
                    relation_type, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    relation_data.from_artifact_id,
                    relation_data.to_artifact_id,
                    relation_data.relation_type.value,
                    metadata_json,
                    now
                )
            )
            await self.db.commit()
        except Exception as e:
            # Likely UNIQUE constraint violation (duplicate relation)
            if "UNIQUE" in str(e):
                raise ValueError(
                    f"Relation already exists: "
                    f"{relation_data.from_artifact_id} → "
                    f"{relation_data.to_artifact_id} "
                    f"({relation_data.relation_type.value})"
                )
            raise

        return relation_id

    async def get_artifact_lineage(
        self, artifact_id: str, max_depth: int = 20
    ) -> ArtifactLineage:
        """
        Get complete artifact lineage (ancestors, descendants, relations).

        Args:
            artifact_id: Artifact UUID
            max_depth: Maximum traversal depth (default 20)

        Returns:
            ArtifactLineage object with all related artifacts and relations
        """
        artifact_repo = ArtifactRepository(self.db)
        artifact = await artifact_repo.get_by_id(artifact_id)

        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        # Collect all artifact IDs in the lineage for complete relation lookup
        ancestor_ids: set = set()
        descendant_ids: set = set()

        ancestors = await self._get_ancestors(
            artifact_id, collected_ids=ancestor_ids, max_depth=max_depth
        )
        descendants = await self._get_descendants(
            artifact_id, collected_ids=descendant_ids, max_depth=max_depth
        )

        # Get all relations between any artifacts in the full lineage
        all_ids = ancestor_ids | descendant_ids | {artifact_id}
        relations = await self._get_lineage_relations(all_ids)

        total_count = len(ancestors) + len(descendants) + 1  # +1 for self

        return ArtifactLineage(
            artifact_id=artifact_id,
            artifact=artifact,
            ancestors=ancestors,
            descendants=descendants,
            relations=relations,
            total_count=total_count
        )

    async def _get_ancestors(
        self,
        artifact_id: str,
        visited: set = None,
        collected_ids: set = None,
        depth: int = 0,
        max_depth: int = 20,
    ) -> List[Artifact]:
        """Recursively get ancestor artifacts with depth limit"""
        if visited is None:
            visited = set()
        if collected_ids is None:
            collected_ids = set()

        if artifact_id in visited or depth >= max_depth:
            return []

        visited.add(artifact_id)
        ancestors = []

        results = await self.db.fetchall(
            """
            SELECT from_artifact_id FROM artifact_relations
            WHERE to_artifact_id = ?
            """,
            (artifact_id,)
        )

        artifact_repo = ArtifactRepository(self.db)

        for row in results:
            parent_id = row["from_artifact_id"]
            parent = await artifact_repo.get_by_id(parent_id)
            if parent:
                ancestors.append(parent)
                collected_ids.add(parent_id)
                grandparents = await self._get_ancestors(
                    parent_id, visited, collected_ids,
                    depth=depth + 1, max_depth=max_depth
                )
                ancestors.extend(grandparents)

        return ancestors

    async def _get_descendants(
        self,
        artifact_id: str,
        visited: set = None,
        collected_ids: set = None,
        depth: int = 0,
        max_depth: int = 20,
    ) -> List[Artifact]:
        """Recursively get descendant artifacts with depth limit"""
        if visited is None:
            visited = set()
        if collected_ids is None:
            collected_ids = set()

        if artifact_id in visited or depth >= max_depth:
            return []

        visited.add(artifact_id)
        descendants = []

        results = await self.db.fetchall(
            """
            SELECT to_artifact_id FROM artifact_relations
            WHERE from_artifact_id = ?
            """,
            (artifact_id,)
        )

        artifact_repo = ArtifactRepository(self.db)

        for row in results:
            child_id = row["to_artifact_id"]
            child = await artifact_repo.get_by_id(child_id)
            if child:
                descendants.append(child)
                collected_ids.add(child_id)
                grandchildren = await self._get_descendants(
                    child_id, visited, collected_ids,
                    depth=depth + 1, max_depth=max_depth
                )
                descendants.extend(grandchildren)

        return descendants

    async def _get_lineage_relations(self, artifact_ids: set) -> List[ArtifactRelation]:
        """Get all relations between artifacts in the lineage"""
        if not artifact_ids:
            return []

        placeholders = ", ".join(["?"] * len(artifact_ids))
        id_list = list(artifact_ids)

        results = await self.db.fetchall(
            f"""
            SELECT * FROM artifact_relations
            WHERE from_artifact_id IN ({placeholders})
               OR to_artifact_id IN ({placeholders})
            """,
            (*id_list, *id_list)
        )

        return [self._row_to_relation(row) for row in results]

    def _row_to_relation(self, row: Dict[str, Any]) -> ArtifactRelation:
        """Convert database row to ArtifactRelation model"""
        metadata = None
        if row["metadata"]:
            metadata = json.loads(row["metadata"])

        return ArtifactRelation(
            relation_id=row["relation_id"],
            from_artifact_id=row["from_artifact_id"],
            to_artifact_id=row["to_artifact_id"],
            relation_type=row["relation_type"],
            metadata=metadata,
            created_at=row["created_at"]
        )


# ============================================================================
# Story Artifact Link Repository
# ============================================================================

class StoryArtifactLinkRepository:
    """Repository for story-artifact links"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def upsert(self, link_data: StoryArtifactLinkCreate) -> str:
        """
        Create or update story-artifact link.

        Args:
            link_data: Link creation data

        Returns:
            link_id (UUID string)

        If a link already exists, updates it to the new state.
        Enforces: one PRIMARY artifact per story+role.
        """
        # Check if link exists
        existing = await self.db.fetchone(
            """
            SELECT link_id FROM story_artifact_links
            WHERE story_id = ? AND artifact_id = ? AND role = ?
            """,
            (link_data.story_id, link_data.artifact_id, link_data.role.value)
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if existing:
            # Update existing link
            await self.db.execute(
                """
                UPDATE story_artifact_links
                SET is_primary = ?, position = ?, updated_at = ?
                WHERE link_id = ?
                """,
                (
                    int(link_data.is_primary),
                    link_data.position,
                    now,
                    existing["link_id"]
                )
            )
            await self.db.commit()
            return existing["link_id"]

        # Check if making primary and one already exists
        if link_data.is_primary:
            existing_primary = await self.db.fetchone(
                """
                SELECT link_id FROM story_artifact_links
                WHERE story_id = ? AND role = ? AND is_primary = 1
                """,
                (link_data.story_id, link_data.role.value)
            )

            if existing_primary:
                # Demote existing primary
                await self.db.execute(
                    """
                    UPDATE story_artifact_links
                    SET is_primary = 0, updated_at = ?
                    WHERE link_id = ?
                    """,
                    (now, existing_primary["link_id"])
                )

        # Create new link
        link_id = str(uuid.uuid4())

        await self.db.execute(
            """
            INSERT INTO story_artifact_links (
                link_id, story_id, artifact_id, role, is_primary,
                position, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id,
                link_data.story_id,
                link_data.artifact_id,
                link_data.role.value,
                int(link_data.is_primary),
                link_data.position,
                now,
                now
            )
        )

        await self.db.commit()
        return link_id

    async def get_canonical_artifact(
        self, story_id: str, role: str
    ) -> Optional[Artifact]:
        """
        Get primary artifact for given story+role.

        Args:
            story_id: Story UUID
            role: Artifact role

        Returns:
            Artifact object or None if not found
        """
        result = await self.db.fetchone(
            """
            SELECT a.* FROM artifacts a
            JOIN story_artifact_links l ON a.artifact_id = l.artifact_id
            WHERE l.story_id = ? AND l.role = ? AND l.is_primary = 1
            """,
            (story_id, role)
        )

        if not result:
            return None

        artifact_repo = ArtifactRepository(self.db)
        return artifact_repo._row_to_artifact(result)

    async def list_by_story(self, story_id: str) -> List[StoryArtifactLink]:
        """
        List all artifacts linked to a story.

        Args:
            story_id: Story UUID

        Returns:
            List of story-artifact links
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM story_artifact_links
            WHERE story_id = ?
            ORDER BY role, is_primary DESC, position
            """,
            (story_id,)
        )

        return [self._row_to_link(row) for row in results]

    def _row_to_link(self, row: Dict[str, Any]) -> StoryArtifactLink:
        """Convert database row to StoryArtifactLink model"""
        return StoryArtifactLink(
            link_id=row["link_id"],
            story_id=row["story_id"],
            artifact_id=row["artifact_id"],
            role=row["role"],
            is_primary=bool(row["is_primary"]),
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


# ============================================================================
# Run Repository
# ============================================================================

class RunRepository:
    """Repository for execution runs"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create(self, run_data: RunCreate) -> str:
        """
        Create a run.

        Args:
            run_data: Run creation data

        Returns:
            run_id (UUID string)
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        await self.db.execute(
            """
            INSERT INTO runs (
                run_id, story_id, session_id, workflow_type, status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_data.story_id,
                run_data.session_id,
                run_data.workflow_type.value,
                "pending",
                now
            )
        )

        await self.db.commit()
        return run_id

    async def get_by_id(self, run_id: str) -> Optional[Run]:
        """Get run by ID"""
        result = await self.db.fetchone(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        )

        if not result:
            return None

        return self._row_to_run(result)

    async def update_status(
        self,
        run_id: str,
        status: str,
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update run status and optionally set result_summary.

        Args:
            run_id: Run UUID
            status: New status
            result_summary: Optional summary dict (stored as JSON)

        Returns:
            True if successful
        """
        # Check if run exists
        run = await self.get_by_id(run_id)
        if not run:
            return False

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started_at = run.started_at
        completed_at = run.completed_at

        if status == "running" and not started_at:
            started_at = now
        elif status in ["completed", "failed"] and not completed_at:
            completed_at = now

        summary_json = json.dumps(result_summary) if result_summary else None

        await self.db.execute(
            """
            UPDATE runs
            SET status = ?, started_at = ?, completed_at = ?, result_summary = ?
            WHERE run_id = ?
            """,
            (status, started_at, completed_at, summary_json, run_id)
        )

        await self.db.commit()
        return True

    async def list_by_story(self, story_id: str) -> List[Run]:
        """
        List all runs for a story.

        Args:
            story_id: Story UUID

        Returns:
            List of runs ordered by created_at DESC
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM runs
            WHERE story_id = ?
            ORDER BY created_at DESC
            """,
            (story_id,),
        )

        return [self._row_to_run(row) for row in results]

    def _row_to_run(self, row: Dict[str, Any]) -> Run:
        """Convert database row to Run model"""
        result_summary = None
        if row["result_summary"]:
            result_summary = json.loads(row["result_summary"])

        return Run(
            run_id=row["run_id"],
            story_id=row["story_id"],
            session_id=row["session_id"],
            workflow_type=row["workflow_type"],
            status=row["status"],
            result_summary=result_summary,
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"]
        )


# ============================================================================
# Agent Step Repository
# ============================================================================

class AgentStepRepository:
    """Repository for agent steps"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create(self, step_data: AgentStepCreate) -> str:
        """
        Create an agent step.

        Args:
            step_data: Step creation data

        Returns:
            agent_step_id (UUID string)
        """
        agent_step_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        input_json = None
        if step_data.input_data:
            input_json = json.dumps(step_data.input_data)

        await self.db.execute(
            """
            INSERT INTO agent_steps (
                agent_step_id, run_id, step_name, step_order,
                input_data, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_step_id,
                step_data.run_id,
                step_data.step_name,
                step_data.step_order,
                input_json,
                "pending",
                now
            )
        )

        await self.db.commit()
        return agent_step_id

    async def list_by_run(self, run_id: str) -> List[AgentStep]:
        """
        List all steps in a run.

        Args:
            run_id: Run UUID

        Returns:
            List of agent steps ordered by step_order
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM agent_steps
            WHERE run_id = ?
            ORDER BY step_order ASC
            """,
            (run_id,)
        )

        return [self._row_to_step(row) for row in results]

    async def update_status(self, agent_step_id: str, status: str) -> bool:
        """
        Update step status (e.g. pending -> running).

        Args:
            agent_step_id: Step UUID
            status: New status string

        Returns:
            True if successful
        """
        result = await self.db.fetchone(
            "SELECT agent_step_id FROM agent_steps WHERE agent_step_id = ?",
            (agent_step_id,)
        )
        if not result:
            return False

        await self.db.execute(
            "UPDATE agent_steps SET status = ? WHERE agent_step_id = ?",
            (status, agent_step_id),
        )
        await self.db.commit()
        return True

    async def complete(self, agent_step_id: str, completion_data: AgentStepComplete) -> bool:
        """
        Complete an agent step.

        Args:
            agent_step_id: Agent step UUID
            completion_data: Completion data (output, status)

        Returns:
            True if successful
        """
        # Check if step exists
        step_result = await self.db.fetchone(
            "SELECT * FROM agent_steps WHERE agent_step_id = ?",
            (agent_step_id,)
        )

        if not step_result:
            return False

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        output_json = None
        if completion_data.output_data:
            output_json = json.dumps(completion_data.output_data)

        await self.db.execute(
            """
            UPDATE agent_steps
            SET output_data = ?, status = ?, error_message = ?, completed_at = ?
            WHERE agent_step_id = ?
            """,
            (
                output_json,
                completion_data.status.value,
                completion_data.error_message,
                now,
                agent_step_id
            )
        )

        await self.db.commit()
        return True

    def _row_to_step(self, row: Dict[str, Any]) -> AgentStep:
        """Convert database row to AgentStep model"""
        input_data = None
        if row["input_data"]:
            input_data = json.loads(row["input_data"])

        output_data = None
        if row["output_data"]:
            output_data = json.loads(row["output_data"])

        return AgentStep(
            agent_step_id=row["agent_step_id"],
            run_id=row["run_id"],
            step_name=row["step_name"],
            step_order=row["step_order"],
            input_data=input_data,
            output_data=output_data,
            status=row["status"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            completed_at=row["completed_at"]
        )


# ============================================================================
# Run Artifact Link Repository
# ============================================================================

class RunArtifactLinkRepository:
    """Repository for run-artifact links"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create(self, link_data: RunArtifactLinkCreate) -> str:
        """
        Create a run-artifact link.

        Args:
            link_data: Link creation data

        Returns:
            link_id (UUID string)
        """
        link_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        await self.db.execute(
            """
            INSERT INTO run_artifact_links (
                link_id, run_id, artifact_id, stage, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                link_id,
                link_data.run_id,
                link_data.artifact_id,
                link_data.stage.value,
                now
            )
        )

        await self.db.commit()
        return link_id

    async def list_by_run(self, run_id: str) -> List[RunArtifactLink]:
        """
        List all artifacts linked to a run.

        Args:
            run_id: Run UUID

        Returns:
            List of run-artifact links
        """
        results = await self.db.fetchall(
            """
            SELECT * FROM run_artifact_links
            WHERE run_id = ?
            ORDER BY created_at DESC
            """,
            (run_id,)
        )

        return [self._row_to_link(row) for row in results]

    def _row_to_link(self, row: Dict[str, Any]) -> RunArtifactLink:
        """Convert database row to RunArtifactLink model"""
        return RunArtifactLink(
            link_id=row["link_id"],
            run_id=row["run_id"],
            artifact_id=row["artifact_id"],
            stage=row["stage"],
            created_at=row["created_at"]
        )


# ============================================================================
# Migration Status Repository
# ============================================================================

class MigrationStatusRepository:
    """Repository for migration status tracking (resume/retry support)"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def upsert(
        self,
        migration_name: str,
        source_type: str,
        source_id: str,
        status: str,
        error_message: Optional[str] = None,
        artifacts_created: int = 0,
        links_created: int = 0,
    ) -> str:
        """
        Create or update a migration status record.

        Uses UNIQUE(migration_name, source_type, source_id) for idempotency.

        Returns:
            migration_id (UUID string)
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Check if record exists
        existing = await self.db.fetchone(
            """
            SELECT migration_id, retry_count FROM migration_status
            WHERE migration_name = ? AND source_type = ? AND source_id = ?
            """,
            (migration_name, source_type, source_id)
        )

        if existing:
            # Update existing record
            await self.db.execute(
                """
                UPDATE migration_status
                SET status = ?, error_message = ?,
                    artifacts_created = ?, links_created = ?,
                    completed_at = CASE WHEN ? IN ('completed', 'failed') THEN ? ELSE completed_at END
                WHERE migration_id = ?
                """,
                (
                    status, error_message,
                    artifacts_created, links_created,
                    status, now,
                    existing["migration_id"]
                )
            )
            await self.db.commit()
            return existing["migration_id"]

        # Create new record
        migration_id = str(uuid.uuid4())

        await self.db.execute(
            """
            INSERT INTO migration_status (
                migration_id, migration_name, source_type, source_id,
                status, error_message, artifacts_created, links_created,
                started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                migration_id, migration_name, source_type, source_id,
                status, error_message, artifacts_created, links_created,
                now
            )
        )

        await self.db.commit()
        return migration_id

    async def get(
        self, migration_name: str, source_type: str, source_id: str
    ) -> Optional[MigrationRecord]:
        """Get migration status for a specific source record."""
        result = await self.db.fetchone(
            """
            SELECT * FROM migration_status
            WHERE migration_name = ? AND source_type = ? AND source_id = ?
            """,
            (migration_name, source_type, source_id)
        )

        if not result:
            return None

        return self._row_to_record(result)

    async def list_by_status(
        self, migration_name: str, status: str
    ) -> List[MigrationRecord]:
        """List migration records by status."""
        results = await self.db.fetchall(
            """
            SELECT * FROM migration_status
            WHERE migration_name = ? AND status = ?
            ORDER BY started_at ASC
            """,
            (migration_name, status)
        )

        return [self._row_to_record(row) for row in results]

    async def list_failed(self, migration_name: str) -> List[MigrationRecord]:
        """List failed migration records."""
        return await self.list_by_status(migration_name, "failed")

    async def increment_retry(
        self, migration_name: str, source_type: str, source_id: str
    ) -> bool:
        """Increment retry count and reset status to in_progress."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        result = await self.db.fetchone(
            """
            SELECT migration_id FROM migration_status
            WHERE migration_name = ? AND source_type = ? AND source_id = ?
            """,
            (migration_name, source_type, source_id)
        )

        if not result:
            return False

        await self.db.execute(
            """
            UPDATE migration_status
            SET retry_count = retry_count + 1,
                status = 'in_progress',
                error_message = NULL,
                started_at = ?
            WHERE migration_id = ?
            """,
            (now, result["migration_id"])
        )

        await self.db.commit()
        return True

    async def get_report(self, migration_name: str) -> MigrationReport:
        """Generate a migration report with aggregated stats."""
        # Count by status
        status_counts = await self.db.fetchall(
            """
            SELECT status, COUNT(*) as cnt,
                   SUM(artifacts_created) as total_artifacts,
                   SUM(links_created) as total_links
            FROM migration_status
            WHERE migration_name = ?
            GROUP BY status
            """,
            (migration_name,)
        )

        completed = 0
        failed = 0
        skipped = 0
        pending = 0
        total_artifacts = 0
        total_links = 0
        total = 0

        for row in status_counts:
            cnt = row["cnt"]
            total += cnt
            total_artifacts += row["total_artifacts"] or 0
            total_links += row["total_links"] or 0

            if row["status"] == "completed":
                completed = cnt
            elif row["status"] == "failed":
                failed = cnt
            elif row["status"] == "skipped":
                skipped = cnt
            elif row["status"] in ("pending", "in_progress"):
                pending += cnt

        success_rate = completed / total if total > 0 else 0.0

        # Get unresolved records
        unresolved_rows = await self.db.fetchall(
            """
            SELECT * FROM migration_status
            WHERE migration_name = ? AND status IN ('failed', 'pending', 'in_progress')
            ORDER BY started_at ASC
            """,
            (migration_name,)
        )

        unresolved = [self._row_to_record(row) for row in unresolved_rows]

        return MigrationReport(
            migration_name=migration_name,
            total_records=total,
            completed=completed,
            failed=failed,
            skipped=skipped,
            pending=pending,
            total_artifacts_created=total_artifacts,
            total_links_created=total_links,
            success_rate=success_rate,
            unresolved_records=unresolved
        )

    def _row_to_record(self, row: Dict[str, Any]) -> MigrationRecord:
        """Convert database row to MigrationRecord model"""
        return MigrationRecord(
            migration_id=row["migration_id"],
            migration_name=row["migration_name"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            status=row["status"],
            error_message=row.get("error_message"),
            artifacts_created=row.get("artifacts_created", 0),
            links_created=row.get("links_created", 0),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            retry_count=row.get("retry_count", 0)
        )
