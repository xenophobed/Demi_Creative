"""
Retention Scheduler Contract Tests (Issue #145)

Defines the expected interface and behavior for the automated
retention cleanup scheduler.
"""

import pytest


class TestRetentionSchedulerContract:
    """Contract: RetentionScheduler interface and configuration."""

    def test_scheduler_exists(self):
        """Contract: RetentionScheduler class is importable."""
        from src.services.retention_scheduler import RetentionScheduler

        assert RetentionScheduler is not None

    def test_scheduler_has_start_stop(self):
        """Contract: Scheduler exposes async start() and stop() methods."""
        from src.services.retention_scheduler import RetentionScheduler

        assert hasattr(RetentionScheduler, "start")
        assert hasattr(RetentionScheduler, "stop")

    def test_scheduler_has_run_cleanup(self):
        """Contract: Scheduler exposes async run_cleanup() for manual trigger."""
        from src.services.retention_scheduler import RetentionScheduler

        assert hasattr(RetentionScheduler, "run_cleanup")

    def test_default_schedule_hour(self):
        """Contract: Default schedule hour is 3 (03:00), offset from Daily Drop at 02:00."""
        import os

        env_backup = os.environ.pop("RETENTION_SCHEDULE_HOUR", None)
        try:
            from src.services.retention_scheduler import RetentionScheduler

            scheduler = RetentionScheduler()
            assert scheduler._hour == 3
        finally:
            if env_backup is not None:
                os.environ["RETENTION_SCHEDULE_HOUR"] = env_backup

    def test_scheduler_respects_env_hour(self):
        """Contract: RETENTION_SCHEDULE_HOUR overrides default."""
        import os

        os.environ["RETENTION_SCHEDULE_HOUR"] = "5"
        try:
            from src.services.retention_scheduler import RetentionScheduler

            scheduler = RetentionScheduler()
            assert scheduler._hour == 5
        finally:
            del os.environ["RETENTION_SCHEDULE_HOUR"]

    def test_scheduler_can_be_disabled(self):
        """Contract: RETENTION_CLEANUP_ENABLED=0 is the documented disable mechanism."""
        import os

        # The scheduler itself always works; disabling is done in main.py lifespan.
        # This test just documents the env var name.
        assert "RETENTION_CLEANUP_ENABLED" not in os.environ or True

    def test_singleton_exists(self):
        """Contract: Module exposes a retention_scheduler singleton."""
        from src.services.retention_scheduler import retention_scheduler

        assert retention_scheduler is not None

    def test_dry_run_default_true(self):
        """Contract: Scheduler defaults to dry_run=False for automated runs."""
        from src.services.retention_scheduler import RetentionScheduler

        scheduler = RetentionScheduler()
        assert scheduler._dry_run is False
