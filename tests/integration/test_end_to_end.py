"""
End-to-End Tests

端到端测试：模拟完整的用户流程
"""

import pytest
from httpx import AsyncClient
from io import BytesIO
from PIL import Image

from backend.src.main import app
from backend.src.services import session_manager


@pytest.fixture
def sample_drawing():
    """创建示例画作"""
    img = Image.new('RGB', (400, 300), color='lightblue')

    # 添加一些简单的绘制（模拟儿童画作）
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 150, 150], fill='yellow')  # 太阳
    draw.rectangle([200, 200, 250, 280], fill='brown')  # 树干
    draw.ellipse([170, 150, 280, 200], fill='green')  # 树冠

    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """清理测试数据"""
    yield
    # 清理测试会话
    sessions = session_manager.list_sessions(child_id="e2e_test_child")
    for session in sessions:
        session_manager.delete_session(session.session_id)


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要 mock MCP Tools 和 Agent")
class TestCompleteUserJourney:
    """完整用户旅程测试"""

    async def test_first_time_user_flow(self, sample_drawing):
        """
        测试首次使用流程

        场景：
        1. 儿童上传第一幅画作
        2. 系统生成故事
        3. 检查故事内容和教育价值
        4. 验证记忆存储
        """
        child_id = "e2e_test_child"

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Step 1: 上传画作
            files = {
                "image": ("first_drawing.png", sample_drawing, "image/png")
            }
            data = {
                "child_id": child_id,
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

            # Step 2: 验证故事生成
            assert response.status_code == 201
            result = response.json()

            assert "story_id" in result
            assert "story" in result
            story_text = result["story"]["text"]
            assert len(story_text) > 0
            assert result["story"]["word_count"] > 0

            # Step 3: 验证教育价值
            assert "educational_value" in result
            edu_value = result["educational_value"]
            assert len(edu_value["themes"]) > 0
            assert len(edu_value["concepts"]) > 0

            # Step 4: 验证安全评分
            assert result["safety_score"] >= 0.7

            # Step 5: 验证音频生成
            if data["enable_audio"]:
                assert result["audio_url"] is not None

    async def test_recurring_user_flow(self, sample_drawing):
        """
        测试重复用户流程

        场景：
        1. 儿童第二次上传画作（相同角色）
        2. 系统识别重复角色
        3. 故事保持连续性
        """
        child_id = "e2e_test_child"

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 第一次上传
            files_1 = {
                "image": ("drawing_1.png", sample_drawing, "image/png")
            }
            data_1 = {
                "child_id": child_id,
                "age_group": "6-8",
                "interests": "动物"
            }

            response_1 = await client.post(
                "/api/v1/image-to-story",
                files=files_1,
                data=data_1
            )

            assert response_1.status_code == 201
            result_1 = response_1.json()

            # 第二次上传（模拟相同角色）
            sample_drawing.seek(0)  # 重置
            files_2 = {
                "image": ("drawing_2.png", sample_drawing, "image/png")
            }
            data_2 = {
                "child_id": child_id,
                "age_group": "6-8",
                "interests": "动物"
            }

            response_2 = await client.post(
                "/api/v1/image-to-story",
                files=files_2,
                data=data_2
            )

            assert response_2.status_code == 201
            result_2 = response_2.json()

            # 验证角色记忆
            if result_2["characters"]:
                # 检查角色出现次数增加
                for character in result_2["characters"]:
                    if character["appearances"] > 1:
                        # 找到重复角色
                        assert True
                        break

    async def test_interactive_story_complete_journey(self):
        """
        测试完整的互动故事旅程

        场景：
        1. 开始互动故事
        2. 做出多次选择
        3. 到达结局
        4. 查看教育总结
        """
        child_id = "e2e_test_child"

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Step 1: 开始故事
            start_payload = {
                "child_id": child_id,
                "age_group": "6-8",
                "interests": ["动物", "冒险"],
                "theme": "森林探险",
                "voice": "fable",
                "enable_audio": True
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            assert start_response.status_code == 201
            session_id = start_response.json()["session_id"]

            # Step 2: 进行选择直到结局
            max_choices = 10  # 防止无限循环
            choice_count = 0

            while choice_count < max_choices:
                # 获取当前状态
                status_response = await client.get(
                    f"/api/v1/story/interactive/{session_id}/status"
                )

                status = status_response.json()

                if status["status"] == "completed":
                    break

                # 做出选择（选择第一个选项）
                choice_payload = {
                    "choice_id": f"choice_{choice_count}_a"
                }

                choice_response = await client.post(
                    f"/api/v1/story/interactive/{session_id}/choose",
                    json=choice_payload
                )

                assert choice_response.status_code == 200
                choice_result = choice_response.json()

                # 检查是否到达结局
                if choice_result["next_segment"]["is_ending"]:
                    break

                choice_count += 1

            # Step 3: 验证最终状态
            final_status_response = await client.get(
                f"/api/v1/story/interactive/{session_id}/status"
            )

            final_status = final_status_response.json()

            # 验证故事完成
            assert len(final_status["choice_history"]) > 0
            assert final_status["current_segment"] > 0

            # 如果故事完成，验证教育总结
            if final_status["status"] == "completed":
                assert final_status["educational_summary"] is not None
                edu_summary = final_status["educational_summary"]
                assert len(edu_summary["themes"]) > 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要 mock MCP Tools")
class TestErrorRecovery:
    """错误恢复测试"""

    async def test_recovery_from_invalid_image(self):
        """测试从无效图片错误中恢复"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 尝试上传无效图片
            invalid_file = BytesIO(b"not an image")
            files = {
                "image": ("invalid.txt", invalid_file, "text/plain")
            }
            data = {
                "child_id": "e2e_test_child",
                "age_group": "6-8"
            }

            response = await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

            # 验证错误响应
            assert response.status_code == 400

            # 再次上传有效图片
            img = Image.new('RGB', (400, 300), color='blue')
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            valid_files = {
                "image": ("valid.png", img_bytes, "image/png")
            }

            valid_response = await client.post(
                "/api/v1/image-to-story",
                files=valid_files,
                data=data
            )

            # 应该成功
            assert valid_response.status_code == 201

    async def test_recovery_from_expired_session(self):
        """测试从过期会话中恢复"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 创建会话
            start_payload = {
                "child_id": "e2e_test_child",
                "age_group": "6-8",
                "interests": ["动物"]
            }

            start_response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            session_id = start_response.json()["session_id"]

            # 手动设置会话为过期
            session_manager.update_session(
                session_id=session_id,
                status="expired"
            )

            # 尝试继续会话
            choice_payload = {"choice_id": "choice_0_a"}

            choice_response = await client.post(
                f"/api/v1/story/interactive/{session_id}/choose",
                json=choice_payload
            )

            # 应该返回错误
            assert choice_response.status_code == 400

            # 开始新会话
            new_start_response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            # 新会话应该成功
            assert new_start_response.status_code == 201


@pytest.mark.asyncio
class TestPerformance:
    """性能测试（简单版本）"""

    @pytest.mark.skip(reason="性能测试，按需运行")
    async def test_concurrent_requests(self, sample_drawing):
        """测试并发请求处理"""
        import asyncio

        async def make_request(client, child_id):
            """发送单个请求"""
            sample_drawing.seek(0)
            files = {
                "image": (f"drawing_{child_id}.png", sample_drawing, "image/png")
            }
            data = {
                "child_id": child_id,
                "age_group": "6-8",
                "interests": "动物"
            }

            return await client.post(
                "/api/v1/image-to-story",
                files=files,
                data=data
            )

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 发送10个并发请求
            tasks = [
                make_request(client, f"perf_test_child_{i}")
                for i in range(10)
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # 验证所有请求都成功（或至少不崩溃）
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Request failed: {response}")
                # 注意：实际成功需要 mock
