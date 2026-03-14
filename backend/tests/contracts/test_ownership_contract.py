"""
Ownership Contract Tests

Ensures that ownerless resources are rejected (403) instead of auto-claimed,
and that standard ownership checks still work correctly.

Related: #187
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from src.api.deps import get_story_for_owner, get_session_for_owner


class TestStoryOwnership:
    """get_story_for_owner must reject ownerless stories and enforce ownership."""

    @pytest.mark.asyncio
    async def test_ownerless_story_returns_403(self):
        """Requesting a story with user_id=None must return 403, not auto-claim."""
        ownerless_story = {"story_id": "s1", "user_id": None, "title": "test"}

        with patch("src.api.deps.story_repo") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=ownerless_story)

            with pytest.raises(HTTPException) as exc_info:
                await get_story_for_owner("s1", "any_user")

            assert exc_info.value.status_code == 403
            # Must NOT have called update_user_id (no auto-claim)
            mock_repo.update_user_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_users_story_returns_403(self):
        """Requesting a story owned by another user must return 403."""
        other_story = {"story_id": "s2", "user_id": "owner_a", "title": "test"}

        with patch("src.api.deps.story_repo") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=other_story)

            with pytest.raises(HTTPException) as exc_info:
                await get_story_for_owner("s2", "owner_b")

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_own_story_succeeds(self):
        """Requesting your own story must succeed."""
        my_story = {"story_id": "s3", "user_id": "me", "title": "my story"}

        with patch("src.api.deps.story_repo") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=my_story)

            result = await get_story_for_owner("s3", "me")

            assert result["story_id"] == "s3"
            assert result["user_id"] == "me"

    @pytest.mark.asyncio
    async def test_missing_story_returns_404(self):
        """Requesting a non-existent story must return 404."""
        with patch("src.api.deps.story_repo") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_story_for_owner("no_such", "me")

            assert exc_info.value.status_code == 404


class TestSessionOwnership:
    """get_session_for_owner must reject ownerless sessions and enforce ownership."""

    @pytest.mark.asyncio
    async def test_ownerless_session_returns_403(self):
        """Requesting a session with user_id=None must return 403, not auto-claim."""
        ownerless_session = MagicMock()
        ownerless_session.user_id = None

        with patch("src.api.deps.session_repo") as mock_repo:
            mock_repo.get_session = AsyncMock(return_value=ownerless_session)

            with pytest.raises(HTTPException) as exc_info:
                await get_session_for_owner("sess1", "any_user")

            assert exc_info.value.status_code == 403
            # Must NOT have called update_user_id (no auto-claim)
            mock_repo.update_user_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_users_session_returns_403(self):
        """Requesting a session owned by another user must return 403."""
        other_session = MagicMock()
        other_session.user_id = "owner_a"

        with patch("src.api.deps.session_repo") as mock_repo:
            mock_repo.get_session = AsyncMock(return_value=other_session)

            with pytest.raises(HTTPException) as exc_info:
                await get_session_for_owner("sess2", "owner_b")

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_own_session_succeeds(self):
        """Requesting your own session must succeed."""
        my_session = MagicMock()
        my_session.user_id = "me"
        my_session.session_id = "sess3"

        with patch("src.api.deps.session_repo") as mock_repo:
            mock_repo.get_session = AsyncMock(return_value=my_session)

            result = await get_session_for_owner("sess3", "me")

            assert result.user_id == "me"

    @pytest.mark.asyncio
    async def test_missing_session_returns_404(self):
        """Requesting a non-existent session must return 404."""
        with patch("src.api.deps.session_repo") as mock_repo:
            mock_repo.get_session = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_session_for_owner("no_such", "me")

            assert exc_info.value.status_code == 404
