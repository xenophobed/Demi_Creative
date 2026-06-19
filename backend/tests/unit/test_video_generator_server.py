"""Unit tests for the Replicate-backed video generation MCP tool.

Cheapest-everywhere (best-value) policy: video uses a low-cost, speed-optimized
Replicate image-to-video model (default ``wan-video/wan-2.2-i2v-fast`` @ 480p)
instead of the expensive, slow OpenAI Sora. These tests lock the provider call
shape, the env override, and the fail-fast error path.
"""

import json
from pathlib import Path

import pytest

from backend.src.mcp_servers import video_generator_server as vgs
from backend.src.paths import VIDEO_DIR, VIDEO_JOBS_DIR


class _FakeFileOutput:
    """Mimics replicate's FileOutput return value (has ``.read()``)."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeReplicate:
    """Stand-in for the replicate module: ``.Client(...).run(...)``."""

    def __init__(self, output=None, raises=None):
        self._output = output
        self._raises = raises
        self.run_calls = []

    def Client(self, api_token=None, timeout=None):
        outer = self

        class _Client:
            def run(self, model, input=None, use_file_output=None):
                outer.run_calls.append({"model": model, "input": input})
                if outer._raises:
                    raise outer._raises
                return outer._output

        return _Client()


class _FakeHttpx:
    """Minimal httpx stand-in for the URL-output download branch."""

    class _Resp:
        content = b"url-mp4-bytes"

    @staticmethod
    def get(*_a, **_k):
        return _FakeHttpx._Resp()

    @staticmethod
    def Timeout(*_a, **_k):
        return None


@pytest.mark.parametrize(
    "requested,expected",
    [(4, 4), (8, 8), (10, 8), (1, 4), (100, 8), ("6", 6), (None, 5)],
)
def test_normalize_duration_clamps_to_cost_window(requested, expected):
    assert vgs.normalize_duration_seconds(requested) == expected


def test_video_paths_default_to_backend_data_dirs(monkeypatch):
    monkeypatch.delenv("VIDEO_OUTPUT_PATH", raising=False)

    assert Path(vgs.get_video_output_path()) == VIDEO_DIR
    assert Path(vgs.get_video_jobs_path()) == VIDEO_JOBS_DIR


def test_load_job_status_reads_legacy_root_job(monkeypatch, tmp_path):
    primary = tmp_path / "backend_jobs"
    legacy = tmp_path / "legacy_jobs"
    legacy.mkdir()
    (legacy / "job-1.json").write_text(
        json.dumps({"job_id": "job-1", "story_id": "story-1"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(vgs, "get_video_jobs_path", lambda: str(primary))
    monkeypatch.setattr(vgs, "_LEGACY_VIDEO_JOBS_DIR", legacy)

    assert vgs.load_job_status("job-1") == {
        "job_id": "job-1",
        "story_id": "story-1",
    }


@pytest.mark.asyncio
async def test_generate_painting_video_uses_replicate_i2v(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.setattr(vgs, "get_video_output_path", lambda: str(tmp_path))
    monkeypatch.setattr(vgs, "save_job_status", lambda *_a, **_k: None)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.delenv("VIDEO_MODEL", raising=False)
    monkeypatch.delenv("VIDEO_RESOLUTION", raising=False)

    fake = _FakeReplicate(output=_FakeFileOutput(b"fake-mp4-bytes"))
    monkeypatch.setattr(vgs, "_replicate", fake)

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

    assert fake.run_calls, "expected replicate.run to be called"
    call = fake.run_calls[0]
    assert call["model"] == "wan-video/wan-2.2-i2v-fast"  # cheapest default
    # Painting is the conditioning frame; the per-style prompt drives motion.
    assert "image" in call["input"]
    assert call["input"]["prompt"]  # non-empty style prompt
    assert call["input"]["resolution"] == "480p"  # cheap tier by default

    # Video bytes were written to disk at the advertised path.
    written = tmp_path / payload["video_filename"]
    assert written.exists() and written.read_bytes() == b"fake-mp4-bytes"


@pytest.mark.asyncio
async def test_video_model_and_resolution_are_env_overridable(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.setattr(vgs, "get_video_output_path", lambda: str(tmp_path))
    monkeypatch.setattr(vgs, "save_job_status", lambda *_a, **_k: None)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setenv("VIDEO_MODEL", "some/other-model")
    monkeypatch.setenv("VIDEO_RESOLUTION", "720p")

    fake = _FakeReplicate(output="https://replicate.delivery/out.mp4")
    monkeypatch.setattr(vgs, "_replicate", fake)
    monkeypatch.setattr(vgs, "_httpx", _FakeHttpx)

    result = await vgs.generate_painting_video(
        {
            "image_path": str(image_path),
            "style": "playful",
            "duration_seconds": 6,
            "story_id": "s2",
        }
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is True
    call = fake.run_calls[0]
    assert call["model"] == "some/other-model"
    assert call["input"]["resolution"] == "720p"
    # URL output goes through the httpx download branch.
    written = tmp_path / payload["video_filename"]
    assert written.read_bytes() == b"url-mp4-bytes"


@pytest.mark.asyncio
async def test_generate_painting_video_fails_fast_on_provider_error(
    monkeypatch, tmp_path
):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.setattr(vgs, "get_video_output_path", lambda: str(tmp_path))
    monkeypatch.setattr(vgs, "save_job_status", lambda *_a, **_k: None)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")

    fake = _FakeReplicate(raises=Exception("moderation rejected"))
    monkeypatch.setattr(vgs, "_replicate", fake)

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


@pytest.mark.asyncio
async def test_generate_painting_video_requires_replicate_token(monkeypatch, tmp_path):
    image_path = tmp_path / "drawing.png"
    image_path.write_bytes(b"fake-png")
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    # SDKs present but no token → clear, non-crashing error.
    monkeypatch.setattr(vgs, "_replicate", _FakeReplicate(output=_FakeFileOutput(b"x")))
    monkeypatch.setattr(vgs, "_httpx", _FakeHttpx)

    result = await vgs.generate_painting_video(
        {
            "image_path": str(image_path),
            "style": "playful",
            "duration_seconds": 8,
            "story_id": "s",
        }
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is False
    assert "REPLICATE_API_TOKEN" in payload["error"]
