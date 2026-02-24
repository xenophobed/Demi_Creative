# Artifact Graph Model (Issue #13, enhanced by #14/#15)

## Decision

Adopt a hybrid model:

- `story` is the user-facing experience container.
- `artifact` is a first-class immutable object.
- `run` and `agent_step` capture multi-agent execution provenance.
- links/relations form a lineage graph instead of embedding everything in `stories`.
- `migration_status` tracks per-record backfill progress for resume/retry.

This keeps `stories` lean and lets us scale storage, observability, and retention safely.

## Entities

- `story`: experience metadata and canonical artifact references.
- `run`: one generation workflow execution for a story/session.
- `agent_step`: one unit of work in a run.
- `artifact`: immutable media/data payload (image/audio/video/text/json).
- `artifact_relation`: directed edges between artifacts.
- `story_artifact_link`: user-facing role mapping for artifacts on a story.
- `run_artifact_link`: stage mapping for artifacts produced/consumed by a run.
- `migration_status`: per-record backfill tracking (Issue #15).

## Artifact Columns (v2 — Issue #14)

Core columns:
- `artifact_id` TEXT UNIQUE NOT NULL — immutable UUID
- `artifact_type` TEXT NOT NULL — image|audio|video|text|json
- `lifecycle_state` TEXT NOT NULL DEFAULT 'intermediate'
- `content_hash` TEXT — SHA256 for dedup
- `artifact_path` TEXT — local file path
- `artifact_url` TEXT — CDN/cloud URL
- `artifact_payload` TEXT — inline content (small artifacts)
- `metadata` TEXT — JSON blob (ArtifactMetadata)
- `description` TEXT

New columns (v2):
- `mime_type` TEXT — e.g. `audio/mpeg`, `image/png`
- `file_size` INTEGER — bytes
- `safety_score` REAL — 0.0–1.0 (threshold ≥ 0.85)
- `created_by_agent` TEXT — agent name that produced the artifact
- `created_by_step_id` TEXT — FK to agent_steps

Timestamps:
- `created_at` TEXT NOT NULL — immutable
- `stored_at` TEXT NOT NULL

## Lifecycle States

- `intermediate`: temporary artifacts generated during orchestration.
- `candidate`: reviewed/usable outputs not yet published.
- `published`: user-visible approved outputs.
- `archived`: retained but not active.

## Canonical Story Roles

- `cover`
- `final_audio`
- `final_video`
- `scene_image`

## Immutability and Versioning

- Artifacts are immutable: updates produce a new `artifact_id`.
- Mutations happen at link level (`story_artifact_link`), not blob level.
- Derivations are recorded via `artifact_relation` using relation types like:
  - `derived_from`
  - `variant_of`
  - `transcoded_from`

## Naming and Relation Semantics

- IDs are opaque UUID strings at API/service boundaries.
- Relation semantics are directional (`from_artifact_id` -> `to_artifact_id`).
- `story_artifact_link.is_primary = 1` enforces one canonical output per role.

## Indexes (v2 — Issue #14)

Single-column indexes:
- `idx_artifacts_lifecycle_state` ON artifacts(lifecycle_state)
- `idx_artifacts_type` ON artifacts(artifact_type)
- `idx_artifacts_content_hash` ON artifacts(content_hash)
- `idx_artifacts_created_at` ON artifacts(created_at DESC)
- `idx_artifacts_created_by_step` ON artifacts(created_by_step_id)

Compound indexes (v2):
- `idx_artifacts_type_lifecycle` ON artifacts(artifact_type, lifecycle_state)
- `idx_artifacts_created_by_agent` ON artifacts(created_by_agent)
- `idx_link_story_role_primary` ON story_artifact_links(story_id, role, is_primary)
- `idx_run_link_run_stage` ON run_artifact_links(run_id, stage)

Partial index (v2):
- `idx_artifacts_safety_flagged` ON artifacts(safety_score) WHERE safety_score IS NOT NULL AND safety_score < 0.85

Unique indexes:
- `idx_link_primary_per_story_role` ON story_artifact_links(story_id, role) WHERE is_primary=1

## Cardinality

| Relation | Cardinality | Notes |
|----------|-------------|-------|
| story → runs | 1:N | One story can have multiple generation runs |
| run → agent_steps | 1:N | Ordered by step_order |
| agent_step → artifacts | 1:N | Via created_by_step_id |
| story → story_artifact_links | 1:N | Multiple roles, A/B candidates |
| story_artifact_link → artifact | N:1 | Many links can point to same artifact |
| run → run_artifact_links | 1:N | Tracks all artifacts in a run |
| artifact → artifact_relations | N:N | Directed graph (from/to) |

## ERD (Logical)

```text
stories (1) --------< runs (N)
   |                    |
   |                    +--------< agent_steps (N)
   |                                  |
   |                                  +--------< artifacts (N) [created_by_step_id]
   |
   +--------< story_artifact_links (N) >-------- artifacts (N)

runs (1) --------< run_artifact_links (N) >-------- artifacts (N)

artifacts (1) ----< artifact_relations (N) >---- artifacts (1)

migration_status (standalone, 1 record per source entity per migration)
```

## Migration Status Table (Issue #15)

Tracks per-record backfill progress for resume/retry:

- `migration_id` TEXT UNIQUE NOT NULL
- `migration_name` TEXT NOT NULL — e.g. `stories_to_artifacts_v2`
- `source_type` TEXT NOT NULL — e.g. `story`
- `source_id` TEXT NOT NULL — e.g. story_id
- `status` TEXT — pending|in_progress|completed|failed|skipped
- `error_message` TEXT — failure details
- `artifacts_created` INTEGER — count per source record
- `links_created` INTEGER — count per source record
- `started_at` TEXT, `completed_at` TEXT
- `retry_count` INTEGER DEFAULT 0
- UNIQUE(migration_name, source_type, source_id) — prevents duplicate tracking

## Story Field Policy

`stories` table should only hold curated references for user-facing defaults:

- `cover_artifact_id`
- `canonical_audio_id`
- `canonical_video_id`
- `current_run_id`

All other generated assets remain in `artifacts` + link tables.

## Migration v2 Features (Issue #15)

1. **Per-story transactions** — failure on story N doesn't roll back stories 1..N-1
2. **Checksum dedup** — SHA256 from files/payloads; skip if artifact exists
3. **File metadata** — populate mime_type (mimetypes), file_size (os.path.getsize)
4. **Safety score** — copy from stories.safety_score to text artifact
5. **Resume/retry** — per-story status in migration_status table
6. **Migration report** — success rate, unresolved records
7. **Enhanced rollback** — uses created_by_agent='migration_v2' to identify artifacts
8. **Sampling validation** — validate_ui_parity() spot-checks migrated stories
