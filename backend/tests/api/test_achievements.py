"""Achievement API contract tests (#536)."""

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_list_achievements_returns_server_owned_definitions(test_client):
    response = await test_client.get("/api/v1/achievements/api_child_defs")

    assert response.status_code == 200
    data = response.json()
    assert data["child_id"] == "api_child_defs"
    assert data["total"] == 0
    assert data["available_definitions"]
    assert {
        "achievement_id",
        "title",
        "description",
        "icon",
        "category",
        "award_event",
    }.issubset(data["available_definitions"][0])


@pytest.mark.asyncio
async def test_award_achievement_is_idempotent(test_client):
    child_id = f"api_child_{uuid4().hex}"
    payload = {
        "child_id": child_id,
        "achievement_id": "first_image_story",
    }

    first = await test_client.post("/api/v1/achievements/award", json=payload)
    second = await test_client.post("/api/v1/achievements/award", json=payload)
    listed = await test_client.get(f"/api/v1/achievements/{child_id}")

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["achievement_id"] == "first_image_story"


@pytest.mark.asyncio
async def test_award_rejects_unknown_achievement(test_client):
    response = await test_client.post(
        "/api/v1/achievements/award",
        json={
            "child_id": "api_child_unknown",
            "achievement_id": "client_made_badge",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown achievement"
