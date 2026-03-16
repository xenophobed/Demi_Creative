"""Automated retention cleanup scheduler (#145).

Runs daily at a configurable hour (default 03:00, one hour after Daily Drop)
to archive expired intermediate/candidate artifacts and delete expired
archived artifacts.

Configuration:
    RETENTION_SCHEDULE_HOUR   — Hour to run (0-23, default 3)
    RETENTION_CLEANUP_ENABLED — Set to "0" to disable (checked in main.py)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, time, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class RetentionScheduler:
    """In-process daily scheduler for artifact retention cleanup."""

    def __init__(self) -> None:
        raw_hour = os.getenv("RETENTION_SCHEDULE_HOUR", "3")
        try:
            self._hour = max(0, min(23, int(raw_hour)))
        except ValueError:
            self._hour = 3
        self._dry_run = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(), name="retention-scheduler"
        )
        logger.info("Retention scheduler started (runs daily at %02d:00)", self._hour)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info("Retention scheduler stopped")

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now()
            next_run = datetime.combine(now.date(), time(self._hour, 0))
            if now >= next_run:
                next_run += timedelta(days=1)

            wait_seconds = max(1.0, (next_run - now).total_seconds())

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=wait_seconds
                )
                break
            except asyncio.TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            await self.run_cleanup()

    async def run_cleanup(self) -> None:
        """Execute one retention cleanup cycle."""
        from .database.connection import db_manager
        from .retention_service import RetentionService

        try:
            service = RetentionService(db_manager)
            report = await service.run_cleanup(dry_run=self._dry_run)

            logger.info(
                "Retention cleanup complete: "
                "candidates=%d safeguarded=%d archived=%d deleted=%d",
                report.candidates_found,
                report.safeguarded_count,
                report.archived_count,
                report.deleted_count,
            )
        except Exception:
            logger.exception("Retention cleanup failed")


retention_scheduler = RetentionScheduler()
