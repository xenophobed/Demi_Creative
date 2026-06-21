"""Archiving the default child must promote a remaining profile (#744).

Before this fix, archiving the default child cleared `users.default_child_id`
to NULL and left no `is_default` profile, stranding the account with no active
child even when other profiles existed.

Parent Epic: #436 | Issue: #744
"""

import pytest
import pytest_asyncio

from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema

USER = "user-1"


@pytest_asyncio.fixture
async def repo():
    db = DatabaseManager(":memory:")
    await db.connect()
    await init_schema(db)
    # A user row so we can assert users.default_child_id sync.
    await db.execute(
        "INSERT INTO users (user_id, username, email, password_hash, created_at, updated_at) "
        "VALUES (?, 'u1', 'u1@example.com', 'x', '2026-01-01', '2026-01-01')",
        (USER,),
    )
    await db.commit()
    r = ChildProfileRepository(db)
    yield r
    await db.disconnect()


async def _default_child_id(repo):
    row = await repo._db.fetchone(
        "SELECT default_child_id FROM users WHERE user_id = ?", (USER,)
    )
    return row.get("default_child_id") if row else None


@pytest.mark.asyncio
async def test_archiving_default_promotes_oldest_remaining(repo):
    # child_old created first, then child_new which becomes default.
    await repo.create(user_id=USER, child_id="child_old", name="Old", age_group="9-12", is_default=False)
    await repo.create(user_id=USER, child_id="child_new", name="New", age_group="9-12", is_default=True)

    await repo.archive(user_id=USER, child_id="child_new")

    remaining = await repo.get_for_user(USER, "child_old")
    assert remaining.is_default is True
    assert await _default_child_id(repo) == "child_old"


@pytest.mark.asyncio
async def test_archiving_last_active_clears_default(repo):
    await repo.create(user_id=USER, child_id="only_child", name="Solo", age_group="9-12", is_default=True)

    await repo.archive(user_id=USER, child_id="only_child")

    assert await _default_child_id(repo) is None


@pytest.mark.asyncio
async def test_archiving_non_default_leaves_default_untouched(repo):
    await repo.create(user_id=USER, child_id="keep", name="Keep", age_group="9-12", is_default=True)
    await repo.create(user_id=USER, child_id="extra", name="Extra", age_group="9-12", is_default=False)

    await repo.archive(user_id=USER, child_id="extra")

    keep = await repo.get_for_user(USER, "keep")
    assert keep.is_default is True
    assert await _default_child_id(repo) == "keep"
