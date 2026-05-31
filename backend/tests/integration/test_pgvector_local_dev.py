"""Local-dev Postgres + pgvector smoke test.

Skipped unless DATABASE_URL points at a Postgres URL. This test exists
to catch dialect-drift bugs the SQLite-only suite would miss — exactly
the kind that surfaced (and got fixed) during the Phase 0 migration:
the schema_artifacts FK ordering and the characters migration
idempotency check on Postgres.

Run it locally after `./backend/scripts/dev_db.sh up`:
    DATABASE_URL=postgresql://creative:creative@localhost:54329/creative_agent_dev \
        pytest backend/tests/integration/test_pgvector_local_dev.py -v

Uses a *fresh* DatabaseManager per test (not the global singleton) to
avoid the pytest-asyncio per-function event-loop tearing down an
asyncpg pool the session-scoped conftest opened in another loop.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="requires DATABASE_URL=postgresql://... pointed at a live Postgres",
)


@pytest.mark.asyncio
async def test_init_schema_runs_clean_on_postgres():
    """All ~30 tables + the pgvector extension tables come up cleanly."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema

    db = DatabaseManager()  # picks up DATABASE_URL
    await db.connect()
    try:
        assert db.dialect == "postgresql"
        await init_schema(db)
        await init_vector_schema(db)

        rows = await db.fetchall(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
        names = {row["tablename"] for row in rows}
        # Spot-check critical tables across the layers — these were the
        # ones that surfaced dialect bugs during the migration.
        assert "users" in names
        assert "stories" in names
        assert "artifacts" in names                # FK ordering fix
        assert "agent_steps" in names              # referenced by artifacts
        assert "characters" in names               # idempotent migration fix
        assert "agent_chat_sessions" in names      # #565
        assert "drawing_embeddings" in names       # pgvector
        assert "story_embeddings_pg" in names      # pgvector
    finally:
        await db.disconnect()
