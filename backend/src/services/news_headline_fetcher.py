"""Shared headline fetcher for Morning Show on-demand and Daily Drop (#303)."""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_HEADLINE_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0

try:
    from ..mcp_servers import get_headlines_by_topic as _raw_tool
    # The @tool decorator from claude_agent_sdk wraps functions in SdkMcpTool
    # objects that aren't directly callable. Unwrap to the original handler.
    get_headlines_by_topic = getattr(_raw_tool, "handler", _raw_tool)
except Exception:  # pragma: no cover — import may fail in minimal test envs
    get_headlines_by_topic = None  # type: ignore[assignment]


async def fetch_news_text(topic: str) -> Optional[str]:
    """Return real headlines for *topic* from Tavily, retrying on transient failures.

    Retries up to ``_MAX_HEADLINE_RETRIES`` times with linear backoff.
    Returns ``None`` only after all attempts are exhausted.
    """
    if get_headlines_by_topic is None:
        logger.warning("Tavily MCP tool not available — skipping topic '%s'", topic)
        return None

    last_error: Optional[str] = None
    for attempt in range(1, _MAX_HEADLINE_RETRIES + 1):
        try:
            result = await get_headlines_by_topic({"topic": topic, "max_results": 5})
            data = _json.loads(result["content"][0]["text"])

            if data.get("error"):
                last_error = data["error"]
                logger.info(
                    "Tavily returned error for '%s' (attempt %d/%d): %s",
                    topic, attempt, _MAX_HEADLINE_RETRIES, last_error,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue

            headlines = data.get("headlines", [])
            if not headlines:
                last_error = "empty headlines"
                logger.info(
                    "No headlines for '%s' (attempt %d/%d)",
                    topic, attempt, _MAX_HEADLINE_RETRIES,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue

            lines = [f"- {h['title']}: {h['description']}" for h in headlines if h.get("title")]
            if not lines:
                last_error = "headlines had no titles"
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue

            if attempt > 1:
                logger.info("Tavily succeeded for '%s' on attempt %d", topic, attempt)
            return f"Today's news about {topic}:\n" + "\n".join(lines)

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Tavily fetch exception for '%s' (attempt %d/%d): %s",
                topic, attempt, _MAX_HEADLINE_RETRIES, exc,
            )
            if attempt < _MAX_HEADLINE_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    logger.warning(
        "All %d headline fetch attempts failed for '%s': %s",
        _MAX_HEADLINE_RETRIES, topic, last_error,
    )
    return None
