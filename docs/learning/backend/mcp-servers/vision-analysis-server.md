# Vision Analysis MCP Server

**Source**: `backend/src/mcp_servers/vision_analysis_server.py`

## What This File Does

**Explorer**: This helper looks at a child's drawing and describes what it sees — colors, shapes, characters, and the story it might tell. It's like a friend who looks at your picture and says "I see a purple dragon flying over a castle!"

**Maker**: This MCP server wraps the Claude Vision API to analyze uploaded images. It handles image resizing (to fit the API's base64 limit), encodes images, sends them with an age-adapted analysis prompt, and returns structured JSON describing the drawing's elements, emotions, and story potential.

## How It Works

1. **Image arrives** as a file path on disk (saved by the upload route)
2. **Size check**: `_ensure_image_fits()` checks if the raw bytes exceed 3.5 MB (Claude Vision's base64 limit after 33% inflation)
   - If too large: progressively re-encodes as JPEG at lower quality (85→75→65→55)
   - If still too large: scales down (90%→80%→70%→60%→50%)
   - Uses Pillow (PIL) for image processing
3. **Base64 encoding**: Converts the (possibly resized) image to a base64 string with proper media type
4. **API call**: Sends to Claude Vision with a prompt asking to identify:
   - Main subjects and characters
   - Colors and art style
   - Emotional tone
   - Story elements and narrative potential
5. **Response parsing**: Extracts structured data (JSON) from Claude's response for the story agent to use

## Key Concepts

**Base64 Encoding**: A way to represent binary data (like images) as text characters. Needed because the API accepts JSON, not raw image bytes. Trade-off: increases size by ~33%.

**Progressive Resize Strategy**: Instead of resizing to one fixed size, the server tries smaller changes first (lower JPEG quality), then bigger changes (scale down) only if needed. This preserves as much image detail as possible while staying under the API limit.

**Media Type**: The format identifier (e.g., `image/jpeg`, `image/png`) that tells the API how to decode the image data.

## Connections

- **Upstream**: Called by `image_to_story_agent.py` as the first step in story generation
- **Downstream**: Uses `anthropic.AsyncAnthropic` for the Vision API call
- **Config**: Model selection via `utils/model_config.py` → `get_vision_model()`
- **Dependencies**: `Pillow` (PIL) for image resizing — gracefully degrades if not installed

## Thinking Question

The progressive resize strategy tries quality reduction before scale reduction. Why this order? Think about what a child's drawing looks like — simple shapes with bold colors. Would JPEG compression artifacts (quality reduction) or resolution loss (scale reduction) hurt the AI's understanding more?
