"""
Scheduler Lifecycle Contract Tests (#157)

Validates that DailyDropScheduler can start/stop cleanly,
parses schedule values correctly, respects the DAILY_DROP_ENABLED flag,
and deduplicates daily generation via _already_generated_today.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from unittest.mock import AsyncMock, patch

from backend.src.services.morning_show_scheduler import DailyDropScheduler


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler() -> DailyDropScheduler:
    return DailyDropScheduler()


# ---------------------------------------------------------------------------
# 1. Start / Stop lifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    """Contract: scheduler can start and stop without error."""

    @pytest.mark.asyncio
    async def test_start_creates_running_task(self, scheduler: DailyDropScheduler):
        """Contract: after start(), _task exists and is not done."""
        await scheduler.start()
        try:
            assert scheduler._task is not None
            assert not scheduler._task.done()
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, scheduler: DailyDropScheduler):
        """Contract: after stop(), _task is done (cancelled)."""
        await scheduler.start()
        await scheduler.stop()
        assert scheduler._task.done()

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self, scheduler: DailyDropScheduler):
        """Contract: calling start() twice does not create a second task."""
        await scheduler.start()
        first_task = scheduler._task
        await scheduler.start()
        assert scheduler._task is first_task
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, scheduler: DailyDropScheduler):
        """Contract: calling stop() before start() does not raise."""
        await scheduler.stop()  # should not raise


# ---------------------------------------------------------------------------
# 2. _parse_schedule
# ---------------------------------------------------------------------------

class TestParseSchedule:
    """Contract: _parse_schedule converts HH:MM strings and handles bad input."""

    def test_valid_hhmm(self, scheduler: DailyDropScheduler):
        assert scheduler._parse_schedule("02:00") == (2, 0)

    def test_valid_afternoon(self, scheduler: DailyDropScheduler):
        assert scheduler._parse_schedule("14:30") == (14, 30)

    def test_hour_only(self, scheduler: DailyDropScheduler):
        """When minute part is missing, default to :00."""
        assert scheduler._parse_schedule("7") == (7, 0)

    def test_invalid_string_falls_back(self, scheduler: DailyDropScheduler):
        """Non-numeric input falls back to 02:00."""
        assert scheduler._parse_schedule("not-a-time") == (2, 0)

    def test_out_of_range_clamped(self, scheduler: DailyDropScheduler):
        """Hours > 23 or minutes > 59 are clamped."""
        assert scheduler._parse_schedule("25:99") == (23, 59)

    def test_empty_string_falls_back(self, scheduler: DailyDropScheduler):
        assert scheduler._parse_schedule("") == (2, 0)


# ---------------------------------------------------------------------------
# 3. DAILY_DROP_ENABLED=0 prevents start
# ---------------------------------------------------------------------------

class TestDailyDropEnabledFlag:
    """Contract: when DAILY_DROP_ENABLED=0, lifespan must not call start()."""

    def test_enabled_flag_checked_in_lifespan(self):
        """Contract: the lifespan reads DAILY_DROP_ENABLED and skips start when '0'."""
        import inspect
        from backend.src.main import lifespan

        source = inspect.getsource(lifespan)
        assert "DAILY_DROP_ENABLED" in source, (
            "lifespan must read DAILY_DROP_ENABLED env var"
        )
        # The pattern: scheduler_enabled = os.getenv("DAILY_DROP_ENABLED", "1") != "0"
        assert '!= "0"' in source or "!= '0'" in source, (
            "lifespan must compare DAILY_DROP_ENABLED to '0' to decide whether to start"
        )


# ---------------------------------------------------------------------------
# 4. _already_generated_today deduplication
# ---------------------------------------------------------------------------

class TestAlreadyGeneratedToday:
    """Contract: _already_generated_today returns True when a matching row exists."""

    @pytest.mark.asyncio
    async def test_returns_true_when_row_exists(self, scheduler: DailyDropScheduler):
        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            mock_db.fetchone = AsyncMock(return_value={"story_id": "s1"})

            result = await scheduler._already_generated_today("user1", "child1", "science")

            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_row(self, scheduler: DailyDropScheduler):
        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            mock_db.fetchone = AsyncMock(return_value=None)

            result = await scheduler._already_generated_today("user1", "child1", "science")

            assert result is False

    @pytest.mark.asyncio
    async def test_query_includes_today_date(self, scheduler: DailyDropScheduler):
        """Contract: the SQL query filters by today's date."""
        from datetime import datetime as _dt

        today = _dt.now().date().isoformat()

        with patch(
            "backend.src.services.morning_show_scheduler.db_manager"
        ) as mock_db:
            mock_db.fetchone = AsyncMock(return_value=None)

            await scheduler._already_generated_today("u", "c", "tech")

            call_args = mock_db.fetchone.call_args
            params = call_args[0][1]
            # Third positional param should be today's date pattern
            assert today in params[2]


# ---------------------------------------------------------------------------
# 5. Health check reports scheduler status
# ---------------------------------------------------------------------------

class TestHealthCheckSchedulerStatus:
    """Contract: /health response includes daily_drop_scheduler status."""

    def test_health_check_references_scheduler(self):
        """Contract: health_check function source must include daily_drop_scheduler."""
        import inspect
        from backend.src.main import health_check

        source = inspect.getsource(health_check)
        assert "daily_drop_scheduler" in source, (
            "/health must report daily_drop_scheduler status"
        )
