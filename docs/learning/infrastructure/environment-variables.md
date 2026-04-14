# Environment Variables — Secrets and Configuration

**Reference**: `backend/.env.example`

## What This File Does

**Explorer**: Environment variables are like secret passwords written on a sticky note that only the server can read. We never put passwords in our code (anyone could see them on GitHub!), so instead we give them to the server separately, like whispering a secret.

**Maker**: Environment variables decouple secrets and configuration from source code. They're injected at runtime by the hosting platform (Railway, Vercel) or loaded from `.env` files locally. This follows the twelve-factor app methodology — config that varies between environments (dev/staging/prod) lives in the environment, not the codebase.

## How Variables Flow

```
Development (your laptop):
  .env file → loaded by Python dotenv / Vite → available in code

Production (Railway + Vercel):
  Railway Dashboard → injected into container → os.environ["KEY"]
  Vercel Dashboard  → injected at build time → import.meta.env.VITE_KEY
```

## Required Variables

### Backend (Railway)

| Variable | Purpose | Where to Get It |
|----------|---------|-----------------|
| `ANTHROPIC_API_KEY` | Claude API for agents, vision, safety checks | console.anthropic.com |
| `OPENAI_API_KEY` | TTS audio generation (OpenAI voices) | platform.openai.com |
| `DATABASE_URL` | PostgreSQL connection string | Supabase project settings |
| `SUPABASE_URL` | Supabase project URL (for JWKS fetch) | Supabase project settings |
| `SUPABASE_JWT_SECRET` | JWT validation fallback (HS256) | Supabase project settings |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin operations (bypass RLS) | Supabase project settings |
| `RESEND_API_KEY` | Email delivery via Resend SMTP | resend.com dashboard |
| `TAVILY_API_KEY` | News headline search for Kids Daily | tavily.com |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS voices | elevenlabs.io |
| `ALLOWED_ORIGINS` | CORS whitelist for frontend URLs | Set manually |
| `ADMIN_API_KEY` | Admin endpoint authentication | Generate a random secret |

### Frontend (Vercel)

| Variable | Purpose | Note |
|----------|---------|------|
| `VITE_SUPABASE_URL` | Supabase project URL | Public — embedded in JS bundle |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous key | Public — safe to expose |
| `VITE_API_BASE_URL` | Backend API URL (Railway) | Public — where API calls go |

**Important**: Frontend variables prefixed with `VITE_` are embedded in the JavaScript bundle at build time. They are visible to anyone who inspects the page source. Never put secret keys in `VITE_` variables.

## Key Concepts

**Secret vs Public**: Secret variables (API keys, database passwords) must never appear in code or frontend bundles. Public variables (Supabase URL, anon key) are safe to embed because they only grant limited access controlled by Supabase's Row Level Security.

**.env File**: A plain text file (`KEY=value`, one per line) that's loaded at startup. `.env` is in `.gitignore` — it never gets committed to GitHub. `.env.example` shows the required keys without real values, so new developers know what to set up.

**Build-Time vs Runtime**: Vite `VITE_*` variables are replaced during `npm run build` — they become literal strings in the output JavaScript. Backend `os.environ` variables are read at runtime — you can change them by restarting the server without rebuilding.

## Connections

- **Backend**: `os.getenv("KEY")` throughout Python code; `paths.py` reads `CHROMA_PATH`
- **Frontend**: `import.meta.env.VITE_KEY` in TypeScript; `lib/supabase.ts` reads Supabase URL
- **Railway**: Set via Railway dashboard → Settings → Variables
- **Vercel**: Set via Vercel dashboard → Project → Settings → Environment Variables
- **Local**: `.env` file in `backend/` (copied from `.env.example`)

## Thinking Question

The `VITE_SUPABASE_ANON_KEY` is embedded in the public JavaScript bundle — anyone can see it. Why is this okay? What prevents someone from using this key to read or modify other users' data? (Hint: look up "Row Level Security" in Supabase and how `anon` key permissions work vs `service_role` key.)
