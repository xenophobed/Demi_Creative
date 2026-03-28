"""Unit tests for ThemeRecommender scoring and filtering logic (#292).

Parent Epic: #42
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.theme_recommender import ThemeRecommender


@pytest.fixture
def recommender():
    return ThemeRecommender()


class TestScoring:
    """Test the frequency x recency scoring algorithm."""

    def test_score_themes_by_frequency(self, recommender):
        """Higher frequency themes should score higher."""
        themes = {"dinosaurs": 10, "space": 3, "pirates": 1}
        scores = recommender._score_themes(themes, recent_themes=[])
        assert scores["dinosaurs"] > scores["space"] > scores["pirates"]

    def test_score_merges_concepts_and_interests(self, recommender):
        """Scores should combine themes, concepts, and interests counters."""
        themes = {"dinosaurs": 5}
        concepts = {"fossils": 3}
        interests = {"adventure": 4}
        scores = recommender._score_all(themes, concepts, interests, recent_themes=[])
        assert "dinosaurs" in scores
        assert "fossils" in scores
        assert "adventure" in scores

    def test_recently_used_themes_are_filtered(self, recommender):
        """Themes used in last 3 stories should be excluded from results."""
        themes = {"dinosaurs": 10, "space": 8, "pirates": 6, "robots": 4}
        recent_themes = ["dinosaurs", "space"]
        result = recommender._rank_and_filter(themes, {}, {}, recent_themes, limit=5)
        assert "dinosaurs" not in result
        assert "space" not in result
        assert "pirates" in result

    def test_limit_caps_output(self, recommender):
        """Should return at most `limit` recommendations."""
        themes = {f"theme_{i}": 10 - i for i in range(10)}
        result = recommender._rank_and_filter(themes, {}, {}, [], limit=3)
        assert len(result) <= 3

    def test_empty_profile_returns_empty(self, recommender):
        """No preference data should yield empty recommendations."""
        result = recommender._rank_and_filter({}, {}, {}, [], limit=5)
        assert result == []


class TestGetRecommendations:
    """Test the full async get_recommendations method."""

    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self, recommender):
        """Recommendations should be a list of strings."""
        mock_profile = {
            "themes": {"dinosaurs": 10, "space": 5, "pirates": 3},
            "concepts": {},
            "interests": {"adventure": 2},
            "recent_choices": [],
        }
        mock_stories = [
            {"educational_value": {"themes": ["dinosaurs"]}},
        ]

        with patch.object(
            recommender, "_get_preference_profile", new_callable=AsyncMock, return_value=mock_profile
        ), patch.object(
            recommender, "_get_recent_story_themes", new_callable=AsyncMock, return_value=["dinosaurs"]
        ), patch.object(
            recommender, "_filter_safe_themes", new_callable=AsyncMock, side_effect=lambda x: x
        ):
            result = await recommender.get_recommendations("user1", "child1", limit=5)

        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)
        # dinosaurs should be filtered out (used in last story)
        assert "dinosaurs" not in result

    @pytest.mark.asyncio
    async def test_default_limit_is_5(self, recommender):
        """Default limit should be 5."""
        mock_profile = {
            "themes": {f"t{i}": 20 - i for i in range(10)},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }

        with patch.object(
            recommender, "_get_preference_profile", new_callable=AsyncMock, return_value=mock_profile
        ), patch.object(
            recommender, "_get_recent_story_themes", new_callable=AsyncMock, return_value=[]
        ), patch.object(
            recommender, "_filter_safe_themes", new_callable=AsyncMock, side_effect=lambda x: x
        ):
            result = await recommender.get_recommendations("user1", "child1")

        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_empty_profile_returns_empty_list(self, recommender):
        """No data should produce an empty list, not an error."""
        mock_profile = {
            "themes": {},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }

        with patch.object(
            recommender, "_get_preference_profile", new_callable=AsyncMock, return_value=mock_profile
        ), patch.object(
            recommender, "_get_recent_story_themes", new_callable=AsyncMock, return_value=[]
        ), patch.object(
            recommender, "_filter_safe_themes", new_callable=AsyncMock, side_effect=lambda x: x
        ):
            result = await recommender.get_recommendations("user1", "child1")

        assert result == []
