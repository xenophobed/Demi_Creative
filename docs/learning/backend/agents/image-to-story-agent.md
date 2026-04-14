# Image-to-Story Agent

**Source**: `backend/src/agents/image_to_story_agent.py`

## What This File Does

**Explorer**: This is the storyteller. A child uploads their drawing, and this agent looks at it, figures out what's in the picture (a dragon? a castle? a rainbow?), and writes a personalized story about it — complete with audio narration.

**Maker**: This agent orchestrates the full image-to-story pipeline using the Claude Agent SDK. It coordinates vision analysis, safety checking, story generation with age adaptation, length validation, and optional TTS audio — all through MCP tool calls and structured output parsing. Supports both streaming (SSE) and non-streaming modes.

## How It Works

### The Full Pipeline

```
1. Image Upload
   └─ Route saves file to data/uploads/

2. Vision Analysis (MCP tool)
   └─ mcp__vision-analysis__analyze_children_drawing
   └─ Returns: subjects, colors, emotions, story hooks

3. Story Generation (Claude Agent SDK)
   └─ Agent builds a prompt with:
       - Vision analysis results
       - Age group rules (word count, complexity)
       - Child's preference history (from memory)
       - Character continuity (recurring characters)
       - Deduplication check (avoid repeating past stories)
   └─ Claude generates: title, story text, characters

4. Length Validation (#233)
   └─ Checks word count against age-group ranges:
       3-5: 100-200 words | 6-8: 200-400 | 9-12: 400-800
   └─ If drastically off: retries generation (up to 1 retry)

5. Safety Check (MCP tool)
   └─ mcp__safety-check__check_content_safety
   └─ Must score >= 0.85 or content is rejected

6. TTS Audio (MCP tool, optional)
   └─ mcp__tts-generation__generate_story_audio
   └─ Generates MP3 narration with age-appropriate voice

7. Response
   └─ Returns: title, text, audio_url, characters, safety_score
```

### Streaming Mode

For better UX, the agent streams progress events via SSE:
- `status` — "Analyzing your drawing..."
- `thinking` — AI reasoning in real-time
- `tool_use` — "Checking content safety..."
- `result` — Final story data
- `complete` — Done

### Age Adaptation

| Age Group | Word Count | Complexity | Vocabulary | Theme Depth |
|-----------|-----------|------------|------------|-------------|
| 3-5 | 100-200 | Very simple | Basic everyday words | Simple, concrete, daily life |
| 6-8 | 200-400 | Simple | Elementary school | Fun adventures, simple moral choices |
| 9-12 | 400-800 | Moderate | Upper elementary | Complex plots, character growth |

## Key Concepts

**Agent Orchestration**: The agent doesn't just call one API — it coordinates multiple steps (vision → generate → validate → safety → audio) and makes decisions between them. If the story is too short, it retries. If safety fails, it requests improvements. This multi-step decision-making is what makes it an "agent" rather than a simple API wrapper.

**Structured Output**: The agent is instructed to return JSON matching a Pydantic schema (`StoryGenerationOutput`). This ensures the response always has the expected fields (title, text, characters) rather than free-form text.

**Mock Fallback**: When `ClaudeSDKClient is None` (test environments), the agent returns deterministic mock data. This lets tests run without API keys and verifies the pipeline logic independent of AI output.

## Connections

- **Upstream**: `api/routes/image_to_story.py` calls `generate_story()` or `generate_story_stream()`
- **MCP tools used**: vision-analysis, safety-check, tts-generation, vector-search
- **Services**: `story_memory.py` for deduplication, `tts_service.py` for audio
- **Prompts**: No separate prompt file — prompt is built inline with age adaptation rules
- **Database**: Stories saved via `story_repository.py`

## Thinking Question

The agent retries story generation if the word count is drastically off. But retries cost money (each Claude API call has a price). How would you design a "budget" system that limits retries per user per day? And what should happen when the budget is exhausted — show a shorter story, show a cached story, or show an error message?
