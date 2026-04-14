# Web Search MCP Server

**Source**: `backend/src/mcp_servers/web_search_server.py`

## What This File Does

**Explorer**: This helper goes out and finds real news from the internet, then brings it back so the Kids Daily agent can rewrite it in kid-friendly language. It's like a reporter who finds the news, while the agent is the editor who makes it fun for kids.

**Maker**: This MCP server wraps the Tavily Search API to fetch real-time news headlines filtered by category (space, animals, technology, etc.). It returns structured search results that the `kids_daily_agent` rewrites into age-appropriate podcast episodes. Includes retry logic for API failures.

## How It Works

1. **Agent calls `search_kids_news`** with a category (e.g., "space") and target age group
2. **Server builds a search query** combining the category with kid-safe search parameters
3. **Tavily API returns** real news articles with titles, URLs, and snippets
4. **Server filters and ranks** results for relevance and appropriateness
5. **Returns structured results** to the agent for rewriting into kid-friendly language

## Key Concepts

**Tavily Search API**: A search engine API designed for AI applications. Unlike Google Search, it returns structured, clean text snippets rather than HTML pages — better for AI consumption.

**Content Curation Pipeline**: Raw news → search → filter → rewrite → safety check → deliver. The web search server handles the "search" step; the agent handles "rewrite"; the safety server handles "check."

**Category Filtering**: The server supports predefined categories (space, animals, technology, science, nature, culture, sports, general) matching the subscription topics in the Morning Show feature.

## Connections

- **Upstream**: Called by `kids_daily_agent.py` to fetch headlines for podcast episodes
- **Downstream**: Tavily Search API (requires `TAVILY_API_KEY` env var)
- **Related**: `services/news_headline_fetcher.py` provides an alternative headline source
- **Related**: `api/routes/kids_daily.py` triggers on-demand episode generation

## Thinking Question

What if the Tavily API returns a news article about a school shooting when a child searches "school"? The search server returns raw results — it's the safety check server's job to filter inappropriate content later. Is this the right design, or should the search server itself pre-filter? What are the trade-offs of filtering at search time vs. generation time?
