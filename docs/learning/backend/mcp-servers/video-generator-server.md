# Video Generator MCP Server

**Source**: `backend/src/mcp_servers/video_generator_server.py`

## What This File Does

**Explorer**: This helper turns a story into a short video — like a cartoon made from the child's own drawing. It takes the story text and images and puts them together into a moving picture.

**Maker**: This MCP server animates a child's drawing into a short clip using a **Replicate image-to-video model** (default `wan-video/wan-2.2-i2v-fast` @ 480p — overridable via the `VIDEO_MODEL` / `VIDEO_RESOLUTION` env vars). It exposes three tools: `generate_painting_video` (render), `check_video_status` (poll a job), and `combine_video_audio` (mux narration over the clip with ffmpeg).

## How It Works

1. **Agent/route calls `generate_painting_video`** with the drawing's `image_path`, a `style`, and `duration_seconds`
2. **Server renders the clip** — the painting is uploaded as the conditioning frame with a per-style motion prompt; a generous client timeout (`VIDEO_RENDER_TIMEOUT_S`, default 300s) covers slow renders
3. **MP4 downloaded** to `data/videos/`, with a job record written to `data/video_jobs/`
4. **Fail-fast (#182)** — if the render fails there is no phantom "pending" job; the tool returns `status: "failed"` immediately

## Key Concepts

**Dynamic Picture Book**: A video format where illustrated scenes transition smoothly, with narration playing over them — like a digital flip book. The child's original drawing style influences the visual output.

**Provider — cheapest-everywhere policy**: video runs on Replicate's fast WAN image-to-video model. It previously used OpenAI Sora, which was swapped out for a model that is both **cheaper and faster** (Sora was the most expensive, slowest path). The exact model and resolution are env-configurable, so quality can be dialed up per deployment without a code change.

## Connections

- **Upstream**: Called from `api/routes/video.py` (`POST /api/v1/video/generate`), which resolves the story's drawing and verifies ownership first
- **Downstream**: Replicate image-to-video model (`VIDEO_MODEL`, default `wan-video/wan-2.2-i2v-fast`); `ffmpeg` for optional audio muxing. Requires `REPLICATE_API_TOKEN`
- **Related**: `api/routes/video.py` provides the HTTP endpoint; see [environment-variables.md](../../infrastructure/environment-variables.md) → Model & Cost Controls

## Thinking Question

Video generation is much more expensive and slower than text or audio generation (minutes vs seconds). How would you design the user experience so children aren't frustrated waiting? Think about: async processing, progress notifications, preview images, and queue management.
