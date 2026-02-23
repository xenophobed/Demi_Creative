"""
Audio Strategy Utility

Age-based audio generation strategy for children's stories.
Determines when and how to generate audio based on child's age group.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AudioMode(str, Enum):
    """Audio generation mode based on age group"""
    AUDIO_FIRST = "audio_first"      # 3-5 years: Audio primary, text optional
    SIMULTANEOUS = "simultaneous"    # 6-9 years: Both audio and text together
    TEXT_FIRST = "text_first"        # 10-12 years: Text primary, audio on-demand


@dataclass
class AudioStrategy:
    """Audio strategy configuration for an age group"""
    mode: AudioMode
    auto_generate_audio: bool
    default_voice: str
    default_speed: float
    primary_mode: str  # "audio" | "text" | "both"
    optional_content_available: bool
    optional_content_type: Optional[str]  # "text" | "audio" | None


# Age-based audio strategies
_AUDIO_STRATEGIES = {
    "3-5": AudioStrategy(
        mode=AudioMode.AUDIO_FIRST,
        auto_generate_audio=True,
        default_voice="nova",  # Warm, gentle voice for young children
        default_speed=0.9,     # Slightly slower for comprehension
        primary_mode="audio",
        optional_content_available=True,
        optional_content_type="text"  # "Show Text" button
    ),
    "6-8": AudioStrategy(
        mode=AudioMode.SIMULTANEOUS,
        auto_generate_audio=True,
        default_voice="shimmer",  # Lively voice for this age group
        default_speed=1.0,
        primary_mode="both",
        optional_content_available=False,
        optional_content_type=None
    ),
    "6-9": AudioStrategy(
        mode=AudioMode.SIMULTANEOUS,
        auto_generate_audio=True,
        default_voice="shimmer",  # Lively voice for this age group
        default_speed=1.0,
        primary_mode="both",
        optional_content_available=False,
        optional_content_type=None
    ),
    "10-12": AudioStrategy(
        mode=AudioMode.TEXT_FIRST,
        auto_generate_audio=False,  # Audio is on-demand
        default_voice="alloy",  # More mature voice
        default_speed=1.1,  # Slightly faster for older children
        primary_mode="text",
        optional_content_available=True,
        optional_content_type="audio"  # "Play Audio" button
    )
}


def get_audio_strategy(age_group: str) -> AudioStrategy:
    """
    Get the audio strategy for a given age group.

    Args:
        age_group: Age group string ("3-5", "6-9", "10-12")

    Returns:
        AudioStrategy for the age group
    """
    return _AUDIO_STRATEGIES.get(age_group, _AUDIO_STRATEGIES["6-9"])


def should_auto_generate_audio(age_group: str, enable_audio: bool = True) -> bool:
    """
    Determine if audio should be auto-generated for the given age group.

    Args:
        age_group: Age group string
        enable_audio: Whether audio is enabled for the session

    Returns:
        True if audio should be auto-generated
    """
    if not enable_audio:
        return False

    strategy = get_audio_strategy(age_group)
    return strategy.auto_generate_audio


def get_default_voice_for_age(age_group: str) -> str:
    """
    Get the default voice type for an age group.

    Args:
        age_group: Age group string

    Returns:
        Default voice name
    """
    strategy = get_audio_strategy(age_group)
    return strategy.default_voice


def get_default_speed_for_age(age_group: str) -> float:
    """
    Get the default speech speed for an age group.

    Args:
        age_group: Age group string

    Returns:
        Default speech speed (1.0 = normal)
    """
    strategy = get_audio_strategy(age_group)
    return strategy.default_speed


def get_segment_display_config(age_group: str) -> dict:
    """
    Get the display configuration for story segments based on age.

    Args:
        age_group: Age group string

    Returns:
        Dict with primary_mode, optional_content_available, optional_content_type
    """
    strategy = get_audio_strategy(age_group)
    return {
        "primary_mode": strategy.primary_mode,
        "optional_content_available": strategy.optional_content_available,
        "optional_content_type": strategy.optional_content_type
    }
