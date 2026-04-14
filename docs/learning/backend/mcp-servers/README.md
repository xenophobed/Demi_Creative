# MCP Tool Servers

## What Are MCP Servers?

**Explorer**: MCP servers are like helpers with special skills. The AI agent is the boss who decides what to do, and it asks these helpers to do specific jobs — one helper checks if a story is safe, another looks at drawings, another reads text aloud.

**Builder**: MCP (Model Context Protocol) servers are standalone tool providers that AI agents can call during generation. Each server exposes one or more tools via the `@tool` decorator. The agent discovers available tools and decides which ones to use based on the task.

**Maker**: MCP servers follow a plugin architecture where each server registers tools with a schema (name, description, parameter types). The Claude Agent SDK orchestrates tool calls — the agent sees tool descriptions in its context and emits structured `tool_use` requests. The SDK routes these to the matching MCP server, executes the function, and returns results to the agent for the next reasoning step.

## How Agents Use Tools

```
Agent receives task (e.g., "generate a story from this drawing")
  │
  ├─ Agent thinks: "I need to analyze the image first"
  │   └─ Calls: mcp__vision-analysis__analyze_children_drawing
  │
  ├─ Agent thinks: "Now I'll write the story"
  │   └─ (Agent generates text itself — no tool needed)
  │
  ├─ Agent thinks: "I must check if this is safe for kids"
  │   └─ Calls: mcp__safety-check__check_content_safety
  │
  └─ Agent thinks: "Time to create audio narration"
      └─ Calls: mcp__tts-generation__generate_story_audio
```

## Server Index

| Server | File | Tools | Purpose |
|--------|------|-------|---------|
| [Safety Check](./safety-check-server.md) | `safety_check_server.py` | `check_content_safety`, `suggest_content_improvements` | Content safety gate (mandatory) |
| [Vision Analysis](./vision-analysis-server.md) | `vision_analysis_server.py` | `analyze_children_drawing` | Understand uploaded drawings |
| [Vector Search](./vector-search-server.md) | `vector_search_server.py` | `store_drawing_embedding`, `search_similar_drawings` | Find similar past drawings |
| [TTS Generator](./tts-generator-server.md) | `tts_generator_server.py` | `generate_story_audio` | Text-to-speech narration |
| [Video Generator](./video-generator-server.md) | `video_generator_server.py` | `generate_story_video` | Dynamic picture book video |
| [Web Search](./web-search-server.md) | `web_search_server.py` | `search_kids_news` | Real-time news headlines |
| [Image Style](./image-style-server.md) | `image_style_server.py` | `apply_art_style` | Art style transfer on drawings |

## Tool Naming Convention

All tools follow: `mcp__<server-name>__<tool_name>`

Example: `mcp__safety-check__check_content_safety`

## SDK Fallback Pattern

Every MCP server guards against the Claude Agent SDK being unavailable (e.g., in test environments):

```python
try:
    from claude_agent_sdk import create_sdk_mcp_server, tool
except Exception:
    def tool(*_args, **_kwargs):    # No-op decorator
        def decorator(func): return func
        return decorator
```

This means the tool functions can be imported and tested directly as regular Python functions, even without the SDK installed.
