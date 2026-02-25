---
name: investigate
description: Investigate a codebase area, feature, or bug. Use when exploring unfamiliar code, understanding how something works, tracing data flow through the Kids Creative Workshop backend/frontend, or understanding agent/MCP tool interactions.
allowed-tools: Read, Grep, Glob, Bash(find:*), Bash(git log:*), Bash(git blame:*)
argument-hint: [topic or area to investigate]
context: fork
---

# Investigation Skill

Investigate: $ARGUMENTS

## Process

1. **Scope the investigation**: Identify what exactly needs to be understood
2. **Find entry points**: Use Grep/Glob to locate relevant files, functions, and classes
3. **Trace the flow**: Follow the code path from entry to exit
   - Data flow: where data comes from, how it's transformed, where it goes
   - Control flow: what triggers this code, what decisions are made
   - Dependencies: what external services/libraries are involved (Claude Agent SDK, MCP servers, ChromaDB, OpenAI TTS)
4. **Check history**: Use `git log` and `git blame` on key files to understand evolution
5. **Identify risks**: Note any code smells, tech debt, or potential issues
6. **Document findings**: Produce a clear summary

## Project-Specific Context

This is **Kids Creative Workshop** (儿童创意工坊), an AI-powered children's content platform.

Key layers to understand when investigating:
- **FastAPI routes** (`backend/src/api/routes/`) — HTTP entry points
- **Agent orchestrators** (`backend/src/agents/`) — Claude Agent SDK consumers
- **MCP tool servers** (`backend/src/mcp_servers/`) — Vision, VectorSearch, Safety, TTS tools
- **Application prompts** (`backend/src/prompts/`) — Story/age-adapter instruction files
- **Services** (`backend/src/services/`) — Session management, database, TTS
- **Database** (`backend/src/services/database/`) — SQLite via repositories
- **Frontend** (`frontend/src/`) — React + TypeScript SPA with Vite

## Output Format

Produce a structured report:
- **Summary**: 2-3 sentence overview
- **Key Files**: List of relevant files with their roles
- **Architecture**: How components connect (ASCII diagram if helpful)
- **Data Flow**: How data moves through the system
- **Risks & Concerns**: Anything noteworthy
- **Recommendations**: Suggested next steps

Refer to @CHECKLIST.md for investigation checklist items.
