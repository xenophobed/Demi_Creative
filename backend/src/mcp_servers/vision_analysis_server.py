"""
Vision Analysis MCP Server

Provides tools for analyzing children's drawings using Claude Vision API.
Includes automatic image resizing to prevent base64 payload overflow.
"""

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from ..utils.model_config import get_vision_model

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None

logger = logging.getLogger(__name__)

import anyio

try:
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover - import fallback for test env
    AsyncAnthropic = None

try:
    from claude_agent_sdk import create_sdk_mcp_server, tool
except Exception:  # pragma: no cover - import fallback for test env

    def tool(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# ============================================================================
# Image size safety: auto-resize before base64 encoding
# ============================================================================

# Claude Vision API accepts at most ~5 MB of base64 image data.
# base64 inflates raw bytes by ~33%, so we cap raw bytes at 3.5 MB.
_MAX_RAW_BYTES = 3_500_000

# Progressive quality steps for JPEG re-encoding
_QUALITY_STEPS = [85, 75, 65, 55]
# Progressive scale factors when quality alone isn't enough
_SCALE_STEPS = [0.90, 0.80, 0.70, 0.60, 0.50]


def _ensure_image_fits(
    raw_bytes: bytes,
    media_type: str,
) -> Tuple[bytes, str, bool]:
    """Ensure *raw_bytes* will fit under the Claude Vision base64 limit.

    Returns (possibly_resized_bytes, media_type, was_resized).
    The returned media_type may change to image/jpeg after re-encoding.
    """
    if len(raw_bytes) <= _MAX_RAW_BYTES:
        return raw_bytes, media_type, False

    if PILImage is None:
        logger.warning(
            "Image is %.2f MB but Pillow is not installed; "
            "sending as-is (may exceed API limit)",
            len(raw_bytes) / 1_000_000,
        )
        return raw_bytes, media_type, False

    logger.info(
        "Image is %.2f MB (> %.2f MB limit), auto-resizing…",
        len(raw_bytes) / 1_000_000,
        _MAX_RAW_BYTES / 1_000_000,
    )

    img = PILImage.open(io.BytesIO(raw_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Phase 1: reduce JPEG quality at original dimensions
    for quality in _QUALITY_STEPS:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= _MAX_RAW_BYTES:
            logger.info(
                "Resized to %.2f MB at quality=%d (original dims)",
                buf.tell() / 1_000_000,
                quality,
            )
            return buf.getvalue(), "image/jpeg", True

    # Phase 2: progressively scale down dimensions
    orig_w, orig_h = img.size
    for scale in _SCALE_STEPS:
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = img.resize((new_w, new_h), PILImage.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=75, optimize=True)
        if buf.tell() <= _MAX_RAW_BYTES:
            logger.info(
                "Resized to %.2f MB at %dx%d (scale=%.0f%%)",
                buf.tell() / 1_000_000,
                new_w,
                new_h,
                scale * 100,
            )
            return buf.getvalue(), "image/jpeg", True

    # Last resort: return the smallest version we produced
    logger.warning(
        "Could not reduce image below %.2f MB; sending smallest attempt",
        buf.tell() / 1_000_000,
    )
    return buf.getvalue(), "image/jpeg", True


def _parse_vision_json_response(response_text: str) -> Dict[str, Any]:
    """Parse Claude Vision JSON even when wrapped in markdown or prose."""
    text = response_text.strip()

    # Prefer fenced code blocks when present. Claude sometimes emits
    # ```json ... ``` and sometimes a plain fence without a language.
    for marker in ("```json", "```"):
        if marker in text:
            json_start = text.find(marker) + len(marker)
            json_end = text.find("```", json_start)
            if json_end != -1:
                fenced = text[json_start:json_end].strip()
                return json.loads(fenced)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: scan for the first valid JSON object embedded in prose.
    # This covers responses like "Here is the analysis: { ... }".
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise json.JSONDecodeError("No JSON object found", response_text, 0)


@tool(
    "analyze_children_drawing",
    """Analyze a children's drawing, identifying objects, scenes, emotions, and colors.

    This tool will:
    1. Identify objects in the drawing (animals, people, plants, items, etc.)
    2. Determine the overall scene (indoor/outdoor, specific location)
    3. Analyze the emotional atmosphere (happy, sad, calm, etc.)
    4. Identify primary colors
    5. Detect recurring characters

    Returns structured analysis results.""",
    {"image_path": str, "child_age": int},
)
async def analyze_children_drawing(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a children's drawing using Claude Vision API.

    Args:
        args: Dictionary containing image_path and child_age

    Returns:
        Dictionary containing analysis results
    """
    image_path = args["image_path"]
    child_age = args["child_age"]

    # Read image file
    if not Path(image_path).exists():
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": f"Image file not found: {image_path}"}, ensure_ascii=False
                    ),
                }
            ]
        }

    # Read image and convert to base64 (non-blocking)
    raw_bytes = await anyio.Path(image_path).read_bytes()

    # Determine image format
    file_extension = Path(image_path).suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(file_extension, "image/jpeg")

    # Auto-resize if the image would exceed Claude Vision API limits
    raw_bytes, media_type, was_resized = _ensure_image_fits(raw_bytes, media_type)
    if was_resized:
        logger.info("Image auto-resized for Vision API: %s", image_path)

    image_data = base64.standard_b64encode(raw_bytes).decode("utf-8")

    # Call Claude Vision API
    if AsyncAnthropic is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": "Anthropic SDK is unavailable in current environment",
                            "objects": [],
                            "scene": "unknown",
                            "mood": "unknown",
                            "confidence_score": 0.0,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Adjust analysis prompt based on age
    age_context = ""
    if child_age <= 5:
        age_context = "This is a drawing by a 3-5 year old preschooler. Focus on identifying simple shapes and bright colors."
    elif child_age <= 8:
        age_context = "This is a drawing by a 6-8 year old early elementary student. It may have more detail and narrative elements."
    else:
        age_context = (
            "This is a drawing by a 9-12 year old upper elementary student. It may contain complex scenes and abstract concepts."
        )

    prompt = f"""Please carefully analyze this children's drawing. {age_context}

Please return the analysis results in the following JSON format:

{{
  "objects": ["All identified objects, e.g.: dog, tree, sun, house"],
  "scene": "Scene description, e.g.: outdoor park, indoor room, beach",
  "mood": "Overall emotional atmosphere, e.g.: happy, calm, excited, sad",
  "colors": ["Primary colors, e.g.: red, blue, yellow"],
  "recurring_characters": [
    {{
      "name": "Character name (if labeled in the drawing)",
      "description": "Character feature description, e.g.: a dog wearing a blue shirt",
      "visual_features": ["Key visual features, e.g.: pointed ears, long tail, red collar"]
    }}
  ],
  "story_potential": "Potential story clues from this drawing",
  "confidence_score": 0.95
}}

Notes:
1. objects should list all identified elements as comprehensively as possible
2. recurring_characters is for identifying characters that may appear repeatedly (if they have distinctive features)
3. confidence_score represents analysis confidence (0.0-1.0)
4. Maintain a child-friendly language style

Always respond in English."""

    try:
        with anyio.fail_after(60):
            response = await client.messages.create(
                model=get_vision_model(),
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

        # Extract response text
        response_text = response.content[0].text

        # Try to parse JSON
        try:
            result = _parse_vision_json_response(response_text)

            # Validate required fields
            required_fields = ["objects", "scene", "mood", "confidence_score"]
            for field in required_fields:
                if field not in result:
                    result[field] = (
                        []
                        if field == "objects"
                        else "unknown"
                        if field != "confidence_score"
                        else 0.5
                    )

            # Ensure recurring_characters exists
            if "recurring_characters" not in result:
                result["recurring_characters"] = []

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ]
            }

        except json.JSONDecodeError:
            # If the model gives a descriptive prose answer instead of JSON,
            # keep the feature usable. The story generator can still consume
            # the raw description as low-confidence drawing analysis.
            logger.warning(
                "Vision API response was not JSON; using raw text fallback: %s",
                response_text[:500],
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "raw_response": response_text,
                                "vision_analysis": response_text,
                                "objects": [],
                                "scene": "unknown",
                                "mood": "unknown",
                                "colors": [],
                                "recurring_characters": [],
                                "story_potential": response_text,
                                "confidence_score": 0.0,
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Vision API call failed: {str(e)}",
                            "objects": [],
                            "scene": "unknown",
                            "mood": "unknown",
                            "confidence_score": 0.0,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }


# Create MCP Server
vision_server = create_sdk_mcp_server(
    name="vision-analysis", version="1.0.0", tools=[analyze_children_drawing]
)


if __name__ == "__main__":
    """Test tools"""
    import asyncio

    async def test():
        # Test example
        result = await analyze_children_drawing(
            {"image_path": "test_image.jpg", "child_age": 7}
        )
        print(
            json.dumps(
                json.loads(result["content"][0]["text"]), indent=2, ensure_ascii=False
            )
        )

    asyncio.run(test())
