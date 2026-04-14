# Video Generator MCP Server

**Source**: `backend/src/mcp_servers/video_generator_server.py`

## What This File Does

**Explorer**: This helper turns a story into a short video — like a cartoon made from the child's own drawing. It takes the story text and images and puts them together into a moving picture.

**Maker**: This MCP server wraps video generation APIs to create "dynamic picture book" videos from story content. It's a Phase 3 feature — the server structure exists but the full pipeline (multi-frame generation, transitions, soundtrack overlay) is still being developed.

## How It Works

1. **Agent calls `generate_story_video`** with story text, scene descriptions, and style parameters
2. **Server generates video frames** using AI image/video generation APIs
3. **Frames are composited** into a video with transitions and optional audio narration
4. **Video saved** to `data/video/` and path returned to the agent

## Key Concepts

**Dynamic Picture Book**: A video format where illustrated scenes transition smoothly, with narration playing over them — like a digital flip book. The child's original drawing style influences the visual output.

**Phase 3 Feature**: This server is part of the project's third development phase. The architecture is in place, but full production implementation depends on video generation API maturity and cost optimization.

## Connections

- **Upstream**: Would be called by `image_to_story_agent.py` as an optional post-story enhancement
- **Downstream**: Video generation APIs (provider TBD)
- **Related**: `api/routes/video.py` provides the HTTP endpoint for video requests

## Thinking Question

Video generation is much more expensive and slower than text or audio generation (minutes vs seconds). How would you design the user experience so children aren't frustrated waiting? Think about: async processing, progress notifications, preview images, and queue management.
