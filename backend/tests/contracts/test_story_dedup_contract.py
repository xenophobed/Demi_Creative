"""
Story Deduplication Contract Tests (#161, #290)

Tests store_story_embedding and search_similar_stories MCP tools,
including the round-trip dedup detection workflow.

Parent Epic: #42 | Issues: #161, #290
"""

import importlib
import json

import chromadb  # noqa: F401 — hard dep; fail loudly if missing (#685)
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


class TestStoryDedupRoundTrip:
    """Round-trip tests: store then search to verify dedup detection (#290)."""

    @pytest.mark.asyncio
    async def test_near_duplicate_detected(self, vs, tmp_path):
        """Store a story, then search with nearly identical text; expect high similarity."""
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        # Store original story
        await _call(vs.store_story_embedding, {
            "child_id": "child-rt",
            "story_id": "rt-story-1",
            "story_text": "A brave dog named Lightning flew to the moon on a shiny rocket and found a glowing crystal.",
            "themes": "space, adventure",
            "age_group": "6-8",
        })

        # Search with very similar text
        result = await _call(vs.search_similar_stories, {
            "child_id": "child-rt",
            "story_description": "A brave dog named Lightning flew to the moon on a rocket and found a glowing crystal.",
            "top_k": 3,
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["total_found"] >= 1
        top_match = payload["similar_stories"][0]
        # Near-duplicate should have high similarity (the exact score depends on
        # ChromaDB's default embedding model, but near-identical text should be
        # well above 0.5)
        assert top_match["similarity_score"] > 0.5
        assert top_match["story_id"] == "rt-story-1"

    @pytest.mark.asyncio
    async def test_different_child_not_found(self, vs, tmp_path):
        """Stories from one child should not appear in another child's search."""
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        # Store story for child-a
        await _call(vs.store_story_embedding, {
            "child_id": "child-a",
            "story_id": "iso-story-1",
            "story_text": "A cat explored a magical garden full of singing flowers.",
            "themes": "nature",
            "age_group": "3-5",
        })

        # Search as child-b — should find nothing
        result = await _call(vs.search_similar_stories, {
            "child_id": "child-b",
            "story_description": "A cat explored a magical garden full of singing flowers.",
            "top_k": 3,
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["total_found"] == 0

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, vs, tmp_path):
        """Calling store with the same story_id should upsert, not duplicate."""
        import os
        os.environ["CHROMA_PATH"] = str(tmp_path / "vectors")

        args = {
            "child_id": "child-up",
            "story_id": "upsert-1",
            "story_text": "Original text about a dragon.",
            "themes": "fantasy",
            "age_group": "9-12",
        }
        r1 = await _call(vs.store_story_embedding, args)
        assert json.loads(r1["content"][0]["text"])["success"] is True

        # Upsert with updated text
        args["story_text"] = "Updated text about a friendly dragon who bakes cakes."
        r2 = await _call(vs.store_story_embedding, args)
        assert json.loads(r2["content"][0]["text"])["success"] is True

        # Search — should find only 1 result (not 2)
        result = await _call(vs.search_similar_stories, {
            "child_id": "child-up",
            "story_description": "dragon",
            "top_k": 5,
        })
        payload = json.loads(result["content"][0]["text"])
        assert payload["total_found"] == 1
