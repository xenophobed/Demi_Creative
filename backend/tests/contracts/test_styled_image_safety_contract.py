"""
Contract tests for styled image safety validation (#273).

Verifies:
- UNSAFE_IMAGE_KEYWORDS list contains required flagged terms
- check_styled_image_safety returns safe=True for benign analysis
- check_styled_image_safety returns safe=False for analysis with flagged keywords
- Fallback to original image when styled image is unsafe
- Safety check result includes required fields (safe, reason, original_image_path, styled_image_path)
- validate_and_fallback returns styled path when safe
- validate_and_fallback returns original path when unsafe
- Safety failure is logged with full context
"""

import json
import logging
import pytest
from unittest.mock import AsyncMock, patch


class TestUnsafeImageKeywordsContract:
    """UNSAFE_IMAGE_KEYWORDS must cover key safety categories."""

    def test_keywords_list_exists(self):
        from backend.src.mcp_servers.image_style_server import UNSAFE_IMAGE_KEYWORDS
        assert isinstance(UNSAFE_IMAGE_KEYWORDS, (list, tuple, set, frozenset))
        assert len(UNSAFE_IMAGE_KEYWORDS) > 0

    def test_violence_keywords_present(self):
        from backend.src.mcp_servers.image_style_server import UNSAFE_IMAGE_KEYWORDS
        keywords_lower = {k.lower() for k in UNSAFE_IMAGE_KEYWORDS}
        violence_terms = {"violence", "weapon", "blood"}
        assert violence_terms.issubset(keywords_lower), (
            f"Missing violence keywords: {violence_terms - keywords_lower}"
        )

    def test_inappropriate_keywords_present(self):
        from backend.src.mcp_servers.image_style_server import UNSAFE_IMAGE_KEYWORDS
        keywords_lower = {k.lower() for k in UNSAFE_IMAGE_KEYWORDS}
        inappropriate_terms = {"nudity", "drug", "horror"}
        assert inappropriate_terms.issubset(keywords_lower), (
            f"Missing inappropriate keywords: {inappropriate_terms - keywords_lower}"
        )


class TestCheckStyledImageSafetyContract:
    """check_styled_image_safety must return correct safety verdicts."""

    def test_safe_analysis_returns_safe(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        safe_analysis = {
            "objects": ["tree", "sun", "house", "flowers"],
            "scene": "outdoor park",
            "mood": "happy",
            "colors": ["green", "yellow", "blue"],
            "story_potential": "A happy day in the park",
            "confidence_score": 0.95,
        }
        result = check_styled_image_safety(safe_analysis)
        assert result["safe"] is True
        assert result["reason"] is None or result["reason"] == ""

    def test_unsafe_analysis_with_violence_returns_unsafe(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        unsafe_analysis = {
            "objects": ["weapon", "sword", "shield"],
            "scene": "battlefield",
            "mood": "aggressive",
            "colors": ["red", "black"],
            "story_potential": "A violent battle scene",
            "confidence_score": 0.9,
        }
        result = check_styled_image_safety(unsafe_analysis)
        assert result["safe"] is False
        assert result["reason"]  # Must include a reason
        assert "weapon" in result["reason"].lower()

    def test_unsafe_analysis_with_horror_returns_unsafe(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        unsafe_analysis = {
            "objects": ["ghost", "skeleton"],
            "scene": "haunted house",
            "mood": "horror",
            "colors": ["black", "grey"],
            "story_potential": "A scary night",
            "confidence_score": 0.85,
        }
        result = check_styled_image_safety(unsafe_analysis)
        assert result["safe"] is False

    def test_result_has_required_fields(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        analysis = {"objects": ["cat"], "mood": "calm"}
        result = check_styled_image_safety(analysis)
        assert "safe" in result
        assert "reason" in result
        assert "flagged_keywords" in result

    def test_flagged_keywords_returned_on_unsafe(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        analysis = {
            "objects": ["knife", "blood"],
            "mood": "scary",
            "scene": "dark room",
        }
        result = check_styled_image_safety(analysis)
        assert result["safe"] is False
        assert len(result["flagged_keywords"]) > 0

    def test_empty_analysis_is_safe(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        result = check_styled_image_safety({})
        assert result["safe"] is True

    def test_keyword_matching_is_case_insensitive(self):
        from backend.src.mcp_servers.image_style_server import check_styled_image_safety

        analysis = {"objects": ["WEAPON", "Gun"], "mood": "Violence"}
        result = check_styled_image_safety(analysis)
        assert result["safe"] is False


class TestValidateAndFallbackContract:
    """validate_and_fallback must return correct image path based on safety."""

    @pytest.mark.asyncio
    async def test_returns_styled_path_when_safe(self):
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        safe_analysis = {
            "objects": ["tree", "sun"],
            "mood": "happy",
            "confidence_score": 0.95,
        }

        mock_vision = AsyncMock(return_value={
            "content": [{"type": "text", "text": json.dumps(safe_analysis)}]
        })

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            result = await validate_and_fallback(
                styled_image_path="data/styled/test_cartoon.jpg",
                original_image_path="data/uploads/test.png",
                child_age=7,
                theme="cartoon",
                session_id="test-session",
            )

        assert result["used_image_path"] == "data/styled/test_cartoon.jpg"
        assert result["safety_passed"] is True
        assert result["fell_back"] is False

    @pytest.mark.asyncio
    async def test_returns_original_path_when_unsafe(self):
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        unsafe_analysis = {
            "objects": ["weapon", "blood"],
            "mood": "violence",
            "confidence_score": 0.9,
        }

        mock_vision = AsyncMock(return_value={
            "content": [{"type": "text", "text": json.dumps(unsafe_analysis)}]
        })

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            result = await validate_and_fallback(
                styled_image_path="data/styled/test_cartoon.jpg",
                original_image_path="data/uploads/test.png",
                child_age=7,
                theme="cartoon",
                session_id="test-session",
            )

        assert result["used_image_path"] == "data/uploads/test.png"
        assert result["safety_passed"] is False
        assert result["fell_back"] is True

    @pytest.mark.asyncio
    async def test_returns_original_on_vision_error(self):
        """If vision analysis fails, fall back to original (fail-closed)."""
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        error_analysis = {"error": "Vision API failed", "objects": []}

        mock_vision = AsyncMock(return_value={
            "content": [{"type": "text", "text": json.dumps(error_analysis)}]
        })

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            result = await validate_and_fallback(
                styled_image_path="data/styled/test_cartoon.jpg",
                original_image_path="data/uploads/test.png",
                child_age=7,
                theme="cartoon",
                session_id="test-session",
            )

        # Fail-closed: if vision errors, discard styled image
        assert result["used_image_path"] == "data/uploads/test.png"
        assert result["fell_back"] is True

    @pytest.mark.asyncio
    async def test_returns_original_on_exception(self):
        """If vision analysis raises exception, fall back to original."""
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        mock_vision = AsyncMock(side_effect=Exception("API timeout"))

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            result = await validate_and_fallback(
                styled_image_path="data/styled/test_cartoon.jpg",
                original_image_path="data/uploads/test.png",
                child_age=7,
                theme="cartoon",
                session_id="test-session",
            )

        assert result["used_image_path"] == "data/uploads/test.png"
        assert result["fell_back"] is True

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self):
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        safe_analysis = {"objects": ["cat"], "mood": "calm", "confidence_score": 0.9}
        mock_vision = AsyncMock(return_value={
            "content": [{"type": "text", "text": json.dumps(safe_analysis)}]
        })

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            result = await validate_and_fallback(
                styled_image_path="data/styled/test.jpg",
                original_image_path="data/uploads/test.png",
                child_age=7,
                theme="cartoon",
                session_id="test-session",
            )

        required_fields = [
            "used_image_path", "safety_passed", "fell_back",
            "flagged_keywords", "reason",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_safety_failure_logs_warning(self, caplog):
        """Safety failure must log a warning with context."""
        from backend.src.mcp_servers.image_style_server import validate_and_fallback

        unsafe_analysis = {
            "objects": ["weapon"],
            "mood": "violence",
            "confidence_score": 0.9,
        }
        mock_vision = AsyncMock(return_value={
            "content": [{"type": "text", "text": json.dumps(unsafe_analysis)}]
        })

        with patch(
            "backend.src.mcp_servers.analyze_children_drawing",
            mock_vision,
        ):
            with caplog.at_level(logging.WARNING):
                await validate_and_fallback(
                    styled_image_path="data/styled/test_cartoon.jpg",
                    original_image_path="data/uploads/test.png",
                    child_age=7,
                    theme="cartoon",
                    session_id="test-session",
                )

        # Should log with context about the failure
        assert any("unsafe" in r.message.lower() or "safety" in r.message.lower()
                    for r in caplog.records), (
            f"Expected safety warning in logs, got: {[r.message for r in caplog.records]}"
        )
