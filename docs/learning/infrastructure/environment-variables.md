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
| `OPENAI_API_KEY` | OpenAI services: story TTS, Whisper STT for Talk-to-Buddy `hybrid` voice | platform.openai.com |
| `DATABASE_URL` | PostgreSQL connection string | Supabase project settings |
| `SUPABASE_URL` | Supabase project URL (for JWKS fetch) | Supabase project settings |
| `SUPABASE_JWT_SECRET` | JWT validation fallback (HS256) | Supabase project settings |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin operations (bypass RLS) | Supabase project settings |
| `RESEND_API_KEY` | Email delivery via Resend SMTP | resend.com dashboard |
| `TAVILY_API_KEY` | News headline search for Kids Daily | tavily.com |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS voices; required for spoken Talk-to-Buddy audio in `hybrid` mode | elevenlabs.io |
| `REALTIME_VOICE_PROVIDER` | Talk-to-Buddy provider: `mock` for deterministic offline testing, `hybrid` for Whisper + My Agent + ElevenLabs | Set manually |
| `ALLOWED_ORIGINS` | CORS whitelist for frontend URLs | Set manually |
| `ADMIN_API_KEY` | Admin endpoint authentication | Generate a random secret |

### Frontend (Vercel)

| Variable | Purpose | Note |
|----------|---------|------|
| `VITE_SUPABASE_URL` | Supabase project URL | Public — embedded in JS bundle |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous key | Public — safe to expose |
| `VITE_API_BASE_URL` | Backend API URL (Railway) | Public — where API calls go |

**Important**: Frontend variables prefixed with `VITE_` are embedded in the JavaScript bundle at build time. They are visible to anyone who inspects the page source. Never put secret keys in `VITE_` variables.

## Model & Cost Controls (Optional)

Every AI call defaults to the **cheapest capable model** for that job. These
optional variables override the model per feature **without a code change** —
leave them unset for the cost-efficient defaults.

| Variable | Default | What it controls |
|----------|---------|------------------|
| `CLAUDE_AGENT_MODEL` / `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Claude model for story / My Agent / interactive / Kids Daily orchestration |
| `SAFETY_CHECK_MODEL` | `claude-haiku-4-5` | Model for the content-safety MCP server |
| `VISION_ANALYSIS_MODEL` | `claude-haiku-4-5` | Model for drawing / vision analysis |
| `VIDEO_MODEL` | `wan-video/wan-2.2-i2v-fast` | Replicate image-to-video model (replaced OpenAI Sora — cheaper **and** faster) |
| `VIDEO_RESOLUTION` | `480p` | Video render resolution; set `720p` for sharper output at higher cost |
| `VIDEO_RENDER_TIMEOUT_S` | `300` | Max seconds to wait for a video render before failing |
| `IMAGE_STYLE_MODEL` | `black-forest-labs/flux-kontext-pro` | Replicate art-style transfer model; `…-dev` is cheaper but slower/lower-fidelity |
| `KIDS_DAILY_IMAGE_MODEL` / `MORNING_SHOW_IMAGE_MODEL` | `gpt-image-1-mini` | OpenAI image model for Kids Daily illustrations |
| `OPENAI_REALTIME_MODEL` | `gpt-realtime-mini` | OpenAI realtime model for Talk-to-Buddy voice |
| `VOICE_ALLOW_PREMIUM_REALTIME` | unset (off) | Set `1` to allow the pricier `gpt-realtime-2` tier on dual opt-in; default keeps **every** session on `mini` |
| `REPLICATE_API_TOKEN` | — | **Required** for video, art-style transfer, and voice cloning (Replicate models) |

**Cheapest-everywhere policy**: the defaults pick the cheapest tier that still
delivers good quality and acceptable latency (e.g. video uses a fast 480p
Replicate model instead of Sora). To raise quality for a single feature, set
just that feature's variable — no redeploy of logic required.

## Key Concepts

**Secret vs Public**: Secret variables (API keys, database passwords) must never appear in code or frontend bundles. Public variables (Supabase URL, anon key) are safe to embed because they only grant limited access controlled by Supabase's Row Level Security.

**.env File**: A plain text file (`KEY=value`, one per line) that's loaded at startup. `.env` is in `.gitignore` — it never gets committed to GitHub. `.env.example` shows the required keys without real values, so new developers know what to set up.

**Build-Time vs Runtime**: Vite `VITE_*` variables are replaced during `npm run build` — they become literal strings in the output JavaScript. Backend `os.environ` variables are read at runtime — you can change them by restarting the server without rebuilding.

## Local Talk-to-Buddy Voice

Talk-to-Buddy uses `REALTIME_VOICE_PROVIDER` on the backend:

| Value | Behavior | Required Keys |
|-------|----------|---------------|
| `mock` | Offline deterministic provider. Every finalized utterance returns the canned transcript `hello buddy this is a mock transcript`; useful for contract tests and UI plumbing. | None |
| `hybrid` | Real local voice path: OpenAI Whisper transcribes the child, My Agent generates the reply, and ElevenLabs streams spoken audio. | `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` |

If `REALTIME_VOICE_PROVIDER` is missing, the current local-safe default is the mock provider. If `hybrid` is set but `ELEVENLABS_API_KEY` is missing, transcription and text replies can still work, but spoken reply audio may be silent.

After changing `REALTIME_VOICE_PROVIDER` or voice keys, restart the backend process. Existing WebSocket voice sessions keep using the provider selected when that session started.

## Connections

- **Backend**: `os.getenv("KEY")` throughout Python code; `paths.py` reads `CHROMA_PATH`
- **Frontend**: `import.meta.env.VITE_KEY` in TypeScript; `lib/supabase.ts` reads Supabase URL
- **Railway**: Set via Railway dashboard → Settings → Variables
- **Vercel**: Set via Vercel dashboard → Project → Settings → Environment Variables
- **Local**: `.env` file in `backend/` (copied from `.env.example`)

## Thinking Question

The `VITE_SUPABASE_ANON_KEY` is embedded in the public JavaScript bundle — anyone can see it. Why is this okay? What prevents someone from using this key to read or modify other users' data? (Hint: look up "Row Level Security" in Supabase and how `anon` key permissions work vs `service_role` key.)
