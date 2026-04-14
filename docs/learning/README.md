# Learning Guide: Kids Creative Workshop

Welcome! This guide explains every part of our application — how it works, why it's built this way, and how the pieces connect. Whether you're a student learning to code, a teacher guiding a project, or a developer onboarding to the codebase, start here.

## Who Is This For?

| Level | Age | What You'll Get |
|-------|-----|-----------------|
| **Explorer** | K-5 | Simple analogies, big-picture understanding, fun "what if" questions |
| **Builder** | 6-8 | Technical terms with definitions, how files connect, basic architecture |
| **Maker** | 9-12 | Design trade-offs, algorithm choices, system constraints, engineering thinking |

Every doc includes all three levels — start with what makes sense for you.

## How the App Works (30-Second Version)

Kids Creative Workshop is an AI-powered creative platform for children aged 3-12. A child can:

1. **Upload a drawing** → AI analyzes it and writes a personalized story
2. **Play an interactive story** → Choose-your-own-adventure with branching paths
3. **Listen to a kids podcast** → AI-generated news episodes adapted to their age
4. **Collect daily rewards** → Tear open a newspaper, earn stars, open mystery bags

The app has three layers:

```
Frontend (React)  ←→  Backend (FastAPI/Python)  ←→  AI + Database
   What you see         The brain                  Memory + intelligence
```

## Guide Structure

### [Infrastructure](./infrastructure/overview.md) — Where the app lives
How we deploy the app to the internet so real users can use it.
- [Supabase](./infrastructure/supabase.md) — Authentication and hosted database
- [Railway](./infrastructure/railway.md) — Backend server hosting
- [Vercel](./infrastructure/vercel.md) — Frontend hosting
- [Database Adapter](./infrastructure/database-adapter.md) — How we support SQLite (dev) and PostgreSQL (prod)
- [Environment Variables](./infrastructure/environment-variables.md) — Secret keys and configuration

### [Backend](./backend/overview.md) — The brain of the app
Python code that processes requests, talks to AI, and manages data.

#### [Agents](./backend/agents/) — AI orchestration
- [Image-to-Story Agent](./backend/agents/image-to-story-agent.md) — Turns drawings into stories
- [Interactive Story Agent](./backend/agents/interactive-story-agent.md) — Branching narratives
- [Kids Daily Agent](./backend/agents/kids-daily-agent.md) — Daily news podcast generation

#### [MCP Servers](./backend/mcp-servers/) — AI tool servers
- [Safety Check](./backend/mcp-servers/safety-check-server.md) — Content safety enforcement
- [Vision Analysis](./backend/mcp-servers/vision-analysis-server.md) — Image understanding
- [Vector Search](./backend/mcp-servers/vector-search-server.md) — Similar content lookup
- [TTS Generator](./backend/mcp-servers/tts-generator-server.md) — Text-to-speech audio
- [Video Generator](./backend/mcp-servers/video-generator-server.md) — Video creation
- [Web Search](./backend/mcp-servers/web-search-server.md) — Real-time news fetching
- [Image Style](./backend/mcp-servers/image-style-server.md) — Art style transfer

#### [API Routes](./backend/api/) — HTTP endpoints
- [Overview](./backend/api/overview.md) — How the API is structured
- Per-route docs for all 14 route modules

#### [Services](./backend/services/) — Business logic
- [Overview](./backend/services/overview.md) — Service layer design
- Per-service docs for database, TTS, auth, memory, and more

#### [Prompts](./backend/prompts/) — AI instructions
- How prompt files guide agent behavior

### [Frontend](./frontend/overview.md) — What users see and touch
React code that renders the UI and manages user interactions.

#### [Pages](./frontend/pages/) — Full-screen views
- Per-page docs for all 10+ pages

#### [Components](./frontend/components/) — Reusable UI pieces
- Grouped by subfolder: common, daily, interactive, story, streaming, effects, depth, layout, upload

#### [State Management](./frontend/store/) — App memory
- Zustand stores for auth, child profile, stories, daily tasks

#### [Hooks](./frontend/hooks/) — Shared logic
- Custom React hooks for audio, stories, generation, parallax

#### [API Client](./frontend/api/) — Talking to the backend
- HTTP client, service modules, SSE streaming

#### [Providers](./frontend/providers/) — Global context
- Auth provider, stream visualization, audio context

## Document Template

Every file doc follows this structure:

```
## What This File Does
One sentence for Explorer level, one for Maker level.

## How It Works
Step-by-step explanation with age-tier annotations.

## Key Concepts
1-3 terms defined simply.

## Connections
Which files this one talks to (upstream and downstream).

## Thinking Question
A "what if" question to build reasoning skills.
```

## Quick Links

| I want to... | Start here |
|--------------|------------|
| Understand the big picture | [Infrastructure Overview](./infrastructure/overview.md) |
| Learn how AI generates stories | [Image-to-Story Agent](./backend/agents/image-to-story-agent.md) |
| Understand the database | [Database Adapter](./infrastructure/database-adapter.md) |
| Learn how the UI works | [Frontend Overview](./frontend/overview.md) |
| Understand authentication | [Supabase](./infrastructure/supabase.md) |
| Learn about content safety | [Safety Check Server](./backend/mcp-servers/safety-check-server.md) |
