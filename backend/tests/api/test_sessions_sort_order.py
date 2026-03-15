"""
Tests for session sort order in user profile.

Verifies that get_user_sessions() returns sessions ordered by updated_at DESC
(most recently active first) rather than created_at DESC.

Fixes #202 — profile recent sessions sorted by creation time instead of
recent activity.
"""

import pytest
from unittest.mock import AsyncMock

from backend.src.services.database.user_repository import UserRepository, UserData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_USER_ROW = {
    "user_id": "user_sort_test",
    "username": "sort_tester",
    "email": "sort@example.com",
    "password_hash": "hashed",
    "display_name": "Sort Tester",
    "avatar_url": None,
    "is_active": 1,
    "is_verified": 1,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
    "last_login_at": None,
}

# Session A: created first, but updated most recently (should appear first)
_SESSION_A = {
    "session_id": "session_a",
    "story_title": "Old Session Recently Active",
    "child_id": "child_1",
    "age_group": "6-8",
    "theme": "adventure",
    "current_segment": 3,
    "total_segments": 5,
    "status": "active",
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-06-15T12:00:00",
}

# Session B: created last, but not updated recently (should appear second)
_SESSION_B = {
    "session_id": "session_b",
    "story_title": "New Session Not Active",
    "child_id": "child_1",
    "age_group": "6-8",
    "theme": "space",
    "current_segment": 1,
    "total_segments": 5,
    "status": "active",
    "created_at": "2025-06-01T00:00:00",
    "updated_at": "2025-06-01T00:00:00",
}


@pytest.mark.asyncio
async def test_get_user_sessions_orders_by_updated_at():
    """Sessions must be sorted by updated_at DESC so recently active ones appear first."""
    repo = UserRepository()

    mock_db = AsyncMock()
    repo._db = mock_db

    mock_db.fetchone = AsyncMock(side_effect=[
        _TEST_USER_ROW,   # get_by_id
        {"total": 2},     # count query
    ])

    mock_db.fetchall = AsyncMock(return_value=[_SESSION_A, _SESSION_B])

    result = await repo.get_user_sessions(user_id="user_sort_test")

    # Verify the SQL query uses ORDER BY updated_at DESC
    fetchall_call = mock_db.fetchall.call_args
    query = fetchall_call[0][0]
    assert "ORDER BY updated_at DESC" in query, (
        f"Expected ORDER BY updated_at DESC in query, got: {query}"
    )

    # Verify result structure
    assert result is not None
    assert len(result["sessions"]) == 2
    assert result["sessions"][0]["session_id"] == "session_a"
    assert result["sessions"][1]["session_id"] == "session_b"


@pytest.mark.asyncio
async def test_get_user_sessions_does_not_order_by_created_at():
    """Regression guard: sessions must NOT be ordered by created_at."""
    repo = UserRepository()

    mock_db = AsyncMock()
    repo._db = mock_db

    mock_db.fetchone = AsyncMock(side_effect=[
        _TEST_USER_ROW,
        {"total": 0},
    ])

    mock_db.fetchall = AsyncMock(return_value=[])

    await repo.get_user_sessions(user_id="user_sort_test")

    query = mock_db.fetchall.call_args[0][0]
    assert "ORDER BY created_at" not in query, (
        f"Sessions query must not use ORDER BY created_at, got: {query}"
    )
