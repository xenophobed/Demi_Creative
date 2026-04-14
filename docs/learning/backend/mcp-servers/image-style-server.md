# Image Style MCP Server

**Source**: `backend/src/mcp_servers/image_style_server.py`

## What This File Does

**Explorer**: This helper is like a magic art filter. A child uploads their drawing, picks an art style (like "watercolor" or "cartoon"), and this helper transforms the drawing to look like it was painted in that style — while keeping the child's original shapes and characters.

**Maker**: This MCP server wraps AI image generation APIs to perform style transfer on children's drawings. It takes the original uploaded image plus a target art style, generates a stylized version using image-to-image models, and returns the new image path. The original drawing is preserved — the styled version is saved separately.

## How It Works

1. **Agent calls `apply_art_style`** with the original image path, target style (e.g., "watercolor", "pixel art", "oil painting"), and style intensity
2. **Server loads the original image** and prepares it as input for the style transfer model
3. **AI generates a styled version** that preserves the composition but applies the chosen artistic style
4. **Styled image saved** to `data/uploads/styled/` alongside the original
5. **Returns**: styled image path + metadata (style applied, original preserved)

### Available Art Styles

The frontend `art theme picker` presents these to children as visual swatches:
- Watercolor, Oil painting, Pixel art, Cartoon, Sketch, Crayon, Pop art, and more

## Key Concepts

**Style Transfer**: An AI technique that takes the "content" from one image (shapes, objects) and the "style" from another (brushstrokes, colors, texture) and combines them. Think of it as painting the same picture but in Van Gogh's style instead of crayon.

**Image-to-Image Generation**: Unlike text-to-image (creating from scratch), this takes an existing image as input and transforms it. The model sees the child's drawing and produces a variation in the target style.

**Non-Destructive**: The original drawing is never modified. The styled version is a new file. This is important because the child's original work has sentimental value.

## Connections

- **Upstream**: Called by `image_to_story_agent.py` when the user selects an art style during upload
- **Downstream**: AI image generation APIs for style transfer
- **Frontend**: `UploadPage` art theme picker → sends style selection with the upload request
- **Storage**: Styled images saved to `data/uploads/styled/`, URL stored in `stories.styled_image_url`

## Thinking Question

Style transfer can sometimes distort the original drawing so much that the child doesn't recognize their own work. How would you let the child preview the styled version before committing, and what would "undo" look like? Consider: generating a low-resolution preview first (cheaper/faster), then full-resolution only on confirmation.
