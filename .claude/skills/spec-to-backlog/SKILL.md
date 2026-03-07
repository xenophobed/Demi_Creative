---
name: spec-to-backlog
description: "Pipeline: feature-spec -> prd update -> batch create issues. Turn ideas into executable backlog."
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(gh:*), Bash(git:*)
argument-hint: [feature idea or approved spec summary]
---

# Spec to Backlog Pipeline Skill

Intake feature: $ARGUMENTS

> **Pipeline skill** - composes `/feature-spec` -> `/prd` -> `/create-issue` into one product intake flow.

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Pipeline Steps

### Step 1: Produce Feature Spec (from /feature-spec)

1. Clarify problem, user value, and success criteria
2. Check overlap with existing issues/epics
3. Define user stories, acceptance criteria, age adaptation, and safety requirements
4. Identify candidate epic and story list with priorities

**Checkpoint**: Present feature spec draft and ask for confirmation.

### Step 2: Update PRD (from /prd)

1. Add or update the relevant PRD section in `docs/product/PRD.md`
2. Keep section numbering/format consistent with existing PRD structure
3. Include explicit in-scope and out-of-scope notes
4. Show diff before proceeding

**Checkpoint**: Show PRD diff and ask for confirmation before issue creation.

### Step 3: Create Backlog Issues (from /create-issue)

1. Create/update epic issue if needed
2. Create child story/bug/chore issues from approved spec
3. Apply labels: type, layer, domain, priority, phase
4. Link children to epic and milestone

## Output Format

```
## Product Intake: <feature>

### Spec Result
- Stories: <count>
- Acceptance criteria coverage: <summary>

### PRD Changes
- File: `docs/product/PRD.md`
- Section: <section>
- Diff summary: <summary>

### Issues Created
| # | Type | Title | Priority | Layer | Epic |
|---|------|-------|----------|-------|------|
| N | story | ... | P1 | backend/frontend/both | #E |

### Next Steps
1. `/plan #<story>` for larger stories
2. `/fix-issue #<story>` for execution
```

## Guardrails

- Never create issues before PRD update is reviewed
- Skip issue creation for items already tracked
- Keep issue scope independently deliverable
