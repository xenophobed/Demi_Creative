"""
MCP Servers Package

Contains all MCP (Model Context Protocol) servers providing tools for the Creative Agent.
"""

from .vision_analysis_server import vision_server, analyze_children_drawing
# from .vector_search_server import vector_server, search_similar_drawings, store_drawing_embedding  # 需要 chromadb
from .safety_check_server import safety_server, check_content_safety, suggest_content_improvements
from .tts_generator_server import tts_server, generate_story_audio, list_available_voices, generate_audio_batch

# 临时禁用 vector_server（需要 chromadb）
vector_server = None
search_similar_drawings = None
store_drawing_embedding = None

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
]
