"""API tests for GET /api/v1/news-to-kids/conversion/{conversion_id} (#181)."""

import json
import uuid

import pytest


@pytest.mark.asyncio
class TestNewsDetailRoute:
    """Tests for the news conversion detail endpoint."""

    async def _create_conversion(self, client, child_id: str = "child-news-detail"):
        """Helper: create a news conversion and return the response data."""
        response = await client.post(
            "/api/v1/news-to-kids/convert",
            json={
                "child_id": child_id,
                "age_group": "6-8",
                "news_text": "Scientists discovered a new species of deep-sea fish that glows in the dark.",
                "category": "science",
                "enable_audio": False,
            },
        )
        assert response.status_code == 200
        return response.json()

    async def test_get_conversion_returns_200_with_correct_fields(self, test_client):
        """GET returns 200 and includes all expected fields for an existing conversion."""
        async with test_client as client:
            created = await self._create_conversion(client)
            conversion_id = created["conversion_id"]

            response = await client.get(
                f"/api/v1/news-to-kids/conversion/{conversion_id}"
            )
            assert response.status_code == 200
            data = response.json()

            # Required fields
            assert data["conversion_id"] == conversion_id
            assert "kid_title" in data
            assert "kid_content" in data
            assert "why_care" in data
            assert "key_concepts" in data
            assert "interactive_questions" in data
            assert "category" in data
            assert "age_group" in data
            assert "created_at" in data
            # audio_url may be None when enable_audio is False
            assert "audio_url" in data

    async def test_get_conversion_returns_404_for_nonexistent(self, test_client):
        """GET returns 404 when the conversion_id does not exist."""
        async with test_client as client:
            fake_id = str(uuid.uuid4())
            response = await client.get(
                f"/api/v1/news-to-kids/conversion/{fake_id}"
            )
            assert response.status_code == 404

    async def test_get_conversion_returns_404_for_wrong_user(self, test_client):
        """GET returns 404 (not 403) when the conversion belongs to another user.

        The test user is overridden globally in conftest, so we simulate this by
        creating a record with a different user_id directly in the repo.
        """
        from backend.src.services.database import story_repo, user_repo

        # Create another user in DB (FK constraint requires it)
        other_username = f"other_user_{uuid.uuid4().hex[:8]}"
        other_user = await user_repo.create_user(
            username=other_username,
            email=f"{other_username}@test.local",
            password_hash="hash",
        )

        other_user_conversion_id = str(uuid.uuid4())
        await story_repo.create({
            "story_id": other_user_conversion_id,
            "user_id": other_user.user_id,
            "child_id": "other-child",
            "age_group": "6-8",
            "story": {"text": "Some content", "word_count": 2, "age_adapted": True},
            "educational_value": {"themes": ["science"], "concepts": [], "moral": ""},
            "characters": [],
            "analysis": {
                "story_type": "news_to_kids",
                "category": "science",
                "kid_title": "Secret Story",
            },
            "story_type": "news_to_kids",
            "safety_score": 0.9,
            "audio_url": None,
        })

        async with test_client as client:
            response = await client.get(
                f"/api/v1/news-to-kids/conversion/{other_user_conversion_id}"
            )
            # Should not expose other user's data
            assert response.status_code == 404
