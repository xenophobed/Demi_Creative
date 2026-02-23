"""
Artifact Graph Schema

Defines database tables for the artifact system:
- artifacts: immutable media/data payloads
- artifact_relations: directed edges between artifacts
- runs: execution workflows
- agent_steps: execution units within runs
- story_artifact_links: story→artifact mappings with canonical roles
- run_artifact_links: run→artifact mappings for execution tracking

Design Principles:
- Artifacts are immutable: INSERT-only, no UPDATE
- Lifecycle states: intermediate → candidate → published → archived
- Foreign key constraints enforce referential integrity
- Indexes optimize common query patterns
- Unique constraints prevent duplicates (UNIQUE relations, one primary per role)
"""

# ============================================================================
# Artifact Tables
# ============================================================================

ARTIFACTS_TABLE = """
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT UNIQUE NOT NULL,
    artifact_type TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'intermediate',
    content_hash TEXT,
    artifact_path TEXT,
    artifact_url TEXT,
    artifact_payload TEXT,
    metadata TEXT,
    description TEXT,
    created_by_step_id TEXT,
    created_at TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    FOREIGN KEY (created_by_step_id) REFERENCES agent_steps(agent_step_id) ON DELETE SET NULL
);
"""

ARTIFACTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_artifacts_lifecycle_state ON artifacts(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_artifacts_created_by_step ON artifacts(created_by_step_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_artifacts_created_at ON artifacts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_content_hash ON artifacts(content_hash);
"""

# ============================================================================
# Artifact Relations Table
# ============================================================================

ARTIFACT_RELATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS artifact_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_id TEXT UNIQUE NOT NULL,
    from_artifact_id TEXT NOT NULL,
    to_artifact_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    FOREIGN KEY (to_artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    UNIQUE(from_artifact_id, to_artifact_id, relation_type)
);
"""

ARTIFACT_RELATIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_relation_from ON artifact_relations(from_artifact_id);
CREATE INDEX IF NOT EXISTS idx_relation_to ON artifact_relations(to_artifact_id);
CREATE INDEX IF NOT EXISTS idx_relation_type ON artifact_relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_relation_created_at ON artifact_relations(created_at DESC);
"""

# ============================================================================
# Story Artifact Links Table
# ============================================================================

STORY_ARTIFACT_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS story_artifact_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id TEXT UNIQUE NOT NULL,
    story_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    role TEXT NOT NULL,
    is_primary INTEGER DEFAULT 1,
    position INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
);
"""

STORY_ARTIFACT_LINKS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_link_story ON story_artifact_links(story_id);
CREATE INDEX IF NOT EXISTS idx_link_artifact ON story_artifact_links(artifact_id);
CREATE INDEX IF NOT EXISTS idx_link_role ON story_artifact_links(role);
CREATE INDEX IF NOT EXISTS idx_link_is_primary ON story_artifact_links(is_primary);
CREATE INDEX IF NOT EXISTS idx_link_story_role ON story_artifact_links(story_id, role);
CREATE UNIQUE INDEX IF NOT EXISTS idx_link_primary_per_story_role ON story_artifact_links(story_id, role) WHERE is_primary=1;
"""

# ============================================================================
# Run Artifact Links Table
# ============================================================================

RUN_ARTIFACT_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS run_artifact_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id TEXT UNIQUE NOT NULL,
    run_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
);
"""

RUN_ARTIFACT_LINKS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_run_link_run ON run_artifact_links(run_id);
CREATE INDEX IF NOT EXISTS idx_run_link_artifact ON run_artifact_links(artifact_id);
CREATE INDEX IF NOT EXISTS idx_run_link_stage ON run_artifact_links(stage);
"""

# ============================================================================
# Runs Table
# ============================================================================

RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    story_id TEXT NOT NULL,
    session_id TEXT,
    workflow_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    result_summary TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);
"""

RUNS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_runs_story ON runs(story_id);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_workflow_type ON runs(workflow_type);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
"""

# ============================================================================
# Agent Steps Table
# ============================================================================

AGENT_STEPS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_step_id TEXT UNIQUE NOT NULL,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    input_data TEXT,
    output_data TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
"""

AGENT_STEPS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_step_run ON agent_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_step_status ON agent_steps(status);
CREATE INDEX IF NOT EXISTS idx_step_order ON agent_steps(run_id, step_order);
CREATE INDEX IF NOT EXISTS idx_step_created_at ON agent_steps(created_at DESC);
"""

# ============================================================================
# Stories Table Modifications
# ============================================================================

# These columns should be added to the existing stories table via migration:
STORIES_ARTIFACT_COLUMNS = """
-- Add artifact reference columns to stories table
-- These are added via migration, not in CREATE TABLE

-- Migration SQL (ALTER TABLE):
ALTER TABLE stories ADD COLUMN cover_artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL;
ALTER TABLE stories ADD COLUMN canonical_audio_id TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL;
ALTER TABLE stories ADD COLUMN canonical_video_id TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL;
ALTER TABLE stories ADD COLUMN current_run_id TEXT REFERENCES runs(run_id) ON DELETE SET NULL;

-- Indexes for artifact lookups
CREATE INDEX IF NOT EXISTS idx_stories_cover_artifact ON stories(cover_artifact_id);
CREATE INDEX IF NOT EXISTS idx_stories_audio_artifact ON stories(canonical_audio_id);
CREATE INDEX IF NOT EXISTS idx_stories_video_artifact ON stories(canonical_video_id);
CREATE INDEX IF NOT EXISTS idx_stories_current_run ON stories(current_run_id);
"""

# ============================================================================
# Schema Initialization Function
# ============================================================================

async def init_artifact_schema(db: "DatabaseManager") -> None:
    """
    Initialize artifact graph schema.

    Creates all artifact-related tables and indexes.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).

    Args:
        db: Database manager instance
    """
    # Create artifacts table
    await db.execute(ARTIFACTS_TABLE)
    for stmt in ARTIFACTS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass  # Index might already exist

    # Create artifact_relations table
    await db.execute(ARTIFACT_RELATIONS_TABLE)
    for stmt in ARTIFACT_RELATIONS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create story_artifact_links table
    await db.execute(STORY_ARTIFACT_LINKS_TABLE)
    for stmt in STORY_ARTIFACT_LINKS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create runs table
    await db.execute(RUNS_TABLE)
    for stmt in RUNS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create run_artifact_links table (after runs table due to FK)
    await db.execute(RUN_ARTIFACT_LINKS_TABLE)
    for stmt in RUN_ARTIFACT_LINKS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create agent_steps table
    await db.execute(AGENT_STEPS_TABLE)
    for stmt in AGENT_STEPS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    await db.commit()

    # Run migrations to add columns to existing stories table
    await _migrate_add_artifact_columns_to_stories(db)

    # Run v2 migration: add new columns and indexes to artifacts table
    await _migrate_add_artifact_columns_v2(db)

    print("✅ Artifact schema initialized")


async def _migrate_add_artifact_columns_to_stories(db: "DatabaseManager") -> None:
    """
    Migration: Add artifact reference columns to stories table.

    Adds:
    - cover_artifact_id
    - canonical_audio_id
    - canonical_video_id
    - current_run_id

    Safe for existing databases (ADD COLUMN IF NOT EXISTS pattern).
    """
    # Check existing columns
    stories_info = await db.fetchall("PRAGMA table_info(stories)")
    stories_columns = {col['name'] for col in stories_info}

    new_columns = [
        ("cover_artifact_id", "TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL"),
        ("canonical_audio_id", "TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL"),
        ("canonical_video_id", "TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL"),
        ("current_run_id", "TEXT REFERENCES runs(run_id) ON DELETE SET NULL")
    ]

    for col_name, col_def in new_columns:
        if col_name not in stories_columns:
            print(f"📝 Migrating stories table: adding {col_name} column...")
            await db.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_def}")

    # Add indexes
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_stories_cover_artifact ON stories(cover_artifact_id)",
        "CREATE INDEX IF NOT EXISTS idx_stories_audio_artifact ON stories(canonical_audio_id)",
        "CREATE INDEX IF NOT EXISTS idx_stories_video_artifact ON stories(canonical_video_id)",
        "CREATE INDEX IF NOT EXISTS idx_stories_current_run ON stories(current_run_id)"
    ]

    for stmt in index_statements:
        try:
            await db.execute(stmt)
        except Exception:
            pass

    await db.commit()
    print("✅ Stories table migration completed")


# ============================================================================
# Migration Status Table (for resume/retry tracking)
# ============================================================================

MIGRATION_STATUS_TABLE = """
CREATE TABLE IF NOT EXISTS migration_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_id TEXT UNIQUE NOT NULL,
    migration_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    artifacts_created INTEGER DEFAULT 0,
    links_created INTEGER DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    retry_count INTEGER DEFAULT 0,
    UNIQUE(migration_name, source_type, source_id)
);
"""

MIGRATION_STATUS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_migration_status ON migration_status(status);
CREATE INDEX IF NOT EXISTS idx_migration_name ON migration_status(migration_name);
CREATE INDEX IF NOT EXISTS idx_migration_source ON migration_status(source_type, source_id);
"""


async def _migrate_add_artifact_columns_v2(db: "DatabaseManager") -> None:
    """
    Migration v2: Add new columns, compound indexes, and migration_status table.

    Adds to artifacts table:
    - mime_type TEXT
    - file_size INTEGER
    - safety_score REAL
    - created_by_agent TEXT

    Adds compound indexes for common query patterns.
    Creates migration_status table for resume/retry tracking.
    """
    # Check existing columns on artifacts table
    artifacts_info = await db.fetchall("PRAGMA table_info(artifacts)")
    artifacts_columns = {col['name'] for col in artifacts_info}

    new_columns = [
        ("mime_type", "TEXT"),
        ("file_size", "INTEGER"),
        ("safety_score", "REAL"),
        ("created_by_agent", "TEXT"),
    ]

    for col_name, col_def in new_columns:
        if col_name not in artifacts_columns:
            print(f"📝 Migrating artifacts table: adding {col_name} column...")
            await db.execute(f"ALTER TABLE artifacts ADD COLUMN {col_name} {col_def}")

    # Add compound indexes
    compound_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_artifacts_type_lifecycle ON artifacts(artifact_type, lifecycle_state)",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_safety_flagged ON artifacts(safety_score) WHERE safety_score IS NOT NULL AND safety_score < 0.85",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_created_by_agent ON artifacts(created_by_agent)",
        "CREATE INDEX IF NOT EXISTS idx_link_story_role_primary ON story_artifact_links(story_id, role, is_primary)",
        "CREATE INDEX IF NOT EXISTS idx_run_link_run_stage ON run_artifact_links(run_id, stage)",
    ]

    for stmt in compound_indexes:
        try:
            await db.execute(stmt)
        except Exception:
            pass  # Index might already exist

    # Create migration_status table
    await db.execute(MIGRATION_STATUS_TABLE)
    for stmt in MIGRATION_STATUS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    await db.commit()
    print("✅ Artifact schema v2 migration completed")


# ============================================================================
# Integration with Existing Schema
# ============================================================================

# This module should be imported and init_artifact_schema() called from
# the main schema initialization function in schema.py:
#
# In backend/src/services/database/schema.py:
#
# async def init_schema(db: "DatabaseManager") -> None:
#     # ... existing schema initialization ...
#
#     # Initialize artifact graph schema
#     from .schema_artifacts import init_artifact_schema
#     await init_artifact_schema(db)
#
#     # ... rest of schema init ...
