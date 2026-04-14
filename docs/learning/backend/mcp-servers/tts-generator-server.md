# TTS Generator MCP Server

**Source**: `backend/src/mcp_servers/tts_generator_server.py`

## What This File Does

**Explorer**: This helper reads stories out loud! It takes the written text and turns it into an audio file with a friendly voice — like a parent reading a bedtime story, but the app does it automatically.

**Maker**: This MCP server wraps multiple TTS (Text-to-Speech) providers — OpenAI, Replicate (minimax/speech-02-turbo), and ElevenLabs — behind a unified `generate_story_audio` tool. The agent selects a voice based on age group, and the server routes to the configured provider, generates audio, saves the MP3 file, and returns the file path.

## How It Works

1. **Agent calls `generate_story_audio`** with text, voice name, speed, and an output ID
2. **Server resolves the voice** from three provider catalogs:
   - OpenAI voices: alloy, echo, fable, onyx, nova, shimmer (6 voices)
   - Replicate minimax voices: 17 character voices (Wise Woman, Young Knight, etc.)
   - ElevenLabs voices: curated catalog with voice IDs
3. **Audio generation**: Calls the matching provider's API via `tts_service.generate_story_audio_file()`
4. **File saved** to `data/audio/` with a unique filename
5. **Returns**: file path + duration metadata for the frontend audio player

### Voice-to-Age Mapping

| Age Group | Default Voice | Provider | Why |
|-----------|--------------|----------|-----|
| 3-5 | Nova | OpenAI | Soft, gentle — soothing for young children |
| 6-8 | Shimmer | OpenAI | Lively, energetic — matches their energy |
| 9-12 | Alloy | OpenAI | Neutral — older kids prefer less "childish" voices |

## Key Concepts

**TTS (Text-to-Speech)**: Technology that converts written text into spoken audio. Different from speech-to-text (which goes the other direction).

**Voice Catalog**: A predefined list of available voices with metadata (name, description, recommended age). The frontend's `VoicePicker` component shows these to the user.

**Multi-Provider Strategy**: Supporting 3 TTS providers means we can choose the best voice for each use case and fall back if one provider is down. Trade-off: more code complexity, but better voice variety and reliability.

## Connections

- **Upstream**: Called by all three agents during content generation when `enable_audio=True`
- **Downstream**: `services/tts_service.py` → OpenAI/Replicate/ElevenLabs APIs
- **Frontend**: `VoicePicker` component displays voices; `AudioPlayer` plays the resulting files
- **Storage**: Audio files saved to `data/audio/`, served via `/data/audio/{filename}` route

## Thinking Question

Each TTS provider has different pricing, latency, and voice quality. How would you decide which provider to use as the default? Consider: cost per character, cold start time, voice naturalness, and what happens if the provider goes down during a story generation.
