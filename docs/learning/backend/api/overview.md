# Backend API Overview

**Source**: `backend/src/api/routes/`, `backend/src/api/models.py`, `backend/src/api/deps.py`

## What This Is

**Explorer**: The API is like a waiter in a restaurant. The frontend (customer) tells the waiter what it wants ("start a story please"), the waiter carries the order to the kitchen (agents), and brings back the food (story data). Every request follows the same pattern: ask → process → respond.

**Maker**: The API layer is 14 FastAPI route modules that expose HTTP endpoints for all app features. Routes handle request validation (via Pydantic models), authentication (via dependency injection), rate limiting (daily quota per user), and response formatting. Long-running operations use SSE streaming. All routes live under `/api/v1/`.

## Route Map

| File | Prefix | Purpose | Key Endpoints |
|------|--------|---------|---------------|
| `image_to_story.py` | `/story` | Drawing → story generation | `POST /upload`, `POST /upload/stream` |
| `interactive_story.py` | `/story/interactive` | Branching narratives | `POST /start/stream`, `POST /{id}/choose/stream`, `POST /{id}/end/stream` |
| `kids_daily.py` | `/news/daily` | Podcast episodes | `POST /generate-on-demand`, `GET /{episode_id}` |
| `users.py` | `/users` | Auth + profiles | `GET /me`, `POST /login`, `POST /register` |
| `library.py` | `/library` | My Library | `GET /`, `GET /stats`, `POST /favorites` |
| `subscriptions.py` | `/news/subscriptions` | Topic subscriptions | `POST /subscribe`, `DELETE /unsubscribe` |
| `memory.py` | `/memory` | Preferences + characters | `GET /preferences`, `GET /characters` |
| `artifacts.py` | `/artifacts` | Content provenance | `GET /{id}`, `GET /{id}/lineage` |
| `audio.py` | `/audio` | On-demand TTS | `POST /generate` |
| `voice.py` | `/voice` | Voice catalog | `GET /catalog`, `POST /preview` |
| `video.py` | `/video` | Video generation | `POST /generate` |
| `usage.py` | `/usage` | Quota tracking | `GET /me` |
| `inspiration_daily.py` | `/inspiration` | Daily creative spark | `GET /today` |
| `admin_artifacts.py` | `/admin/artifacts` | Admin artifact mgmt | `GET /`, `DELETE /{id}` |

## Shared Infrastructure

### Authentication (`deps.py`)

Every protected route uses `Depends(get_current_user)`:
```python
@router.get("/me")
async def get_profile(user: UserData = Depends(get_current_user)):
    return user  # FastAPI injects the authenticated user automatically
```

The `get_current_user` dependency:
1. Reads `Authorization: Bearer <token>` header
2. Tries Supabase JWT validation (ES256 → HS256 fallback)
3. Falls back to legacy custom token validation
4. Auto-creates local user row for new Supabase users

### Quota System (`deps.py`)

`check_generation_quota` enforces daily limits:
- Free tier: 3 generations/day
- Plus tier: 9 generations/day (earned via referrals)
- Env var override: `DAILY_GENERATION_QUOTA`

### Request Models (`models.py`)

All requests/responses use Pydantic v2 models with validation:
```python
class InteractiveStoryStartRequest(BaseModel):
    child_id: str = Field(..., min_length=1, max_length=100)
    age_group: AgeGroup  # Enum: "3-5", "6-8", "9-12"
    interests: List[str] = Field(..., min_length=1, max_length=5)
```

Invalid requests automatically return HTTP 422 with detailed error messages.

## Key Concepts

**REST API**: A pattern where each URL represents a resource and HTTP methods (GET, POST, PUT, DELETE) represent actions. `GET /library` = "give me my library." `POST /story/upload` = "create a new story from this image."

**Dependency Injection**: FastAPI's `Depends()` system. Instead of every route checking auth itself, you declare `user = Depends(get_current_user)` and FastAPI handles it. One place to change auth logic, all routes benefit.

**SSE (Server-Sent Events)**: A streaming protocol where the server pushes events to the client over a single HTTP connection. Used for story generation progress — the frontend shows real-time updates ("Analyzing drawing...", "Writing story...") instead of a spinner.

## Connections

- **Upstream**: Frontend `storyService.ts`, `authService.ts` etc. call these endpoints
- **Downstream**: Routes call agents (`image_to_story_agent`, `interactive_story_agent`, `kids_daily_agent`) and repositories
- **Auth**: `deps.py` → `supabase_auth.py` for JWT validation
- **Models**: `models.py` defines all request/response shapes shared across routes

## Thinking Question

Every route validates requests using Pydantic models. What happens if the frontend sends a request with an extra field that the model doesn't define (e.g., `{"age_group": "6-8", "hack": "drop table"}`)? Does Pydantic reject it, ignore it, or include it? Look up Pydantic v2's `model_config` and the `extra` setting.
