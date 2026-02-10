"""
Utils Package

Utility functions for the Creative Agent.
"""

from .audio_strategy import (
    AudioMode,
    AudioStrategy,
    get_audio_strategy,
    should_auto_generate_audio,
    get_default_voice_for_age,
    get_default_speed_for_age,
)

__all__ = [
    "AudioMode",
    "AudioStrategy",
    "get_audio_strategy",
    "should_auto_generate_audio",
    "get_default_voice_for_age",
    "get_default_speed_for_age",
]
