"""
API Tests Configuration

Test configuration and shared fixtures.
Uses FastAPI dependency_overrides to bypass auth (no DB writes in deps.py).
Manually manages DB lifecycle since ASGITransport does NOT trigger lifespan.
"""

import pytest
import os
from pathlib import Path

from httpx import AsyncClient, ASGITransport

from backend.src.main import app
from backend.src.api.deps import get_current_user
from backend.src.services.user_service import UserData
from backend.src.services.database import db_manager
from backend.src.services.database.schema import init_schema


# ---------------------------------------------------------------------------
# Test user returned by the auth override (no DB interaction)
# ---------------------------------------------------------------------------

_TEST_USER = UserData(
    user_id="test_user",
    username="test_user",
    email="test@example.com",
    password_hash="test_hash",
    display_name="Test User",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)


async def _fake_get_current_user() -> UserData:
    """Return a deterministic test user — avoids all DB calls in deps.py."""
    return _TEST_USER


# ---------------------------------------------------------------------------
# Session-scoped environment + dependency override setup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables and dependency overrides."""
    os.environ["ENVIRONMENT"] = "test"

    # Ensure test data directory exists
    test_data_dir = Path("./data/test")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Override auth dependency so no DB writes happen during request handling
    app.dependency_overrides[get_current_user] = _fake_get_current_user

    yield

    # Restore original dependency after all tests finish
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Database lifecycle — connect before tests, disconnect after
# ASGITransport does NOT trigger FastAPI lifespan events, so we must do it.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def _init_database():
    """Connect to DB and initialize schema once for the entire test session."""
    if not db_manager.is_connected:
        await db_manager.connect()
        await init_schema(db_manager)

    yield

    await db_manager.disconnect()


# ---------------------------------------------------------------------------
# Shared async test client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    """Create an httpx AsyncClient using ASGITransport (httpx >= 0.27 compat)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Common test data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_child_id():
    return "test_child_001"


@pytest.fixture
def test_age_group():
    return "6-8"


@pytest.fixture
def test_interests():
    return ["animals", "adventure", "space"]
