"""
Tests for Health Check API

健康检查 API 测试
"""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.src.main import app


@pytest.mark.asyncio
class TestHealthCheck:
    """健康检查测试"""

    async def test_root_endpoint(self):
        """测试根路径"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")

            assert response.status_code == 200
            result = response.json()

            assert "status" in result
            assert "version" in result
            assert "timestamp" in result
            assert "services" in result

            assert result["status"] in ["healthy", "degraded"]
            assert result["version"] == "1.0.0"

    async def test_health_endpoint(self):
        """Test health check endpoint"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

            assert response.status_code == 200
            result = response.json()

            assert "status" in result
            assert "version" in result
            assert "timestamp" in result
            assert "services" in result

            services = result["services"]
            assert "api" in services
            assert "session_manager" in services
            assert "environment" in services

            assert services["api"] == "running"

    async def test_health_status_values(self):
        """Test health status values"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

            assert response.status_code == 200
            result = response.json()

            assert result["status"] in ["healthy", "degraded", "unhealthy"]

            services = result["services"]
            valid_statuses = ["running", "degraded", "configured", "missing_keys"]

            for service, status in services.items():
                assert status in valid_statuses


@pytest.mark.asyncio
class TestAPIDocumentation:
    """API 文档测试"""

    async def test_openapi_json(self):
        """Test OpenAPI JSON is accessible"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/openapi.json")

            assert response.status_code == 200
            openapi_spec = response.json()

            assert "openapi" in openapi_spec
            assert "info" in openapi_spec
            assert "paths" in openapi_spec

            assert openapi_spec["info"]["title"] == "Creative Agent API"
            assert openapi_spec["info"]["version"] == "1.0.0"

    async def test_swagger_ui_accessible(self):
        """Test Swagger UI is accessible"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/docs")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    async def test_redoc_accessible(self):
        """Test ReDoc is accessible"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/redoc")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
