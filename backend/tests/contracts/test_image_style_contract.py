"""
Contract tests for Art Style Transfer (#269, #270, #275).

Verifies:
- ArtTheme enum has exactly 8 values including 'none'
- transform_art_style MCP tool returns correct output shape
- All 7 art themes produce valid output
- Invalid theme is rejected
- Age-based theme filtering works correctly
- Mock mode returns deterministic output
"""

import pytest
import json


class TestArtThemeEnumContract:
    """ArtTheme enum must have exactly 8 values."""

    def test_enum_has_8_values(self):
        from backend.src.api.models import ArtTheme
        assert len(ArtTheme) == 8

    def test_enum_has_none(self):
        from backend.src.api.models import ArtTheme
        assert ArtTheme.NONE.value == "none"

    def test_enum_has_all_themes(self):
        from backend.src.api.models import ArtTheme
        expected = {"cartoon", "oil_painting", "watercolor", "pixel_art", "anime", "crayon", "storybook", "none"}
        actual = {t.value for t in ArtTheme}
        assert actual == expected


class TestAgeThemeFilterContract:
    """Age-based theme filtering must restrict young children to safe themes."""

    def test_age_3_5_gets_4_themes(self):
        from backend.src.mcp_servers.image_style_server import get_allowed_themes
        allowed = get_allowed_themes(4)
        assert allowed == {"cartoon", "crayon", "watercolor", "storybook"}

    def test_age_5_gets_young_themes(self):
        from backend.src.mcp_servers.image_style_server import get_allowed_themes
        allowed = get_allowed_themes(5)
        assert allowed == {"cartoon", "crayon", "watercolor", "storybook"}

    def test_age_6_gets_all_themes(self):
        from backend.src.mcp_servers.image_style_server import get_allowed_themes
        allowed = get_allowed_themes(6)
        assert len(allowed) == 7

    def test_age_12_gets_all_themes(self):
        from backend.src.mcp_servers.image_style_server import get_allowed_themes
        allowed = get_allowed_themes(12)
        assert len(allowed) == 7


class TestTransformArtStyleOutputContract:
    """transform_art_style must return MCP-compliant output shape."""

    @pytest.mark.asyncio
    async def test_mock_output_has_required_fields(self):
        """In test env (PYTEST_CURRENT_TEST set), tool returns mock with correct shape."""
        from backend.src.mcp_servers.image_style_server import transform_art_style

        result = await transform_art_style({
            "image_path": "/tmp/test.png",
            "theme": "cartoon",
            "child_age": 7,
            "session_id": "test-session",
        })

        # MCP tool output format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert "styled_image_path" in data
        assert data["original_preserved"] is True
        assert data["theme_applied"] == "cartoon"

    @pytest.mark.asyncio
    async def test_all_themes_produce_valid_output(self):
        from backend.src.mcp_servers.image_style_server import transform_art_style, ART_THEME_PROMPTS

        for theme in ART_THEME_PROMPTS:
            result = await transform_art_style({
                "image_path": "/tmp/test.png",
                "theme": theme,
                "child_age": 10,
                "session_id": f"test-{theme}",
            })
            data = json.loads(result["content"][0]["text"])
            assert data["success"] is True
            assert data["theme_applied"] == theme

    @pytest.mark.asyncio
    async def test_invalid_theme_returns_error(self):
        from backend.src.mcp_servers.image_style_server import transform_art_style

        result = await transform_art_style({
            "image_path": "/tmp/test.png",
            "theme": "invalid_theme",
            "child_age": 7,
            "session_id": "test-session",
        })

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is False
        assert "error" in data

    @pytest.mark.asyncio
    async def test_age_restricted_theme_returns_error(self):
        """3-5 year old should not be able to use pixel_art theme."""
        from backend.src.mcp_servers.image_style_server import transform_art_style

        result = await transform_art_style({
            "image_path": "/tmp/test.png",
            "theme": "pixel_art",
            "child_age": 4,
            "session_id": "test-session",
        })

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is False
        assert "not available" in data["error"].lower() or "not allowed" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_age_restricted_anime_returns_error(self):
        """3-5 year old should not be able to use anime theme."""
        from backend.src.mcp_servers.image_style_server import transform_art_style

        result = await transform_art_style({
            "image_path": "/tmp/test.png",
            "theme": "anime",
            "child_age": 5,
            "session_id": "test-session",
        })

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_young_child_can_use_cartoon(self):
        """3-5 year old should be able to use cartoon theme."""
        from backend.src.mcp_servers.image_style_server import transform_art_style

        result = await transform_art_style({
            "image_path": "/tmp/test.png",
            "theme": "cartoon",
            "child_age": 4,
            "session_id": "test-session",
        })

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert data["theme_applied"] == "cartoon"
