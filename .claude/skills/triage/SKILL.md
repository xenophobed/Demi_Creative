---
name: triage
description: "Pipeline: issues -> prioritize -> plan -> create-issue (optional). Turn backlog chaos into an execution queue."
allowed-tools: Read, Grep, Glob, Bash(gh:*), Bash(git:*)
argument-hint: [optional filter, e.g. "P1", "bugs", "mvp", or domain]
---

# Triage Pipeline Skill

Triage scope: $ARGUMENTS

> **Pipeline skill** - composes `/issues` -> prioritization -> `/plan` -> optional `/create-issue`.

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Pipeline Steps

### Step 1: Survey Current Backlog (from /issues)

1. List current open issues and epics
2. Group by priority, then by milestone/epic
3. Identify blockers and unassigned high-priority work

**Checkpoint**: Confirm which issues should enter the active queue.

### Step 2: Prioritize and Sequence

1. Rank selected items by impact, risk, and dependency
2. Mark execution style per item:
   - Small: direct `/fix-issue`
   - Medium/Large: run `/plan` first
3. Produce a short ordered queue for the next cycle

### Step 3: Plan the Top Items (from /plan)

For top 1-3 items:
1. Draft implementation plan with files, interfaces, tests, and risks
2. Identify prerequisites and safe execution order

**Checkpoint**: Confirm the queue and planned first item.

### Step 4: Optional Follow-Up Issue Creation (from /create-issue)

If triage discovers missing tracking items:
1. Create follow-up bug/story/chore issues
2. Link to parent epic and apply labels

## Output Format

```
## Triage Result

### Queue Summary
| Order | Issue | Priority | Effort | Suggested Command |
|------|-------|----------|--------|-------------------|
| 1 | #N | P1 | Medium | /plan #N |

### Planned Items
- #N: <plan summary>

### New Issues Created (optional)
- #N <title>

### Next Action
Run `<command>` for the top item now.
```

## Guardrails

- Keep the active queue small (default top 3)
- Do not auto-create issues unless requested
- Explicitly flag dependency conflicts before execution
