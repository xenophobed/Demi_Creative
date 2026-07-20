# Infrastructure Overview

## What This Is

**Explorer**: Infrastructure is where our app lives on the internet. Just like a restaurant needs a building, a kitchen, and a menu board, our app needs three services: one to show the website (Vercel), one to do the thinking (Railway), and one to remember everything (Supabase).

**Maker**: The production infrastructure uses three managed cloud services, each handling a distinct concern. This separation follows the principle of single responsibility at the infrastructure level — each service does one thing well, and they communicate over HTTPS.

## How the Three Services Work Together

```
User's Browser
     │
     ▼
┌─────────────┐
│   Vercel    │  ← Hosts the React SPA (frontend)
│   (CDN)     │     creative.demi-app.com
└──────┬──────┘
       │ HTTPS API calls
       ▼
┌─────────────┐
│  Railway    │  ← Runs the FastAPI server (backend)
│  (Server)   │     Backend deploys manually from the repository
└──────┬──────┘
       │ SQL + Auth
       ▼
┌─────────────┐
│  Supabase   │  ← PostgreSQL database + Auth + Storage
│  (Database) │     Manages users, sessions, stories, vectors
└─────────────┘
       │
       ▼
   AI APIs (Anthropic, OpenAI, ElevenLabs, Tavily)
```

## What Each Service Does

| Service | Role | URL | Deploys How |
|---------|------|-----|-------------|
| **[Vercel](./vercel.md)** | Hosts the React frontend as static files on a CDN | `creative.demi-app.com` | Manual `vercel --prod` from CLI |
| **[Railway](./railway.md)** | Runs the Python FastAPI backend server | Internal Railway URL | Auto-deploys when `main` branch updates on GitHub |
| **[Supabase](./supabase.md)** | PostgreSQL database + email auth + file storage | Supabase project URL | Always running (managed service) |

## How Deployment Works

**Explorer**: When we change the code and push it to GitHub, the servers automatically update — like a magic notebook where whatever you write appears on everyone's screen.

**Builder**: Deployment is the process of taking code from your computer and putting it on a server so users can access it. We have two deployment modes:
- **Backend (Railway)**: Automatic — push to `main` on GitHub and Railway rebuilds + restarts
- **Frontend (Vercel)**: Manual — run `vercel --prod` from the CLI to build and deploy

**Maker**: The split deployment model (auto backend, manual frontend) is intentional. Backend changes that break the API are immediately visible through health checks and error logs. Frontend changes are visual — we want to verify the build locally before pushing to production. Both could be fully automated with CI/CD, but the manual frontend step adds a human review gate.

## Supporting Infrastructure

- **[Database Adapter](./database-adapter.md)** — How the backend supports both SQLite (development) and PostgreSQL (production) with the same code
- **[Environment Variables](./environment-variables.md)** — How secrets and configuration flow to each service

## Key Concepts

**CDN (Content Delivery Network)**: Copies of your website stored on servers around the world. When a user in Tokyo visits the site, they get the copy from a nearby server instead of one in the US — much faster.

**Managed Service**: A cloud service where someone else handles the hardware, backups, security patches, and uptime. We focus on building the app, not maintaining servers.

**Health Check**: A simple API endpoint (`/health`) that returns "ok" if the server is running correctly. Railway and monitoring tools ping this periodically to detect outages.

## Thinking Question

Our backend and frontend are currently deployed manually from the same repository. What could go wrong if we deploy a backend change that adds a new API field, but forget to deploy the frontend that needs that field? How would you design a system to prevent this mismatch?
