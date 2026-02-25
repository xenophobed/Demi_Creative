# Kids Creative Workshop (儿童创意工坊)

AI-powered creative content platform for children aged 3-12. Children upload drawings and the system generates personalized, age-appropriate stories, interactive branching narratives, and child-friendly news summaries — all with content safety enforcement and TTS audio narration.

## Architecture at a Glance

```
FastAPI (backend/src/api/)
    └─► Agent Orchestrators (backend/src/agents/)
            └─► Claude Agent SDK
                    ├─► MCP Tool Servers (backend/src/mcp_servers/)
                    │       ├── vision_analysis_server    — Claude Vision API
                    │       ├── vector_search_server      — ChromaDB embeddings
                    │       ├── safety_check_server       — Content safety (required)
                    │       ├── tts_generator_server      — OpenAI TTS
                    │       └── video_generator_server    — Video generation
                    └─► Application Prompts (backend/src/prompts/)
                            ├── story-generation.md
                            ├── interactive-story.md
                            └── age-adapter.md

React SPA (frontend/src/)
    └─► API calls + SSE streaming → FastAPI routes
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| AI Engine | Claude Agent SDK (`claude_agent_sdk`), Anthropic API |
| MCP Tools | Custom Python MCP servers |
| Database | SQLite (via repository pattern) |
| Vector DB | ChromaDB (local) |
| TTS | OpenAI TTS API |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |

## Key Directories

```
creative_agent/
├── .claude/
│   ├── rules/               # Always-loaded conventions (label taxonomy, epics)
│   └── skills/              # Claude Code developer skills (slash commands)
├── backend/
│   └── src/
│       ├── agents/          # Claude Agent SDK orchestration
│       ├── api/routes/      # FastAPI endpoints
│       ├── mcp_servers/     # MCP tool server implementations
│       ├── prompts/         # Application-level agent prompts (markdown)
│       └── services/        # Session mgmt, database, TTS
├── frontend/src/            # React SPA
├── docs/
│   ├── product/             # PRD, domain knowledge
│   ├── architecture/        # System design, artifact graph model
│   └── guides/              # Development workflow guide
└── data/                    # Runtime: uploads/, audio/, sessions/
```

## Development Workflows

Always use `/investigate` before starting unfamiliar work:
```
/investigate <topic>
```

Use `/review` before merging any PR:
```
/review <PR number or branch>
```

Use `/commit` for all commits (enforces conventional commit format):
```
/commit
```

Use `/test` to add missing coverage:
```
/test backend/src/mcp_servers/safety_check_server.py
```

## Running the Project

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/start_server.py

# Frontend
cd frontend
npm install
npm run dev

# Tests
cd backend
python -m pytest tests/ -v
python -m pytest tests/contracts/ -v        # contract tests only
python -m pytest tests/integration/ -v     # integration tests only
```

## Environment Variables

```env
ANTHROPIC_API_KEY=...     # Required for Claude Agent SDK + Vision
OPENAI_API_KEY=...        # Required for TTS
CHROMA_PATH=./data/vectors
```

## Critical Project Rules

### Content Safety (Non-Negotiable)
All AI-generated content MUST pass through `check_content_safety` MCP tool before delivery.
Safety score threshold: >= 0.85. The `suggest_content_improvements` tool is used to fix failing content.

### Age Adaptation
Stories must be adapted to the child's age group (3-5, 6-8, 9-12). See `backend/src/prompts/age-adapter.md` for rules.

### TDD / Contract-Driven Development
- Write contract tests in `backend/tests/contracts/` before implementing MCP tools or agents
- Write API tests in `backend/tests/api/` before implementing routes
- Tests must pass before merging

### Agent SDK Fallback
All agent functions guard against `claude_agent_sdk` being unavailable:
```python
if ClaudeSDKClient is None or ClaudeAgentOptions is None:
    return _mock_result(...)   # Return deterministic mock for test environments
```

### MCP Tool Naming
Tool names follow the pattern `mcp__server-name__tool_name`:
- `mcp__vision-analysis__analyze_children_drawing`
- `mcp__vector-search__search_similar_drawings`
- `mcp__safety-check__check_content_safety`
- `mcp__tts-generation__generate_story_audio`

### No Direct DB Access from Agents
Agents must use services/repositories — never query SQLite directly.

### Application Prompts vs Claude Code Skills
- `backend/src/prompts/` — runtime prompts consumed by agents at application level
- `.claude/skills/` — Claude Code developer skills (slash commands for you, the developer)
  These are two completely separate layers. Do not mix them.

## Available Claude Code Skills

### Product Skills
| Command | Use When |
|---------|---------|
| `/product-audit [area]` | Find gaps between PRD and actual implementation |
| `/feature-spec [idea]` | Design a new feature before engineering |
| `/prd [action]` | Update the Product Requirements Document |

### Engineering Skills
| Command | Use When |
|---------|---------|
| `/issues [filter]` | See open issues, plan what to work on |
| `/investigate [topic]` | Before starting any unfamiliar work |
| `/plan [issue/description]` | Design implementation for multi-file changes |
| `/create-issue [description]` | Filing a GitHub issue |
| `/fix-issue [number]` | Resolving a GitHub issue end-to-end |
| `/codegen [description]` | Creating new code |
| `/test [file]` | Adding test coverage |
| `/debug [error]` | Something is broken |
| `/refactor [area]` | Improving code quality |
| `/review [PR/branch]` | Before merging |
| `/commit` | Creating a git commit |
| `/pr` | Opening a pull request |
| `/merge [PR number]` | Merging an approved PR |
| `/dev [start/stop/status]` | Start or stop dev servers |
| `/release [version]` | Cut a versioned release |
| `/docs [file/topic]` | Writing documentation |
