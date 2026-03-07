---
name: fix
description: "Pipeline: fetch issue -> fix with TDD -> review -> commit -> PR. Resolve an issue end-to-end in one guided flow."
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: [issue number]
---

# Fix Pipeline Skill

Fix issue: #$ARGUMENTS

> **Pipeline skill** - composes `/fix-issue` -> `/review` -> `/commit` -> `/pr`.

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Scope Check

Before starting, classify complexity:
- Small/medium issue (about 1-5 files): continue in this pipeline
- Large issue (many files, architecture-level change): run `/plan #$ARGUMENTS` first

## Pipeline Steps

### Step 1: Read and Investigate (from /fix-issue)

1. Read issue details and comments
2. Identify acceptance criteria and labels
3. Locate affected code paths and probable root cause
4. Decide test layers needed for safe change

**Checkpoint**: Show investigation summary and proposed fix path.

### Step 2: Implement with TDD (from /fix-issue + /test)

1. Create issue branch with project naming convention
2. Write failing test first (RED)
3. Implement minimal fix (GREEN)
4. Re-run focused and related tests

**Checkpoint**: Show changed files + test results.

### Step 3: Self Review (from /review)

1. Review the diff for correctness, safety, and maintainability
2. Resolve any Must Fix findings before shipping
3. Re-run tests if review changes were applied

### Step 4: Commit and PR (from /commit + /pr)

1. Stage intended files only
2. Commit with conventional format and issue reference
3. Push branch and create PR with `Fixes #$ARGUMENTS`
4. Inherit milestone/epic context from issue when available

## Output Format

```
## Fixed: #<issue>

### Investigation
- Root cause: <summary>
- Scope: <files/modules>

### Changes Applied
- <file>: <what changed>

### Tests
- Commands: <commands>
- Result: pass/fail

### Review
- Must Fix resolved: <yes/no>

### PR
- <url>
```

## Guardrails

- Never skip tests for behavior changes
- Keep fix scoped to issue acceptance criteria
- Avoid unrelated refactors in this pipeline
