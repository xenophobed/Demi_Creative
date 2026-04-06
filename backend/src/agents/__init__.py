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
from .kids_daily_agent import (
    generate_kids_daily_text,
    stream_kids_daily_text,
    generate_kids_daily_dialogue,
    generate_kids_daily_episode,
    stream_kids_daily_generation,
    pick_age_voice,
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
    # Kids Daily Agent
    "generate_kids_daily_text",
    "stream_kids_daily_text",
    "generate_kids_daily_dialogue",
    "generate_kids_daily_episode",
    "stream_kids_daily_generation",
    "pick_age_voice",
]
