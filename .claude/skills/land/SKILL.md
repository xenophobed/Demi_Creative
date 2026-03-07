---
name: land
description: "Pipeline: review -> merge -> cleanup. Land a ready PR safely after final checks."
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(gh:*)
argument-hint: [PR number]
---

# Land Pipeline Skill

Land PR: $ARGUMENTS

> **Pipeline skill** - composes final `/review` -> `/merge` -> local cleanup.

## Pipeline Steps

### Step 1: Final Review Gate (from /review)

1. Resolve PR number from `$ARGUMENTS` or current branch
2. Pull PR metadata, checks, and diff
3. Review for correctness, safety, and regressions
4. Categorize findings by severity

**Hard stop rule**: If any Must Fix finding exists, stop and do not merge.

### Step 2: Merge Gate (from /merge)

Proceed only when all conditions pass:
1. PR state is OPEN
2. Review decision is APPROVED
3. Required checks pass
4. PR is MERGEABLE (no conflicts)

Then merge with squash strategy and delete remote branch.

### Step 3: Local Cleanup

1. Switch to `main`
2. Pull latest `origin/main`
3. Delete local topic branch safely (`git branch -d`)
4. Confirm local repo is clean and up to date

## Output Format

```
## Landed: PR #<number>

### Review Gate
- Verdict: Approve / Request Changes
- Must Fix: N

### Merge
- Strategy: squash
- Commit: <hash>

### Cleanup
- Remote branch: deleted/not deleted
- Local branch: deleted/not deleted
- Current branch: main
```

## Guardrails

- Never merge with failing required checks
- Never force-delete local branch by default
- If merge is blocked, report exact blocker and next command (`/debug`, `/fix`, `/review`)
