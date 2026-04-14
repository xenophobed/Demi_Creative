# Railway — Backend Server Hosting

**Config**: `backend/railway.toml` | **Entry**: `backend/src/main.py`

## What This File Does

**Explorer**: Railway is like a house for our Python brain. When someone visits the website and asks for a story, the request travels to Railway where our FastAPI server lives, thinks about it, and sends back the answer.

**Maker**: Railway is a PaaS (Platform as a Service) that runs our FastAPI backend as a containerized process. It auto-deploys from the `main` branch on GitHub using Nixpacks (a buildpack system), injects environment variables, and provides health monitoring.

## How It Works

### Deployment Pipeline
```
1. Developer pushes to main branch on GitHub
2. Railway detects the push → triggers a new build
3. Nixpacks reads requirements.txt → installs Python dependencies
4. Railway runs the start command: python backend/scripts/start_server.py
5. Server starts on Railway's assigned PORT → health check passes
6. Railway routes traffic to the new deployment → old one shuts down
```

### Configuration (`railway.toml`)
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python backend/scripts/start_server.py"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### What the Health Check Does
Railway pings `GET /health` every few seconds. The endpoint returns:
- Server status (ok/degraded)
- Database connection status
- MCP server availability
- Version number

If health checks fail, Railway automatically restarts the process (up to 3 retries).

## Key Concepts

**PaaS (Platform as a Service)**: A cloud service that runs your code without you managing servers, operating systems, or networking. You give it code; it handles the rest.

**Nixpacks**: Railway's build system that auto-detects your language (Python, Node, etc.) and installs dependencies. It reads `requirements.txt` for Python and creates a container image automatically.

**Auto-Deploy**: Every push to the `main` branch triggers a new deployment. This means code merged on GitHub is live in production within ~2 minutes. Fast feedback, but also means broken code deploys immediately.

**Zero-Downtime Deploy**: Railway starts the new version alongside the old one, waits for the health check to pass, then switches traffic. Users never see downtime during deployments.

## Connections

- **Upstream**: Receives HTTPS requests from the Vercel frontend and direct API calls
- **Downstream**: Connects to Supabase PostgreSQL via `DATABASE_URL` env var
- **External APIs**: Calls Anthropic (Claude), OpenAI (TTS), ElevenLabs, Tavily from Railway's server
- **Config**: Environment variables set via Railway dashboard (not in code)

## Thinking Question

Railway auto-deploys every push to `main`. What if someone merges a broken migration that corrupts the database? The code deploys, the server starts, but database queries fail. How would you add a pre-deploy check that runs migrations in a test database first? Think about: staging environments, migration dry-runs, and rollback strategies.
