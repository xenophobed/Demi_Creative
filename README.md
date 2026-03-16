# Kids Creative Workshop

> AI-powered creative content platform for children aged 3-12

Kids Creative Workshop uses Claude Agent SDK to generate personalized, age-appropriate stories, interactive branching narratives, and child-friendly news summaries from children's drawings — all with mandatory content safety enforcement and TTS audio narration.

## Architecture

```
React SPA (frontend/src/)
    └── API calls + SSE streaming
            ↓
FastAPI (backend/src/api/routes/)
    └── Agent Orchestrators (backend/src/agents/)
            └── Claude Agent SDK
                    ├── MCP Tool Servers (backend/src/mcp_servers/)
                    │       ├── vision_analysis_server    — Claude Vision API
                    │       ├── vector_search_server      — ChromaDB embeddings
                    │       ├── safety_check_server       — Content safety (required)
                    │       ├── tts_generator_server      — OpenAI TTS
                    │       ├── video_generator_server     — Video generation
                    │       └── web_search_server          — Web search
                    └── Application Prompts (backend/src/prompts/)
                            ├── story-generation.md
                            ├── interactive-story.md
                            ├── morning-show.md
                            └── age-adapter.md
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| AI Engine | Claude Agent SDK, Anthropic API |
| MCP Tools | Custom Python MCP servers |
| Database | SQLite (via repository pattern) |
| Vector DB | ChromaDB (local, for memory/embeddings) |
| TTS | OpenAI TTS API |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |

## Quick Start

### 1. Environment Variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=...     # Required — Claude Agent SDK + Vision
OPENAI_API_KEY=...        # Required — TTS audio narration
CHROMA_PATH=./data/vectors
```

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/start_server.py
```

The API server starts at `http://localhost:8000`. API docs are available at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5173`.

### 4. Run Tests

```bash
cd backend

# All tests
python -m pytest tests/ -v

# Contract tests only
python -m pytest tests/contracts/ -v

# API tests only
python -m pytest tests/api/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Database tests only
python -m pytest tests/database/ -v
```

## Project Structure

```
creative_agent/
├── .claude/
│   ├── rules/                  # Project conventions (labels, epics)
│   └── skills/                 # Claude Code developer skills
├── backend/
│   ├── scripts/                # start_server.py, run_tests.py, etc.
│   └── src/
│       ├── agents/             # Claude Agent SDK orchestrators
│       │   ├── image_to_story_agent.py
│       │   ├── interactive_story_agent.py
│       │   ├── morning_show_agent.py
│       │   └── news_to_kids_agent.py
│       ├── api/
│       │   ├── routes/         # FastAPI endpoint modules
│       │   ├── models.py       # Request/response models
│       │   └── deps.py         # Dependency injection
│       ├── mcp_servers/        # MCP tool server implementations
│       │   ├── vision_analysis_server.py
│       │   ├── vector_search_server.py
│       │   ├── safety_check_server.py
│       │   ├── tts_generator_server.py
│       │   ├── video_generator_server.py
│       │   └── web_search_server.py
│       ├── prompts/            # Runtime agent prompts (markdown)
│       ├── services/           # Business logic layer
│       │   ├── database/       # SQLite repositories & migrations
│       │   ├── models/         # Domain models
│       │   ├── session_manager.py
│       │   ├── tts_service.py
│       │   ├── user_service.py
│       │   └── ...
│       └── utils/
├── backend/tests/
│   ├── api/                    # API route tests
│   ├── contracts/              # Contract tests (TDD)
│   ├── database/               # Database/repository tests
│   └── integration/            # Integration tests
├── frontend/src/               # React SPA
│   ├── components/
│   ├── pages/
│   ├── api/
│   ├── store/                  # Zustand state management
│   └── hooks/
├── docs/
│   ├── product/                # PRD, domain knowledge
│   ├── architecture/           # System design docs
│   └── guides/                 # Development workflow guide
└── data/                       # Runtime data (uploads/, audio/, sessions/)
```

## Core Features

- **Image-to-Story**: Children upload drawings; Claude Vision analyzes them and generates personalized stories
- **Interactive Stories**: Multi-branch narratives where children choose the path
- **News-to-Kids (Morning Show)**: Adult news rewritten as age-appropriate summaries with illustrations and TTS
- **Content Safety**: All AI-generated content passes through `safety_check_server` (score >= 0.85 required)
- **Age Adaptation**: Stories adapt vocabulary, length, and complexity to age groups (3-5, 6-8, 9-12)
- **TTS Audio**: OpenAI TTS generates narration for all content types
- **My Library**: Unified content library for saved stories and artifacts

## Development Conventions

### TDD / Contract-Driven

Write contract tests in `backend/tests/contracts/` before implementing MCP tools or agents. Write API tests in `backend/tests/api/` before implementing routes. Tests must pass before merging.

### Agent SDK Fallback

All agent functions guard against `claude_agent_sdk` being unavailable, returning deterministic mocks in test environments.

### Commit Format

```
feat: add character memory to story generation
fix: correct safety score threshold check
docs: update architecture diagram
test: add contract test for morning show agent
```

### Branch Naming

```
feat/<issue#>-<short-desc>
fix/<issue#>-<short-desc>
chore/<issue#>-<short-desc>
```

## License

MIT License
