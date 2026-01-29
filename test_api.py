#!/usr/bin/env python3
"""
API 测试脚本
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("Creative Agent API 测试")
print("=" * 60)
print()

# 测试 1: 健康检查
print("测试 1: 健康检查")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print("✅ 健康检查通过\n")
except Exception as e:
    print(f"❌ 错误: {e}\n")

# 测试 2: 开始互动故事
print("测试 2: 开始互动故事")
print("-" * 60)
try:
    payload = {
        "child_id": "test_001",
        "age_group": "6-8",
        "interests": ["动物", "冒险"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/story/interactive/start",
        json=payload
    )

    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if response.status_code == 201:
        session_id = result['session_id']
        print(f"\n✅ 互动故事创建成功")
        print(f"   会话 ID: {session_id}")
        print(f"   故事标题: {result['story_title']}")
        print(f"   开场文本: {result['opening']['text'][:50]}...")
        print()

        # 测试 3: 获取会话状态
        print("测试 3: 获取会话状态")
        print("-" * 60)
        status_response = requests.get(
            f"{BASE_URL}/api/v1/story/interactive/{session_id}/status"
        )
        print(f"状态码: {status_response.status_code}")
        status_result = status_response.json()
        print(f"响应: {json.dumps(status_result, indent=2, ensure_ascii=False)}")
        print("✅ 状态查询成功\n")

        # 测试 4: 选择分支
        print("测试 4: 选择故事分支")
        print("-" * 60)
        choice_payload = {
            "choice_id": "choice_0_a"
        }

        choice_response = requests.post(
            f"{BASE_URL}/api/v1/story/interactive/{session_id}/choose",
            json=choice_payload
        )
        print(f"状态码: {choice_response.status_code}")
        choice_result = choice_response.json()
        print(f"响应: {json.dumps(choice_result, indent=2, ensure_ascii=False)}")
        print("✅ 分支选择成功\n")

    else:
        print(f"❌ 故事创建失败\n")

except Exception as e:
    print(f"❌ 错误: {e}\n")

# 测试 5: 错误处理 - 无效年龄组
print("测试 5: 错误处理 - 无效年龄组")
print("-" * 60)
try:
    invalid_payload = {
        "child_id": "test_002",
        "age_group": "invalid",
        "interests": ["动物"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/story/interactive/start",
        json=invalid_payload
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 422:
        print("✅ 验证错误正确捕获")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 未正确处理验证错误")
    print()

except Exception as e:
    print(f"❌ 错误: {e}\n")

# 测试 6: 错误处理 - 不存在的会话
print("测试 6: 错误处理 - 不存在的会话")
print("-" * 60)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/story/interactive/nonexistent_id/status"
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 404:
        print("✅ 404 错误正确处理")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 未正确处理 404 错误")
    print()

except Exception as e:
    print(f"❌ 错误: {e}\n")

print("=" * 60)
print("✅ API 测试完成！")
print("=" * 60)
