"""Unit tests for the Sora-backed video generation MCP tool.

Regression guard for the bug where generate_painting_video called
client.images.generate(image=...), which raises
"Images.generate() got an unexpected keyword argument 'image'" — that
endpoint accepts no image input and returns stills, not video.
"""

import json

import pytest

from backend.src.mcp_servers import video_generator_server as vgs


class _FakeBinaryContent:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.written_to = None

    def write_to_file(self, path):
        self.written_to = str(path)
        with open(path, "wb") as f:
            f.write(self._payload)


class _FakeVideo:
    def __init__(self, status="completed", error=None):
        self.id = "vid_123"
        self.status = status
        self.error = error


class _FakeVideos:
    def __init__(self, video):
        self._video = video
        self.create_calls = []
        self.download_calls = []

    def create_and_poll(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._video

    def download_content(self, video_id, variant="video"):
        self.download_calls.append((video_id, variant))
        return _FakeBinaryContent(b"fake-mp4-bytes")


class _FakeImages:
    def generate(self, **kwargs):  # pragma: no cover - must never be called
        raise AssertionError("images.generate must not be used for video")


class _FakeOpenAI:
    last_instance = None

    def __init__(self, api_key=None, video=None):
        self.api_key = api_key
        self.videos = _FakeVideos(video or _FakeVideo())
        self.images = _FakeImages()
        _FakeOpenAI.last_instance = self


def _patch_openai(monkeypatch, video=None):
    def factory(api_key=None):
        return _FakeOpenAI(api_key=api_key, video=video)

    monkeypatch.setattr(vgs, "OpenAI", factory)


@pytest.mark.parametrize(
    "requested,expected",
    [(4, "4"), (8, "8"), (12, "12"), (10, "8"), (1, "4"), (100, "12")],
)
def test_nearest_supported_duration_snaps_to_sora_lengths(requested, expected):
    assert vgs.nearest_supported_duration(requested) == expected


@pytest.mark.asyncio
async def test_generate_painting_video_uses_sora_videos_api(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.setattr(vgs, "get_video_output_path", lambda: str(tmp_path))
    monkeypatch.setattr(vgs, "save_job_status", lambda *_a, **_k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _patch_openai(monkeypatch)

    result = await vgs.generate_painting_video(
        {
            "image_path": str(image_path),
            "style": "gentle_animation",
            "duration_seconds": 10,
            "story_id": "story-1",
        }
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is True
    assert payload["status"] == "completed"

    client = _FakeOpenAI.last_instance
    # The bug path (images.generate) must never run.
    assert client.videos.create_calls, "expected videos.create_and_poll to be called"
    call = client.videos.create_calls[0]
    assert call["model"] == "sora-2"
    assert call["seconds"] == "8"  # 10s request snapped to nearest Sora length
    assert "input_reference" in call  # painting passed as a reference, not a kwarg
    assert client.videos.download_calls == [("vid_123", "video")]

    # Video bytes were written to disk at the advertised path.
    written = tmp_path / payload["video_filename"]
    assert written.exists() and written.read_bytes() == b"fake-mp4-bytes"


@pytest.mark.asyncio
async def test_generate_painting_video_fails_fast_on_incomplete_job(
    monkeypatch, tmp_path
):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.setattr(vgs, "get_video_output_path", lambda: str(tmp_path))
    monkeypatch.setattr(vgs, "save_job_status", lambda *_a, **_k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _patch_openai(monkeypatch, video=_FakeVideo(status="failed", error="moderation"))

    result = await vgs.generate_painting_video(
        {
            "image_path": str(image_path),
            "style": "playful",
            "duration_seconds": 8,
            "story_id": "story-1",
        }
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is False
    assert payload["status"] == "failed"
    assert "failed" in payload["error"]
