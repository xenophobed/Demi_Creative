# Backend Overview

## What This Is

**Explorer**: The backend is the brain of the app. When you upload a drawing or start a story, the frontend sends a message to the backend, which figures out what to do — talk to AI, check safety, save to the database — and sends the result back.

**Maker**: The backend is a Python FastAPI application that orchestrates AI agents, MCP tool servers, and database operations. It follows a layered architecture: HTTP routes → dependency injection → agents → MCP tools → services → repositories → database. Each layer has a single responsibility and communicates through well-defined interfaces.

## Architecture Layers

```
HTTP Request from Frontend
     │
     ▼
┌─────────────────────┐
│  API Routes          │  backend/src/api/routes/
│  (14 route modules)  │  Parse request, validate, return response
└──────────┬──────────┘
           │
     ▼─────┴─────▼
┌──────────┐  ┌──────────┐
│ Auth     │  │ Quota    │  backend/src/api/deps.py
│ (deps)   │  │ Check    │  Dependency injection: who is this user? Can they generate?
└────┬─────┘  └────┬─────┘
     │              │
     ▼──────────────▼
┌─────────────────────┐
│  Agents              │  backend/src/agents/
│  (3 agent modules)   │  Orchestrate AI generation with Claude Agent SDK
└──────────┬──────────┘
           │
     ▼─────┴─────▼─────────▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ MCP      │  │ MCP      │  │ MCP      │  backend/src/mcp_servers/
│ Safety   │  │ Vision   │  │ TTS      │  7 tool servers the agent can call
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │
     ▼──────────────▼──────────────▼
┌─────────────────────┐
│  Services            │  backend/src/services/
│  (TTS, Auth, Memory) │  Business logic, external API wrappers
└──────────┬──────────┘
           │
     ▼─────┴─────▼
┌──────────────────────┐
│  Repositories         │  backend/src/services/database/
│  (20 repo modules)    │  CRUD operations on database tables
└──────────┬───────────┘
           │
     ▼─────┴─────▼
┌──────────┐  ┌──────────┐
│ SQLite   │  │ Postgres │  backend/src/services/database/
│ (dev)    │  │ (prod)   │  Adapter pattern selects at runtime
└──────────┘  └──────────┘
```

## Directory Map

| Directory | Files | Purpose |
|-----------|-------|---------|
| `agents/` | 3 | AI orchestration — each agent manages one creative workflow |
| `api/routes/` | 14 | HTTP endpoint handlers — one file per feature area |
| `api/` | 2 | Shared models (`models.py`) and auth/quota deps (`deps.py`) |
| `mcp_servers/` | 7 | MCP tool servers — specialized capabilities agents can call |
| `services/` | 14 | Business logic — TTS, auth, scheduling, memory, storage |
| `services/database/` | 20 | Repository pattern — one repo per database table |
| `prompts/` | 4 | Markdown prompt templates consumed by agents at runtime |
| `utils/` | 3 | Shared utilities — audio strategy, model config, text helpers |

## Key Design Patterns

### Agent SDK Fallback
All agent functions guard against the Claude SDK being unavailable (test environments):
```python
if ClaudeSDKClient is None:
    return _mock_result(...)  # Deterministic mock for tests
```

### Repository Pattern
Database access is always through repository objects (`session_repo`, `story_repo`, etc.) — never raw SQL in routes or agents. This makes it easy to swap database backends and write tests.

### Streaming (SSE)
Long-running generations use Server-Sent Events. The route yields events as the agent works:
```
event: status    → "Creating story..."
event: thinking  → AI reasoning content
event: tool_use  → "Checking content safety..."
event: result    → Final story data
event: complete  → Generation finished
```

### Talk-to-Buddy Voice Provider
Realtime voice sessions use `backend/src/services/realtime_voice_service.py` to pick a provider from `REALTIME_VOICE_PROVIDER`.

| Provider | Local behavior |
|----------|----------------|
| `mock` | Deterministic offline path for UI and contract tests. It always returns the canned transcript `hello buddy this is a mock transcript`. |
| `hybrid` | Real local path: OpenAI Whisper STT → My Agent reply → ElevenLabs TTS audio. Requires `OPENAI_API_KEY` for transcription and `ELEVENLABS_API_KEY` for spoken reply audio. |

If the provider flag is unset, local development falls back to `mock`, so hearing or seeing the canned transcript usually means the backend is not running with `REALTIME_VOICE_PROVIDER=hybrid`. Restart the backend after changing this env var; existing voice WebSocket sessions keep the provider they started with.

## Key Concepts

**FastAPI**: A modern Python web framework that uses type hints for automatic request validation, documentation generation, and async support. Think of it as the receptionist who takes requests and routes them to the right department.

**Dependency Injection**: Instead of each route function loading the user from the database itself, FastAPI "injects" the current user via `Depends(get_current_user)`. This keeps routes focused on their main job and makes auth reusable across all endpoints.

**MCP (Model Context Protocol)**: A standard for giving AI agents access to tools. The agent doesn't have built-in abilities to check safety or generate audio — it calls external tool servers via MCP, like a person using apps on their phone.

## Thinking Question

The backend has 7 MCP tool servers, but the agent decides which ones to call at runtime based on the task. What would happen if you added a new MCP tool server (say, `music_generator_server`) — would you need to modify the agent code? Think about how MCP tool discovery works and the trade-off between flexibility and predictability.
