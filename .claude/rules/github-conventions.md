# GitHub Issue & Project Management Conventions

> Single source of truth for issue organization. Referenced by `/create-issue`, `/fix-issue`, `/pr` skills.

## Label Taxonomy

Every issue gets **one label from each required category**.

### Type (required — pick one)
- `type:epic` — Product epic grouping related stories. Maps to a PRD section.
- `type:story` — Deliverable unit of work within an epic.
- `type:bug` — Something is broken.
- `type:chore` — Tech debt, docs, tooling — no user-visible change.
- `type:spike` — Research / investigation / prototype — time-boxed.

### Layer (required — one or more)
- `layer:backend` — Python / FastAPI / agents / MCP servers / services
- `layer:frontend` — React / TypeScript / Vite / Tailwind
- `layer:infra` — CI, DB schema, deployment, migrations, tooling
- `layer:docs` — Documentation only

### Domain (required for stories and bugs)
- `domain:image-to-story` — PRD §3.1
- `domain:interactive-story` — PRD §3.2
- `domain:news-to-kids` — PRD §3.3
- `domain:safety` — PRD §3.4
- `domain:memory` — PRD §3.5
- `domain:tts-audio` — TTS narration and sound design
- `domain:artifacts` — Artifact graph, provenance, lifecycle
- `domain:library` — PRD §3.6 — My Library, unified content library
- `domain:video` — Phase 3 video / dynamic picture book

### Priority (required)
- `P0:critical` — Blocks launch or breaks safety — fix NOW
- `P1:high` — Must have for current milestone
- `P2:medium` — Should have — improves quality
- `P3:low` — Nice to have — backlog

### Phase (required for epics and stories)
- `phase:mvp` — Image-to-Story + safety + TTS + basic memory
- `phase:2` — Interactive story + advanced memory + news-to-kids
- `phase:3` — Video, gamification, parent dashboard

## Milestones

- `phase:mvp` → milestone `MVP — Core Story Flow`
- `phase:2` → milestone `Phase 2 — Interactive + Memory + News`
- `phase:3` → milestone `Phase 3 — Video, Gamification, Parent Dashboard`

Every issue MUST be assigned to a milestone.

## Epic Registry

| #   | Epic                              | Domain               | Phase |
| --- | --------------------------------- | -------------------- | ----- |
| #40 | Image-to-Story — MVP Happy Path  | domain:image-to-story | mvp   |
| #41 | Interactive Story — Branching     | domain:interactive-story | 2  |
| #42 | Memory System — Recall & Prefs   | domain:memory         | 2     |
| #43 | Artifact Lifecycle                | domain:artifacts      | mvp   |
| #44 | News-to-Kids — Deferred          | domain:news-to-kids   | 2     |
| #45 | TTS & Audio Pipeline Upgrade     | domain:tts-audio      | 2     |
| #49 | My Library — Unified Content Library | domain:library     | mvp   |

Every story/bug body MUST include `**Parent Epic**: #<number>`.

## Naming Conventions

### Issue Titles
- Epic: `Epic: <domain> — <goal>`
- Story: `<verb phrase>` (e.g. "Add character memory to story generation")
- Bug: `Bug: <what's broken>`
- Chore: `Chore: <what needs cleaning>`
- Spike: `Spike: <what we're investigating>`

### Branch Names
- `feat/<issue#>-<short-desc>` — stories
- `fix/<issue#>-<short-desc>` — bugs
- `chore/<issue#>-<short-desc>` — chores
- `spike/<issue#>-<short-desc>` — spikes

### PR Body
- MUST include `Fixes #<issue>` or `Related to #<issue>`
- MUST reference parent epic if applicable
- Milestone inherited from linked issue
