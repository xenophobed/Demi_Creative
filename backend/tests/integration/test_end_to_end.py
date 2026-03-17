"""
End-to-End Tests

端到端测试：模拟完整的用户流程
Uses agent mock fallback (deterministic results in test env).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from io import BytesIO
from PIL import Image

from backend.src.main import app
from backend.src.api.deps import get_current_user
from backend.src.services.user_service import UserData


# ---------------------------------------------------------------------------
# Auth override (matches conftest pattern)
# ---------------------------------------------------------------------------

_TEST_USER = UserData(
    user_id="e2e_test_user",
    username="e2e_test_user",
    email="e2e@example.com",
    password_hash="test_hash",
    display_name="E2E Test User",
    avatar_url=None,
    is_active=True,
    is_verified=True,
    created_at="",
    updated_at="",
    last_login_at=None,
)


async def _fake_user() -> UserData:
    return _TEST_USER


@pytest.fixture(autouse=True)
def _override_auth():
    """Override auth for e2e tests."""
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_drawing():
    """创建示例画作"""
    img = Image.new('RGB', (400, 300), color='lightblue')

    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 150, 150], fill='yellow')
    draw.rectangle([200, 200, 250, 280], fill='brown')
    draw.ellipse([170, 150, 280, 200], fill='green')

    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


# ---------------------------------------------------------------------------
# Complete User Journey Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCompleteUserJourney:
    """完整用户旅程测试 — uses agent mock fallback."""

    async def test_first_time_user_flow(self, sample_drawing):
        """测试首次使用流程: upload drawing, generate story, check response."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {
                "image": ("first_drawing.png", sample_drawing, "image/png")
            }
            data = {
                "child_id": "e2e_test_child",
                "age_group": "6-8",
                "interests": "自然,动物",
                "voice": "nova",
                "enable_audio": "true"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            assert response.status_code == 201
            result = response.json()

            assert "story_id" in result
            assert "story" in result
            assert len(result["story"]["text"]) > 0
            assert result["story"]["word_count"] > 0
            assert "educational_value" in result
            assert len(result["educational_value"]["themes"]) > 0
            assert result["safety_score"] >= 0.7

    async def test_recurring_user_flow(self, sample_drawing):
        """测试重复用户流程: two uploads, verify characters present."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files_1 = {
                "image": ("drawing_1.png", sample_drawing, "image/png")
            }
            data_1 = {
                "child_id": "e2e_test_child",
                "age_group": "6-8",
                "interests": "动物"
            }

            response_1 = await client.post(
                "/api/v1/image-to-story", files=files_1, data=data_1
            )
            assert response_1.status_code == 201
            assert "characters" in response_1.json()

            sample_drawing.seek(0)
            files_2 = {
                "image": ("drawing_2.png", sample_drawing, "image/png")
            }

            response_2 = await client.post(
                "/api/v1/image-to-story", files=files_2, data=data_1
            )
            assert response_2.status_code == 201
            assert "characters" in response_2.json()

    async def test_interactive_story_complete_journey(self):
        """测试互动故事旅程: start session, make choice, verify progression."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start_payload = {
                "child_id": "e2e_test_child",
                "age_group": "6-8",
                "interests": ["动物", "冒险"],
                "theme": "森林探险",
                "voice": "fable",
                "enable_audio": True
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start", json=start_payload
            )
            assert start_response.status_code == 201
            start_result = start_response.json()
            session_id = start_result["session_id"]
            assert "opening" in start_result

            opening = start_result["opening"]
            assert "choices" in opening
            assert len(opening["choices"]) > 0

            choice_response = await client.post(
                f"/api/v1/story/interactive/{session_id}/choose",
                json={"choice_id": opening["choices"][0]["choice_id"]}
            )
            assert choice_response.status_code == 200
            assert "next_segment" in choice_response.json()


# ---------------------------------------------------------------------------
# Error Recovery Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorRecovery:
    """错误恢复测试 — uses agent mock fallback."""

    async def test_recovery_from_invalid_image(self, sample_drawing):
        """测试从无效图片错误中恢复"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid_file = BytesIO(b"not an image")
            files = {
                "image": ("invalid.txt", invalid_file, "text/plain")
            }
            data = {
                "child_id": "e2e_test_child",
                "age_group": "6-8"
            }

            response = await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )
            assert response.status_code == 400

            valid_files = {
                "image": ("valid.png", sample_drawing, "image/png")
            }
            valid_response = await client.post(
                "/api/v1/image-to-story", files=valid_files, data=data
            )
            assert valid_response.status_code == 201

    async def test_recovery_from_expired_session(self):
        """测试从过期会话中恢复"""
        from backend.src.services.database import session_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start_payload = {
                "child_id": "e2e_test_child",
                "age_group": "6-8",
                "interests": ["动物"]
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start", json=start_payload
            )
            assert start_response.status_code == 201
            session_id = start_response.json()["session_id"]

            await session_repo.update_session(session_id, status="expired")

            choice_response = await client.post(
                f"/api/v1/story/interactive/{session_id}/choose",
                json={"choice_id": "choice_0_a"}
            )
            assert choice_response.status_code == 400

            new_start = await client.post(
                "/api/v1/story/interactive/start", json=start_payload
            )
            assert new_start.status_code == 201


# ---------------------------------------------------------------------------
# Performance Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPerformance:
    """性能测试 — uses agent mock fallback."""

    async def test_concurrent_requests(self, sample_drawing):
        """测试并发请求处理"""
        import asyncio

        async def make_request(client, child_id, img_bytes):
            img_bytes.seek(0)
            files = {
                "image": (f"drawing_{child_id}.png", img_bytes, "image/png")
            }
            data = {
                "child_id": child_id,
                "age_group": "6-8",
                "interests": "动物"
            }
            return await client.post(
                "/api/v1/image-to-story", files=files, data=data
            )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            images = []
            for _ in range(5):
                img = Image.new('RGB', (400, 300), color='lightblue')
                buf = BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                images.append(buf)

            tasks = [
                make_request(client, f"perf_test_child_{i}", images[i])
                for i in range(5)
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    pytest.fail(f"Request {i} failed: {response}")
                assert response.status_code == 201, f"Request {i} returned {response.status_code}"
