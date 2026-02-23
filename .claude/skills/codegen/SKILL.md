---
name: codegen
description: Generate new code — API routes, agent functions, MCP tool servers, React components, Pydantic models, repository methods, or tests. Use for any code creation task in the Kids Creative Workshop project.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [what to generate, e.g. "MCP tool for image resize" or "React component for audio player"]
---

# Code Generation Skill

Generate: $ARGUMENTS

## Process

1. **Understand requirements**: Parse what needs to be built

2. **Study existing patterns**:
   - Find similar code in the project and match the style
   - Check for shared utilities, base classes, or conventions
   - Review `CLAUDE.md` for project-specific conventions
   - Key pattern examples:
     - MCP tools: see `backend/src/mcp_servers/`
     - Agent functions: see `backend/src/agents/`
     - API routes: see `backend/src/api/routes/`
     - Pydantic models: see `backend/src/api/models.py`
     - Repository pattern: see `backend/src/services/database/`
     - React components: see `frontend/src/components/`
     - Zustand stores: see `frontend/src/store/`

3. **Plan the structure**:
   - List files to create/modify
   - Define interfaces/types first (Pydantic models, TypeScript types)
   - Plan the dependency graph

4. **Generate code**:
   - Follow project naming conventions
   - Include proper error handling
   - Add appropriate types/interfaces
   - Write docstrings/JSDoc for public APIs
   - For async Python: always use `async def` with `await`
   - For MCP tools: use `@tool` decorator pattern from existing servers

5. **Add tests**:
   - Contract tests for MCP tools (`backend/tests/contracts/`)
   - API tests for routes (`backend/tests/api/`)
   - Match the project's pytest patterns

6. **Verify**:
   - Run linter: `cd backend && python -m ruff check .` (if available)
   - Run the new tests: `cd backend && python -m pytest tests/ -k "<new_test>" -v`
   - Run related existing tests

## Project Conventions

- **Python**: async/await everywhere in agents and MCP servers; Pydantic v2 for models
- **TypeScript**: strict mode; functional React components with hooks
- **Test pattern**: Contract-driven — define input/output schemas first, then implement
- **MCP tool naming**: `mcp__server-name__tool_name` (kebab-case server, snake_case tool)
- **Language**: Code comments and docstrings in English; user-facing content bilingual (Chinese primary)
- **Safety**: All generated story content must pass through `check_content_safety` MCP tool

## Principles

- Match existing code style exactly
- Handle errors explicitly with try/except; yield error events in streaming functions
- Keep functions focused and small
- Follow the repository pattern for database access — never query SQLite directly from agents
- Add fallback/mock behaviour for when `claude_agent_sdk` is unavailable (test environments)
