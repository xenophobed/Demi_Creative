"""
Vector Embedding Schema (pgvector)

DDL for drawing_embeddings and story_embeddings tables with vector(1536) columns.
Uses OpenAI text-embedding-3-small (1536 dimensions).
Only initialized when dialect is 'postgresql' since SQLite does not support
the pgvector extension.

Issue: #342
"""

from typing import TYPE_CHECKING

from .sql_compat import translate_ddl

if TYPE_CHECKING:
    from .connection import DatabaseManager


# ============================================================================
# Drawing Embeddings Table
# ============================================================================

DRAWING_EMBEDDINGS_TABLE = """
CREATE TABLE IF NOT EXISTS drawing_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT UNIQUE NOT NULL,
    child_id TEXT NOT NULL,
    document_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata_json TEXT,
    text_search tsvector GENERATED ALWAYS AS (to_tsvector('english', document_text)) STORED,
    created_at TEXT NOT NULL
);
"""

DRAWING_EMBEDDINGS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_drawing_embeddings_child_id ON drawing_embeddings(child_id);
CREATE INDEX IF NOT EXISTS idx_drawing_embeddings_text_search ON drawing_embeddings USING GIN (text_search);
"""

# IVFFlat index for cosine similarity search (PostgreSQL only, raw SQL)
DRAWING_EMBEDDINGS_VECTOR_INDEX = """
CREATE INDEX IF NOT EXISTS idx_drawing_embeddings_vector
ON drawing_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""

# ============================================================================
# Story Embeddings Table
# ============================================================================

STORY_EMBEDDINGS_PG_TABLE = """
CREATE TABLE IF NOT EXISTS story_embeddings_pg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT UNIQUE NOT NULL,
    child_id TEXT NOT NULL,
    document_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata_json TEXT,
    text_search tsvector GENERATED ALWAYS AS (to_tsvector('english', document_text)) STORED,
    created_at TEXT NOT NULL
);
"""

STORY_EMBEDDINGS_PG_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_story_embeddings_pg_child_id ON story_embeddings_pg(child_id);
CREATE INDEX IF NOT EXISTS idx_story_embeddings_pg_text_search ON story_embeddings_pg USING GIN (text_search);
"""

STORY_EMBEDDINGS_PG_VECTOR_INDEX = """
CREATE INDEX IF NOT EXISTS idx_story_embeddings_pg_vector
ON story_embeddings_pg USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""


# ============================================================================
# Schema Initialization
# ============================================================================

async def init_vector_schema(db: "DatabaseManager") -> None:
    """Initialize pgvector tables and indexes.

    Only called when dialect == 'postgresql'. SQLite environments use
    ChromaDB directly and skip this schema entirely.
    """
    if db.dialect != "postgresql":
        return

    # Enable the pgvector extension
    try:
        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass  # Extension may already exist or require superuser

    d = db.dialect

    # Drawing embeddings
    await db.execute(translate_ddl(DRAWING_EMBEDDINGS_TABLE, d))
    for stmt in DRAWING_EMBEDDINGS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # IVFFlat index (skip if not enough rows yet -- Postgres requires rows for IVFFlat)
    try:
        await db.execute(DRAWING_EMBEDDINGS_VECTOR_INDEX)
    except Exception:
        pass  # IVFFlat needs data; will be created later or manually

    # Story embeddings
    await db.execute(translate_ddl(STORY_EMBEDDINGS_PG_TABLE, d))
    for stmt in STORY_EMBEDDINGS_PG_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    try:
        await db.execute(STORY_EMBEDDINGS_PG_VECTOR_INDEX)
    except Exception:
        pass

    # Idempotent migration for existing DBs that pre-date hybrid search
    # (#590). The CREATE TABLE above only adds the column on fresh
    # tables; older DBs need an ALTER TABLE.
    await _migrate_add_text_search_columns(db)

    await db.commit()
    print("Vector schema initialized (pgvector)")


async def _migrate_add_text_search_columns(db: "DatabaseManager") -> None:
    """Add the generated ``text_search`` tsvector column + GIN index to
    drawing_embeddings + story_embeddings_pg (#590).

    Idempotent: re-running on a freshly-created DB is a no-op because
    the column already exists from CREATE TABLE.
    """
    for table in ("drawing_embeddings", "story_embeddings_pg"):
        rows = await db.fetchall(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = 'text_search'",
            (table,),
        )
        if not rows:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN text_search tsvector "
                f"GENERATED ALWAYS AS (to_tsvector('english', document_text)) STORED"
            )
            await db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_text_search "
                f"ON {table} USING GIN (text_search)"
            )
