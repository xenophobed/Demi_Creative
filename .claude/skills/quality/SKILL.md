---
name: quality
description: "Pipeline: test -> review -> refactor. Raise code quality with measurable safety checks."
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file or module to improve]
---

# Quality Pipeline Skill

Improve quality for: $ARGUMENTS

> **Pipeline skill** - composes `/test` -> `/review` -> `/refactor`.

## Pipeline Steps

### Step 1: Strengthen Tests (from /test)

1. Read target code and identify behaviors to lock down
2. Add/expand tests for happy path, edge cases, and failures
3. Run tests and ensure green baseline before refactor

**Checkpoint**: Show test coverage added and current pass/fail status.

### Step 2: Review for Risks (from /review)

1. Review target area for correctness, safety, and maintainability
2. List findings by severity: Must Fix / Should Fix / Suggestion
3. Select refactors that can be done without behavior changes

**Checkpoint**: Confirm which refactors should be applied now.

### Step 3: Refactor Safely (from /refactor)

1. Apply small refactors (naming, extraction, duplication removal, simplification)
2. Re-run tests after each refactor batch
3. Keep behavior unchanged and document trade-offs

## Output Format

```
## Quality: <target>

### Tests Added/Updated
- <test file>: <coverage summary>

### Review Findings
- Must Fix: N
- Should Fix: N
- Suggestion: N

### Refactors Applied
- <file>: <change and reason>

### Verification
- Command(s): <test commands>
- Result: pass/fail
```

## Guardrails

- Do not start refactoring before a passing test baseline exists
- Reject behavior-changing edits under this skill (use `/fix-issue` instead)
- Keep each refactor small and reversible
