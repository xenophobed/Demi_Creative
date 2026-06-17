from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.src.api.routes import kids_daily


@pytest.mark.asyncio
async def test_generate_illustrations_uploads_placeholder_via_storage(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(kids_daily, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(kids_daily, "_is_live_illustration_enabled", lambda: False)

    async def fake_safe_description(description: str, age_group: str) -> str:
        assert age_group == "6-8"
        return description

    storage = SimpleNamespace(
        upload=AsyncMock(return_value="https://cdn.example.com/uploads/kids_daily_ep-1_0.svg")
    )
    monkeypatch.setattr(kids_daily, "_safe_illustration_description", fake_safe_description)
    monkeypatch.setattr(kids_daily, "storage", storage)

    illustrations = await kids_daily._generate_illustrations(
        episode_id="ep-1",
        kid_title="Science Time",
        topic="science",
        age_group="6-8",
    )

    assert len(illustrations) == 1
    assert illustrations[0].url == "https://cdn.example.com/uploads/kids_daily_ep-1_0.svg"
    assert (tmp_path / "kids_daily_ep-1_0.svg").exists()
    storage.upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_kids_daily_svg_rebuilds_from_story_metadata(monkeypatch):
    monkeypatch.setattr(
        kids_daily.story_repo,
        "get_by_id",
        AsyncMock(
            return_value={
                "story_type": "kids_daily",
                "analysis": {
                    "kid_title": "Ocean Rescue",
                    "category": "science",
                },
            }
        ),
    )

    svg = await kids_daily.get_legacy_kids_daily_svg_for_upload(
        "kids_daily_713dd9f8-5bef-4ad5-a4b4-bda6ed7f3505_0.svg"
    )

    assert svg is not None
    assert "Ocean Rescue" in svg
    assert "Science scene 1" in svg


@pytest.mark.asyncio
async def test_legacy_kids_daily_svg_returns_none_when_story_missing(monkeypatch):
    monkeypatch.setattr(
        kids_daily.story_repo,
        "get_by_id",
        AsyncMock(return_value=None),
    )

    svg = await kids_daily.get_legacy_kids_daily_svg_for_upload(
        "kids_daily_missing_0.svg"
    )

    assert svg is None
