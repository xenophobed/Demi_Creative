# Operations Guide — Kids Creative Workshop

Production deployment across three services: **Railway** (backend), **Vercel** (frontend), **Supabase** (database, auth, storage).

## Service Map

| Service | What | URL | Deploy Method |
|---------|------|-----|---------------|
| **Railway** | FastAPI backend | https://kids-creative-backend-production.up.railway.app | `railway up` (manual CLI push) |
| **Vercel** | React SPA frontend | https://frontend-tau-drab-78.vercel.app | `vercel deploy --prod` (manual CLI push) |
| **Supabase** | PostgreSQL, Auth, Storage | https://lhwuyiaeavkjkbpesjfj.supabase.co | Supabase Dashboard or CLI |

> **None of these auto-deploy on `git push`** currently. You must deploy manually via CLI after pushing code.

---

## 1. Install CLIs

### Railway CLI

```bash
npm install -g @railway/cli
railway login          # opens browser for OAuth
railway whoami         # verify: should show demi2014@proton.me
```

### Vercel CLI

```bash
npm install -g vercel@latest
vercel login           # opens browser for OAuth
vercel whoami          # verify: should show demi2014-9944
```

### Supabase CLI

```bash
# macOS
brew install supabase/tap/supabase

# Or npm
npm install -g supabase

supabase login         # opens browser for OAuth
supabase projects list # verify: should show kids-creative-workshop
```

---

## 2. Project Linking (First Time Only)

After cloning the repo on a new machine, link to the remote projects:

### Railway

```bash
cd /path/to/Demi_Creative
railway link            # select "kids-creative-backend" project
railway service link kids-creative-backend
```

### Vercel

```bash
cd /path/to/Demi_Creative/frontend
vercel link --yes --scope demis-projects-4566cc61
```

### Supabase

```bash
cd /path/to/Demi_Creative/backend
supabase link --project-ref lhwuyiaeavkjkbpesjfj
```

---

## 3. Deploy Backend (Railway)

Railway deploys the entire repo and uses `railway.toml` to build/start the backend.

```bash
# From project root
cd /path/to/Demi_Creative

# Deploy (uploads code, builds on Railway servers)
railway up --detach

# Watch build status
railway service status --all

# View logs
railway service logs

# Redeploy latest (no code change, just restart)
railway service redeploy
```

### Railway Environment Variables

```bash
# List all variables
railway variables

# Set a variable
railway variables set KEY=value

# Set multiple at once
railway variables set KEY1=value1 KEY2=value2

# Delete a variable
railway variables delete KEY
```

**Current required variables:**

| Variable | Description | Status |
|----------|-------------|--------|
| `ENVIRONMENT` | `production` | Set |
| `STORAGE_BACKEND` | `supabase` | Set |
| `SUPABASE_URL` | `https://lhwuyiaeavkjkbpesjfj.supabase.co` | Set |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role JWT | Set |
| `SUPABASE_JWT_SECRET` | JWT signing secret | Set |
| `SECRET_KEY` | Server secret (random hex) | Set |
| `ANTHROPIC_API_KEY` | Claude API key | **Placeholder — add real key** |
| `OPENAI_API_KEY` | OpenAI TTS key | **Placeholder — add real key** |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS key | Not set (optional) |
| `TAVILY_API_KEY` | Web search for Daily Drop | Not set (optional) |
| `DAILY_DROP_ENABLED` | `0` = disabled, `1` = enabled | Set to `0` |
| `ALLOWED_ORIGINS` | Comma-separated frontend URLs | Set |

### Health Check

```bash
curl https://kids-creative-backend-production.up.railway.app/health
```

Status will show `degraded` until `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are set to real values.

---

## 4. Deploy Frontend (Vercel)

Vercel deploys only the `frontend/` directory as a Vite SPA.

```bash
# From project root (Vercel auto-detects linked project in frontend/)
cd /path/to/Demi_Creative

# Preview deployment (staging)
vercel deploy --scope demis-projects-4566cc61

# Production deployment
vercel deploy --prod --scope demis-projects-4566cc61

# Check deployment status
vercel ls --scope demis-projects-4566cc61
```

### Vercel Environment Variables

```bash
# List all env vars
vercel env ls --scope demis-projects-4566cc61

# Add a variable (reads value from stdin)
echo "value" | vercel env add VAR_NAME production --scope demis-projects-4566cc61

# Remove a variable
vercel env rm VAR_NAME production --scope demis-projects-4566cc61 --yes

# Pull env vars to local .env.local
vercel env pull --scope demis-projects-4566cc61
```

**Current variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://kids-creative-backend-production.up.railway.app/api/v1` |
| `VITE_SUPABASE_URL` | `https://lhwuyiaeavkjkbpesjfj.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key (public, safe for frontend) |

> `VITE_` prefixed variables are embedded at build time and visible to anyone visiting the site. Never put secrets here.

---

## 5. Manage Supabase

Supabase doesn't need "deploys" — it's a managed service. You manage schema, auth, and storage.

### Database (SQL)

```bash
# Run SQL directly
supabase db execute "SELECT count(*) FROM users;"

# Run a migration file
supabase db push

# Dump current schema
supabase db dump > schema.sql

# Open Supabase Studio (web dashboard)
# https://supabase.com/dashboard/project/lhwuyiaeavkjkbpesjfj
```

### Auth

```bash
# List users (via Admin API)
curl -s "https://lhwuyiaeavkjkbpesjfj.supabase.co/auth/v1/admin/users" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"

# Confirm a user's email (bypass email verification)
curl -s -X PUT "https://lhwuyiaeavkjkbpesjfj.supabase.co/auth/v1/admin/users/<USER_ID>" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"email_confirm": true}'
```

Or use the dashboard: **Authentication > Users** at https://supabase.com/dashboard/project/lhwuyiaeavkjkbpesjfj/auth/users

### Storage Buckets

Current buckets: `uploads`, `audio`, `videos`, `styled` (all public).

```bash
# List buckets
curl -s "https://lhwuyiaeavkjkbpesjfj.supabase.co/storage/v1/bucket" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"

# Create a bucket
curl -s -X POST "https://lhwuyiaeavkjkbpesjfj.supabase.co/storage/v1/bucket" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"id":"bucket-name","name":"bucket-name","public":true}'

# Delete a bucket (must be empty)
curl -s -X DELETE "https://lhwuyiaeavkjkbpesjfj.supabase.co/storage/v1/bucket/<bucket-name>" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"
```

Or manage in dashboard: **Storage** at https://supabase.com/dashboard/project/lhwuyiaeavkjkbpesjfj/storage/buckets

---

## 6. Typical Workflows

### Push code + deploy everything

```bash
git add -A && git commit -m "feat: description"
git push origin main

# Deploy backend
railway up --detach
railway service status --all   # wait for SUCCESS

# Deploy frontend
vercel deploy --prod --scope demis-projects-4566cc61
```

### Backend-only change (Python code)

```bash
git add backend/ && git commit -m "fix: description"
git push origin main
railway up --detach
```

### Frontend-only change (React/TypeScript)

```bash
git add frontend/ && git commit -m "feat: description"
git push origin main
vercel deploy --prod --scope demis-projects-4566cc61
```

### Add a new API key to Railway

```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
# Railway auto-redeploys when variables change
```

### Rollback a bad deploy

```bash
# Railway — redeploy previous version
railway service redeploy

# Vercel — promote a previous deployment
vercel ls --scope demis-projects-4566cc61
vercel promote <deployment-url> --scope demis-projects-4566cc61
```

---

## 7. Monitoring & Debugging

### Railway (Backend)

```bash
# Live logs
railway service logs

# Health check
curl -s https://kids-creative-backend-production.up.railway.app/health | python3 -m json.tool

# API docs (Swagger)
open https://kids-creative-backend-production.up.railway.app/api/docs
```

### Vercel (Frontend)

```bash
# Recent deployments
vercel ls --scope demis-projects-4566cc61

# Inspect a deployment
vercel inspect <deployment-url> --scope demis-projects-4566cc61

# View function logs (if applicable)
vercel logs <deployment-url> --scope demis-projects-4566cc61
```

### Supabase

- **Dashboard**: https://supabase.com/dashboard/project/lhwuyiaeavkjkbpesjfj
- **Logs**: Dashboard > Logs > Edge, Auth, Postgres
- **API health**: `curl -s https://lhwuyiaeavkjkbpesjfj.supabase.co/rest/v1/ -H "apikey: <ANON_KEY>"`

---

## 8. Important Notes

### JWT Authentication

The backend supports two JWT algorithms for Supabase auth:
- **ES256** (JWKS, asymmetric) — current default for new Supabase projects. The backend fetches the public key from `SUPABASE_URL/auth/v1/.well-known/jwks.json` automatically.
- **HS256** (symmetric) — legacy. Uses `SUPABASE_JWT_SECRET` env var.

ES256 is tried first. No config change needed if your Supabase project uses the default.

### CORS

`ALLOWED_ORIGINS` on Railway must include the Vercel frontend URL. If you add a custom domain, update it:

```bash
railway variables set "ALLOWED_ORIGINS=https://your-domain.com,https://frontend-tau-drab-78.vercel.app"
```

### Storage Backend

Set `STORAGE_BACKEND=supabase` on Railway for production (files stored in Supabase Storage). Use `STORAGE_BACKEND=local` for local development (files stored in `data/` directory).

### Auto-Deploy Setup (Optional)

To enable auto-deploy on `git push`:

**Vercel**: Connect the GitHub repo via `vercel git connect` or in the Vercel dashboard under Project Settings > Git. Set root directory to `frontend/`.

**Railway**: Connect the GitHub repo in Railway dashboard under Service Settings > Source. Railway will auto-deploy on push to main.

Once connected, you only need `git push origin main` — no manual CLI deploys.

---

## 9. Reference IDs

| Service | Identifier |
|---------|-----------|
| Railway Project | `82fb5342-ab60-4ab9-9b97-4161f0e71508` |
| Railway Service | `kids-creative-backend` |
| Vercel Team | `demis-projects-4566cc61` |
| Vercel Project | `frontend` |
| Supabase Project Ref | `lhwuyiaeavkjkbpesjfj` |
| Supabase Org ID | `rbepvunwbjovpkskohal` |
| GitHub Repo | `xenophobed/Demi_Creative` |
