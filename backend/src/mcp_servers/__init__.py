"""MCP server exports with dependency-safe fallbacks."""

from typing import Any, Dict


async def _unavailable_tool(_args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": [{
            "type": "text",
            "text": "{\"error\": \"MCP server dependency unavailable\"}",
        }]
    }


vision_server = {}
analyze_children_drawing = _unavailable_tool
vector_server = {}
search_similar_drawings = _unavailable_tool
store_drawing_embedding = _unavailable_tool
safety_server = {}
check_content_safety = _unavailable_tool
suggest_content_improvements = _unavailable_tool
tts_server = {}
generate_story_audio = _unavailable_tool
list_available_voices = _unavailable_tool
generate_audio_batch = _unavailable_tool
video_server = {}
generate_painting_video = _unavailable_tool
check_video_status = _unavailable_tool
combine_video_audio = _unavailable_tool

try:
    from .vision_analysis_server import vision_server, analyze_children_drawing
except Exception:
    pass

try:
    from .vector_search_server import vector_server, search_similar_drawings, store_drawing_embedding
except Exception:
    pass

try:
    from .safety_check_server import safety_server, check_content_safety, suggest_content_improvements
except Exception:
    pass

try:
    from .tts_generator_server import tts_server, generate_story_audio, list_available_voices, generate_audio_batch
except Exception:
    pass

try:
    from .video_generator_server import (
        video_server,
        generate_painting_video,
        check_video_status,
        combine_video_audio,
    )
except Exception:
    pass


__all__ = [
    "vision_server",
    "analyze_children_drawing",
    "vector_server",
    "search_similar_drawings",
    "store_drawing_embedding",
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
]
