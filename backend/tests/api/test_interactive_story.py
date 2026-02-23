"""
Tests for Interactive Story API

互动故事 API 单元测试
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.src.main import app
from backend.src.services import session_manager


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """每个测试后清理会话"""
    yield
    # 清理测试会话
    sessions = session_manager.list_sessions(child_id="test_child_001")
    for session in sessions:
        session_manager.delete_session(session.session_id)


@pytest.mark.asyncio
class TestStartInteractiveStory:
    """开始互动故事测试"""

    async def test_start_story_success(self):
        """测试成功开始故事"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["动物", "冒险"],
                "theme": "森林探险",
                "voice": "fable",
                "enable_audio": True
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            assert response.status_code == 201
            result = response.json()

            # 验证响应字段
            assert "session_id" in result
            assert "story_title" in result
            assert "opening" in result

            opening = result["opening"]
            assert "segment_id" in opening
            assert "text" in opening
            assert "choices" in opening
            assert len(opening["choices"]) > 0

            # 验证选项格式
            for choice in opening["choices"]:
                assert "choice_id" in choice
                assert "text" in choice
                assert "emoji" in choice

    async def test_start_story_missing_interests(self):
        """测试缺少兴趣标签"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": []  # 空列表
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            assert response.status_code == 422
            error = response.json()
            assert error["error"] == "ValidationError"

    async def test_start_story_too_many_interests(self):
        """测试兴趣标签过多"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["动物", "冒险", "太空", "科学", "音乐", "运动"]  # 6个
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            assert response.status_code == 422

    async def test_start_story_invalid_age_group(self):
        """测试无效年龄组"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "invalid",
                "interests": ["动物"]
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            assert response.status_code == 422


@pytest.mark.asyncio
class TestChooseStoryBranch:
    """选择故事分支测试"""

    @pytest_asyncio.fixture
    async def active_session_id(self):
        """创建活跃会话"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["动物", "冒险"]
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            return response.json()["session_id"]

    async def test_choose_branch_success(self, active_session_id):
        """测试成功选择分支"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 获取第一段的选项
            status_response = await client.get(
                f"/api/v1/story/interactive/{active_session_id}/status"
            )
            # 假设选择第一个选项（实际需要从会话中获取）
            choice_id = "choice_0_a"

            payload = {
                "choice_id": choice_id
            }

            response = await client.post(
                f"/api/v1/story/interactive/{active_session_id}/choose",
                json=payload
            )

            assert response.status_code == 200
            result = response.json()

            # 验证响应
            assert "session_id" in result
            assert "next_segment" in result
            assert "choice_history" in result
            assert "progress" in result

            assert result["session_id"] == active_session_id
            assert choice_id in result["choice_history"]
            assert 0.0 <= result["progress"] <= 1.0

    async def test_choose_branch_invalid_session(self):
        """测试无效会话ID"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "choice_id": "choice_0_a"
            }

            response = await client.post(
                "/api/v1/story/interactive/invalid_session/choose",
                json=payload
            )

            assert response.status_code == 404
            assert "会话不存在" in response.json()["detail"]

    async def test_choose_branch_completed_session(self, active_session_id):
        """测试已完成的会话"""
        # 先将会话标记为完成
        session_manager.update_session(
            session_id=active_session_id,
            status="completed"
        )

        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "choice_id": "choice_0_a"
            }

            response = await client.post(
                f"/api/v1/story/interactive/{active_session_id}/choose",
                json=payload
            )

            assert response.status_code == 400
            assert "无法继续" in response.json()["detail"]


@pytest.mark.asyncio
class TestGetSessionStatus:
    """获取会话状态测试"""

    @pytest_asyncio.fixture
    async def test_session_id(self):
        """创建测试会话"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["动物"]
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload
            )

            return response.json()["session_id"]

    async def test_get_status_success(self, test_session_id):
        """测试成功获取状态"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/story/interactive/{test_session_id}/status"
            )

            assert response.status_code == 200
            result = response.json()

            # 验证响应字段
            assert "session_id" in result
            assert "status" in result
            assert "child_id" in result
            assert "story_title" in result
            assert "current_segment" in result
            assert "total_segments" in result
            assert "choice_history" in result
            assert "created_at" in result
            assert "updated_at" in result
            assert "expires_at" in result

            assert result["session_id"] == test_session_id
            assert result["status"] == "active"
            assert result["child_id"] == "test_child_001"

    async def test_get_status_invalid_session(self):
        """测试获取不存在的会话状态"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/story/interactive/invalid_session/status"
            )

            assert response.status_code == 404
            assert "会话不存在" in response.json()["detail"]


@pytest.mark.asyncio
class TestStoryProgression:
    """故事进度测试"""

    async def test_full_story_flow(self):
        """测试完整故事流程"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. 开始故事
            start_payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["动物", "冒险"]
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            assert start_response.status_code == 201
            session_id = start_response.json()["session_id"]

            # 2. 进行多次选择
            for i in range(3):
                choice_payload = {
                    "choice_id": f"choice_{i}_a"
                }

                choice_response = await client.post(
                    f"/api/v1/story/interactive/{session_id}/choose",
                    json=choice_payload
                )

                assert choice_response.status_code == 200
                result = choice_response.json()

                # 检查进度递增
                assert result["progress"] >= i / 5

            # 3. 检查最终状态
            status_response = await client.get(
                f"/api/v1/story/interactive/{session_id}/status"
            )

            assert status_response.status_code == 200
            final_status = status_response.json()

            assert len(final_status["choice_history"]) == 3
            assert final_status["current_segment"] >= 3
