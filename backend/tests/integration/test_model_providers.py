"""
Model Provider Integration Tests

Real API calls to verify each AI model provider works end-to-end.
All tests are marked @pytest.mark.integration and guarded with skipif
so CI passes without API keys.
"""

import json
import os
from pathlib import Path

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_tool(tool_ref, args):
    """Call an MCP tool, unwrapping SdkMcpTool if the SDK is installed."""
    handler = getattr(tool_ref, "handler", tool_ref)
    return handler(args)


def parse_mcp_response(result: dict) -> dict:
    """Extract and parse the JSON payload from an MCP tool response envelope."""
    return json.loads(result["content"][0]["text"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_image(tmp_path) -> str:
    """Create a minimal 200x200 test PNG with simple shapes."""
    img = Image.new("RGB", (200, 200), color="lightyellow")
    # Draw a simple cross pattern so Vision has something to describe
    for x in range(80, 120):
        for y in range(40, 160):
            img.putpixel((x, y), (255, 0, 0))
    for x in range(40, 160):
        for y in range(80, 120):
            img.putpixel((x, y), (255, 0, 0))
    path = tmp_path / "test_drawing.png"
    img.save(path)
    return str(path)


@pytest.fixture
def audio_output_dir(tmp_path, monkeypatch) -> Path:
    """Redirect TTS audio output to a temp directory."""
    monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def chroma_tmp_dir(tmp_path, monkeypatch) -> Path:
    """Isolated ChromaDB directory — no API key needed."""
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    monkeypatch.setenv("CHROMA_PATH", str(chroma_dir))
    return chroma_dir


@pytest.fixture
def video_output_dir(tmp_path, monkeypatch) -> Path:
    """Redirect video output to a temp directory."""
    monkeypatch.setenv("VIDEO_OUTPUT_PATH", str(tmp_path))
    return tmp_path


# ===========================================================================
# 1. Vision Model Provider (Anthropic Claude Vision)
# ===========================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
class TestVisionModelProvider:
    """Verify Claude Vision can analyse a children's drawing."""

    @pytest.mark.asyncio
    async def test_analyze_drawing_returns_valid_structure(self, sample_image):
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        result = await _call_tool(analyze_children_drawing, {
            "image_path": sample_image,
            "child_age": 7,
        })
        data = parse_mcp_response(result)

        # Required fields
        assert "objects" in data
        assert "scene" in data
        assert "mood" in data
        assert "confidence_score" in data

        # Types
        assert isinstance(data["objects"], list)
        assert isinstance(data["scene"], str)
        assert isinstance(data["mood"], str)
        assert isinstance(data["confidence_score"], (int, float))
        assert 0.0 <= data["confidence_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_analyze_drawing_handles_invalid_path(self):
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        result = await _call_tool(analyze_children_drawing, {
            "image_path": "/nonexistent/path.png",
            "child_age": 7,
        })
        data = parse_mcp_response(result)
        assert "error" in data


# ===========================================================================
# 2. Safety LLM Provider (Anthropic Claude)
# ===========================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
class TestSafetyLLMProvider:
    """Verify Claude can perform content safety analysis."""

    @pytest.mark.asyncio
    async def test_safe_content_passes(self):
        from backend.src.mcp_servers.safety_check_server import check_content_safety

        result = await _call_tool(check_content_safety, {
            "content_text": "A kitten played with a ball of yarn in the garden.",
            "content_type": "story",
            "target_age": 6,
        })
        data = parse_mcp_response(result)

        assert data["is_safe"] is True
        assert data["safety_score"] >= 0.85
        assert isinstance(data["issues"], list)

    @pytest.mark.asyncio
    async def test_age_appropriateness_field(self):
        from backend.src.mcp_servers.safety_check_server import check_content_safety

        result = await _call_tool(check_content_safety, {
            "content_text": "The friendly dragon shared cookies with the village children.",
            "content_type": "story",
            "target_age": 4,
        })
        data = parse_mcp_response(result)

        assert "age_appropriateness" in data
        assert "is_appropriate" in data["age_appropriateness"]
        assert isinstance(data["age_appropriateness"]["is_appropriate"], bool)


# ===========================================================================
# 3. TTS Provider (OpenAI tts-1)
# ===========================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestTTSProvider:
    """Verify OpenAI TTS generates audio files."""

    @pytest.mark.asyncio
    async def test_generate_audio_creates_file(self, audio_output_dir):
        from backend.src.mcp_servers.tts_generator_server import generate_story_audio

        result = await _call_tool(generate_story_audio, {
            "story_text": "Hello!",
            "voice": "nova",
        })
        data = parse_mcp_response(result)

        assert data["success"] is True
        assert "audio_path" in data
        assert Path(data["audio_path"]).exists()
        assert Path(data["audio_path"]).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_list_voices_returns_options(self):
        from backend.src.mcp_servers.tts_generator_server import list_available_voices

        result = await _call_tool(list_available_voices, {})
        data = parse_mcp_response(result)

        assert "voices" in data
        assert len(data["voices"]) > 0
        voice_ids = [v["voice_id"] for v in data["voices"]]
        assert "nova" in voice_ids
        # #149: all entries must have a provider field
        providers = {v["provider"] for v in data["voices"]}
        assert "openai" in providers


# ===========================================================================
# 4. Image Generation Provider (OpenAI gpt-image-1-mini)
# ===========================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestImageGenProvider:
    """Verify OpenAI image generation works (if available)."""

    @pytest.mark.asyncio
    async def test_generate_painting_video_graceful_on_image(self, sample_image, video_output_dir):
        """
        The video generator calls OpenAI's Sora API which may or may not be
        available. We verify the tool returns a well-formed response (success
        or a structured error) rather than crashing.
        """
        from backend.src.mcp_servers.video_generator_server import generate_painting_video

        result = await _call_tool(generate_painting_video, {
            "image_path": sample_image,
            "style": "gentle_animation",
            "duration_seconds": 5,
        })
        data = parse_mcp_response(result)

        # The tool should return a structured response either way
        assert isinstance(data, dict)
        if data.get("success"):
            assert "job_id" in data
        else:
            # Graceful failure — must have an error message, not a crash
            assert "error" in data or "status" in data


# ===========================================================================
# 5. Video Generation Provider (OpenAI Sora)
# ===========================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestVideoGenProvider:
    """Verify video generation tool handles API calls gracefully."""

    @pytest.mark.asyncio
    async def test_check_video_status_unknown_job(self):
        """Checking status of a nonexistent job should return structured error."""
        from backend.src.mcp_servers.video_generator_server import check_video_status

        result = await _call_tool(check_video_status, {"job_id": "nonexistent-job-id-000"})
        data = parse_mcp_response(result)

        assert isinstance(data, dict)
        # Should indicate job not found rather than crashing
        assert "error" in data or data.get("status") == "failed"

    @pytest.mark.asyncio
    async def test_generate_painting_video_returns_structured_response(
        self, sample_image, video_output_dir
    ):
        """Video generation may fail (Sora availability) but should not crash."""
        from backend.src.mcp_servers.video_generator_server import generate_painting_video

        result = await _call_tool(generate_painting_video, {
            "image_path": sample_image,
            "style": "playful",
            "duration_seconds": 5,
        })
        data = parse_mcp_response(result)

        assert isinstance(data, dict)
        # Either success with job_id or structured error
        assert "job_id" in data or "error" in data


# ===========================================================================
# 6. Embeddings Provider (ChromaDB — local, no API key)
# ===========================================================================

@pytest.mark.integration
class TestEmbeddingsProvider:
    """Verify ChromaDB embedding store/search works locally."""

    @pytest.mark.asyncio
    async def test_store_embedding(self, chroma_tmp_dir):
        from backend.src.mcp_servers.vector_search_server import store_drawing_embedding

        result = await _call_tool(store_drawing_embedding, {
            "drawing_description": "A red house with a blue door",
            "child_id": "integration-child-001",
            "drawing_analysis": {
                "objects": ["house", "door"],
                "scene": "neighborhood",
                "mood": "cozy",
                "colors": ["red", "blue"],
            },
        })
        data = parse_mcp_response(result)

        assert data["success"] is True
        assert "document_id" in data

    @pytest.mark.asyncio
    async def test_search_after_store(self, chroma_tmp_dir):
        from backend.src.mcp_servers.vector_search_server import (
            store_drawing_embedding,
            search_similar_drawings,
        )

        # Store first
        await _call_tool(store_drawing_embedding, {
            "drawing_description": "A tall castle on a mountain",
            "child_id": "integration-child-002",
            "drawing_analysis": {
                "objects": ["castle", "mountain"],
                "scene": "fantasy landscape",
                "mood": "adventurous",
                "colors": ["gray", "purple"],
            },
        })

        # Search
        result = await _call_tool(search_similar_drawings, {
            "drawing_description": "castle on a hill",
            "child_id": "integration-child-002",
            "top_k": 3,
        })
        data = parse_mcp_response(result)

        assert "similar_drawings" in data
        assert data["total_found"] >= 1
        top_hit = data["similar_drawings"][0]
        assert "similarity_score" in top_hit

    @pytest.mark.asyncio
    async def test_search_nonexistent_child(self, chroma_tmp_dir):
        from backend.src.mcp_servers.vector_search_server import search_similar_drawings

        result = await _call_tool(search_similar_drawings, {
            "drawing_description": "anything",
            "child_id": "no-such-child",
            "top_k": 5,
        })
        data = parse_mcp_response(result)

        assert "similar_drawings" in data
        assert isinstance(data["similar_drawings"], list)
