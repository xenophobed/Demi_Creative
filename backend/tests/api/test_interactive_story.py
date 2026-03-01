"""
Tests for Interactive Story API

Uses dependency_overrides (see conftest.py) so get_current_user never
touches the DB.  All requests go through ASGITransport for httpx >= 0.27.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.src.main import app
from backend.src.services.database import session_repo


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Cleanup fixture — async, uses session_repo instead of sync session_manager
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def cleanup_sessions():
    """每个测试后清理会话"""
    yield
    try:
        sessions = await session_repo.list_sessions(child_id="test_child_001")
        for s in sessions:
            await session_repo.delete_session(s.session_id)
    except Exception:
        pass  # DB may not be connected for pure-validation tests


# ============================================================================
# Start Interactive Story
# ============================================================================

@pytest.mark.asyncio
class TestStartInteractiveStory:
    """Start interactive story tests"""

    async def test_start_story_success(self):
        """测试成功开始故事"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["animals", "adventure"],
                "theme": "forest exploration",
                "voice": "fable",
                "enable_audio": True,
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 201
            result = response.json()

            assert "session_id" in result
            assert "story_title" in result
            assert "opening" in result

            opening = result["opening"]
            assert "segment_id" in opening
            assert "text" in opening
            assert "choices" in opening
            assert len(opening["choices"]) > 0

            for choice in opening["choices"]:
                assert "choice_id" in choice
                assert "text" in choice
                assert "emoji" in choice

    async def test_start_story_missing_interests(self):
        """测试缺少兴趣标签"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": [],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 422
            error = response.json()
            assert error["error"] == "ValidationError"

    async def test_start_story_too_many_interests(self):
        """测试兴趣标签过多"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["a", "b", "c", "d", "e", "f"],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 422

    async def test_start_story_invalid_age_group(self):
        """测试无效年龄组"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "invalid",
                "interests": ["animals"],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 422

    async def test_start_story_with_empty_preferences(self):
        """New child with no preference history still gets a story."""
        async with _client() as client:
            payload = {
                "child_id": "brand_new_child_no_prefs",
                "age_group": "6-8",
                "interests": ["robots"],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 201
            result = response.json()
            assert "session_id" in result
            assert "story_title" in result
            assert "opening" in result

    async def test_start_story_response_shape_unchanged(self):
        """API response shape is unchanged after memory features."""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "3-5",
                "interests": ["colors"],
                "theme": "rainbow adventure",
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 201
            result = response.json()

            # Top-level keys
            assert set(result.keys()) >= {"session_id", "story_title", "opening"}

            # Opening segment shape
            opening = result["opening"]
            assert "segment_id" in opening
            assert "text" in opening
            assert "choices" in opening
            assert isinstance(opening["choices"], list)


# ============================================================================
# Choose Story Branch
# ============================================================================

@pytest.mark.asyncio
class TestChooseStoryBranch:
    """Choose story branch tests"""

    @pytest_asyncio.fixture
    async def active_session_id(self):
        """创建活跃会话"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["animals", "adventure"],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 201
            return response.json()["session_id"]

    async def test_choose_branch_success(self, active_session_id):
        """测试成功选择分支"""
        async with _client() as client:
            choice_id = "choice_0_a"

            response = await client.post(
                f"/api/v1/story/interactive/{active_session_id}/choose",
                json={"choice_id": choice_id},
            )

            assert response.status_code == 200
            result = response.json()

            assert "session_id" in result
            assert "next_segment" in result
            assert "choice_history" in result
            assert "progress" in result

            assert result["session_id"] == active_session_id
            assert choice_id in result["choice_history"]
            assert 0.0 <= result["progress"] <= 1.0

    async def test_choose_branch_invalid_session(self):
        """测试无效会话ID"""
        async with _client() as client:
            response = await client.post(
                "/api/v1/story/interactive/invalid_session/choose",
                json={"choice_id": "choice_0_a"},
            )

            assert response.status_code == 404

    async def test_choose_branch_completed_session(self, active_session_id):
        """Test choosing a branch on a completed session returns 400."""
        await session_repo.update_session(
            session_id=active_session_id,
            status="completed",
        )

        async with _client() as client:
            response = await client.post(
                f"/api/v1/story/interactive/{active_session_id}/choose",
                json={"choice_id": "choice_0_a"},
            )

            assert response.status_code == 400


# ============================================================================
# Get Session Status
# ============================================================================

@pytest.mark.asyncio
class TestGetSessionStatus:
    """Session status tests"""

    @pytest_asyncio.fixture
    async def test_session_id(self):
        """创建测试会话"""
        async with _client() as client:
            payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["animals"],
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=payload,
            )

            assert response.status_code == 201
            return response.json()["session_id"]

    async def test_get_status_success(self, test_session_id):
        """测试成功获取状态"""
        async with _client() as client:
            response = await client.get(
                f"/api/v1/story/interactive/{test_session_id}/status",
            )

            assert response.status_code == 200
            result = response.json()

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
        async with _client() as client:
            response = await client.get(
                "/api/v1/story/interactive/invalid_session/status",
            )

            assert response.status_code == 404


# ============================================================================
# Full Story Progression
# ============================================================================

@pytest.mark.asyncio
class TestStoryProgression:
    """Full story flow tests"""

    async def test_full_story_flow(self):
        """测试完整故事流程"""
        async with _client() as client:
            # 1. 开始故事
            start_payload = {
                "child_id": "test_child_001",
                "age_group": "6-8",
                "interests": ["animals", "adventure"],
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload,
            )

            assert start_response.status_code == 201
            session_id = start_response.json()["session_id"]

            # 2. Make several choices
            for i in range(3):
                choice_response = await client.post(
                    f"/api/v1/story/interactive/{session_id}/choose",
                    json={"choice_id": f"choice_{i}_a"},
                )

                assert choice_response.status_code == 200
                result = choice_response.json()
                assert result["progress"] >= i / 5

            # 3. Check final status
            status_response = await client.get(
                f"/api/v1/story/interactive/{session_id}/status",
            )

            assert status_response.status_code == 200
            final_status = status_response.json()

            assert len(final_status["choice_history"]) == 3
            assert final_status["current_segment"] >= 3
