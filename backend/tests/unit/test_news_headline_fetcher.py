"""Unit tests for news_headline_fetcher retry logic and backoff timing (#311).

Complements the tests in test_scheduler_no_stub.py with focused coverage of:
- Retry succeeds after transient failure
- Retry gives up after max retries
- Returns None when tool is unavailable
- Backoff timing increases linearly
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, call

from src.services.news_headline_fetcher import (
    fetch_news_text,
    _MAX_HEADLINE_RETRIES,
    _RETRY_BACKOFF_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tavily_response(headlines: list[dict] | None = None) -> dict:
    """Build a mock MCP tool response with valid headlines."""
    data = {"headlines": headlines or [], "topic": "science"}
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _tavily_error_response(error: str = "timeout") -> dict:
    """Build a mock MCP tool response with an error."""
    data = {"error": error, "headlines": [], "topic": "science"}
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


# ---------------------------------------------------------------------------
# Tool unavailable
# ---------------------------------------------------------------------------
class TestToolUnavailable:
    """fetch_news_text returns None when the MCP tool is not available."""

    @pytest.mark.asyncio
    async def test_returns_none_when_tool_is_none(self):
        """If get_headlines_by_topic is None (import failed), return None immediately."""
        with patch("src.services.news_headline_fetcher.get_headlines_by_topic", None):
            result = await fetch_news_text("science")
        assert result is None


# ---------------------------------------------------------------------------
# Retry logic — succeeds after transient failure
# ---------------------------------------------------------------------------
class TestRetrySucceedsAfterTransientFailure:
    """fetch_news_text should succeed when a transient failure is followed by a good response."""

    @pytest.mark.asyncio
    async def test_succeeds_after_one_exception(self):
        """One exception then a valid response should return headlines."""
        good = _tavily_response([{"title": "New species", "description": "A frog was found"}])
        mock_fn = AsyncMock(side_effect=[Exception("network error"), good])
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("nature")
        assert result is not None
        assert "New species" in result
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_after_empty_then_good(self):
        """Empty headlines on first attempt, real headlines on second."""
        empty = _tavily_response([])
        good = _tavily_response([{"title": "Solar eclipse", "description": "Amazing event"}])
        mock_fn = AsyncMock(side_effect=[empty, good])
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("space")
        assert result is not None
        assert "Solar eclipse" in result

    @pytest.mark.asyncio
    async def test_succeeds_after_error_response_then_good(self):
        """Tavily error dict on first attempt, valid response on second."""
        error = _tavily_error_response("rate limited")
        good = _tavily_response([{"title": "Robot dog", "description": "Walks on its own"}])
        mock_fn = AsyncMock(side_effect=[error, good])
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("technology")
        assert result is not None
        assert "Robot dog" in result


# ---------------------------------------------------------------------------
# Retry logic — gives up after max retries
# ---------------------------------------------------------------------------
class TestRetryGivesUpAfterMaxRetries:
    """fetch_news_text returns None after exhausting all retry attempts."""

    @pytest.mark.asyncio
    async def test_returns_none_after_all_exceptions(self):
        """When every attempt raises an exception, return None."""
        mock_fn = AsyncMock(side_effect=Exception("persistent failure"))
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("sports")
        assert result is None
        assert mock_fn.call_count == _MAX_HEADLINE_RETRIES

    @pytest.mark.asyncio
    async def test_returns_none_after_all_empty_responses(self):
        """When every attempt returns empty headlines, return None."""
        empty = _tavily_response([])
        mock_fn = AsyncMock(return_value=empty)
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("animals")
        assert result is None
        assert mock_fn.call_count == _MAX_HEADLINE_RETRIES

    @pytest.mark.asyncio
    async def test_returns_none_after_all_error_responses(self):
        """When every attempt returns an error dict, return None."""
        error = _tavily_error_response("service unavailable")
        mock_fn = AsyncMock(return_value=error)
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_news_text("culture")
        assert result is None
        assert mock_fn.call_count == _MAX_HEADLINE_RETRIES


# ---------------------------------------------------------------------------
# Backoff timing increases linearly
# ---------------------------------------------------------------------------
class TestBackoffTimingLinear:
    """Backoff delay should increase linearly: _RETRY_BACKOFF_SECONDS * attempt."""

    @pytest.mark.asyncio
    async def test_backoff_increases_on_exceptions(self):
        """Sleep durations should be 2s, 4s (for _RETRY_BACKOFF_SECONDS=2, attempts 1,2)."""
        mock_fn = AsyncMock(side_effect=Exception("timeout"))
        mock_sleep = AsyncMock()
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", mock_sleep),
        ):
            await fetch_news_text("science")

        # Sleep is called between retries: attempts 1..(N-1) sleep, last attempt does not
        # because the code only sleeps when attempt < _MAX_HEADLINE_RETRIES
        expected_sleeps = [
            call(_RETRY_BACKOFF_SECONDS * attempt)
            for attempt in range(1, _MAX_HEADLINE_RETRIES)
        ]
        assert mock_sleep.call_args_list == expected_sleeps

    @pytest.mark.asyncio
    async def test_backoff_increases_on_empty_headlines(self):
        """Sleep durations should increase linearly on empty headline retries."""
        empty = _tavily_response([])
        mock_fn = AsyncMock(return_value=empty)
        mock_sleep = AsyncMock()
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", mock_sleep),
        ):
            await fetch_news_text("sports")

        # Empty headlines always sleep (all attempts including last)
        expected_sleeps = [
            call(_RETRY_BACKOFF_SECONDS * attempt)
            for attempt in range(1, _MAX_HEADLINE_RETRIES + 1)
        ]
        assert mock_sleep.call_args_list == expected_sleeps

    @pytest.mark.asyncio
    async def test_no_sleep_on_first_success(self):
        """When the first attempt succeeds, no sleep should be called."""
        good = _tavily_response([{"title": "Happy news", "description": "Everything is great"}])
        mock_fn = AsyncMock(return_value=good)
        mock_sleep = AsyncMock()
        with (
            patch("src.services.news_headline_fetcher.get_headlines_by_topic", mock_fn),
            patch("src.services.news_headline_fetcher.asyncio.sleep", mock_sleep),
        ):
            result = await fetch_news_text("general")
        assert result is not None
        mock_sleep.assert_not_called()
