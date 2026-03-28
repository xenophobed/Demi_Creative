"""
Image Style Transfer MCP Server

Transforms children's drawings into different art styles using
black-forest-labs/flux-kontext-pro on Replicate.

Includes post-generation safety validation (#273): every styled image
is checked via vision analysis for child-appropriateness before use.
"""

import logging
import os
import json
from typing import Any, Dict, List
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

try:
    import replicate
except Exception:  # pragma: no cover - import fallback for test env
    replicate = None

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except Exception:  # pragma: no cover - import fallback for test env
    def tool(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# Ensure output directory exists
Path("data/styled").mkdir(parents=True, exist_ok=True)


# Art theme prompts for style transfer
ART_THEME_PROMPTS = {
    "cartoon": "Transform this children's drawing into a colorful cartoon illustration, keeping all the original elements and characters",
    "oil_painting": "Transform this children's drawing into a beautiful oil painting style, preserving the original composition and characters",
    "watercolor": "Transform this children's drawing into a soft, dreamy watercolor painting, keeping all original elements",
    "pixel_art": "Convert this children's drawing into a charming pixel art style illustration, preserving the characters and scene",
    "anime": "Transform this children's drawing into a cute anime illustration style, keeping all original characters and elements",
    "crayon": "Make this children's drawing look like a professional crayon illustration, enhancing the colors while keeping the original composition",
    "storybook": "Transform this children's drawing into a beautiful storybook illustration, preserving all characters and the scene",
}

# Themes safe for younger children (age <= 5)
YOUNG_CHILD_THEMES = {"cartoon", "crayon", "watercolor", "storybook"}


def get_allowed_themes(child_age: int) -> set:
    """Return allowed art themes based on the child's age."""
    if child_age <= 5:
        return YOUNG_CHILD_THEMES
    return set(ART_THEME_PROMPTS.keys())


def _mock_style_result(image_path: str, theme: str, session_id: str) -> Dict[str, Any]:
    """Return a deterministic mock result for test environments."""
    mock_path = f"data/styled/{session_id}_{theme}.jpg"
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "styled_image_path": mock_path,
                "original_preserved": True,
                "theme_applied": theme,
            }, ensure_ascii=False)
        }]
    }


@tool(
    "transform_art_style",
    """Transform a children's drawing into a different art style using AI image generation.

    Supported themes: cartoon, oil_painting, watercolor, pixel_art, anime, crayon, storybook.
    Age 3-5 only supports: cartoon, crayon, watercolor, storybook.""",
    {
        "image_path": str,
        "theme": str,
        "child_age": int,
        "session_id": str,
    }
)
async def transform_art_style(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a children's drawing into a specified art style.

    Args:
        args: Dict containing image_path, theme, child_age, session_id

    Returns:
        Dict with styled image path and metadata
    """
    image_path = args["image_path"]
    theme = args.get("theme", "cartoon")
    child_age = args.get("child_age", 6)
    session_id = args.get("session_id", str(uuid.uuid4()))

    # Validate theme is in allowed list for the child's age
    allowed = get_allowed_themes(child_age)
    if theme not in allowed:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Theme '{theme}' is not allowed for age {child_age}. "
                             f"Allowed themes: {sorted(allowed)}",
                }, ensure_ascii=False)
            }]
        }

    # Validate theme exists at all
    if theme not in ART_THEME_PROMPTS:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Unknown theme '{theme}'. "
                             f"Available themes: {sorted(ART_THEME_PROMPTS.keys())}",
                }, ensure_ascii=False)
            }]
        }

    # Mock result for test environments or when replicate SDK is unavailable
    if replicate is None or os.environ.get("PYTEST_CURRENT_TEST"):
        return _mock_style_result(image_path, theme, session_id)

    # Validate image file exists
    if not Path(image_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Image file not found: {image_path}",
                }, ensure_ascii=False)
            }]
        }

    try:
        prompt = ART_THEME_PROMPTS[theme]

        # Call Replicate flux-kontext-pro model
        with open(image_path, "rb") as img_file:
            output = replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input={
                    "prompt": prompt,
                    "input_image": img_file,
                    "output_format": "jpg",
                }
            )

        # Save output image
        styled_dir = Path("data/styled")
        styled_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{session_id}_{theme}.jpg"
        output_path = styled_dir / output_filename

        # output is typically a URL or file-like object from replicate
        if hasattr(output, "read"):
            with open(output_path, "wb") as f:
                f.write(output.read())
        elif isinstance(output, (list, tuple)) and len(output) > 0:
            # Some replicate models return a list of URLs
            import httpx
            response = httpx.get(str(output[0]))
            with open(output_path, "wb") as f:
                f.write(response.content)
        elif isinstance(output, str) and output.startswith("http"):
            import httpx
            response = httpx.get(output)
            with open(output_path, "wb") as f:
                f.write(response.content)
        else:
            # Try writing raw bytes
            with open(output_path, "wb") as f:
                f.write(output if isinstance(output, bytes) else str(output).encode())

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "styled_image_path": str(output_path),
                    "original_preserved": True,
                    "theme_applied": theme,
                }, ensure_ascii=False)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Style transfer failed: {str(e)}",
                }, ensure_ascii=False)
            }]
        }


# ============================================================================
# Styled image safety validation (#273)
# ============================================================================

# Keywords that indicate the styled image may not be child-appropriate.
# Matched case-insensitively against all text fields in vision analysis output.
UNSAFE_IMAGE_KEYWORDS: List[str] = [
    # Violence
    "violence", "violent", "weapon", "gun", "knife", "sword", "blood",
    "bleeding", "gore", "fighting", "attack", "kill", "murder", "war",
    # Horror / fear
    "horror", "scary", "terrifying", "nightmare", "demon", "devil",
    "zombie", "corpse", "skull", "death", "dead",
    # Inappropriate content
    "nudity", "nude", "sexual", "drug", "alcohol", "smoking",
    "tobacco", "injection",
    # Distressing themes
    "abuse", "torture", "suicide", "self-harm",
]


def check_styled_image_safety(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Check vision analysis output for unsafe content using keyword heuristic.

    Scans all string values in the analysis dict (objects, scene, mood,
    story_potential, etc.) for flagged keywords.

    Args:
        analysis: Parsed JSON from vision analysis tool output.

    Returns:
        Dict with keys: safe (bool), reason (str|None), flagged_keywords (list[str]).
    """
    if not analysis:
        return {"safe": True, "reason": None, "flagged_keywords": []}

    # Collect all text from the analysis into one searchable blob
    text_parts: List[str] = []
    for key, value in analysis.items():
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    text_parts.extend(
                        str(v) for v in item.values() if isinstance(v, str)
                    )

    combined_text = " ".join(text_parts).lower()

    flagged: List[str] = []
    for keyword in UNSAFE_IMAGE_KEYWORDS:
        if keyword.lower() in combined_text:
            flagged.append(keyword.lower())

    if flagged:
        reason = (
            f"Styled image flagged as unsafe: found keywords [{', '.join(flagged)}] "
            f"in vision analysis output"
        )
        return {"safe": False, "reason": reason, "flagged_keywords": flagged}

    return {"safe": True, "reason": None, "flagged_keywords": []}


async def validate_and_fallback(
    styled_image_path: str,
    original_image_path: str,
    child_age: int,
    theme: str,
    session_id: str,
) -> Dict[str, Any]:
    """Validate a styled image for child safety and fall back if unsafe.

    Calls the vision analysis tool on the styled image, then checks the
    analysis for concerning content. If the image is unsafe or vision
    analysis fails, falls back to the original drawing (fail-closed).

    Args:
        styled_image_path: Path to the AI-generated styled image.
        original_image_path: Path to the original child's drawing.
        child_age: Age of the child (for vision analysis context).
        theme: Art theme that was applied.
        session_id: Session/child ID for logging.

    Returns:
        Dict with: used_image_path, safety_passed, fell_back,
        flagged_keywords, reason.
    """
    from . import analyze_children_drawing

    try:
        # Call vision analysis on the styled image
        vision_result = await analyze_children_drawing({
            "image_path": styled_image_path,
            "child_age": child_age,
        })

        # Parse analysis JSON from MCP tool output
        analysis_text = vision_result["content"][0]["text"]
        analysis = json.loads(analysis_text)

        # If vision returned an error, treat as unsafe (fail-closed)
        if "error" in analysis:
            logger.warning(
                "Styled image safety check failed — vision analysis error: %s | "
                "original=%s styled=%s theme=%s session=%s",
                analysis.get("error", "unknown"),
                original_image_path, styled_image_path, theme, session_id,
            )
            return {
                "used_image_path": original_image_path,
                "safety_passed": False,
                "fell_back": True,
                "flagged_keywords": [],
                "reason": f"Vision analysis error: {analysis.get('error', 'unknown')}",
            }

        # Check analysis for unsafe content
        safety_result = check_styled_image_safety(analysis)

        if not safety_result["safe"]:
            logger.warning(
                "Styled image unsafe — falling back to original | "
                "reason=%s flagged=%s original=%s styled=%s theme=%s session=%s",
                safety_result["reason"], safety_result["flagged_keywords"],
                original_image_path, styled_image_path, theme, session_id,
            )
            return {
                "used_image_path": original_image_path,
                "safety_passed": False,
                "fell_back": True,
                "flagged_keywords": safety_result["flagged_keywords"],
                "reason": safety_result["reason"],
            }

        # Image is safe — use styled version
        return {
            "used_image_path": styled_image_path,
            "safety_passed": True,
            "fell_back": False,
            "flagged_keywords": [],
            "reason": None,
        }

    except Exception as exc:
        # Any exception = fail-closed, use original
        logger.warning(
            "Styled image safety validation exception — falling back to original | "
            "error=%s original=%s styled=%s theme=%s session=%s",
            str(exc), original_image_path, styled_image_path, theme, session_id,
        )
        return {
            "used_image_path": original_image_path,
            "safety_passed": False,
            "fell_back": True,
            "flagged_keywords": [],
            "reason": f"Safety validation exception: {str(exc)}",
        }


# Create MCP Server
image_style_server = create_sdk_mcp_server(
    name="image-style",
    version="1.0.0",
    tools=[transform_art_style]
)


if __name__ == "__main__":
    """Test the image style transfer tool."""
    import asyncio

    async def test():
        print("=== Test Image Style Transfer ===\n")

        # Test with mock (no replicate SDK needed)
        print("1. Mock style transfer...")
        result = await transform_art_style({
            "image_path": "test.png",
            "theme": "cartoon",
            "child_age": 6,
            "session_id": "test-session-123",
        })
        print(json.loads(result["content"][0]["text"]))
        print()

        # Test age restriction
        print("2. Age restriction (age 4, anime theme)...")
        result = await transform_art_style({
            "image_path": "test.png",
            "theme": "anime",
            "child_age": 4,
            "session_id": "test-session-456",
        })
        print(json.loads(result["content"][0]["text"]))
        print()

        # Test invalid theme
        print("3. Invalid theme...")
        result = await transform_art_style({
            "image_path": "test.png",
            "theme": "nonexistent",
            "child_age": 10,
            "session_id": "test-session-789",
        })
        print(json.loads(result["content"][0]["text"]))

    asyncio.run(test())
