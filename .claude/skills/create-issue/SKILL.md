---
name: create-issue
description: Create a well-structured GitHub issue from a description or bug report. Use when filing new bugs, feature requests, or tasks for the Kids Creative Workshop project.
allowed-tools: Bash(gh:*), Read, Grep, Glob
argument-hint: [issue title or description]
disable-model-invocation: true
---

# Create Issue Skill

Create issue: $ARGUMENTS

## Process

1. **Analyze the request**: Determine if this is a bug, feature, task, or improvement

2. **Research context**:
   - Search codebase for relevant files and current behaviour
   - Check for existing related issues: `gh issue list --search "$ARGUMENTS"`
   - Identify affected components (backend/frontend/agent/MCP/database)

3. **Draft the issue**:

### For Bugs:
```
Title: [Bug] <concise description>

## Description
<What's happening vs what should happen>

## Steps to Reproduce
1. ...
2. ...

## Expected Behavior
<What should happen>

## Actual Behavior
<What actually happens, including any error messages>

## Affected Component
- [ ] FastAPI routes (backend/src/api/routes/)
- [ ] Agent orchestration (backend/src/agents/)
- [ ] MCP tool server (backend/src/mcp_servers/)
- [ ] Database/services (backend/src/services/)
- [ ] Frontend (frontend/src/)
- [ ] Application prompts (backend/src/prompts/)

## Affected Files
- `path/to/file.py` — <why relevant>

## Possible Fix
<If you have an idea>
```

### For Features:
```
Title: [Feature] <concise description>

## Summary
<What and why>

## Motivation
<Problem this solves for the children / parents using the platform>

## Proposed Solution
<How to implement, referencing the agent-first architecture>

## Alternatives Considered
<Other approaches>

## Affected Areas
- <component/module>
```

4. **Create**: Use `gh issue create` with the drafted content
5. **Add labels**: Apply appropriate labels based on type and priority
6. **Report**: Show the created issue URL

## Labels Guide

- `bug` — something is broken
- `enhancement` — new feature or improvement
- `agent` — relates to Claude Agent SDK or MCP tools
- `content-safety` — relates to children's content safety system
- `documentation` — docs needed
- `good first issue` — beginner friendly
- `priority:high` / `priority:low` — urgency
- `backend` / `frontend` — layer affected
