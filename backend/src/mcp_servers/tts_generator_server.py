"""
TTS Generation MCP Server

Provides tools for generating audio narration using OpenAI TTS API
and Replicate minimax/speech-02-turbo (#149).
"""

import json
from typing import Any, Dict, Optional

from claude_agent_sdk import tool, create_sdk_mcp_server
from ..services.tts_service import generate_story_audio_file


# Available voice options — OpenAI
OPENAI_VOICES = {
    "alloy": {"display_name": "Alloy", "description": "Neutral and gentle voice, suitable for all ages", "recommended_for": "All age groups"},
    "echo": {"display_name": "Echo", "description": "Male voice, clear and friendly", "recommended_for": "Ages 9-12, adventure stories"},
    "fable": {"display_name": "Fable", "description": "British accent, great for storytelling", "recommended_for": "Traditional fairy tales"},
    "onyx": {"display_name": "Onyx", "description": "Deep male voice", "recommended_for": "Ages 9-12, educational content"},
    "nova": {"display_name": "Nova", "description": "Soft female voice, suitable for young children", "recommended_for": "Ages 3-6, bedtime stories"},
    "shimmer": {"display_name": "Shimmer", "description": "Lively female voice", "recommended_for": "Ages 6-9, lively stories"},
}

# Available voice options — Replicate minimax/speech-02-turbo (#149)
MINIMAX_VOICES = {
    "Wise_Woman": {"display_name": "Wise Woman", "description": "Warm, wise female voice", "recommended_for": "Bedtime stories, educational"},
    "Friendly_Person": {"display_name": "Friendly Person", "description": "Approachable, gender-neutral", "recommended_for": "All age groups"},
    "Inspirational_girl": {"display_name": "Inspirational Girl", "description": "Energetic young female voice", "recommended_for": "Ages 6-9, adventure"},
    "Deep_Voice_Man": {"display_name": "Deep Voice Man", "description": "Deep, commanding male voice", "recommended_for": "Ages 9-12, narration"},
    "Calm_Woman": {"display_name": "Calm Woman", "description": "Soothing, calm female voice", "recommended_for": "Ages 3-6, bedtime"},
    "Casual_Guy": {"display_name": "Casual Guy", "description": "Relaxed, casual male voice", "recommended_for": "Ages 6-9, fun stories"},
    "Lively_Girl": {"display_name": "Lively Girl", "description": "Bright, energetic female voice", "recommended_for": "Ages 6-9, playful"},
    "Patient_Man": {"display_name": "Patient Man", "description": "Patient, gentle male voice", "recommended_for": "Ages 3-6, educational"},
    "Young_Knight": {"display_name": "Young Knight", "description": "Adventurous young male voice", "recommended_for": "Ages 9-12, adventure"},
    "Determined_Man": {"display_name": "Determined Man", "description": "Strong, decisive male voice", "recommended_for": "Ages 9-12, action"},
    "Lovely_Woman": {"display_name": "Lovely Woman", "description": "Sweet, pleasant female voice", "recommended_for": "All age groups"},
    "Decent_Boy": {"display_name": "Decent Boy", "description": "Polite young male voice", "recommended_for": "Ages 6-9"},
    "Imposing_Manner": {"display_name": "Imposing Manner", "description": "Authoritative voice", "recommended_for": "Narration, educational"},
    "Gentle_Woman": {"display_name": "Gentle Woman", "description": "Soft, gentle female voice", "recommended_for": "Ages 3-6, bedtime"},
    "Serious_Girl": {"display_name": "Serious Girl", "description": "Thoughtful female voice", "recommended_for": "Ages 9-12, educational"},
    "Warm_Woman": {"display_name": "Warm Woman", "description": "Warm, motherly female voice", "recommended_for": "Ages 3-6, bedtime"},
    "Sweet_Girl_2": {"display_name": "Sweet Girl", "description": "Sweet, cheerful female voice", "recommended_for": "Ages 6-9, playful"},
}

# Backward-compatible flat dict for legacy code
AVAILABLE_VOICES = {vid: meta["description"] for vid, meta in OPENAI_VOICES.items()}


@tool(
    "generate_story_audio",
    """Convert story text into a speech audio file.

    This tool is used to:
    1. Convert written stories into spoken narration
    2. Support multiple voice options from OpenAI and Replicate providers
    3. Adapt to children of different age groups
    4. Generate MP3 format audio files
    5. Optionally apply emotion, pitch, and volume controls (Replicate provider)

    Returns the audio file path.""",
    {"story_text": str, "voice": str, "speed": float, "child_age": int,
     "emotion": str, "pitch": int, "volume": float, "language_boost": str,
     "provider": str, "age_group": str}
)
async def generate_story_audio(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate story audio with optional expressive controls (#149)."""
    story_text = args["story_text"]
    voice = args.get("voice", "nova")
    speed = args.get("speed")
    child_age = args.get("child_age")

    # New optional expressive params (#149)
    emotion = args.get("emotion")
    pitch = args.get("pitch")
    volume = args.get("volume")
    language_boost = args.get("language_boost")
    provider = args.get("provider")
    age_group = args.get("age_group")

    result = await generate_story_audio_file(
        text=story_text,
        voice=voice,
        speed=speed,
        child_age=child_age,
        emotion=emotion,
        pitch=pitch,
        volume=volume,
        language_boost=language_boost,
        provider=provider,
        age_group=age_group,
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "list_available_voices",
    """List all available TTS voice options from all providers.

    Returns a merged catalog of OpenAI and Replicate minimax voices,
    each with provider, voice_id, display_name, and description.""",
    {}
)
async def list_available_voices(args: Dict[str, Any]) -> Dict[str, Any]:
    """List available voice options from all providers (#149)."""
    voices = []

    for voice_id, meta in OPENAI_VOICES.items():
        voices.append({
            "voice_id": voice_id,
            "provider": "openai",
            "display_name": meta["display_name"],
            "description": meta["description"],
            "recommended_for": meta["recommended_for"],
        })

    for voice_id, meta in MINIMAX_VOICES.items():
        voices.append({
            "voice_id": voice_id,
            "provider": "replicate",
            "display_name": meta["display_name"],
            "description": meta["description"],
            "recommended_for": meta["recommended_for"],
        })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({"voices": voices}, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "generate_audio_batch",
    """Batch generate multiple audio files.

    Used for interactive story segments, generating all audio at once.

    Note: Batch generation may take a while; it is recommended to keep segments under 10.""",
    {"story_segments": list, "voice": str, "speed": float,
     "emotion": str, "provider": str, "age_group": str}
)
async def generate_audio_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Batch generate audio files with optional expressive params (#149)."""
    story_segments = args["story_segments"]
    voice = args.get("voice", "nova")
    speed = args.get("speed", 1.0)

    # New optional params (#149)
    emotion = args.get("emotion")
    provider = args.get("provider")
    age_group = args.get("age_group")

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
                emotion=emotion,
                provider=provider,
                age_group=age_group,
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
