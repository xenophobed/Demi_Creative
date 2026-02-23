# Investigation Checklist

## General
- [ ] Entry points identified (API routes, agent functions, or frontend pages)
- [ ] All relevant files located
- [ ] Data flow traced end-to-end
- [ ] Error handling paths checked
- [ ] External dependencies cataloged
- [ ] Configuration/env vars documented
- [ ] Tests coverage assessed
- [ ] Recent changes reviewed (git log)

## Backend-Specific
- [ ] FastAPI route → agent → MCP tool chain traced
- [ ] Claude Agent SDK options (allowed_tools, mcp_servers, max_turns) reviewed
- [ ] MCP server tool contracts checked (input/output schemas)
- [ ] Database repository pattern understood
- [ ] Session management behaviour verified
- [ ] Pydantic models validated

## Frontend-Specific
- [ ] React component tree understood
- [ ] API client calls identified (frontend/src/api/)
- [ ] Zustand store interactions mapped
- [ ] Streaming SSE event handling reviewed

## Agent-Specific
- [ ] System prompt / application prompt located (backend/src/prompts/)
- [ ] Tool call sequence documented
- [ ] Structured output schema verified
- [ ] Fallback / mock behaviour understood
- [ ] Audio generation flow traced (age-group → voice → TTS MCP tool)
