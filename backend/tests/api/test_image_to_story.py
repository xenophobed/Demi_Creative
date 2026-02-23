"""
Tests for Image to Story API

画作转故事 API 单元测试
"""

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from io import BytesIO
from PIL import Image

from backend.src.main import app


@pytest.fixture
def sample_image():
    """创建测试图片"""
    img = Image.new('RGB', (400, 300), color='lightblue')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


@pytest.mark.asyncio
class TestImageToStoryAPI:
    """画作转故事 API 测试"""

    async def test_upload_valid_image(self, sample_image):
        """测试上传有效图片"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("drawing.png", sample_image, "image/png")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险",
                "voice": "nova",
                "enable_audio": "true"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            # 注意：由于依赖外部服务，这里可能需要 mock
            # assert response.status_code == 201
            # assert "story_id" in response.json()

    async def test_upload_invalid_file_type(self):
        """测试上传无效文件类型"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 创建文本文件
            text_file = BytesIO(b"This is not an image")

            files = {
                "image": ("test.txt", text_file, "text/plain")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 400
            assert "文件必须是图片类型" in response.json()["detail"]

    async def test_upload_too_large_file(self):
        """测试上传超大文件"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 创建超大图片（模拟）
            large_file = BytesIO(b"0" * (11 * 1024 * 1024))  # 11MB

            files = {
                "image": ("large.png", large_file, "image/png")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 413
            assert "文件大小超过限制" in response.json()["detail"]

    async def test_missing_required_fields(self, sample_image):
        """测试缺少必填字段"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("drawing.png", sample_image, "image/png")
            }
            data = {
                "child_id": "test_child_001"
                # 缺少 age_group
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 422
            error_response = response.json()
            assert error_response["error"] == "ValidationError"

    async def test_invalid_age_group(self, sample_image):
        """测试无效的年龄组"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("drawing.png", sample_image, "image/png")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "13-15"  # 无效年龄组
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 422

    async def test_too_many_interests(self, sample_image):
        """测试兴趣标签过多"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("drawing.png", sample_image, "image/png")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险,太空,科学,音乐,运动"  # 6个标签
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 400
            assert "兴趣标签最多5个" in response.json()["detail"]


@pytest.mark.asyncio
class TestImageToStoryResponseFormat:
    """响应格式测试"""

    @pytest.mark.skip(reason="需要 mock Agent 响应")
    async def test_response_structure(self, sample_image):
        """测试响应结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("drawing.png", sample_image, "image/png")
            }
            data = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": "动物,冒险"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
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
