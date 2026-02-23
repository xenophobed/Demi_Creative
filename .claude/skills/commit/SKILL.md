---
name: commit
description: Create a well-structured git commit from current changes using conventional commit format.
allowed-tools: Bash(git:*)
argument-hint: [optional commit message override]
disable-model-invocation: true
---

# Smart Commit Skill

## Context

- Current status: !`git status --short`
- Staged diff: !`git diff --staged`
- Unstaged changes: !`git diff`
- Current branch: !`git branch --show-current`
- Recent commits for style reference: !`git log --oneline -5`

## Process

1. If nothing is staged, stage all changes: `git add -A`
2. Analyze the diff to understand what changed
3. Generate a commit message following conventional commits:
   ```
   type(scope): concise description

   - Detail of change 1
   - Detail of change 2
   ```
   **Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `perf`, `ci`

   **Scopes for this project**:
   - `agent` — changes to `backend/src/agents/`
   - `mcp` — changes to `backend/src/mcp_servers/`
   - `api` — changes to `backend/src/api/`
   - `prompts` — changes to `backend/src/prompts/`
   - `db` — changes to `backend/src/services/database/`
   - `frontend` — changes to `frontend/src/`
   - `skills` — changes to `.claude/skills/`
   - `config` — changes to config/env files

4. If `$ARGUMENTS` is provided, use it as the message instead
5. Create the commit
6. Show the result with `git log --oneline -1`

## Examples

```
feat(agent): add streaming support to image-to-story agent

fix(mcp): correct TTS audio path extraction from tool result

refactor(prompts): move inline age-adapter prompt to backend/src/prompts/

test(api): add contract tests for safety check MCP tool

docs(skills): add SDLC Claude Code skills and CLAUDE.md
```
