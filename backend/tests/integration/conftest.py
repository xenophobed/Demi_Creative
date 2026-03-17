"""
Integration test configuration.

Ensures DB is connected, schema is initialized, and a test user exists
for e2e tests that use ASGITransport (which does NOT trigger FastAPI lifespan).
"""

import os
import pytest

from backend.src.services.database import db_manager
from backend.src.services.database.schema import init_schema


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

    # Ensure e2e test user exists (FK constraint on stories.user_id)
    from datetime import datetime
    now = datetime.now().isoformat()
    await db_manager.execute(
        """
        INSERT OR IGNORE INTO users (user_id, username, email, password_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("e2e_test_user", "e2e_test_user", "e2e@example.com", "test_hash", now, now),
    )
    await db_manager.commit()

    yield

    await db_manager.disconnect()
