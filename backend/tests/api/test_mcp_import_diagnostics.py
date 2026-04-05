"""
Tests for MCP import failure diagnostics (#183)

Verify that:
1. Import failures are logged with module name and exception
2. MCP_SERVER_STATUS tracks loaded vs failed servers
3. Health endpoint reports MCP server availability
"""

import importlib
import logging
import types
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport


class TestMCPImportLogging:
    """Import failures must be logged at WARNING with module + exception."""

    def test_successful_import_tracked(self):
        """Successfully imported MCP servers appear as 'ok' in status dict."""
        # Re-import to get fresh status
        import backend.src.mcp_servers as pkg

        importlib.reload(pkg)

        # At minimum, the status dict should exist and have entries
        assert hasattr(pkg, "MCP_SERVER_STATUS")
        assert isinstance(pkg.MCP_SERVER_STATUS, dict)
        # All servers must be tracked
        expected_servers = {
            "vision_analysis_server",
            "vector_search_server",
            "safety_check_server",
            "tts_generator_server",
            "video_generator_server",
            "image_style_server",
            "web_search_server",
        }
        assert expected_servers == set(pkg.MCP_SERVER_STATUS.keys())

    def test_failed_import_logged_with_module_and_exception(self, caplog):
        """When an MCP server import fails, WARNING log includes module name and exception."""
        # Sabotage one import by making it raise
        bad_module = types.ModuleType("backend.src.mcp_servers.vision_analysis_server")
        bad_module.__spec__ = None  # force ImportError on reload

        with (
            patch.dict(
                "sys.modules",
                {"backend.src.mcp_servers.vision_analysis_server": None},
            ),
            caplog.at_level(logging.WARNING, logger="backend.src.mcp_servers"),
        ):
            import backend.src.mcp_servers as pkg

            importlib.reload(pkg)

        # Should have logged at WARNING or ERROR mentioning the module name
        relevant_messages = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        assert any("vision_analysis_server" in m for m in relevant_messages), (
            f"Expected log mentioning 'vision_analysis_server', got: {relevant_messages}"
        )

    def test_failed_import_status_is_error(self):
        """Failed imports are recorded as 'error: ...' in MCP_SERVER_STATUS."""
        with patch.dict(
            "sys.modules",
            {"backend.src.mcp_servers.vision_analysis_server": None},
        ):
            import backend.src.mcp_servers as pkg

            importlib.reload(pkg)

        assert pkg.MCP_SERVER_STATUS["vision_analysis_server"].startswith("error:")


@pytest.mark.asyncio
class TestHealthEndpointMCPStatus:
    """Health endpoint must include mcp_servers in services."""

    async def test_health_includes_mcp_servers(self):
        """GET /health response includes mcp_servers key."""
        from backend.src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        result = response.json()
        services = result["services"]
        assert "mcp_servers" in services

    async def test_health_mcp_servers_shows_individual_status(self):
        """mcp_servers value is a dict with per-server status."""
        from backend.src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        result = response.json()
        mcp_status = result["services"]["mcp_servers"]
        assert isinstance(mcp_status, dict)
        assert "vision_analysis_server" in mcp_status
        assert "safety_check_server" in mcp_status

    async def test_health_degraded_when_mcp_server_fails(self):
        """Overall status should be degraded if any MCP server failed to load."""
        import backend.src.mcp_servers as pkg

        original_status = dict(pkg.MCP_SERVER_STATUS)
        try:
            pkg.MCP_SERVER_STATUS["vision_analysis_server"] = "error: ModuleNotFoundError"

            from backend.src.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

            result = response.json()
            assert result["status"] == "degraded"
        finally:
            pkg.MCP_SERVER_STATUS.update(original_status)
