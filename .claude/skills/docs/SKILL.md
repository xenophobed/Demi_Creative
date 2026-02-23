---
name: docs
description: Generate or update documentation for code, APIs, agent workflows, or features in the Kids Creative Workshop project.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file, module, or topic to document, e.g. "backend/src/mcp_servers/safety_check_server.py" or "image-to-story agent workflow"]
---

# Documentation Skill

Document: $ARGUMENTS

## Process

1. **Analyze the target**: Read the code to understand its purpose, inputs, outputs, and behaviour

2. **Check existing docs**: Look in `docs/` for existing documentation to update rather than duplicate
   - `docs/ARCHITECTURE.md` — technical architecture overview
   - `docs/PRD.md` — product requirements
   - `docs/DOMAIN.md` — domain background
   - `backend/docs/` — API-specific docs

3. **Generate documentation**:

   **For MCP tool servers** (`backend/src/mcp_servers/`):
   - Tool name, description, input schema, output schema
   - When to use / when not to use
   - Error conditions and fallback behaviour

   **For agent functions** (`backend/src/agents/`):
   - Function signature and parameters
   - Agent workflow step-by-step
   - `ClaudeAgentOptions` configuration
   - Streaming event types yielded
   - Structured output schema

   **For API routes** (`backend/src/api/routes/`):
   - Endpoint URL, method, request/response schema
   - Authentication requirements
   - Example request/response (in `backend/docs/`)

   **For application prompts** (`backend/src/prompts/`):
   - What agent uses this prompt
   - Key workflow steps described
   - Age adaptation rules if applicable
   - Safety requirements

   **For React components** (`frontend/src/`):
   - Props interface (TypeScript)
   - Usage example
   - State management (which Zustand store)
   - SSE events consumed

4. **Add inline comments**: For complex logic that needs explanation
   - Agent tool call sequences
   - Age-group config lookups
   - Safety score threshold logic

5. **Verify**: Ensure code examples in docs actually work
   - Test any bash commands shown
   - Verify API examples against actual Pydantic schemas
