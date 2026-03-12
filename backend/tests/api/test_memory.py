"""API tests for memory endpoints (#162).

Tests GET/DELETE preferences and GET characters.
"""

import uuid
import pytest


@pytest.mark.asyncio
class TestMemoryPreferencesEndpoints:
    async def test_get_preferences_returns_profile(self, test_client):
        child_id = f"child-mem-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            resp = await client.get(f"/api/v1/memory/preferences/{child_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["child_id"] == child_id
            profile = body["profile"]
            assert "themes" in profile
            assert "concepts" in profile
            assert "interests" in profile
            assert "recent_choices" in profile
            assert "morning_show" in profile

    async def test_get_preferences_invalid_child_id(self, test_client):
        async with test_client as client:
            resp = await client.get("/api/v1/memory/preferences/bad id!@#")
            assert resp.status_code == 400

    async def test_delete_preferences(self, test_client):
        child_id = f"child-del-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            # Create some preference data first
            from backend.src.services.database import preference_repo
            await preference_repo.update_from_story_result(child_id, {"themes": ["space"]})

            # Verify it exists
            resp = await client.get(f"/api/v1/memory/preferences/{child_id}")
            assert resp.json()["profile"]["themes"].get("space") == 1

            # Delete
            del_resp = await client.delete(f"/api/v1/memory/preferences/{child_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["deleted"] is True

            # Verify cleared (returns empty profile)
            after = await client.get(f"/api/v1/memory/preferences/{child_id}")
            assert after.json()["profile"]["themes"] == {}


@pytest.mark.asyncio
class TestMemoryCharactersEndpoints:
    async def test_get_characters_empty(self, test_client):
        child_id = f"child-chr-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            resp = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["child_id"] == child_id
            assert body["characters"] == []

    async def test_get_characters_returns_data(self, test_client):
        child_id = f"child-chr-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            # Insert a character directly
            from backend.src.services.database import character_repo
            await character_repo.upsert_character(
                child_id=child_id,
                name="Lightning Dog",
                description="A fast golden dog",
            )

            resp = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert resp.status_code == 200
            chars = resp.json()["characters"]
            assert len(chars) == 1
            assert chars[0]["name"] == "Lightning Dog"
            assert chars[0]["appearance_count"] == 1
