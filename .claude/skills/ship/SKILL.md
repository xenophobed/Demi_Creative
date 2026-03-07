---
name: ship
description: "Pipeline: commit -> PR -> optional review. Ship current branch in one guided flow."
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: [optional commit message or PR title]
---

# Ship Pipeline Skill

Ship current work: $ARGUMENTS

> **Pipeline skill** - composes `/commit` -> `/pr` -> optional `/review`.

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Pipeline Steps

### Step 1: Commit (from /commit)

1. Inspect working tree and staged changes
2. Stage required files safely
3. Create conventional commit message
4. Commit and show summary

**Checkpoint**: Confirm commit details before creating PR.

### Step 2: Create PR (from /pr)

1. Push branch to origin
2. Build PR title/body from changes and linked issue context
3. Create PR and show URL

**Checkpoint**: Ask whether to run a review pass now.

### Step 3: Optional Review (from /review)

If requested:
1. Review PR diff for correctness/security/performance
2. Report severity-based findings
3. Provide merge readiness verdict

## Output Format

```
## Shipped

### Commit
<hash> <message>

### PR
<url>

### Review (optional)
- Verdict: Approve / Request Changes / Comment
- Must Fix: N
```

## Guardrails

- Never push directly to `main`
- Stop if there are failing required checks
- If sensitive files are detected, warn and require explicit confirmation
