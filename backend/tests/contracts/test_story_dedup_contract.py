"""
Story Deduplication Contract Tests (#161)

Tests store_story_embedding and search_similar_stories MCP tools.

Parent Epic: #42 | Issue: #161
"""

import importlib
import json
import pytest


@pytest.fixture()
def vs():
    return importlib.import_module("backend.src.mcp_servers.vector_search_server")


async def _call(tool_obj, args):
    if hasattr(tool_obj, "handler"):
        return await tool_obj.handler(args)
    return await tool_obj(args)


class TestStoreStoryEmbedding:
    @pytest.mark.asyncio
    async def test_rejects_empty_child_id(self, vs):
        result = await _call(vs.store_story_embedding, {
            "child_id": "",
            "story_id": "s1",
            "story_text": "A dog flew to the moon",
            "themes": "space",
            "age_group": "6-8",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False

    @pytest.mark.asyncio
    async def test_rejects_empty_story_text(self, vs):
        result = await _call(vs.store_story_embedding, {
            "child_id": "child-1",
            "story_id": "s1",
            "story_text": "",
            "themes": "",
            "age_group": "",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False

    @pytest.mark.asyncio
    async def test_stores_successfully(self, vs, tmp_path):
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.store_story_embedding, {
            "child_id": "child-dedup",
            "story_id": "story-001",
            "story_text": "Lightning Dog flew to the moon and found a glowing rock.",
            "themes": "space, adventure",
            "age_group": "6-8",
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is True
        assert payload["document_id"] == "story-001"


class TestSearchSimilarStories:
    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_child(self, vs, tmp_path):
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.search_similar_stories, {
            "child_id": "ghost",
            "story_description": "anything",
            "top_k": 3,
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["similar_stories"] == []
        assert payload["total_found"] == 0

    @pytest.mark.asyncio
    async def test_finds_similar_story(self, vs, tmp_path):
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        await _call(vs.store_story_embedding, {
            "child_id": "child-sim",
            "story_id": "story-sim-1",
            "story_text": "A brave dog named Lightning flew to the moon on a rocket ship.",
            "themes": "space",
            "age_group": "6-8",
        })

        result = await _call(vs.search_similar_stories, {
            "child_id": "child-sim",
            "story_description": "Lightning Dog goes to the moon",
            "top_k": 3,
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["total_found"] >= 1
        assert 0.0 <= payload["similar_stories"][0]["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_response_shape(self, vs, tmp_path):
        pytest.importorskip("chromadb")
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        result = await _call(vs.search_similar_stories, {
            "child_id": "child-shape",
            "story_description": "test",
            "top_k": 1,
        })
        payload = json.loads(result["content"][0]["text"])
        assert "similar_stories" in payload
        assert "total_found" in payload
        assert "query" in payload
