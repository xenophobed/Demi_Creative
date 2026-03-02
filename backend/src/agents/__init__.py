"""
Agents Package

Contains all Claude Agent SDK agents for the Creative Agent project.
"""

from .image_to_story_agent import image_to_story, stream_image_to_story, StoryOutput
from .interactive_story_agent import (
    generate_story_opening,
    generate_story_opening_stream,
    generate_next_segment,
    generate_next_segment_stream,
    AGE_CONFIG,
    StoryOpeningOutput,
    NextSegmentOutput
)
from .news_to_kids_agent import convert_news_to_kids, stream_news_to_kids
from .morning_show_agent import (
    convert_news_to_morning_show,
    generate_morning_show_dialogue,
    stream_morning_show_generation,
)

__all__ = [
    # Image to Story Agent
    "image_to_story",
    "stream_image_to_story",
    "StoryOutput",
    # Interactive Story Agent
    "generate_story_opening",
    "generate_story_opening_stream",
    "generate_next_segment",
    "generate_next_segment_stream",
    "AGE_CONFIG",
    "StoryOpeningOutput",
    "NextSegmentOutput",
    # News to Kids Agent
    "convert_news_to_kids",
    "stream_news_to_kids",
    # Morning Show Agent
    "convert_news_to_morning_show",
    "generate_morning_show_dialogue",
    "stream_morning_show_generation",
]
