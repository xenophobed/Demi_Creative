"""MCP server exports with dependency-safe fallbacks."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Track which MCP servers loaded successfully vs failed.
# Keys: server module name, Values: "ok" or "error: <exception details>"
MCP_SERVER_STATUS: Dict[str, str] = {}


def _get_unavailable_msg(server_name: str) -> str:
    """Return a descriptive error message for a missing MCP server."""
    err_detail = MCP_SERVER_STATUS.get(server_name, "unknown error")
    return json.dumps({
        "error": "MCP server dependency unavailable",
        "server": server_name,
        "details": err_detail,
        "instruction": "Check server logs/diagnostics and ensure required dependencies are installed."
    })


def create_unavailable_tool(server_name: str):
    """Factory to create a tool stub that reports why it's missing."""
    async def _unavailable_stub(_args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": [{
                "type": "text",
                "text": _get_unavailable_msg(server_name),
            }]
        }
    return _unavailable_stub


# Default stubs
vision_server = {}
analyze_children_drawing = create_unavailable_tool("vision_analysis_server")

vector_server = {}
search_similar_drawings = create_unavailable_tool("vector_search_server")
store_drawing_embedding = create_unavailable_tool("vector_search_server")
store_story_embedding = create_unavailable_tool("vector_search_server")
search_similar_stories = create_unavailable_tool("vector_search_server")

safety_server = {}
check_content_safety = create_unavailable_tool("safety_check_server")
suggest_content_improvements = create_unavailable_tool("safety_check_server")

tts_server = {}
generate_story_audio = create_unavailable_tool("tts_generator_server")
list_available_voices = create_unavailable_tool("tts_generator_server")
generate_audio_batch = create_unavailable_tool("tts_generator_server")

video_server = {}
generate_painting_video = create_unavailable_tool("video_generator_server")
check_video_status = create_unavailable_tool("video_generator_server")
combine_video_audio = create_unavailable_tool("video_generator_server")

image_style_server = {}
transform_art_style = create_unavailable_tool("image_style_server")

web_search_server = {}
get_headlines_by_topic = create_unavailable_tool("web_search_server")
fetch_article_text = create_unavailable_tool("web_search_server")

# Import attempts
try:
    from .vision_analysis_server import vision_server, analyze_children_drawing
    MCP_SERVER_STATUS["vision_analysis_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["vision_analysis_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'vision_analysis_server': %s", exc, exc_info=True)

try:
    from .vector_search_server import (
        vector_server,
        search_similar_drawings,
        store_drawing_embedding,
        store_story_embedding,
        search_similar_stories
    )
    MCP_SERVER_STATUS["vector_search_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["vector_search_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'vector_search_server': %s", exc, exc_info=True)

try:
    from .safety_check_server import safety_server, check_content_safety, suggest_content_improvements
    MCP_SERVER_STATUS["safety_check_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["safety_check_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'safety_check_server': %s", exc, exc_info=True)

try:
    from .tts_generator_server import tts_server, generate_story_audio, list_available_voices, generate_audio_batch
    MCP_SERVER_STATUS["tts_generator_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["tts_generator_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'tts_generator_server': %s", exc, exc_info=True)

try:
    from .video_generator_server import (
        video_server,
        generate_painting_video,
        check_video_status,
        combine_video_audio,
    )
    MCP_SERVER_STATUS["video_generator_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["video_generator_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'video_generator_server': %s", exc, exc_info=True)

try:
    from .image_style_server import image_style_server, transform_art_style
    MCP_SERVER_STATUS["image_style_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["image_style_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'image_style_server': %s", exc, exc_info=True)

try:
    from .web_search_server import (
        web_search_server,
        get_headlines_by_topic,
        fetch_article_text,
    )
    MCP_SERVER_STATUS["web_search_server"] = "ok"
except Exception as exc:
    MCP_SERVER_STATUS["web_search_server"] = f"error: {exc}"
    logger.error("❌ Failed to import MCP server 'web_search_server': %s", exc, exc_info=True)


__all__ = [
    "MCP_SERVER_STATUS",
    "vision_server",
    "analyze_children_drawing",
    "vector_server",
    "search_similar_drawings",
    "store_drawing_embedding",
    "store_story_embedding",
    "search_similar_stories",
    "safety_server",
    "check_content_safety",
    "suggest_content_improvements",
    "tts_server",
    "generate_story_audio",
    "list_available_voices",
    "generate_audio_batch",
    "video_server",
    "generate_painting_video",
    "check_video_status",
    "combine_video_audio",
    "image_style_server",
    "transform_art_style",
    "web_search_server",
    "get_headlines_by_topic",
    "fetch_article_text",
]
