"""
Integration test configuration.

Ensures DB is connected, schema is initialized, and a test user exists
for e2e tests that use ASGITransport (which does NOT trigger FastAPI lifespan).
"""

import os
import pytest

from backend.src.services.database import db_manager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.sql_compat import insert_or_ignore


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    """Set test environment."""
    os.environ["ENVIRONMENT"] = "test"


@pytest.fixture(scope="session", autouse=True)
async def _init_database():
    """Connect to DB and initialize schema once for integration tests."""
    if not db_manager.is_connected:
        await db_manager.connect()
        await init_schema(db_manager)

    # Ensure e2e test user exists (FK constraint on stories.user_id).
    # `INSERT OR IGNORE` is SQLite-only; insert_or_ignore() routes through
    # `ON CONFLICT DO NOTHING` on Postgres so this conftest works against
    # both dev (SQLite default) and the new local pgvector dev backend.
    from datetime import datetime
    now = datetime.now().isoformat()
    sql = insert_or_ignore(
        "users",
        ["user_id", "username", "email", "password_hash", "created_at", "updated_at"],
        db_manager.dialect,
    )
    await db_manager.execute(
        sql,
        ("e2e_test_user", "e2e_test_user", "e2e@example.com", "test_hash", now, now),
    )
    await db_manager.commit()

    yield

    await db_manager.disconnect()
