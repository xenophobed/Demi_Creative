# Artifact Graph Model (Issue #13)

## Decision

Adopt a hybrid model:

- `story` is the user-facing experience container.
- `artifact` is a first-class immutable object.
- `run` and `agent_step` capture multi-agent execution provenance.
- links/relations form a lineage graph instead of embedding everything in `stories`.

This keeps `stories` lean and lets us scale storage, observability, and retention safely.

## Entities

- `story`: experience metadata and canonical artifact references.
- `run`: one generation workflow execution for a story/session.
- `agent_step`: one unit of work in a run.
- `artifact`: immutable media/data payload (image/audio/video/text/json).
- `artifact_relation`: directed edges between artifacts.
- `story_artifact_link`: user-facing role mapping for artifacts on a story.
- `run_artifact_link`: stage mapping for artifacts produced/consumed by a run.

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
```

## Story Field Policy

`stories` table should only hold curated references for user-facing defaults:

- `cover_artifact_id`
- `canonical_audio_id`
- `canonical_video_id`
- `current_run_id`

All other generated assets remain in `artifacts` + link tables.
