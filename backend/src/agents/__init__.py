"""
Agents Package

Contains all Claude Agent SDK agents for the Creative Agent project.
"""

from .image_to_story_agent import image_to_story, stream_image_to_story, StoryOutput
from .interactive_story_agent import (
    generate_story_opening,
    generate_next_segment,
    AGE_CONFIG,
    StoryOpeningOutput,
    NextSegmentOutput
)

__all__ = [
    # Image to Story Agent
    "image_to_story",
    "stream_image_to_story",
    "StoryOutput",
    # Interactive Story Agent
    "generate_story_opening",
    "generate_next_segment",
    "AGE_CONFIG",
    "StoryOpeningOutput",
    "NextSegmentOutput",
]
