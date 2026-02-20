"""
TTS Generation MCP Server

Provides tools for generating audio narration using OpenAI TTS API.
"""

import json
from typing import Any, Dict, Optional

from claude_agent_sdk import tool, create_sdk_mcp_server
from ..services.tts_service import generate_story_audio_file


# Available voice options
AVAILABLE_VOICES = {
    "alloy": "Neutral and gentle voice, suitable for all ages",
    "echo": "Male voice, clear and friendly",
    "fable": "British accent, great for storytelling",
    "onyx": "Deep male voice",
    "nova": "Soft female voice, suitable for young children",
    "shimmer": "Lively female voice"
}


@tool(
    "generate_story_audio",
    """Convert story text into a speech audio file.

    This tool is used to:
    1. Convert written stories into spoken narration
    2. Support multiple voice options
    3. Adapt to children of different age groups
    4. Generate MP3 format audio files

    Returns the audio file path.""",
    {"story_text": str, "voice": str, "speed": float, "child_age": int}
)
async def generate_story_audio(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate story audio.

    Args:
        args: Dictionary containing story_text, voice, speed

    Returns:
        Dictionary containing the audio file path
    """
    story_text = args["story_text"]
    voice = args.get("voice", "nova")
    speed = args.get("speed")
    child_age = args.get("child_age")

    result = await generate_story_audio_file(
        text=story_text,
        voice=voice,
        speed=speed,
        child_age=child_age,
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "list_available_voices",
    """List all available TTS voice options.

    Returns a list of voices with descriptions to help choose the right one.""",
    {}
)
async def list_available_voices(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List available voice options.

    Args:
        args: Empty dictionary

    Returns:
        List of voices
    """
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "voices": [
                    {
                        "id": voice_id,
                        "description": description,
                        "recommended_for": _get_recommendation(voice_id)
                    }
                    for voice_id, description in AVAILABLE_VOICES.items()
                ]
            }, ensure_ascii=False, indent=2)
        }]
    }


def _get_recommendation(voice_id: str) -> str:
    """Get voice recommendation."""
    recommendations = {
        "nova": "Ages 3-6, bedtime stories",
        "shimmer": "Ages 6-9, lively stories",
        "alloy": "All age groups",
        "echo": "Ages 9-12, adventure stories",
        "fable": "Traditional fairy tales",
        "onyx": "Ages 9-12, educational content"
    }
    return recommendations.get(voice_id, "General purpose")


@tool(
    "generate_audio_batch",
    """Batch generate multiple audio files.

    Used for interactive story segments, generating all audio at once.

    Note: Batch generation may take a while; it is recommended to keep segments under 10.""",
    {"story_segments": list, "voice": str, "speed": float}
)
async def generate_audio_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Batch generate audio files.

    Args:
        args: Dictionary containing story_segments, voice, speed

    Returns:
        Dictionary containing all audio file paths
    """
    story_segments = args["story_segments"]
    voice = args.get("voice", "nova")
    speed = args.get("speed", 1.0)

    results = []
    errors = []

    for segment in story_segments:
        segment_id = segment["segment_id"]
        text = segment["text"]

        try:
            result_data = await generate_story_audio_file(
                text=text,
                voice=voice,
                speed=speed,
            )
            if result_data.get("success"):
                results.append({
                    "segment_id": segment_id,
                    "audio_path": result_data["audio_path"],
                    "filename": result_data["filename"]
                })
            else:
                errors.append({
                    "segment_id": segment_id,
                    "error": result_data.get("error")
                })

        except Exception as e:
            errors.append({
                "segment_id": segment_id,
                "error": str(e)
            })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "total_segments": len(story_segments),
                "successful": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors if errors else None
            }, ensure_ascii=False, indent=2)
        }]
    }


# Create MCP Server
tts_server = create_sdk_mcp_server(
    name="tts-generation",
    version="1.0.0",
    tools=[generate_story_audio, list_available_voices, generate_audio_batch]
)
