"""Achievement API contract tests (#536)."""

from uuid import uuid4

import pytest

from backend.src.services.achievement_service import FIRST_STORY
from backend.src.services.database import child_profile_repo, db_manager


async def _ensure_owned_child(child_id: str) -> None:
    existing = await child_profile_repo.get_for_user(
        "test_user", child_id, include_archived=True
    )
    if existing is not None:
        return

    await db_manager.execute(
        """
        INSERT OR IGNORE INTO users (
            user_id, username, email, password_hash, display_name,
            is_active, is_verified, role, consent_status,
            membership_tier, referral_code, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "test_user",
            "test_user",
            "test@example.com",
            "h",
            "Test User",
            1,
            1,
            "parent",
            "not_required",
            "free",
            "TESTUSER",
            "2026-05-24T00:00:00",
            "2026-05-24T00:00:00",
        ),
    )
    await db_manager.commit()
    await child_profile_repo.create(
        user_id="test_user",
        child_id=child_id,
        name="Test Child",
        age_group="6-8",
        is_default=True,
    )


@pytest.mark.asyncio
async def test_list_achievements_returns_server_owned_definitions(test_client):
    await _ensure_owned_child("api_child_defs")
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
        "achievement_id": FIRST_STORY,
    }
    await _ensure_owned_child(child_id)

    first = await test_client.post("/api/v1/achievements/award", json=payload)
    second = await test_client.post("/api/v1/achievements/award", json=payload)
    listed = await test_client.get(f"/api/v1/achievements/{child_id}")

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["achievement_id"] == FIRST_STORY


@pytest.mark.asyncio
async def test_award_rejects_unknown_achievement(test_client):
    await _ensure_owned_child("api_child_unknown")
    response = await test_client.post(
        "/api/v1/achievements/award",
        json={
            "child_id": "api_child_unknown",
            "achievement_id": "client_made_badge",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown achievement"
