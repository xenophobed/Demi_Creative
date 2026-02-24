---
name: fix-issue
description: Fix a GitHub issue end-to-end. Reads the issue, investigates, implements a fix, and prepares a PR. Use when resolving a tracked issue by number.
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: [issue number]
disable-model-invocation: true
---

# Fix Issue Skill

Fix issue #$ARGUMENTS

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Process

1. **Read the issue**:
   ```bash
   gh issue view $ARGUMENTS --json title,body,labels,comments,milestone
   ```

2. **Understand the problem**:
   - Parse the issue description and any reproduction steps
   - Read all comments for additional context
   - Identify acceptance criteria
   - Note the parent epic, domain, and layer from labels

3. **Investigate**:
   - Use `/investigate` approach to locate relevant code
   - Understand the current behaviour
   - Identify root cause (for bugs) or implementation plan (for stories)
   - Check contract tests in `backend/tests/contracts/` for affected interfaces

4. **Create a branch** following the naming convention:
   - Bug: `fix/$ARGUMENTS-<short-description>`
   - Story: `feat/$ARGUMENTS-<short-description>`
   - Chore: `chore/$ARGUMENTS-<short-description>`
   ```bash
   git checkout -b <prefix>/$ARGUMENTS-<short-description>
   ```

5. **Implement the fix**:
   - Make minimal, focused changes
   - Follow existing code patterns (async/await, Pydantic v2, repository pattern)
   - Add/update tests — TDD: write failing test first, then fix
   - Update `backend/src/prompts/` if agent behaviour needs changing

6. **Verify**:
   ```bash
   cd backend && python -m pytest tests/ -v
   ```
   - Manually verify the fix matches the issue description
   - Check for regressions in related tests

7. **Commit and prepare PR**:
   - Write a clear commit message referencing the issue
   - Push the branch
   - Create a PR with:
     - `Fixes #$ARGUMENTS` in the body
     - Reference to the parent epic
     - Summary of changes and testing done
     - Milestone inherited from the issue

## Output
- Summary of what was changed and why
- Link to the created PR
