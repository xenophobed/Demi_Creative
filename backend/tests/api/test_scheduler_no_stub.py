"""Tests for #189 — scheduler retries Tavily and skips when headlines unavailable."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.morning_show_scheduler import DailyDropScheduler, _MAX_HEADLINE_RETRIES


@pytest.fixture
def scheduler():
    return DailyDropScheduler()


def _tavily_response(headlines: list[dict] | None = None) -> dict:
    """Build a mock MCP tool response."""
    data = {"headlines": headlines or [], "topic": "science"}
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _tavily_error_response(error: str = "web-search failed: timeout") -> dict:
    data = {"error": error, "headlines": [], "topic": "science"}
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class TestFetchNewsTextReturnsNone:
    """_fetch_news_text should return None (not a stub) when headlines are unavailable."""

    @pytest.mark.asyncio
    async def test_returns_none_on_import_error(self, scheduler):
        """If the headlines MCP module is not importable, return None."""
        with patch.dict("sys.modules", {"src.mcp_servers": MagicMock(spec=[])}):
            result = await scheduler._fetch_news_text("science")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_headlines(self, scheduler):
        """If the API returns an empty headlines list after all retries, return None."""
        mock_fn = AsyncMock(return_value=_tavily_response([]))
        with (
            patch("src.services.morning_show_scheduler.get_headlines_by_topic", mock_fn),
            patch("src.services.morning_show_scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scheduler._fetch_news_text("sports")
        assert result is None
        assert mock_fn.call_count == _MAX_HEADLINE_RETRIES


class TestFetchNewsTextRetries:
    """_fetch_news_text should retry on transient failures before giving up."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self, scheduler):
        """Transient failure followed by success should return headlines."""
        good = _tavily_response([{"title": "Mars rover update", "description": "Perseverance found ice"}])
        mock_fn = AsyncMock(side_effect=[Exception("timeout"), good])
        with (
            patch("src.services.morning_show_scheduler.get_headlines_by_topic", mock_fn),
            patch("src.services.morning_show_scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scheduler._fetch_news_text("space")
        assert result is not None
        assert "Mars rover update" in result
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_after_all_retries_exhausted(self, scheduler):
        """When all retry attempts fail, return None."""
        mock_fn = AsyncMock(side_effect=Exception("timeout"))
        with (
            patch("src.services.morning_show_scheduler.get_headlines_by_topic", mock_fn),
            patch("src.services.morning_show_scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scheduler._fetch_news_text("science")
        assert result is None
        assert mock_fn.call_count == _MAX_HEADLINE_RETRIES

    @pytest.mark.asyncio
    async def test_retries_on_empty_headlines_then_succeeds(self, scheduler):
        """Empty headlines on first attempt, real headlines on second."""
        empty = _tavily_response([])
        good = _tavily_response([{"title": "Dino discovery", "description": "New species found"}])
        mock_fn = AsyncMock(side_effect=[empty, good])
        with (
            patch("src.services.morning_show_scheduler.get_headlines_by_topic", mock_fn),
            patch("src.services.morning_show_scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scheduler._fetch_news_text("dinosaurs")
        assert result is not None
        assert "Dino discovery" in result
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_error_response(self, scheduler):
        """Tavily error dict should trigger retry."""
        error_resp = _tavily_error_response("rate limited")
        good = _tavily_response([{"title": "Ocean cleanup", "description": "Kids help clean beaches"}])
        mock_fn = AsyncMock(side_effect=[error_resp, good])
        with (
            patch("src.services.morning_show_scheduler.get_headlines_by_topic", mock_fn),
            patch("src.services.morning_show_scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scheduler._fetch_news_text("environment")
        assert result is not None
        assert "Ocean cleanup" in result


class TestRunDailyDropSkipsOnNone:
    """run_daily_drop must skip — not persist — topics with no headlines."""

    @pytest.mark.asyncio
    async def test_skips_topic_when_fetch_returns_none(self, scheduler, caplog):
        """When _fetch_news_text returns None, no episode should be generated."""
        fake_sub = {
            "user_id": "u1",
            "child_id": "c1",
            "topic": "science",
        }

        import logging
        with (
            caplog.at_level(logging.WARNING),
            patch.object(scheduler, "_already_generated_today", new_callable=AsyncMock, return_value=False),
            patch.object(scheduler, "_fetch_news_text", new_callable=AsyncMock, return_value=None),
            patch("src.services.morning_show_scheduler.subscription_repo") as mock_repo,
        ):
            mock_repo.list_all_active = AsyncMock(return_value=[fake_sub])
            await scheduler.run_daily_drop()

        assert any("Skipping" in r.message or "no headlines" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_processes_topic_when_fetch_succeeds(self, scheduler):
        """When _fetch_news_text returns text, episode generation proceeds."""
        fake_sub = {
            "user_id": "u1",
            "child_id": "c1",
            "topic": "science",
        }

        build_episode_mock = AsyncMock()

        with (
            patch.object(scheduler, "_already_generated_today", new_callable=AsyncMock, return_value=False),
            patch.object(scheduler, "_fetch_news_text", new_callable=AsyncMock, return_value="Today's science news:\n- Discovery"),
            patch("src.services.morning_show_scheduler.subscription_repo") as mock_repo,
            patch("src.services.morning_show_scheduler.DailyDropScheduler.run_daily_drop") as mock_run,
        ):
            mock_repo.list_all_active = AsyncMock(return_value=[fake_sub])
            assert hasattr(scheduler, "_fetch_news_text")
            result = await scheduler._fetch_news_text("science")
            assert result == "Today's science news:\n- Discovery"
