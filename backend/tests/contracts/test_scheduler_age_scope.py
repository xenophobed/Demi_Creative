"""
Scheduler Age Scope Contract Tests (#188)

Validates that _resolve_child_age_group scopes the age lookup by user_id,
preventing cross-account data leakage when two accounts share the same child_id.
"""

from __future__ import annotations

import pytest

from unittest.mock import AsyncMock, patch

from backend.src.api.models import AgeGroup
from backend.src.services.morning_show_scheduler import DailyDropScheduler


@pytest.fixture
def scheduler() -> DailyDropScheduler:
    return DailyDropScheduler()


class TestResolveChildAgeGroupScope:
    """Contract: _resolve_child_age_group must scope by user_id (#188)."""

    @pytest.mark.asyncio
    async def test_matching_user_id_returns_correct_age_group(self, scheduler: DailyDropScheduler):
        """Contract: query with matching child_id AND user_id returns the stored age group."""
        mock_row = {"age_group": "3-5"}

        with patch.object(
            type(scheduler),
            "_resolve_child_age_group",
            wraps=scheduler._resolve_child_age_group,
        ):
            with patch(
                "backend.src.services.morning_show_scheduler.db_manager"
            ) as mock_db:
                mock_db.fetchone = AsyncMock(return_value=mock_row)

                result = await scheduler._resolve_child_age_group("child_001", "user_alice")

                assert result == AgeGroup.AGE_3_5

                # Verify the query includes both child_id AND user_id
                call_args = mock_db.fetchone.call_args
                query = call_args[0][0]
                params = call_args[0][1]

                assert "child_id = ?" in query
                assert "user_id = ?" in query
                assert params == ("child_001", "user_alice")

    @pytest.mark.asyncio
    async def test_different_user_id_does_not_return_other_users_data(self, scheduler: DailyDropScheduler):
        """Contract: query scoped by user_id returns None when no stories exist for that user,
        even if stories exist for the same child_id under a different user."""
        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            # Simulate: no rows found for this user_id + child_id combination
            mock_db.fetchone = AsyncMock(return_value=None)

            result = await scheduler._resolve_child_age_group("child_001", "user_bob")

            # Should fall back to default, not return another user's age group
            assert result == AgeGroup.AGE_6_8

            # Verify user_id was included in the query
            call_args = mock_db.fetchone.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            assert "user_id = ?" in query
            assert "user_bob" in params

    @pytest.mark.asyncio
    async def test_no_stories_returns_default_age_group(self, scheduler: DailyDropScheduler):
        """Contract: when no stories exist for the child+user, return AGE_6_8 default."""
        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            mock_db.fetchone = AsyncMock(return_value=None)

            result = await scheduler._resolve_child_age_group("child_new", "user_new")

            assert result == AgeGroup.AGE_6_8

    @pytest.mark.asyncio
    async def test_invalid_age_group_in_db_returns_default(self, scheduler: DailyDropScheduler):
        """Contract: if stored age_group value is invalid, return the default AGE_6_8."""
        mock_row = {"age_group": "invalid_age"}

        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            mock_db.fetchone = AsyncMock(return_value=mock_row)

            result = await scheduler._resolve_child_age_group("child_001", "user_alice")

            assert result == AgeGroup.AGE_6_8

    @pytest.mark.asyncio
    async def test_function_signature_requires_user_id(self):
        """Contract: _resolve_child_age_group must accept user_id as second parameter."""
        import inspect

        sig = inspect.signature(DailyDropScheduler._resolve_child_age_group)
        params = list(sig.parameters.keys())

        # self, child_id, user_id
        assert "child_id" in params
        assert "user_id" in params


class TestRunDailyDropPassesUserId:
    """Contract: run_daily_drop must pass user_id to _resolve_child_age_group."""

    @pytest.mark.asyncio
    async def test_run_daily_drop_passes_user_id_to_resolve(self, scheduler: DailyDropScheduler):
        """Contract: the caller in run_daily_drop passes user_id from subscription context."""
        import inspect

        # Verify the source code of run_daily_drop calls _resolve_child_age_group
        # with both child_id and user_id
        source = inspect.getsource(DailyDropScheduler.run_daily_drop)
        assert "_resolve_child_age_group(child_id, user_id)" in source, (
            "_resolve_child_age_group must be called with both child_id and user_id"
        )
