"""
Tests for degraded-generation metadata persistence (#179).

Verifies that fallback/mock content is persisted with explicit
is_degraded and degraded_reason fields in both non-streaming and
streaming code paths, for both news-to-kids and morning show pipelines.
"""

import json
import uuid

import pytest


@pytest.mark.asyncio
class TestNewsDegradedMetadata:
    """News-to-kids fallback content must carry degradation metadata."""

    async def test_non_streaming_persists_degradation_fields(self, test_client):
        """Non-streaming /convert saves is_degraded + degraded_reason in analysis."""
        child_id = f"child-deg-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/kids-daily/convert",
                json={
                    "child_id": child_id,
                    "age_group": "6-8",
                    "news_text": "Scientists discovered a new butterfly species in the Amazon.",
                    "category": "science",
                },
            )
            assert response.status_code == 200
            data = response.json()

            # Response exposes degradation status
            assert "is_degraded" in data
            assert "degraded_reason" in data

            # Fetch persisted record and verify analysis has the fields
            conversion_id = data["conversion_id"]
            get_resp = await client.get(
                f"/api/v1/kids-daily/conversion/{conversion_id}"
            )
            assert get_resp.status_code == 200
            stored = get_resp.json()
            assert "is_degraded" in stored
            assert "degraded_reason" in stored

    async def test_streaming_persists_degradation_fields(self, test_client):
        """Streaming /convert/stream must also persist degradation metadata."""
        child_id = f"child-deg-s-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/kids-daily/convert/stream",
                json={
                    "child_id": child_id,
                    "age_group": "6-8",
                    "news_text": "A robot dog learned to fetch a ball for kids.",
                    "category": "technology",
                },
            )
            assert response.status_code == 200
            body = response.text

            # Extract conversion_id from SSE result event
            conversion_id = None
            for line in body.split("\n"):
                if line.startswith("data:") and "conversion_id" in line:
                    event_data = json.loads(line[len("data:"):])
                    conversion_id = event_data.get("conversion_id")
                    break

            assert conversion_id is not None, "Stream result must include conversion_id"

            # Verify stored record has degradation metadata
            get_resp = await client.get(
                f"/api/v1/kids-daily/conversion/{conversion_id}"
            )
            assert get_resp.status_code == 200
            stored = get_resp.json()
            assert "is_degraded" in stored
            assert "degraded_reason" in stored
            # In test env, mock is used → must be marked degraded
            assert stored["is_degraded"] is True
            assert stored["degraded_reason"] is not None


@pytest.mark.asyncio
class TestMorningShowDegradedMetadata:
    """Morning show fallback content must carry degradation metadata."""

    async def test_episode_persists_degradation_fields(self, test_client):
        """Generated episode stores is_degraded + degraded_reason in analysis."""
        child_id = f"child-ms-deg-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/kids-daily/generate",
                json={
                    "child_id": child_id,
                    "age_group": "6-8",
                    "news_text": "A friendly whale visited a harbour and played with boats.",
                },
            )
            assert response.status_code == 200
            data = response.json()

            episode = data["episode"]
            metadata = data["metadata"]

            # Episode exposes degradation status
            assert "is_degraded" in episode
            assert "degraded_reason" in episode

            # Metadata contains degradation info
            assert "is_degraded" in metadata
            assert "used_mock" in metadata

            # Fetch persisted record
            episode_id = episode["episode_id"]
            get_resp = await client.get(
                f"/api/v1/kids-daily/episode/{episode_id}"
            )
            assert get_resp.status_code == 200
            stored = get_resp.json()
            assert "is_degraded" in stored
            assert "degraded_reason" in stored


@pytest.mark.asyncio
class TestProvenanceArtifactDegradedMetadata:
    """Provenance artifacts from degraded runs must carry degradation info in metadata."""

    async def test_news_provenance_artifact_has_degradation_custom_metadata(self, test_client):
        """News conversion provenance artifacts include is_degraded in custom metadata."""
        child_id = f"child-prov-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            response = await client.post(
                "/api/v1/kids-daily/convert",
                json={
                    "child_id": child_id,
                    "age_group": "9-12",
                    "news_text": "Engineers built a bridge using recycled materials.",
                    "category": "technology",
                },
            )
            assert response.status_code == 200
            conversion_id = response.json()["conversion_id"]

            # Query provenance artifacts via admin endpoint
            lineage_resp = await client.get(
                f"/api/v1/admin/artifacts/stories/{conversion_id}/lineage"
            )
            if lineage_resp.status_code == 200:
                lineage = lineage_resp.json()
                # Find text artifact and verify custom metadata
                for artifact in lineage.get("artifacts", []):
                    meta = artifact.get("metadata") or {}
                    custom = meta.get("custom") or {}
                    if artifact.get("artifact_type") == "text":
                        assert "is_degraded" in custom, (
                            "Text artifact must include is_degraded in custom metadata"
                        )
                        assert "degraded_reason" in custom
