---
name: audit-and-fix
description: "Pipeline: product-audit -> create-issue. Audit spec gaps and convert confirmed gaps into tracked work."
allowed-tools: Read, Grep, Glob, Bash(gh:*), Bash(git:*)
argument-hint: [area to audit, e.g. "my library", "upload flow", or "full"]
---

# Audit and Fix Pipeline Skill

Audit scope: $ARGUMENTS

> **Pipeline skill** - composes `/product-audit` -> `/create-issue` for spec enforcement.

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Pipeline Steps

### Step 1: Audit Product vs Implementation (from /product-audit)

1. Load PRD/domain expectations for the target area
2. Compare code behavior with product expectations
3. Categorize gaps:
   - Naming mismatch
   - Missing feature
   - Incomplete behavior
   - Safety or age-adaptation gap
   - UX gap
4. Cross-check open issues to remove duplicates
5. Prioritize P0-P3

**Checkpoint**: Present findings and ask which gaps should be tracked as issues.

### Step 2: File Confirmed Issues (from /create-issue)

For each confirmed gap:
1. Create title and body with spec reference + actual behavior
2. Assign labels and priority from conventions
3. Link parent epic/milestone
4. Create issue via `gh issue create`

## Output Format

```
## Audit & Fix: <area>

### Gaps Found
| # | Gap | Type | Priority | Already Tracked? |
|---|-----|------|----------|------------------|
| 1 | ... | Missing feature | P1 | No |

### Issues Created
| # | Title | Labels | Priority |
|---|-------|--------|----------|
| N | ... | ... | P1 |

### Not Filed
- #N — already tracked

### Suggested Execution
1. `/fix-issue #N` for high-priority bugs
2. `/plan #N` for multi-file stories
```

## Guardrails

- Never file issues without user confirmation of the final list
- Do not duplicate already-open issues
- Keep each issue scoped to one clear behavior gap
