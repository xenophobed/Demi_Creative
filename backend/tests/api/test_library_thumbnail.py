"""
Tests for Library Thumbnail Resolution (#136)

Verifies that _resolve_thumbnail() correctly reads artifact_url
from the Artifact model returned by get_canonical_artifact().

Bug: The code referenced artifact.storage_url which does not exist
on the Artifact model — the correct field is artifact_url.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from backend.src.api.routes.library import _resolve_thumbnail


class TestResolveThumbnail:
    """Unit tests for _resolve_thumbnail() helper."""

    def _make_artifact(self, artifact_url="https://cdn.example.com/cover.png"):
        """Create a mock Artifact with artifact_url field."""
        artifact = MagicMock()
        artifact.artifact_url = artifact_url
        # Ensure storage_url does NOT exist, to catch the old bug
        del artifact.storage_url
        return artifact

    @pytest.mark.asyncio
    async def test_returns_artifact_url_when_cover_exists(self):
        """Should return artifact_url from the canonical cover artifact."""
        mock_artifact = self._make_artifact("https://cdn.example.com/cover.png")

        with patch(
            "backend.src.api.routes.library.StoryArtifactLinkRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get_canonical_artifact = AsyncMock(return_value=mock_artifact)

            result = await _resolve_thumbnail("story-123")

        assert result == "https://cdn.example.com/cover.png"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cover_artifact(self):
        """Should return None when no canonical cover artifact exists."""
        with patch(
            "backend.src.api.routes.library.StoryArtifactLinkRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get_canonical_artifact = AsyncMock(return_value=None)

            result = await _resolve_thumbnail("story-456")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_artifact_url_is_none(self):
        """Should return None when artifact exists but has no URL."""
        mock_artifact = self._make_artifact(artifact_url=None)

        with patch(
            "backend.src.api.routes.library.StoryArtifactLinkRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get_canonical_artifact = AsyncMock(return_value=mock_artifact)

            result = await _resolve_thumbnail("story-789")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        """Should swallow exceptions and return None."""
        with patch(
            "backend.src.api.routes.library.StoryArtifactLinkRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get_canonical_artifact = AsyncMock(
                side_effect=Exception("DB error")
            )

            result = await _resolve_thumbnail("story-err")

        assert result is None
