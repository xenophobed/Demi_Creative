# Database Adapter — SQLite (Dev) vs PostgreSQL (Prod)

**Source**: `backend/src/services/database/adapter.py`, `sqlite_adapter.py`, `postgres_adapter.py`, `connection.py`

## What This File Does

**Explorer**: The database adapter is like a translator. Our app speaks one language (SQL), but the database in development (SQLite) and the database in production (PostgreSQL) understand slightly different dialects. The adapter translates so our code works with both — no changes needed.

**Maker**: The adapter pattern abstracts database-specific SQL dialect differences behind a common interface. `adapter.py` defines the base class; `sqlite_adapter.py` and `postgres_adapter.py` implement it. `connection.py` reads `DATABASE_URL` to pick the right adapter at startup. This lets us develop with zero-install SQLite locally and deploy to Supabase PostgreSQL in production.

## How It Works

### Adapter Selection
```python
# connection.py picks the adapter based on DATABASE_URL
if database_url.startswith("postgresql"):
    adapter = PostgresAdapter(database_url)    # Production
else:
    adapter = SQLiteAdapter(db_path)           # Development
```

### What Differs Between Dialects

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Auto-increment | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| Upsert | `INSERT OR IGNORE` | `ON CONFLICT DO NOTHING` |
| Boolean | `INTEGER (0/1)` | Native `BOOLEAN` |
| JSON | Stored as `TEXT` | Native `JSONB` |
| Vector search | ChromaDB (separate) | pgvector extension (built-in) |
| Concurrency | Single-writer | Multi-writer with MVCC |

### The `sql_compat` Module
Helper functions like `insert_or_ignore()` and `column_exists()` generate the correct SQL for whichever dialect is active:

```python
def insert_or_ignore(table, columns, dialect):
    if dialect == "postgresql":
        return f"INSERT INTO {table} (...) VALUES (...) ON CONFLICT DO NOTHING"
    else:
        return f"INSERT OR IGNORE INTO {table} (...) VALUES (...)"
```

## Key Concepts

**Adapter Pattern**: A design pattern where you create a wrapper that makes one interface look like another. Like a power plug adapter — same appliance, different outlet shapes. Our code uses one interface; the adapter translates to the correct database dialect.

**SQL Dialect**: Different databases use slightly different SQL syntax, even though they all speak "SQL." It's like British English vs American English — mostly the same, but "colour" vs "color" matters to the machine.

**Connection Pool**: PostgreSQL adapter maintains a pool of reusable database connections instead of opening a new one per request. This is faster because establishing a connection is expensive (network handshake, authentication). SQLite doesn't need pooling because it's a local file.

**Migration**: When we add a new column to a table, we need an `ALTER TABLE` statement. The `schema.py` file runs migrations on startup using `column_exists()` to check whether each migration has already been applied — safe to run repeatedly.

## Connections

- **Upstream**: Every repository (`session_repository.py`, `story_repository.py`, etc.) uses `db_manager` from `connection.py`
- **Config**: `DATABASE_URL` env var determines which adapter is used
- **Migrations**: `schema.py` runs `ALTER TABLE` migrations using `sql_compat` helpers
- **Vector search**: SQLite → ChromaDB (separate process); PostgreSQL → pgvector (same DB)

## Thinking Question

We chose the adapter pattern to support two databases. An alternative would be using an ORM (like SQLAlchemy) that generates correct SQL for any database automatically. What are the trade-offs? Think about: learning curve, query performance, debugging difficulty, and how much control you have over the exact SQL that runs.
