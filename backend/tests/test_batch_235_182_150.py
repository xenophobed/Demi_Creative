"""Tests for batch fix: #235 (streaming char sync), #182 (video fail-fast), #150 (voice cloning).

Each class covers one issue's acceptance criteria.
"""

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# #235 — Streaming character sync
# ============================================================================

class TestStreamingCharacterSync:
    """Streaming path must call character_repo.upsert_character for detected characters."""

    def test_streaming_route_contains_character_sync_code(self):
        """Verify the streaming event_generator has character sync logic."""
        source = Path(__file__).resolve().parents[1] / "src" / "api" / "routes" / "image_to_story.py"
        code = source.read_text(encoding="utf-8")
        # Must contain #235 comment and upsert call in the streaming section
        assert "# Sync detected characters to characters table (#235)" in code
        assert "character_repo.upsert_character" in code

    def test_sync_and_streaming_both_have_character_upsert(self):
        """Both sync and streaming paths must call upsert_character."""
        source = Path(__file__).resolve().parents[1] / "src" / "api" / "routes" / "image_to_story.py"
        code = source.read_text(encoding="utf-8")
        # Count occurrences — should be at least 2 (sync #160 + streaming #235)
        count = code.count("character_repo.upsert_character")
        assert count >= 2, f"Expected >= 2 upsert calls (sync + streaming), found {count}"

    def test_streaming_character_extraction_uses_result_data(self):
        """Streaming path extracts characters from result_data.get('characters', [])."""
        source = Path(__file__).resolve().parents[1] / "src" / "api" / "routes" / "image_to_story.py"
        code = source.read_text(encoding="utf-8")
        # The streaming path should iterate result_data characters
        assert 'result_data.get("characters", [])' in code


# ============================================================================
# #182 — Video generation fail-fast
# ============================================================================

class TestVideoFailFast:
    """Video generation must fail fast instead of creating pending jobs with no worker."""

    @pytest.mark.asyncio
    async def test_generate_painting_video_fails_with_status_failed(self, tmp_path):
        """When the video provider fails, job status must be 'failed', not 'pending'."""
        from src.mcp_servers import video_generator_server as vgs
        from src.mcp_servers.video_generator_server import generate_painting_video, load_job_status

        # Create a dummy image
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        # Simulate Replicate i2v failure → must fail fast.
        fake_replicate = MagicMock()
        fake_replicate.Client.return_value.run.side_effect = RuntimeError(
            "video model not available"
        )

        with patch.dict("os.environ", {"REPLICATE_API_TOKEN": "r8_test"}):
            with patch.object(vgs, "_replicate", fake_replicate):
                result = await generate_painting_video({
                    "image_path": str(img),
                    "style": "gentle_animation",
                    "duration_seconds": 10,
                    "story_id": "test-story",
                })

        result_data = json.loads(result["content"][0]["text"])
        assert result_data["status"] == "failed", "Must fail fast, not create pending job"
        assert result_data["success"] is False

        # Verify persisted job is also failed
        job = load_job_status(result_data["job_id"])
        assert job is not None
        assert job["status"] == "failed"
        assert job["error"] is not None

    def test_no_pending_status_in_generate_function(self):
        """The generate_painting_video function must not create 'pending' status jobs."""
        source = Path(__file__).resolve().parents[1] / "src" / "mcp_servers" / "video_generator_server.py"
        code = source.read_text(encoding="utf-8")
        # The exception handler should use "failed", not "pending"
        # Check the except block specifically (not the check_video_status function)
        lines = code.split("\n")
        in_except = False
        for line in lines:
            if "except Exception as e:" in line:
                in_except = True
            if in_except and '"status": "pending"' in line:
                pytest.fail("Found 'pending' status in exception handler — should be 'failed' (#182)")
            if in_except and "async def" in line:
                break  # Past the function


# ============================================================================
# #150 — Voice cloning
# ============================================================================

class TestVoiceCloneSchema:
    """Cloned voices table must exist in schema."""

    def test_cloned_voices_table_defined(self):
        from src.services.database.schema import CLONED_VOICES_TABLE
        assert "cloned_voices" in CLONED_VOICES_TABLE
        assert "voice_id" in CLONED_VOICES_TABLE
        assert "user_id" in CLONED_VOICES_TABLE
        assert "replicate_voice_id" in CLONED_VOICES_TABLE
        assert "voice_file_hash" in CLONED_VOICES_TABLE
        assert "is_active" in CLONED_VOICES_TABLE

    def test_schema_init_creates_table(self):
        """init_schema must include cloned_voices table creation."""
        source = Path(__file__).resolve().parents[1] / "src" / "services" / "database" / "schema.py"
        code = source.read_text(encoding="utf-8")
        assert "CLONED_VOICES_TABLE" in code
        assert "# Create cloned voices table (#150)" in code


class TestVoiceCloneValidation:
    """Voice file validation must enforce format, size, and content rules."""

    def test_valid_mp3(self):
        from src.services.voice_service import validate_voice_file
        assert validate_voice_file("sample.mp3", 1024) is None

    def test_valid_wav(self):
        from src.services.voice_service import validate_voice_file
        assert validate_voice_file("sample.wav", 5 * 1024 * 1024) is None

    def test_valid_m4a(self):
        from src.services.voice_service import validate_voice_file
        assert validate_voice_file("sample.m4a", 100) is None

    def test_reject_unsupported_format(self):
        from src.services.voice_service import validate_voice_file
        error = validate_voice_file("sample.ogg", 1024)
        assert error is not None
        assert "Unsupported format" in error

    def test_reject_oversized_file(self):
        from src.services.voice_service import validate_voice_file
        error = validate_voice_file("sample.mp3", 25 * 1024 * 1024)
        assert error is not None
        assert "too large" in error

    def test_reject_empty_file(self):
        from src.services.voice_service import validate_voice_file
        error = validate_voice_file("sample.mp3", 0)
        assert error is not None
        assert "empty" in error

    def test_reject_too_short_duration(self):
        from src.services import voice_service as vs
        with patch.object(vs, "get_audio_duration_seconds", return_value=5.0):
            error = vs.validate_voice_duration("sample.mp3")
        assert error is not None and "too short" in error

    def test_reject_too_long_duration(self):
        from src.services import voice_service as vs
        with patch.object(vs, "get_audio_duration_seconds", return_value=400.0):
            error = vs.validate_voice_duration("sample.mp3")
        assert error is not None and "too long" in error

    def test_accept_valid_duration(self):
        from src.services import voice_service as vs
        with patch.object(vs, "get_audio_duration_seconds", return_value=30.0):
            assert vs.validate_voice_duration("sample.mp3") is None

    def test_indeterminate_duration_allows_upload(self):
        # ffprobe unavailable / unprobeable → don't block; provider is final gate.
        from src.services import voice_service as vs
        with patch.object(vs, "get_audio_duration_seconds", return_value=None):
            assert vs.validate_voice_duration("sample.mp3") is None


class TestVoiceCloneService:
    """Voice cloning service must call Replicate and persist result."""

    @pytest.mark.asyncio
    async def test_clone_voice_missing_sdk(self):
        from src.services import voice_service
        with patch.object(voice_service, "_replicate_module", None):
            result = await voice_service.clone_voice(
                voice_file_path="/tmp/test.mp3",
                voice_file_data=b"fake",
                display_name="Test Voice",
                user_id="u1",
                child_id="c1",
            )
        assert result["success"] is False
        assert "not installed" in result["error"]

    @pytest.mark.asyncio
    async def test_clone_voice_missing_token(self):
        from src.services import voice_service
        mock_replicate = MagicMock()
        with patch.object(voice_service, "_replicate_module", mock_replicate):
            with patch.dict("os.environ", {}, clear=True):
                result = await voice_service.clone_voice(
                    voice_file_path="/tmp/test.mp3",
                    voice_file_data=b"fake",
                    display_name="Test Voice",
                    user_id="u1",
                    child_id="c1",
                )
        assert result["success"] is False
        assert "REPLICATE_API_TOKEN" in result["error"]


class TestVoiceCloneRepository:
    """Voice repository contract tests."""

    def test_voice_repo_importable(self):
        from src.services.database import voice_repo
        assert voice_repo is not None

    def test_voice_repo_has_crud_methods(self):
        from src.services.database.voice_repository import VoiceRepository
        repo = VoiceRepository()
        assert hasattr(repo, "create_voice")
        assert hasattr(repo, "get_voice")
        assert hasattr(repo, "get_voices_for_user")
        assert hasattr(repo, "get_voices_for_child")
        assert hasattr(repo, "deactivate_voice")


class TestVoiceCloneAPI:
    """Voice API route contract tests."""

    def test_voice_route_registered(self):
        """Voice route must be registered in main app."""
        source = Path(__file__).resolve().parents[1] / "src" / "main.py"
        code = source.read_text(encoding="utf-8")
        assert "voice.router" in code

    def test_voice_route_has_endpoints(self):
        from src.api.routes.voice import router
        paths = [r.path for r in router.routes]
        assert "/clone" in paths or any("/clone" in p for p in paths)
