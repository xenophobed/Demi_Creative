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
            assert "kids_daily" in profile or "morning_show" in profile

    async def test_get_preferences_invalid_child_id(self, test_client):
        async with test_client as client:
            resp = await client.get("/api/v1/memory/preferences/bad id!@#")
            assert resp.status_code == 400

    async def test_delete_preferences(self, test_client):
        child_id = f"child-del-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            # Create some preference data first, using the same user_id
            # that the auth context provides so keys match (#178 composite keys)
            from backend.src.services.database import character_repo, preference_repo

            await preference_repo.update_from_story_result(
                child_id, {"themes": ["space"]}, user_id="test_user"
            )
            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Lightning Dog",
                description="A fast golden dog",
            )

            # Verify it exists
            resp = await client.get(f"/api/v1/memory/preferences/{child_id}")
            assert resp.json()["profile"]["themes"].get("space") == 1
            chars_before = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert len(chars_before.json()["characters"]) == 1

            # Delete
            del_resp = await client.delete(f"/api/v1/memory/preferences/{child_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["deleted"] is True
            assert del_resp.json()["deleted_records"]["characters"] >= 1

            # Verify cleared (returns empty profile)
            after = await client.get(f"/api/v1/memory/preferences/{child_id}")
            assert after.json()["profile"]["themes"] == {}
            chars_after = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert chars_after.json()["characters"] == []

    async def test_delete_single_preference_item(self, test_client):
        child_id = f"child-pref-item-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import preference_repo

            await preference_repo.update_from_story_result(
                child_id,
                {"themes": ["space", "adventure"]},
                user_id="test_user",
            )

            resp = await client.delete(
                f"/api/v1/memory/preferences/{child_id}/item",
                params={"category": "themes", "label": "space"},
            )
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

            after = await client.get(f"/api/v1/memory/preferences/{child_id}")
            themes = after.json()["profile"]["themes"]
            assert "space" not in themes
            assert themes.get("adventure") == 1

    async def test_delete_single_preference_item_invalid_category(self, test_client):
        child_id = f"child-pref-item-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            resp = await client.delete(
                f"/api/v1/memory/preferences/{child_id}/item",
                params={"category": "bad", "label": "space"},
            )
            assert resp.status_code == 400


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
                user_id="test_user",
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
            assert "main_characters" in resp.json()
            assert "other_characters" in resp.json()

    async def test_get_characters_grouped_main_and_other(self, test_client):
        child_id = f"child-chr-group-{uuid.uuid4().hex[:8]}"
        story_id_1 = f"story-chr-group-1-{uuid.uuid4().hex[:8]}"
        story_id_2 = f"story-chr-group-2-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import character_repo, story_repo

            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Hero Fox",
                description="The protagonist",
            )
            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Helper Bunny",
                description="The helper",
            )

            await story_repo.create(
                {
                    "story_id": story_id_1,
                    "user_id": "test_user",
                    "child_id": child_id,
                    "age_group": "6-8",
                    "story": {"text": "Story one", "word_count": 2},
                    "educational_value": {"themes": [], "concepts": [], "moral": None},
                    "characters": [
                        {"character_name": "Hero Fox"},
                        {"character_name": "Helper Bunny"},
                    ],
                    "analysis": {},
                    "safety_score": 0.9,
                    "story_type": "image_to_story",
                }
            )
            await story_repo.create(
                {
                    "story_id": story_id_2,
                    "user_id": "test_user",
                    "child_id": child_id,
                    "age_group": "6-8",
                    "story": {"text": "Story two", "word_count": 2},
                    "educational_value": {"themes": [], "concepts": [], "moral": None},
                    "characters": [{"name": "Hero Fox"}],
                    "analysis": {},
                    "safety_score": 0.9,
                    "story_type": "image_to_story",
                }
            )

            resp = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert resp.status_code == 200
            body = resp.json()

            main_names = [c["name"] for c in body["main_characters"]]
            other_names = [c["name"] for c in body["other_characters"]]
            assert "Hero Fox" in main_names
            assert "Helper Bunny" in other_names

            hero = next(c for c in body["main_characters"] if c["name"] == "Hero Fox")
            assert hero["main_story_count"] == 2
            assert hero["character_role"] == "main"

    async def test_delete_single_character_item(self, test_client):
        child_id = f"child-chr-item-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import character_repo

            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Lightning Dog",
                description="A fast golden dog",
            )
            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Moon Cat",
                description="A silver cat",
            )

            resp = await client.delete(
                f"/api/v1/memory/characters/{child_id}/item",
                params={"name": "Moon Cat"},
            )
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

            after = await client.get(f"/api/v1/memory/characters/{child_id}")
            names = [c["name"] for c in after.json()["characters"]]
            assert "Moon Cat" not in names
            assert "Lightning Dog" in names

    async def test_delete_character_item_removes_normalized_variants(self, test_client):
        child_id = f"child-chr-variants-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import character_repo

            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Star Cat",
                description="v1",
            )
            await character_repo._db.execute(
                """
                INSERT INTO characters (user_id, child_id, name, description, visual_features, traits, appearance_count, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test_user",
                    child_id,
                    " star   cat ",
                    "v2",
                    None,
                    None,
                    1,
                    "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00",
                ),
            )
            await character_repo._db.commit()

            resp = await client.delete(
                f"/api/v1/memory/characters/{child_id}/item",
                params={"name": "STAR CAT"},
            )
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

            after = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert after.json()["characters"] == []


@pytest.mark.asyncio
class TestStoryDeletionCharacterCounts:
    async def test_deleting_story_decrements_character_appearance(self, test_client):
        child_id = f"child-del-link-{uuid.uuid4().hex[:8]}"
        story_id = f"story-del-link-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import character_repo, story_repo

            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Lightning Dog",
                description="A fast golden dog",
            )
            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Lightning Dog",
                description="A fast golden dog",
            )

            await story_repo.create(
                {
                    "story_id": story_id,
                    "user_id": "test_user",
                    "child_id": child_id,
                    "age_group": "6-8",
                    "story": {"text": "A short story", "word_count": 3},
                    "educational_value": {"themes": [], "concepts": [], "moral": None},
                    "characters": [
                        {
                            "character_name": "Lightning Dog",
                            "description": "A fast golden dog",
                            "appearances": 1,
                        }
                    ],
                    "analysis": {},
                    "safety_score": 0.9,
                    "story_type": "image_to_story",
                }
            )

            resp = await client.delete(f"/api/v1/stories/{story_id}")
            assert resp.status_code == 200

            chars_resp = await client.get(f"/api/v1/memory/characters/{child_id}")
            chars = chars_resp.json()["characters"]
            assert len(chars) == 1
            assert chars[0]["name"] == "Lightning Dog"
            assert chars[0]["appearance_count"] == 1

    async def test_deleting_story_removes_character_when_count_hits_zero(
        self, test_client
    ):
        child_id = f"child-del-zero-{uuid.uuid4().hex[:8]}"
        story_id = f"story-del-zero-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            from backend.src.services.database import character_repo, story_repo

            await character_repo.upsert_character(
                user_id="test_user",
                child_id=child_id,
                name="Moon Cat",
                description="A silver cat",
            )

            await story_repo.create(
                {
                    "story_id": story_id,
                    "user_id": "test_user",
                    "child_id": child_id,
                    "age_group": "6-8",
                    "story": {"text": "Another short story", "word_count": 3},
                    "educational_value": {"themes": [], "concepts": [], "moral": None},
                    "characters": [
                        {
                            "character_name": "Moon Cat",
                            "description": "A silver cat",
                            "appearances": 1,
                        }
                    ],
                    "analysis": {},
                    "safety_score": 0.9,
                    "story_type": "image_to_story",
                }
            )

            resp = await client.delete(f"/api/v1/stories/{story_id}")
            assert resp.status_code == 200

            chars_resp = await client.get(f"/api/v1/memory/characters/{child_id}")
            assert chars_resp.json()["characters"] == []
