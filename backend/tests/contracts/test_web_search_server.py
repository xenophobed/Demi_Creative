"""
Contract tests for the web_search_server MCP tools.

These tests verify the shape of tool responses independently of the Tavily
API being available.  All network calls are mocked so the suite can run
in CI without a live TAVILY_API_KEY.

NOTE: The @tool decorator from claude_agent_sdk wraps functions in SdkMcpTool
objects.  Call the underlying function via `.handler(args)`.
"""

import importlib
import json
import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Module fixture — loads the actual .py file, not the __init__ server dict
# ---------------------------------------------------------------------------

@pytest.fixture()
def ws():
    """Return the web_search_server module (not the package-level server dict)."""
    return importlib.import_module("backend.src.mcp_servers.web_search_server")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_result(result: dict) -> dict:
    """Unwrap the MCP content envelope and return the parsed JSON payload."""
    assert "content" in result, "Response must contain 'content' key"
    assert isinstance(result["content"], list), "'content' must be a list"
    assert len(result["content"]) > 0, "'content' list must not be empty"
    item = result["content"][0]
    assert item.get("type") == "text", "content[0].type must be 'text'"
    return json.loads(item["text"])


def _make_fake_tavily(client_cls) -> types.ModuleType:
    """Return a fake 'tavily' module containing *client_cls* as AsyncTavilyClient."""
    mod = types.ModuleType("tavily")
    mod.AsyncTavilyClient = client_cls
    return mod


# ---------------------------------------------------------------------------
# get_headlines_by_topic
# ---------------------------------------------------------------------------

class TestGetHeadlinesByTopic:
    """Contract: mcp__web-search__get_headlines_by_topic"""

    @pytest.mark.asyncio
    async def test_successful_response_shape(self, ws, monkeypatch):
        """Tool returns a properly shaped headlines list when Tavily responds."""

        class _FakeClient:
            def __init__(self, api_key):
                pass

            async def search(self, **kwargs):
                return {
                    "results": [
                        {
                            "title": "Astronauts land on the Moon!",
                            "url": "https://example.com/moon",
                            "content": "Scientists celebrated as astronauts touched down.",
                            "published_date": "2026-03-03",
                        },
                        {
                            "title": "New dinosaur fossil found in Argentina",
                            "url": "https://example.com/dino",
                            "content": "Paleontologists uncovered a massive sauropod.",
                            "published_date": "2026-03-02",
                        },
                    ]
                }

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-fake-key")
        monkeypatch.setitem(sys.modules, "tavily", _make_fake_tavily(_FakeClient))

        result = await ws.get_headlines_by_topic.handler({"topic": "space", "max_results": 3})
        data = _parse_result(result)

        assert "headlines" in data, "Response must contain 'headlines'"
        assert "topic" in data, "Response must contain 'topic'"
        assert data["topic"] == "space"
        assert isinstance(data["headlines"], list)
        assert len(data["headlines"]) == 2

        headline = data["headlines"][0]
        assert "title" in headline
        assert "url" in headline
        assert "description" in headline
        assert "published_date" in headline

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_graceful_fallback(self, ws, monkeypatch):
        """Tool returns error dict (not an exception) when TAVILY_API_KEY is absent."""
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        result = await ws.get_headlines_by_topic.handler({"topic": "science"})
        data = _parse_result(result)

        assert data.get("error") == "web-search unavailable"
        assert data.get("headlines") == []
        assert data.get("topic") == "science"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self, ws, monkeypatch):
        """Tool handles an empty result set from Tavily without crashing."""

        class _EmptyClient:
            def __init__(self, api_key):
                pass

            async def search(self, **kwargs):
                return {"results": []}

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-fake-key")
        monkeypatch.setitem(sys.modules, "tavily", _make_fake_tavily(_EmptyClient))

        result = await ws.get_headlines_by_topic.handler({"topic": "penguins"})
        data = _parse_result(result)

        assert data.get("headlines") == []
        assert "error" not in data

    @pytest.mark.asyncio
    async def test_max_results_is_capped(self, ws, monkeypatch):
        """Tool never requests more than _MAX_RESULTS_LIMIT results."""
        received_kwargs: dict = {}

        class _CapClient:
            def __init__(self, api_key):
                pass

            async def search(self, **kwargs):
                received_kwargs.update(kwargs)
                return {"results": []}

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-fake-key")
        monkeypatch.setitem(sys.modules, "tavily", _make_fake_tavily(_CapClient))

        await ws.get_headlines_by_topic.handler({"topic": "robots", "max_results": 999})
        assert received_kwargs.get("max_results", 0) <= ws._MAX_RESULTS_LIMIT


# ---------------------------------------------------------------------------
# fetch_article_text
# ---------------------------------------------------------------------------

class TestFetchArticleText:
    """Contract: mcp__web-search__fetch_article_text"""

    @pytest.mark.asyncio
    async def test_successful_response_shape(self, ws, monkeypatch):
        """Tool returns url and text keys when extraction succeeds."""

        class _ExtractClient:
            def __init__(self, api_key):
                pass

            async def extract(self, urls):
                return {
                    "results": [{"url": urls[0], "raw_content": "Article body text here."}],
                    "failed_results": [],
                }

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-fake-key")
        monkeypatch.setitem(sys.modules, "tavily", _make_fake_tavily(_ExtractClient))

        result = await ws.fetch_article_text.handler({"url": "https://example.com/article"})
        data = _parse_result(result)

        assert "url" in data
        assert "text" in data
        assert data["url"] == "https://example.com/article"
        assert data["text"] == "Article body text here."

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_graceful_fallback(self, ws, monkeypatch):
        """Tool returns error dict when TAVILY_API_KEY is absent."""
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        result = await ws.fetch_article_text.handler({"url": "https://example.com/article"})
        data = _parse_result(result)

        assert data.get("error") == "web-search unavailable"
        assert data.get("text") == ""
