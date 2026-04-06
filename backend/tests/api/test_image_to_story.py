"""
Tests for Image to Story API

画作转故事 API 单元测试
"""

import json
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.src.main import app


@pytest.fixture
def sample_image():
    """创建测试图片"""
    img = Image.new("RGB", (400, 300), color="lightblue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes


@pytest.mark.asyncio
class TestImageToStoryAPI:
    """画作转故事 API 测试"""

    async def test_upload_valid_image(self, sample_image, test_client):
        """测试上传有效图片 — uses agent mock fallback for test env."""
        async with test_client as client:
            files = {"image": ("drawing.png", sample_image, "image/png")}
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险",
                "voice": "nova",
                "enable_audio": "true",
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 201
            result = response.json()

            # Core fields
            assert "story_id" in result

            # Story text exists and has content
            assert "story" in result
            assert "text" in result["story"]
            assert len(result["story"]["text"]) > 0

            # Word count is positive
            assert "word_count" in result["story"]
            assert result["story"]["word_count"] > 0

            # Safety score present and in valid range
            assert "safety_score" in result
            assert 0.0 <= result["safety_score"] <= 1.0

            # Age group adaptation flag
            assert result["story"]["age_adapted"] is True

            # Educational value fields present
            assert "educational_value" in result
            edu = result["educational_value"]
            assert "themes" in edu
            assert "concepts" in edu
            assert isinstance(edu["themes"], list)
            assert isinstance(edu["concepts"], list)

    async def test_upload_invalid_file_type(self):
        """测试上传无效文件类型"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 创建文本文件
            text_file = BytesIO(b"This is not an image")

            files = {"image": ("test.txt", text_file, "text/plain")}
            data = {"child_id": "test_child_001", "age_group": "6-8"}

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 400
            assert "文件必须是图片类型" in response.json()["detail"]

    async def test_upload_too_large_file(self):
        """测试上传超大文件"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 创建超大图片（模拟）
            large_file = BytesIO(b"0" * (11 * 1024 * 1024))  # 11MB

            files = {"image": ("large.png", large_file, "image/png")}
            data = {"child_id": "test_child_001", "age_group": "6-8"}

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 413
            assert "文件大小超过限制" in response.json()["detail"]

    async def test_missing_required_fields(self, sample_image):
        """测试缺少必填字段"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            files = {"image": ("drawing.png", sample_image, "image/png")}
            data = {
                "child_id": "test_child_001"
                # 缺少 age_group
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 422
            error_response = response.json()
            assert error_response["error"] == "ValidationError"

    async def test_invalid_age_group(self, sample_image):
        """测试无效的年龄组"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            files = {"image": ("drawing.png", sample_image, "image/png")}
            data = {
                "child_id": "test_child_001",
                "age_group": "13-15",  # 无效年龄组
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 422

    async def test_too_many_interests(self, sample_image):
        """测试兴趣标签过多"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            files = {"image": ("drawing.png", sample_image, "image/png")}
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险,太空,科学,音乐,运动",  # 6个标签
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 400
            assert "兴趣标签最多5个" in response.json()["detail"]


@pytest.mark.asyncio
class TestImageToStoryResponseFormat:
    """响应格式测试 — uses agent mock fallback for test env."""

    async def test_response_structure(self, sample_image, test_client):
        """测试响应结构"""
        async with test_client as client:
            files = {"image": ("drawing.png", sample_image, "image/png")}
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险",
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

            assert response.status_code == 201
            result = response.json()

            # 验证响应字段
            assert "story_id" in result
            assert "story" in result
            assert "text" in result["story"]
            assert "word_count" in result["story"]
            assert "educational_value" in result
            assert "safety_score" in result
            assert 0.0 <= result["safety_score"] <= 1.0


@pytest.mark.asyncio
class TestStreamingProvenance:
    """Streaming path provenance parity tests (Issue #234)."""

    async def _get_artifact_types_for_story(self, client, story_id: str) -> set:
        resp = await client.get(f"/api/v1/admin/artifacts/stories/{story_id}/lineage")
        assert resp.status_code == 200, f"Lineage query failed: {resp.text}"
        lineage = resp.json()
        types = set()
        for run in lineage.get("runs", []):
            for artifact in run.get("artifacts", []):
                types.add(artifact.get("artifact_type"))
        return types

    async def test_streaming_records_provenance_artifacts(
        self, sample_image, test_client
    ):
        """Streaming event_generator must create provenance run with image + text artifacts."""
        child_id = f"child-prov-stream-{uuid.uuid4().hex[:8]}"
        async with test_client as client:
            resp = await client.post(
                "/api/v1/image-to-story/stream",
                files={"image": ("d.png", sample_image, "image/png")},
                data={"child_id": child_id, "age_group": "6-8", "interests": "animals"},
            )
            assert resp.status_code == 200
            story_id = None
            for line in resp.text.split("\n"):
                if line.startswith("data:") and "story_id" in line:
                    story_id = json.loads(line[5:]).get("story_id")
                    if story_id:
                        break
            assert story_id is not None
            types = await self._get_artifact_types_for_story(client, story_id)
            assert "image" in types, "Streaming path must record IMAGE artifact"
            assert "text" in types, "Streaming path must record TEXT artifact"

    async def test_streaming_and_sync_record_same_artifact_types(
        self, sample_image, test_client
    ):
        """Parity: streaming path records the same artifact types as sync path."""
        async with test_client as client:
            img1 = BytesIO()
            Image.new("RGB", (100, 100), color="red").save(img1, format="PNG")
            img1.seek(0)
            r1 = await client.post(
                "/api/v1/image-to-story",
                files={"image": ("s.png", img1, "image/png")},
                data={"child_id": f"c-sync-{uuid.uuid4().hex[:8]}", "age_group": "6-8"},
            )
            assert r1.status_code == 201
            sync_id = r1.json()["story_id"]

            img2 = BytesIO()
            Image.new("RGB", (100, 100), color="blue").save(img2, format="PNG")
            img2.seek(0)
            r2 = await client.post(
                "/api/v1/image-to-story/stream",
                files={"image": ("t.png", img2, "image/png")},
                data={
                    "child_id": f"c-stream-{uuid.uuid4().hex[:8]}",
                    "age_group": "6-8",
                },
            )
            assert r2.status_code == 200
            stream_id = None
            for line in r2.text.split("\n"):
                if line.startswith("data:") and "story_id" in line:
                    stream_id = json.loads(line[5:]).get("story_id")
                    if stream_id:
                        break
            assert stream_id is not None
            assert await self._get_artifact_types_for_story(
                client, sync_id
            ) == await self._get_artifact_types_for_story(client, stream_id)

    async def test_streaming_provenance_run_is_completed(
        self, sample_image, test_client
    ):
        """Successful streaming run must mark provenance run as completed."""
        async with test_client as client:
            resp = await client.post(
                "/api/v1/image-to-story/stream",
                files={"image": ("d.png", sample_image, "image/png")},
                data={"child_id": f"c-done-{uuid.uuid4().hex[:8]}", "age_group": "6-8"},
            )
            assert resp.status_code == 200
            story_id = None
            for line in resp.text.split("\n"):
                if line.startswith("data:") and "story_id" in line:
                    story_id = json.loads(line[5:]).get("story_id")
                    if story_id:
                        break
            assert story_id is not None
            lineage = (
                await client.get(f"/api/v1/admin/artifacts/stories/{story_id}/lineage")
            ).json()
            runs = lineage.get("runs", [])
            assert len(runs) >= 1, "Must have at least one provenance run"
            assert runs[0]["run"]["status"] == "completed"


@pytest.mark.asyncio
class TestStyleFallbackHelpers:
    """Regression tests for deterministic style fallback in image-to-story routes."""

    async def test_skip_styled_safety_in_dev_default_true(self, monkeypatch):
        from backend.src.api.routes import image_to_story as route_module

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STYLE_SAFETY_VALIDATE_IN_DEV", raising=False)
        assert route_module._skip_styled_safety_in_dev() is True

    async def test_skip_styled_safety_in_dev_can_be_forced_off(self, monkeypatch):
        from backend.src.api.routes import image_to_story as route_module

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("STYLE_SAFETY_VALIDATE_IN_DEV", "1")
        assert route_module._skip_styled_safety_in_dev() is False

    async def test_style_fallback_tool_is_directly_callable(self):
        from backend.src.api.routes import image_to_story as route_module

        assert callable(route_module.transform_art_style)

    async def test_extract_styled_path_from_tool_result(self):
        from backend.src.api.routes import image_to_story as route_module

        payload = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": True,
                            "styled_image_path": "/tmp/styled_cartoon.jpg",
                        }
                    ),
                }
            ]
        }

        assert (
            route_module._extract_styled_path_from_tool_result(payload)
            == "/tmp/styled_cartoon.jpg"
        )

    async def test_ensure_styled_image_path_uses_fallback_when_missing(
        self, monkeypatch
    ):
        from backend.src.api.models import ArtTheme
        from backend.src.api.routes import image_to_story as route_module

        backend_root = Path(__file__).resolve().parents[2]
        existing_file = backend_root / "test_art.png"
        assert existing_file.exists()

        called = {"count": 0}

        async def _fake_transform(args):
            called["count"] += 1
            assert args["theme"] == "cartoon"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "success": True,
                                "styled_image_path": str(existing_file),
                            }
                        ),
                    }
                ]
            }

        monkeypatch.setattr(route_module, "transform_art_style", _fake_transform)

        styled = await route_module._ensure_styled_image_path(
            current_styled_path="data/styled/missing.jpg",
            image_path=existing_file,
            art_theme=ArtTheme.CARTOON,
            child_age=7,
            session_id="test-child",
        )

        assert called["count"] == 1
        assert styled == str(existing_file)
