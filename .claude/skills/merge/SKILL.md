---
name: merge
description: Merge a pull request after verifying it is approved, CI passes, and there are no conflicts. Squash-merges by default, cleans up remote and local branches, and pulls latest main.
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: [PR number]
---

# Merge Skill

Merge PR: $ARGUMENTS

## Context

- Current branch: !`git branch --show-current`
- PR status: !`gh pr view $ARGUMENTS --json state,reviewDecision,statusCheckRollup,mergeable,headRefName,baseRefName,title --jq '{state,reviewDecision,mergeable,title,head:.headRefName,base:.baseRefName,checks:(.statusCheckRollup // [] | length)}'`

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Pre-merge Checklist

Before merging, verify ALL of the following. If any check fails, stop and report why.

1. **PR exists and is open**
   ```bash
   gh pr view $ARGUMENTS --json state --jq '.state'
   ```
   Must be `OPEN`. If already merged or closed, report and stop.

2. **Review approved**
   ```bash
   gh pr view $ARGUMENTS --json reviewDecision --jq '.reviewDecision'
   ```
   Must be `APPROVED`. If not reviewed, suggest running `/review $ARGUMENTS` first.

3. **CI checks pass** (if configured)
   ```bash
   gh pr checks $ARGUMENTS
   ```
   All required checks must pass. If failing, suggest `/debug` to investigate.

4. **No merge conflicts**
   ```bash
   gh pr view $ARGUMENTS --json mergeable --jq '.mergeable'
   ```
   Must be `MERGEABLE`. If conflicted, report and suggest resolving conflicts first.

5. **Branch is up to date with base**
   ```bash
   gh pr view $ARGUMENTS --json baseRefName,headRefName
   ```

## Process

1. **Run pre-merge checklist** — stop if any check fails
2. **Squash merge** (default strategy for clean history):
   ```bash
   gh pr merge $ARGUMENTS --squash --delete-branch
   ```
3. **Switch to main and pull latest**:
   ```bash
   git checkout main
   git pull origin main
   ```
4. **Clean up local branch** (if it exists locally):
   ```bash
   git branch -d <branch-name>
   ```
   Use `-d` (safe delete) — never `-D`.
5. **Verify merge**:
   ```bash
   git log --oneline -3
   ```

## Error Handling

| Problem | Action |
|---------|--------|
| PR not approved | Stop. Suggest `/review $ARGUMENTS` |
| CI checks failing | Stop. Suggest `/debug <failure>` |
| Merge conflicts | Stop. Suggest `rebase my branch on main and resolve conflicts` |
| PR already merged | Report it and show the merge commit |
| PR is closed (not merged) | Report it — do not reopen |

## Output

- Confirmation that the PR was merged
- The squash commit hash on main
- Branches cleaned up (remote + local)
- Current state: on `main`, up to date
