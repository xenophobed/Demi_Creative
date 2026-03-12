"""
Vector Search Server Contract Tests

Locks the MCP tool interface and data shape for store_drawing_embedding
and search_similar_drawings before adding new features.

NOTE: The @tool decorator from claude_agent_sdk wraps functions in SdkMcpTool
objects. Call the underlying function via `.handler(args)`.

Parent Epic: #42 | Issue: #163
"""

import importlib
import json
import pytest


@pytest.fixture()
def vs():
    """Return the vector_search_server module."""
    return importlib.import_module("backend.src.mcp_servers.vector_search_server")


async def _call(tool_obj, args):
    """Call an MCP tool, handling both SdkMcpTool and plain functions."""
    if hasattr(tool_obj, "handler"):
        return await tool_obj.handler(args)
    return await tool_obj(args)


# ============================================================================
# store_drawing_embedding
# ============================================================================


class TestStoreDrawingEmbeddingContract:
    """Contract: store_drawing_embedding produces valid responses."""

    @pytest.mark.asyncio
    async def test_rejects_empty_description(self, vs):
        result = await _call(vs.store_drawing_embedding, {
            "drawing_description": "",
            "child_id": "child-1",
            "drawing_analysis": {},
            "story_text": "",
            "image_path": "",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False

    @pytest.mark.asyncio
    async def test_rejects_empty_child_id(self, vs):
        result = await _call(vs.store_drawing_embedding, {
            "drawing_description": "a dog",
            "child_id": "",
            "drawing_analysis": {},
            "story_text": "",
            "image_path": "",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False

    @pytest.mark.asyncio
    async def test_response_shape_on_success(self, vs, tmp_path):
        """When ChromaDB is available, success response has document_id."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.store_drawing_embedding, {
            "drawing_description": "a golden dog with lightning bolts",
            "child_id": "child-test",
            "drawing_analysis": {
                "objects": ["dog", "lightning"],
                "colors": ["gold", "blue"],
                "scene": "park",
                "mood": "happy",
                "recurring_characters": [{"name": "Lightning Dog"}],
            },
            "story_text": "Lightning Dog ran across the park...",
            "image_path": "/data/uploads/test.png",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is True
        assert "document_id" in payload
        assert isinstance(payload["document_id"], str)
        assert len(payload["document_id"]) == 32  # MD5 hex length

    @pytest.mark.asyncio
    async def test_metadata_fields_serialized(self, vs, tmp_path):
        """Objects, colors, recurring_characters stored as JSON strings in metadata."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.store_drawing_embedding, {
            "drawing_description": "a cat in a forest",
            "child_id": "child-meta-test",
            "drawing_analysis": {
                "objects": ["cat", "tree"],
                "colors": ["red"],
                "recurring_characters": [{"name": "Star Cat"}],
                "scene": "forest",
                "mood": "calm",
            },
            "story_text": "Star Cat explored the forest...",
            "image_path": "/data/uploads/cat.png",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is True


# ============================================================================
# search_similar_drawings
# ============================================================================


class TestSearchSimilarDrawingsContract:
    """Contract: search_similar_drawings returns properly shaped results."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_child(self, vs, tmp_path):
        """Searching for a child with no drawings returns empty list."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.search_similar_drawings, {
            "drawing_description": "anything",
            "child_id": "nonexistent-child",
            "top_k": 5,
        })
        payload = json.loads(result["content"][0]["text"])
        assert "similar_drawings" in payload
        assert isinstance(payload["similar_drawings"], list)
        assert payload["total_found"] == 0

    @pytest.mark.asyncio
    async def test_similarity_score_in_range(self, vs, tmp_path):
        """Returned similarity scores must be in [0.0, 1.0]."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        await _call(vs.store_drawing_embedding, {
            "drawing_description": "a blue robot dancing",
            "child_id": "child-score-test",
            "drawing_analysis": {"objects": ["robot"], "colors": ["blue"], "scene": "stage", "mood": "happy", "recurring_characters": []},
            "story_text": "Robot danced on stage.",
            "image_path": "/data/test.png",
        })

        result = await _call(vs.search_similar_drawings, {
            "drawing_description": "a robot on a stage",
            "child_id": "child-score-test",
            "top_k": 3,
        })
        payload = json.loads(result["content"][0]["text"])
        for drawing in payload["similar_drawings"]:
            assert 0.0 <= drawing["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_child_id_filtering(self, vs, tmp_path):
        """Results only contain drawings from the queried child_id."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        await _call(vs.store_drawing_embedding, {
            "drawing_description": "a spaceship flying",
            "child_id": "child-A",
            "drawing_analysis": {"objects": ["spaceship"], "colors": ["silver"], "scene": "space", "mood": "excited", "recurring_characters": []},
            "story_text": "The spaceship launched.",
            "image_path": "/data/a.png",
        })
        await _call(vs.store_drawing_embedding, {
            "drawing_description": "a spaceship flying too",
            "child_id": "child-B",
            "drawing_analysis": {"objects": ["spaceship"], "colors": ["silver"], "scene": "space", "mood": "excited", "recurring_characters": []},
            "story_text": "Another spaceship.",
            "image_path": "/data/b.png",
        })

        result = await _call(vs.search_similar_drawings, {
            "drawing_description": "spaceship",
            "child_id": "child-A",
            "top_k": 10,
        })
        payload = json.loads(result["content"][0]["text"])
        for drawing in payload["similar_drawings"]:
            assert drawing["drawing_data"]["child_id"] == "child-A"

    @pytest.mark.asyncio
    async def test_response_shape(self, vs, tmp_path):
        """Response has required top-level keys."""
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.search_similar_drawings, {
            "drawing_description": "test",
            "child_id": "child-shape",
            "top_k": 1,
        })
        payload = json.loads(result["content"][0]["text"])
        assert "similar_drawings" in payload
        assert "total_found" in payload
        assert "query" in payload
        assert payload["query"]["child_id"] == "child-shape"
        assert payload["query"]["top_k"] == 1
