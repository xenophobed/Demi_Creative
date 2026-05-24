import json
from datetime import datetime

import pytest
from fastapi import HTTPException, status

from backend.src.api.models import VideoJobRequest
from backend.src.api.routes import video
from backend.src.services.database.user_repository import UserData


def _user(user_id: str = "owner") -> UserData:
    return UserData(
        user_id=user_id,
        username=user_id,
        email=f"{user_id}@example.com",
        password_hash="hash",
        is_active=True,
        is_verified=True,
        created_at="",
        updated_at="",
    )


@pytest.mark.asyncio
async def test_generate_video_checks_story_owner_before_provider(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    called_provider = False

    async def fake_get_story_for_owner(story_id: str, user_id: str):
        assert story_id == "story-1"
        assert user_id == "owner"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    async def fake_generate_painting_video(_payload):
        nonlocal called_provider
        called_provider = True
        return {"content": [{"text": json.dumps({"success": True})}]}

    monkeypatch.setattr(video, "get_story_for_owner", fake_get_story_for_owner)
    monkeypatch.setattr(video, "generate_painting_video", fake_generate_painting_video)

    with pytest.raises(HTTPException) as exc:
        await video.generate_video(
            VideoJobRequest(story_id="story-1"),
            user=_user("owner"),
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert called_provider is False


@pytest.mark.asyncio
async def test_generate_video_unwraps_sdk_tool_handler(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")

    async def fake_get_story_for_owner(story_id: str, user_id: str):
        return {"story_id": story_id, "user_id": user_id, "image_path": str(image_path)}

    class FakeSdkTool:
        async def handler(self, payload):
            assert payload["story_id"] == "story-1"
            return {
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "success": True,
                                "job_id": "job-1",
                                "status": "pending",
                            }
                        )
                    }
                ]
            }

    monkeypatch.setattr(video, "get_story_for_owner", fake_get_story_for_owner)
    monkeypatch.setattr(video, "generate_painting_video", FakeSdkTool())

    result = await video.generate_video(
        VideoJobRequest(story_id="story-1"),
        user=_user("owner"),
    )

    assert result.job_id == "job-1"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_get_video_status_rejects_unowned_job_without_story_binding(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(video, "VIDEO_JOBS_DIR", tmp_path)
    (tmp_path / "job-1.json").write_text(
        json.dumps({"job_id": "job-1", "status": "completed"}),
        encoding="utf-8",
    )

    async def fake_check_video_status(_payload):
        raise AssertionError("status provider should not be called")

    monkeypatch.setattr(video, "check_video_status", fake_check_video_status)

    with pytest.raises(HTTPException) as exc:
        await video.get_video_status("job-1", user=_user("owner"))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc.value.detail == "Video job is not linked to an owned story"


@pytest.mark.asyncio
async def test_get_video_status_verifies_story_owner_before_returning_url(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(video, "VIDEO_JOBS_DIR", tmp_path)
    (tmp_path / "job-1.json").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "story_id": "story-1",
                "status": "completed",
                "created_at": datetime.now().isoformat(),
            }
        ),
        encoding="utf-8",
    )

    async def fake_get_story_for_owner(story_id: str, user_id: str):
        assert story_id == "story-1"
        assert user_id == "intruder"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    async def fake_check_video_status(_payload):
        raise AssertionError("status provider should not be called")

    monkeypatch.setattr(video, "get_story_for_owner", fake_get_story_for_owner)
    monkeypatch.setattr(video, "check_video_status", fake_check_video_status)

    with pytest.raises(HTTPException) as exc:
        await video.get_video_status("job-1", user=_user("intruder"))

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_video_status_returns_owned_completed_video_url(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(video, "VIDEO_JOBS_DIR", tmp_path)
    (tmp_path / "job-1.json").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "story_id": "story-1",
                "status": "completed",
                "combined_video_url": "/data/videos/combined.mp4",
                "created_at": "2026-05-20T10:00:00",
            }
        ),
        encoding="utf-8",
    )

    async def fake_get_story_for_owner(story_id: str, user_id: str):
        assert story_id == "story-1"
        assert user_id == "owner"
        return {"story_id": story_id, "child_id": "child-1"}

    async def fake_check_video_status(_payload):
        return {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "success": True,
                            "status": "completed",
                            "progress_percent": 100,
                            "video_url": "/data/videos/raw.mp4",
                            "created_at": "2026-05-20T10:00:00",
                            "completed_at": "2026-05-20T10:02:00",
                        }
                    )
                }
            ]
        }

    class NoopAchievementService:
        async def award_event_safely(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(video, "get_story_for_owner", fake_get_story_for_owner)
    monkeypatch.setattr(video, "check_video_status", fake_check_video_status)
    monkeypatch.setattr(video, "achievement_service", NoopAchievementService())

    result = await video.get_video_status("job-1", user=_user("owner"))

    assert result.status == "completed"
    assert result.video_url == "/data/videos/combined.mp4"
