"""
API 真实测试脚本

运行 API 端点的真实测试
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目路径到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== Creative Agent API 真实测试 ===\n")


async def test_health_check():
    """测试健康检查"""
    print("📋 测试 1: 健康检查")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 测试根路径
            response = await client.get("/")
            print(f"GET / - 状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {result}")

            assert response.status_code == 200
            assert result["status"] in ["healthy", "degraded"]
            print("✅ 根路径健康检查通过\n")

            # 测试 /health 端点
            response = await client.get("/health")
            print(f"GET /health - 状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {result}")

            assert response.status_code == 200
            assert "services" in result
            print("✅ 健康检查端点通过\n")

    except Exception as e:
        print(f"❌ 健康检查测试失败: {e}\n")
        return False

    return True


async def test_session_manager():
    """测试会话管理器"""
    print("📋 测试 2: 会话管理器")
    print("-" * 50)

    try:
        from backend.src.services import SessionManager

        # 创建测试会话管理器
        manager = SessionManager(sessions_dir="./data/test_sessions")

        # 创建会话
        print("创建测试会话...")
        session = manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物", "冒险"],
            theme="森林探险",
            voice="fable",
            enable_audio=True,
            total_segments=5
        )

        print(f"会话 ID: {session.session_id}")
        print(f"儿童 ID: {session.child_id}")
        print(f"故事标题: {session.story_title}")
        print(f"状态: {session.status}")
        assert session.status == "active"
        print("✅ 会话创建成功\n")

        # 获取会话
        print("获取会话...")
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        print("✅ 会话获取成功\n")

        # 更新会话
        print("更新会话...")
        segment = {
            "segment_id": 1,
            "text": "故事第一段",
            "choices": [
                {"choice_id": "c1_a", "text": "选项A", "emoji": "🅰️"}
            ]
        }

        success = manager.update_session(
            session_id=session.session_id,
            segment=segment,
            choice_id="c1_a"
        )

        assert success is True
        updated = manager.get_session(session.session_id)
        assert len(updated.segments) == 1
        assert "c1_a" in updated.choice_history
        print("✅ 会话更新成功\n")

        # 列出会话
        print("列出会话...")
        sessions = manager.list_sessions(child_id="test_child_001")
        assert len(sessions) >= 1
        print(f"找到 {len(sessions)} 个会话")
        print("✅ 会话列表查询成功\n")

        # 删除会话
        print("删除会话...")
        success = manager.delete_session(session.session_id)
        assert success is True

        # 验证删除
        deleted = manager.get_session(session.session_id)
        assert deleted is None
        print("✅ 会话删除成功\n")

        # 清理测试目录
        import shutil
        test_dir = Path("./data/test_sessions")
        if test_dir.exists():
            shutil.rmtree(test_dir)

    except Exception as e:
        print(f"❌ 会话管理器测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_interactive_story_api():
    """测试互动故事 API"""
    print("📋 测试 3: 互动故事 API")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app
        from backend.src.services import session_manager

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 开始互动故事
            print("开始互动故事...")
            start_payload = {
                "child_id": "test_child_api",
                "age_group": "6-8",
                "interests": ["动物", "冒险"],
                "theme": "森林探险",
                "voice": "fable",
                "enable_audio": True
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            print(f"状态码: {response.status_code}")
            if response.status_code != 201:
                print(f"错误响应: {response.text}")

            assert response.status_code == 201
            result = response.json()

            session_id = result["session_id"]
            print(f"会话 ID: {session_id}")
            print(f"故事标题: {result['story_title']}")
            print(f"开场段落: {result['opening']['text'][:50]}...")
            print(f"选项数量: {len(result['opening']['choices'])}")
            print("✅ 互动故事开始成功\n")

            # 获取会话状态
            print("获取会话状态...")
            status_response = await client.get(
                f"/api/v1/story/interactive/{session_id}/status"
            )

            assert status_response.status_code == 200
            status = status_response.json()
            print(f"会话状态: {status['status']}")
            print(f"当前段落: {status['current_segment']}/{status['total_segments']}")
            print("✅ 状态查询成功\n")

            # 选择分支
            print("选择故事分支...")
            choice_payload = {
                "choice_id": "choice_0_a"
            }

            choice_response = await client.post(
                f"/api/v1/story/interactive/{session_id}/choose",
                json=choice_payload
            )

            assert choice_response.status_code == 200
            choice_result = choice_response.json()
            print(f"下一段落: {choice_result['next_segment']['text'][:50]}...")
            print(f"进度: {choice_result['progress'] * 100:.0f}%")
            print(f"选择历史: {choice_result['choice_history']}")
            print("✅ 分支选择成功\n")

            # 清理测试会话
            session_manager.delete_session(session_id)

    except Exception as e:
        print(f"❌ 互动故事 API 测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_api_error_handling():
    """测试 API 错误处理"""
    print("📋 测试 4: API 错误处理")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 测试无效年龄组
            print("测试无效年龄组...")
            invalid_payload = {
                "child_id": "test_child",
                "age_group": "invalid",
                "interests": ["动物"]
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=invalid_payload
            )

            assert response.status_code == 422
            error = response.json()
            print(f"错误类型: {error['error']}")
            print("✅ 验证错误正确捕获\n")

            # 测试不存在的会话
            print("测试不存在的会话...")
            response = await client.get(
                "/api/v1/story/interactive/nonexistent_session/status"
            )

            assert response.status_code == 404
            error = response.json()
            print(f"错误消息: {error['detail']}")
            print("✅ 404 错误正确处理\n")

            # 测试缺少必填字段
            print("测试缺少必填字段...")
            incomplete_payload = {
                "child_id": "test_child"
                # 缺少 age_group 和 interests
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=incomplete_payload
            )

            assert response.status_code == 422
            error = response.json()
            print(f"错误详情数量: {len(error.get('details', []))}")
            print("✅ 必填字段验证成功\n")

    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_api_documentation():
    """测试 API 文档"""
    print("📋 测试 5: API 文档访问")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 测试 OpenAPI JSON
            print("测试 OpenAPI 规范...")
            response = await client.get("/api/openapi.json")

            assert response.status_code == 200
            openapi = response.json()
            assert "openapi" in openapi
            assert "info" in openapi
            assert "paths" in openapi
            print(f"API 标题: {openapi['info']['title']}")
            print(f"API 版本: {openapi['info']['version']}")
            print(f"端点数量: {len(openapi['paths'])}")
            print("✅ OpenAPI 规范可访问\n")

            # 测试 Swagger UI
            print("测试 Swagger UI...")
            response = await client.get("/api/docs")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            print("✅ Swagger UI 可访问\n")

            # 测试 ReDoc
            print("测试 ReDoc...")
            response = await client.get("/api/redoc")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            print("✅ ReDoc 可访问\n")

    except Exception as e:
        print(f"❌ API 文档测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def main():
    """运行所有测试"""
    print("开始运行 API 真实测试...\n")

    results = []

    # 运行测试
    results.append(("健康检查", await test_health_check()))
    results.append(("会话管理器", await test_session_manager()))
    results.append(("互动故事 API", await test_interactive_story_api()))
    results.append(("错误处理", await test_api_error_handling()))
    results.append(("API 文档", await test_api_documentation()))

    # 统计结果
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    print("\n" + "=" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    print("=" * 60)

    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
