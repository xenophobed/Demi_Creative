---
name: fix-issue
description: Fix a GitHub issue end-to-end. Reads the issue, investigates, implements a fix, and prepares a PR. Use when resolving a tracked issue by number.
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: [issue number]
disable-model-invocation: true
---

# Fix Issue Skill

Fix issue #$ARGUMENTS

## Process

1. **Read the issue**:
   ```bash
   gh issue view $ARGUMENTS --json title,body,labels,comments
   ```

2. **Understand the problem**:
   - Parse the issue description and any reproduction steps
   - Read all comments for additional context
   - Identify acceptance criteria
   - Identify which layer is affected (routes / agents / MCP servers / services / frontend)

3. **Investigate**:
   - Use `/investigate` approach to locate relevant code
   - Understand the current behaviour
   - Identify root cause (for bugs) or implementation plan (for features)
   - Check contract tests in `backend/tests/contracts/` for affected interfaces

4. **Create a branch**:
   ```bash
   git checkout -b fix/$ARGUMENTS-<short-description>
   ```

5. **Implement the fix**:
   - Make minimal, focused changes
   - Follow existing code patterns (async/await, Pydantic v2, repository pattern)
   - Add/update tests — TDD: write failing test first, then fix
   - Update `backend/src/prompts/` if agent behaviour needs changing
   - Update documentation if needed

6. **Verify**:
   ```bash
   cd backend && python -m pytest tests/ -v
   ```
   - Manually verify the fix matches the issue description
   - Check for regressions in related tests

7. **Commit and prepare PR**:
   - Write a clear commit message referencing the issue (e.g., `fix: resolve TTS audio path extraction (#$ARGUMENTS)`)
   - Push the branch
   - Create a PR with:
     - Reference to the issue (`Fixes #$ARGUMENTS`)
     - Summary of changes
     - Testing done
     - Any notes on agent/MCP behaviour changes

## Output
- Summary of what was changed and why
- Link to the created PR
