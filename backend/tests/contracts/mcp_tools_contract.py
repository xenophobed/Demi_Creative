"""
MCP Tools Contract Tests

Tests the input/output contracts of MCP Tools, ensuring tools conform to specification.
"""

import pytest
import json
import os
from pathlib import Path
from PIL import Image
import io


def _call_tool(tool_ref, args):
    """Call an MCP tool, unwrapping SdkMcpTool if the SDK is installed."""
    handler = getattr(tool_ref, "handler", tool_ref)
    return handler(args)


class TestVisionAnalysisContract:
    """Vision Analysis MCP Tool contract tests"""

    @pytest.fixture
    def sample_drawing_path(self, tmp_path):
        """Create a test children's drawing"""
        # Create a simple test image
        img = Image.new('RGB', (400, 300), color='lightblue')
        img_path = tmp_path / "test_drawing.png"
        img.save(img_path)
        return str(img_path)

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_contract(self, sample_drawing_path):
        """Test the input/output contract of analyze_children_drawing tool"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        # Prepare input
        input_data = {
            "image_path": sample_drawing_path,
            "child_age": 7
        }

        # Call tool
        result = await _call_tool(analyze_children_drawing, input_data)

        # Verify output format
        assert "content" in result, "Output must contain content field"
        assert isinstance(result["content"], list), "content must be a list"
        assert len(result["content"]) > 0, "content must not be empty"

        # Verify content format
        content_item = result["content"][0]
        assert "type" in content_item, "content item must contain type field"
        assert content_item["type"] == "text", "content type must be text"
        assert "text" in content_item, "content item must contain text field"

        # Parse JSON response
        data = json.loads(content_item["text"])

        # Verify required fields exist
        assert "objects" in data, "Output must contain objects field"
        assert "scene" in data, "Output must contain scene field"
        assert "mood" in data, "Output must contain mood field"
        assert "confidence_score" in data, "Output must contain confidence_score field"

        # Verify field types
        assert isinstance(data["objects"], list), "objects must be a list"
        assert isinstance(data["scene"], str), "scene must be a string"
        assert isinstance(data["mood"], str), "mood must be a string"
        assert isinstance(data["confidence_score"], (int, float)), "confidence_score must be a number"

        # Verify value ranges
        assert 0.0 <= data["confidence_score"] <= 1.0, "confidence_score must be between 0.0 and 1.0"

        # Verify optional fields exist and have correct types
        if "colors" in data:
            assert isinstance(data["colors"], list), "colors must be a list"

        if "recurring_characters" in data:
            assert isinstance(data["recurring_characters"], list), "recurring_characters must be a list"
            for char in data["recurring_characters"]:
                assert isinstance(char, dict), "Each character must be a dict"
                if "name" in char:
                    assert isinstance(char["name"], str), "Character name must be a string"
                if "description" in char:
                    assert isinstance(char["description"], str), "Character description must be a string"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_age_range(self, sample_drawing_path):
        """Test input for different age groups"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        ages = [3, 5, 7, 9, 12]
        for age in ages:
            input_data = {
                "image_path": sample_drawing_path,
                "child_age": age
            }

            result = await _call_tool(analyze_children_drawing, input_data)
            data = json.loads(result["content"][0]["text"])

            assert "objects" in data, f"Output for age {age} must contain objects"
            assert isinstance(data["objects"], list), f"objects for age {age} must be a list"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_invalid_path(self):
        """Test error handling for invalid image path"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        input_data = {
            "image_path": "/nonexistent/path/image.jpg",
            "child_age": 7
        }

        result = await _call_tool(analyze_children_drawing, input_data)
        data = json.loads(result["content"][0]["text"])

        # Should return an error message
        assert "error" in data, "Invalid path should return an error"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_required_fields(self, sample_drawing_path):
        """Test required field validation"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        # Test missing child_age
        with pytest.raises(KeyError):
            await _call_tool(analyze_children_drawing, {
                "image_path": sample_drawing_path
            })

        # Test missing image_path
        with pytest.raises(KeyError):
            await _call_tool(analyze_children_drawing, {
                "child_age": 7
            })


class TestVectorSearchContract:
    """Vector Search MCP Tool contract tests"""

    @pytest.fixture
    def chroma_tmp_dir(self, tmp_path, monkeypatch):
        """Isolated ChromaDB directory for contract tests."""
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        monkeypatch.setenv("CHROMA_PATH", str(chroma_dir))
        return chroma_dir

    @pytest.mark.asyncio
    async def test_store_drawing_embedding_contract(self, chroma_tmp_dir):
        """Test the input/output contract of store_drawing_embedding tool"""
        from backend.src.mcp_servers.vector_search_server import store_drawing_embedding

        result = await _call_tool(store_drawing_embedding, {
            "drawing_description": "A dog playing in the park",
            "child_id": "contract-child-001",
            "drawing_analysis": {
                "objects": ["dog", "tree"],
                "scene": "park",
                "mood": "happy",
                "colors": ["green", "brown"],
            },
        })

        # Verify MCP response envelope format
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert "document_id" in data
        assert isinstance(data["document_id"], str)

    @pytest.mark.asyncio
    async def test_search_similar_drawings_contract(self, chroma_tmp_dir):
        """Test the input/output contract of search_similar_drawings tool"""
        from backend.src.mcp_servers.vector_search_server import search_similar_drawings

        result = await _call_tool(search_similar_drawings, {
            "drawing_description": "a cat on a sofa",
            "child_id": "contract-child-002",
            "top_k": 3,
        })

        # Verify MCP response envelope format
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert "similar_drawings" in data
        assert isinstance(data["similar_drawings"], list)
        assert "total_found" in data
        assert isinstance(data["total_found"], int)


class TestSafetyCheckContract:
    """Safety Check MCP Tool contract tests"""

    @pytest.mark.asyncio
    async def test_check_content_safety_contract(self):
        """Test the input/output contract of check_content_safety tool — uses real Anthropic API"""
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        from backend.src.mcp_servers.safety_check_server import check_content_safety

        result = await _call_tool(check_content_safety, {
            "content_text": "A bunny shared carrots with friends in the garden.",
            "content_type": "story",
            "target_age": 5,
        })

        # Verify MCP response envelope format
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert "safety_score" in data
        assert isinstance(data["safety_score"], (int, float))
        assert 0.0 <= data["safety_score"] <= 1.0
        assert "is_safe" in data
        assert isinstance(data["is_safe"], bool)
        assert "issues" in data
        assert isinstance(data["issues"], list)


class TestTTSGenerationContract:
    """TTS Generation MCP Tool contract tests"""

    @pytest.mark.asyncio
    async def test_generate_story_audio_contract(self, tmp_path, monkeypatch):
        """Test the input/output contract of generate_story_audio tool — uses real OpenAI API"""
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY not set")

        monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

        from backend.src.mcp_servers.tts_generator_server import generate_story_audio

        result = await _call_tool(generate_story_audio, {
            "story_text": "Hello!",
            "voice": "nova",
        })

        # Verify MCP response envelope format
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert "audio_path" in data
        assert Path(data["audio_path"]).exists()

    @pytest.mark.asyncio
    async def test_list_available_voices_contract(self):
        """Test the input/output contract of list_available_voices tool — no API key needed"""
        from backend.src.mcp_servers.tts_generator_server import list_available_voices

        result = await _call_tool(list_available_voices, {})

        assert "content" in result
        data = json.loads(result["content"][0]["text"])
        assert "voices" in data
        assert len(data["voices"]) > 0
        for voice in data["voices"]:
            assert "id" in voice
            assert "description" in voice
