# Backend Services Overview

**Source**: `backend/src/services/`

## What This Is

**Explorer**: Services are the workers behind the scenes. The API route is the manager who takes orders, and services are the people who actually do the work — one person handles the database, another handles audio recording, another handles logins.

**Maker**: The services layer contains business logic, external API wrappers, and the repository pattern for database access. Services sit between API routes and the database/external APIs, encapsulating complex operations that multiple routes might need. This prevents routes from growing into monolithic functions.

## Service Map

### Core Services

| File | Purpose |
|------|---------|
| `supabase_auth.py` | JWT validation (ES256 JWKS + HS256 fallback) for Supabase tokens |
| `user_service.py` | Legacy auth (password hashing, custom tokens) + user account operations |
| `tts_service.py` | Text-to-speech wrapper — routes to OpenAI/Replicate/ElevenLabs based on provider |
| `voice_service.py` | Voice catalog management — available voices, preview generation |
| `session_manager.py` | Legacy JSON-based session storage (superseded by `session_repository.py`) |
| `story_memory.py` | Cross-story memory — deduplication, character continuity, theme tracking |
| `theme_recommender.py` | Theme suggestion engine — recommends themes based on child's history |
| `inspiration_seed_bank.py` | Curated seed content for Inspiration Daily feature |
| `storage_adapter.py` | File storage abstraction (local filesystem; extensible to cloud storage) |
| `provenance_tracker.py` | Content lineage tracking — records which agent/tool/model produced each artifact |

### Scheduling Services

| File | Purpose |
|------|---------|
| `kids_daily_scheduler.py` | Cron-like scheduler for pre-generating podcast episodes |
| `news_headline_fetcher.py` | Tavily API wrapper for fetching real news headlines |
| `retention_scheduler.py` | Data cleanup — expires old sessions, deletes orphaned files |
| `retention_service.py` | Retention policy implementation — what to keep, what to delete, for how long |

### Database Layer (`services/database/`)

| File | Purpose |
|------|---------|
| `connection.py` | Database connection manager — picks SQLite or PostgreSQL adapter |
| `adapter.py` | Base adapter class defining the database interface |
| `sqlite_adapter.py` | SQLite implementation (development) |
| `postgres_adapter.py` | PostgreSQL implementation (production) |
| `schema.py` | Table definitions + migration runner (ALTER TABLE on startup) |
| `sql_compat.py` | SQL dialect helpers (`insert_or_ignore`, `column_exists`) |

### Repositories (one per table)

| File | Table | Purpose |
|------|-------|---------|
| `session_repository.py` | `sessions` | Interactive story session CRUD |
| `story_repository.py` | `stories` | Story CRUD + search |
| `user_repository.py` | `users` | User profile CRUD |
| `subscription_repository.py` | `subscriptions` | Topic subscription management |
| `usage_repository.py` | `usage_tracking` | Daily generation counting |
| `preference_repository.py` | `preferences` | Child preference tracking |
| `character_repository.py` | `characters` | Recurring character memory |
| `favorite_repository.py` | `favorites` | User favorite items |
| `artifact_repository.py` | `artifacts` | Content provenance records |
| `vector_repository.py` | `vector_embeddings` | pgvector similarity search (prod) |
| `voice_repository.py` | `voice_preferences` | Per-user voice selections |
| `referral_repository.py` | `referrals` | Referral tracking + tier upgrades |

## Key Design Patterns

### Repository Pattern
Every database table has a dedicated repository class. Routes never write raw SQL — they call repository methods:
```python
# Good: repository method
session = await session_repo.create_session(child_id="abc", ...)

# Bad: raw SQL in route (never do this)
await db.execute("INSERT INTO sessions ...")
```

### Service vs Repository
- **Repository**: Pure CRUD — `create`, `get`, `update`, `delete`, `list`. No business logic.
- **Service**: Business logic that may span multiple repositories or external APIs. Example: `tts_service.py` calls OpenAI API, saves the file, and returns metadata.

### Migration on Startup
`schema.py`'s `init_schema()` runs every time the server starts:
1. Creates tables if they don't exist (`CREATE TABLE IF NOT EXISTS`)
2. Runs column migrations (`ALTER TABLE ADD COLUMN` with `column_exists()` guard)
3. Safe to run repeatedly — idempotent by design

## Connections

- **Upstream**: API routes import repositories and services directly
- **Downstream**: Repositories use `db_manager` from `connection.py`; services call external APIs
- **Agents**: Agents call MCP servers, which may use services (e.g., `tts_generator_server` → `tts_service`)
- **Config**: `connection.py` reads `DATABASE_URL` to pick the database adapter

## Thinking Question

The repository pattern means every table has its own file. With 12 repositories, that's a lot of files with similar CRUD code. Would it be better to create a generic `BaseRepository` class that all repositories inherit from? Think about: code reuse vs. readability, what happens when one table needs a unique query pattern, and whether "less files" actually means "less complexity."
