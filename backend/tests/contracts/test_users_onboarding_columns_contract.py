"""
Users Onboarding Columns Schema Contract Tests

Locks the schema contract for the four nullable onboarding columns added to
the users table by issue #438:
  - nickname
  - onboarded_at
  - parent_consent_at
  - default_child_id

Parent Epic: #436 (My Agent — personalized buddy persona)
Issue: #438
"""

from typing import Dict, List

import pytest
import pytest_asyncio

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema


REQUIRED_ONBOARDING_COLUMNS = (
    "nickname",
    "onboarded_at",
    "parent_consent_at",
    "default_child_id",
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory database with full schema applied."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


async def _users_columns(db: DatabaseManager) -> List[Dict]:
    return await db.fetchall("PRAGMA table_info(users)")


# ============================================================================
# Contract: columns exist
# ============================================================================


class TestOnboardingColumnsExist:
    """All four onboarding columns are present on the users table."""

    @pytest.mark.asyncio
    async def test_nickname_column_exists(self, db):
        cols = {row["name"] for row in await _users_columns(db)}
        assert "nickname" in cols

    @pytest.mark.asyncio
    async def test_onboarded_at_column_exists(self, db):
        cols = {row["name"] for row in await _users_columns(db)}
        assert "onboarded_at" in cols

    @pytest.mark.asyncio
    async def test_parent_consent_at_column_exists(self, db):
        cols = {row["name"] for row in await _users_columns(db)}
        assert "parent_consent_at" in cols

    @pytest.mark.asyncio
    async def test_default_child_id_column_exists(self, db):
        cols = {row["name"] for row in await _users_columns(db)}
        assert "default_child_id" in cols


# ============================================================================
# Contract: columns are nullable
# ============================================================================


class TestOnboardingColumnsNullable:
    """All four onboarding columns must be NULLABLE — non-destructive migration."""

    @pytest.mark.asyncio
    async def test_all_onboarding_columns_nullable(self, db):
        rows = await _users_columns(db)
        # PRAGMA table_info: column "notnull" is 1 if NOT NULL, 0 if nullable.
        info = {row["name"]: row for row in rows}
        for name in REQUIRED_ONBOARDING_COLUMNS:
            assert name in info, f"missing column {name}"
            assert info[name]["notnull"] == 0, (
                f"column {name} must be NULLABLE so existing rows stay valid"
            )


# ============================================================================
# Contract: idempotent migrations
# ============================================================================


class TestSchemaIdempotency:
    """init_schema can run multiple times without error or duplicate columns."""

    @pytest.mark.asyncio
    async def test_init_schema_runs_twice_without_error(self, db):
        # Fixture already ran init_schema once; run it again.
        await init_schema(db)
        cols = {row["name"] for row in await _users_columns(db)}
        for name in REQUIRED_ONBOARDING_COLUMNS:
            assert name in cols

    @pytest.mark.asyncio
    async def test_init_schema_three_runs_no_duplicates(self, db):
        await init_schema(db)
        await init_schema(db)
        rows = await _users_columns(db)
        names = [row["name"] for row in rows]
        for col in REQUIRED_ONBOARDING_COLUMNS:
            assert names.count(col) == 1, f"column {col} duplicated after rerun"


# ============================================================================
# Contract: existing data preserved
# ============================================================================


class TestNonDestructive:
    """Inserting a user without onboarding fields stays valid post-migration."""

    @pytest.mark.asyncio
    async def test_user_insert_without_onboarding_fields(self, db):
        await db.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash,
                display_name, is_active, is_verified, role,
                membership_tier, referral_code, referred_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "u-onb-1",
                "onbuser",
                "onb@test.com",
                "h",
                "Onb",
                1,
                0,
                "child",
                "free",
                "code1234",
                None,
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        await db.commit()
        row = await db.fetchone(
            "SELECT nickname, onboarded_at, parent_consent_at, default_child_id "
            "FROM users WHERE user_id = ?",
            ("u-onb-1",),
        )
        assert row is not None
        assert row["nickname"] is None
        assert row["onboarded_at"] is None
        assert row["parent_consent_at"] is None
        assert row["default_child_id"] is None
