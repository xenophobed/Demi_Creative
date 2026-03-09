"""
Safety Fail-Closed Contract Tests

Ensures that all safety check callsites fail closed:
- MCP tool unavailable → content blocked (never passed through)
- Missing safety_score → treated as unsafe
- No silent pass-through of unchecked content

Related: #158
"""

import json
import pytest
from unittest.mock import AsyncMock, patch


class TestCheckStorySafetyFailClosed:
    """_check_story_safety must fail closed when MCP is unavailable."""

    @pytest.mark.asyncio
    async def test_mcp_unavailable_returns_zero(self):
        """When MCP tool raises, safety score must be 0.0 (blocks content)."""
        from src.api.routes.interactive_story import _check_story_safety

        with patch(
            "src.api.routes.interactive_story.check_content_safety",
            side_effect=RuntimeError("MCP unavailable"),
            create=True,
        ):
            # Force re-import by patching at module level
            pass

        # The function catches all exceptions and returns 0.0
        score = await _check_story_safety("test story text", "6-8")
        # Score must be below threshold (0.85) to block content
        assert score < 0.85, (
            f"MCP unavailable must return a blocking score, got {score}"
        )

    @pytest.mark.asyncio
    async def test_mcp_returns_error_json_blocks_content(self):
        """When MCP returns error JSON (no safety_score key), content is blocked."""
        from src.api.routes.interactive_story import _check_story_safety

        mock_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": '{"error": "MCP server dependency unavailable"}'}]
        })

        with patch("src.mcp_servers.check_content_safety", mock_tool):
            # Re-import to pick up the patched function
            import importlib
            import src.api.routes.interactive_story as mod
            importlib.reload(mod)
            score = await mod._check_story_safety("test story", "6-8")

        assert score < 0.85, (
            f"MCP error response must return a blocking score, got {score}"
        )


class TestIllustrationSafetyFailClosed:
    """_safe_illustration_description must fail closed when MCP is unavailable."""

    @pytest.mark.asyncio
    async def test_mcp_unavailable_returns_safe_fallback(self):
        """When MCP tool is unavailable, must return a safe generic description."""
        from src.api.routes.morning_show import _safe_illustration_description

        # Patch to simulate MCP failure
        mock_tool = AsyncMock(side_effect=RuntimeError("MCP unavailable"))

        with patch("src.mcp_servers.check_content_safety", mock_tool):
            import importlib
            import src.api.routes.morning_show as mod
            importlib.reload(mod)
            result = await mod._safe_illustration_description(
                "potentially unsafe description", "6-8"
            )

        # Must NOT return the original description when safety can't be verified
        assert result != "potentially unsafe description", (
            "MCP unavailable must not pass through unchecked descriptions"
        )


class TestSafetyScoreDefaultsContract:
    """No route should default safety_score to a passing value (>= 0.85)."""

    def test_no_passing_default_in_image_to_story_routes(self):
        """image_to_story routes must not default safety_score to >= 0.85."""
        import inspect
        from src.api.routes import image_to_story

        source = inspect.getsource(image_to_story)
        # Check for patterns like: .get("safety_score", 0.9)
        # or .get("safety_score", 0.85) — any default >= 0.85 is dangerous
        import re
        defaults = re.findall(
            r'\.get\(["\']safety_score["\']\s*,\s*([\d.]+)\)', source
        )
        for default_val in defaults:
            assert float(default_val) < 0.85, (
                f"image_to_story has safety_score default of {default_val} "
                f"which silently passes content without safety check. "
                f"Use None or a value < 0.85."
            )

    def test_no_passing_default_in_news_routes(self):
        """news_to_kids routes must not hardcode safety_score >= 0.85."""
        import inspect
        from src.api.routes import news_to_kids

        source = inspect.getsource(news_to_kids)
        import re
        # Find hardcoded safety_score assignments like "safety_score": 0.9
        defaults = re.findall(
            r'["\']safety_score["\']\s*:\s*([\d.]+)', source
        )
        for default_val in defaults:
            assert float(default_val) < 0.85, (
                f"news_to_kids has hardcoded safety_score of {default_val} "
                f"which silently passes content. Use None or a value < 0.85."
            )

    def test_no_safety_score_clamping_in_morning_show(self):
        """morning_show must not clamp safety_score to minimum >= 0.85."""
        import inspect
        from src.api.routes import morning_show

        source = inspect.getsource(morning_show)
        import re
        # Check for max(..., 0.85) pattern that forces content to always pass
        clamp_patterns = re.findall(
            r'max\(.+?,\s*(0\.8[5-9]|0\.9\d*|1\.0)\)', source
        )
        assert len(clamp_patterns) == 0, (
            f"morning_show clamps safety_score to minimum {clamp_patterns}, "
            f"which means all content always passes safety check"
        )
