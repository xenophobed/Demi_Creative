"""
API tests for artifact endpoint auth guards and response redaction (#192).

Tests:
- Mutation endpoints return 401 without auth token
- Read endpoints with auth return expected data
- Public responses do not contain internal fields (content_hash, artifact_path, created_by_step_id)
"""

import uuid
import pytest

from backend.src.main import app
from backend.src.api.deps import get_current_user
from backend.src.services.database import db_manager

from httpx import AsyncClient, ASGITransport

# Internal fields that MUST NOT appear in public responses
INTERNAL_FIELDS = {"content_hash", "artifact_path", "created_by_step_id"}


# ---------------------------------------------------------------------------
# Helper: client without auth override (simulates unauthenticated requests)
# ---------------------------------------------------------------------------


@pytest.fixture
def noauth_client():
    """Client that simulates unauthenticated requests (auth raises 401)."""
    from fastapi import HTTPException, status

    async def _reject_auth():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    app.dependency_overrides[get_current_user] = _reject_auth
    client = AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )
    yield client
    # Restore test bypass
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 1. Mutation endpoints return 401 without auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestArtifactAuthGuards:
    """Verify that all mutation/read endpoints reject unauthenticated requests."""

    async def test_create_artifact_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.post(
                "/api/v1/artifacts",
                json={"artifact_type": "text"},
            )
            assert resp.status_code == 401

    async def test_update_state_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.patch(
                "/api/v1/artifacts/fake-id/state?new_state=published"
            )
            assert resp.status_code == 401

    async def test_publish_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.post("/api/v1/artifacts/fake-id/publish")
            assert resp.status_code == 401

    async def test_create_run_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.post(
                "/api/v1/artifacts/runs",
                json={
                    "story_id": "s1",
                    "workflow_type": "image_to_story",
                },
            )
            assert resp.status_code == 401

    async def test_link_story_artifact_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.post(
                "/api/v1/artifacts/stories/s1/artifacts",
                json={
                    "story_id": "s1",
                    "artifact_id": "a1",
                    "role": "cover",
                },
            )
            assert resp.status_code == 401

    async def test_get_artifact_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.get("/api/v1/artifacts/fake-id")
            assert resp.status_code == 401

    async def test_list_artifacts_requires_auth(self, noauth_client):
        async with noauth_client as client:
            resp = await client.get("/api/v1/artifacts")
            assert resp.status_code == 401

    async def test_health_remains_public(self, noauth_client):
        """The /health endpoint must remain accessible without auth."""
        async with noauth_client as client:
            resp = await client.get("/api/v1/artifacts/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# 2. Authenticated read returns expected data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestArtifactAuthenticatedRead:
    """Verify that authenticated requests succeed and return expected data."""

    async def test_list_artifacts_with_auth(self, test_client):
        async with test_client as client:
            resp = await client.get("/api/v1/artifacts")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    async def test_create_and_get_artifact_with_auth(self, test_client):
        async with test_client as client:
            create_resp = await client.post(
                "/api/v1/artifacts",
                json={"artifact_type": "text", "description": "test artifact"},
            )
            assert create_resp.status_code == 200
            body = create_resp.json()
            artifact_id = body["artifact_id"]

            # GET should return the artifact
            get_resp = await client.get(
                f"/api/v1/artifacts/{artifact_id}"
            )
            assert get_resp.status_code == 200
            assert get_resp.json()["artifact_id"] == artifact_id


# ---------------------------------------------------------------------------
# 3. Public responses must NOT contain internal fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestArtifactResponseRedaction:
    """Verify internal fields are stripped from public API responses."""

    async def test_create_response_excludes_internal_fields(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/api/v1/artifacts",
                json={"artifact_type": "text", "description": "redaction test"},
            )
            assert resp.status_code == 200
            body = resp.json()
            for field in INTERNAL_FIELDS:
                assert field not in body, (
                    f"Internal field '{field}' leaked in create response"
                )

    async def test_get_response_excludes_internal_fields(self, test_client):
        async with test_client as client:
            # Create an artifact first
            create_resp = await client.post(
                "/api/v1/artifacts",
                json={"artifact_type": "text"},
            )
            artifact_id = create_resp.json()["artifact_id"]

            # GET it
            resp = await client.get(f"/api/v1/artifacts/{artifact_id}")
            assert resp.status_code == 200
            body = resp.json()
            for field in INTERNAL_FIELDS:
                assert field not in body, (
                    f"Internal field '{field}' leaked in get response"
                )

    async def test_list_response_excludes_internal_fields(self, test_client):
        async with test_client as client:
            # Create one artifact so list is non-empty
            await client.post(
                "/api/v1/artifacts",
                json={"artifact_type": "text"},
            )

            resp = await client.get("/api/v1/artifacts?state=intermediate")
            assert resp.status_code == 200
            artifacts = resp.json()
            assert len(artifacts) > 0, "Expected at least one artifact"
            for artifact in artifacts:
                for field in INTERNAL_FIELDS:
                    assert field not in artifact, (
                        f"Internal field '{field}' leaked in list response"
                    )
