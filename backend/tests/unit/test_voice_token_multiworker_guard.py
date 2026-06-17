"""Unit tests for the multi-worker guard on the voice-token nonce (#684).

Parent Epic: #605

The single-use voice token replay guard (``_USED_JTIS``) is an in-process
dict. It is only correct with exactly one process/replica. Prod runs a single
uvicorn worker today (no ``--workers``), so it is safe NOW. This guard warns
loudly at startup if anyone configures ``WEB_CONCURRENCY``/``UVICORN_WORKERS``
> 1 so the safety assumption can never be violated silently. The full fix
(DB-backed nonce on the voice_sessions row) is the documented future path.
"""

import logging

from src.services.voice_ephemeral_token import assert_single_process_or_warn


class TestAssertSingleProcessOrWarn:
    """Startup guard: single worker is silent; multi-worker warns."""

    def test_no_warning_when_concurrency_unset(self, caplog, monkeypatch):
        monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
        monkeypatch.delenv("UVICORN_WORKERS", raising=False)
        with caplog.at_level(logging.WARNING):
            assert_single_process_or_warn()
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_no_warning_when_concurrency_is_one(self, caplog, monkeypatch):
        monkeypatch.setenv("WEB_CONCURRENCY", "1")
        monkeypatch.delenv("UVICORN_WORKERS", raising=False)
        with caplog.at_level(logging.WARNING):
            assert_single_process_or_warn()
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_warns_when_web_concurrency_gt_one(self, caplog, monkeypatch):
        monkeypatch.setenv("WEB_CONCURRENCY", "2")
        monkeypatch.delenv("UVICORN_WORKERS", raising=False)
        with caplog.at_level(logging.WARNING):
            assert_single_process_or_warn()
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings, "expected a warning when WEB_CONCURRENCY=2"
        assert "#684" in warnings[0].getMessage()

    def test_warns_when_uvicorn_workers_gt_one(self, caplog, monkeypatch):
        monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
        monkeypatch.setenv("UVICORN_WORKERS", "4")
        with caplog.at_level(logging.WARNING):
            assert_single_process_or_warn()
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings, "expected a warning when UVICORN_WORKERS=4"
        assert "#684" in warnings[0].getMessage()

    def test_no_warning_on_unparseable_value(self, caplog, monkeypatch):
        monkeypatch.setenv("WEB_CONCURRENCY", "auto")
        monkeypatch.delenv("UVICORN_WORKERS", raising=False)
        with caplog.at_level(logging.WARNING):
            assert_single_process_or_warn()
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
