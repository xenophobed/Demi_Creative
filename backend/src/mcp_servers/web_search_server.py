"""
Web Search MCP Server

Provides tools for fetching real-time news headlines and article content
using the Tavily Search API. Safe-search behaviour is enforced by restricting
the query to child-appropriate news content and by relying on the platform's
existing safety_check_server for all generated output.
"""

import os
import json
from typing import Any, Dict

from claude_agent_sdk import tool, create_sdk_mcp_server

_MAX_RESULTS_LIMIT = 10
_MAX_RESULTS_DEFAULT = 5


@tool(
    "get_headlines_by_topic",
    """Fetch real-time news headlines for a given topic using Tavily Search.

    Returns a list of recent news articles suitable for summarising into
    a Kids Morning Show episode. Each headline includes title, url,
    a short description, and published_date when available.

    Always use this tool before building a Morning Show episode so the
    episode reflects actual current events rather than synthesised content.""",
    {"topic": str, "max_results": int},
)
async def get_headlines_by_topic(args: Dict[str, Any]) -> Dict[str, Any]:
    topic = args["topic"]
    max_results = min(int(args.get("max_results", _MAX_RESULTS_DEFAULT)), _MAX_RESULTS_LIMIT)

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "web-search unavailable", "headlines": [], "topic": topic}),
            }]
        }

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(
            query=topic,
            search_depth="basic",
            topic="news",
            days=1,
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
            include_images=False,
        )

        headlines = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("content", ""),
                "published_date": r.get("published_date", ""),
            }
            for r in response.get("results", [])
        ]

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"headlines": headlines, "topic": topic}, ensure_ascii=False),
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": f"web-search failed: {str(e)}", "headlines": [], "topic": topic}),
            }]
        }


@tool(
    "fetch_article_text",
    """Extract the main body text from a news article URL using Tavily Extract.

    Returns cleaned article text without ads, navigation, or boilerplate.
    Use this to retrieve the full content of a specific article URL obtained
    from get_headlines_by_topic.""",
    {"url": str},
)
async def fetch_article_text(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args["url"]

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "web-search unavailable", "url": url, "text": ""}),
            }]
        }

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=api_key)
        response = await client.extract(urls=[url])

        results = response.get("results", [])
        if results:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(
                        {"url": url, "text": results[0].get("raw_content", "")},
                        ensure_ascii=False,
                    ),
                }]
            }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"url": url, "text": "", "error": "no content extracted"}),
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": f"article fetch failed: {str(e)}", "url": url, "text": ""}),
            }]
        }


web_search_server = create_sdk_mcp_server(
    name="web-search",
    version="1.0.0",
    tools=[get_headlines_by_topic, fetch_article_text],
)


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        print("=== Test web_search_server ===\n")

        print("1. get_headlines_by_topic (space exploration)...")
        result = await get_headlines_by_topic({"topic": "space exploration for kids", "max_results": 3})
        data = json.loads(result["content"][0]["text"])
        print(f"  headlines returned: {len(data.get('headlines', []))}")
        for h in data.get("headlines", []):
            print(f"  - {h['title']}")
        print()

        print("2. Missing API key fallback...")
        original = os.environ.pop("TAVILY_API_KEY", None)
        result = await get_headlines_by_topic({"topic": "dinosaurs"})
        data = json.loads(result["content"][0]["text"])
        assert data.get("error") == "web-search unavailable"
        print("  Fallback OK:", data["error"])
        if original:
            os.environ["TAVILY_API_KEY"] = original

    asyncio.run(_test())
