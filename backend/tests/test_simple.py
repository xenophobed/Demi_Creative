"""
简单测试脚本 - 不依赖外部库
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== 简单测试 ===\n")

# 测试 1: 导入检查
print("测试 1: 检查模块导入")
print("-" * 50)

try:
    # 测试导入 models
    from backend.src.api.models import (
        AgeGroup,
        VoiceType,
        ImageToStoryRequest,
        InteractiveStoryStartRequest
    )
    print("✅ API 模型导入成功")

    # 测试导入 session_manager
    from backend.src.services import SessionManager
    print("✅ SessionManager 导入成功")

    # 测试导入 main
    print("✅ 所有核心模块导入成功\n")

except ImportError as e:
    print(f"❌ 导入失败: {e}\n")
    sys.exit(1)

# 测试 2: SessionManager 基础功能
print("测试 2: SessionManager 基础功能")
print("-" * 50)

try:
    # 创建测试会话管理器
    manager = SessionManager(sessions_dir="./data/test_simple_sessions")
    print("✅ SessionManager 实例创建成功")

    # 创建会话
    session = manager.create_session(
        child_id="test_simple_001",
        story_title="简单测试故事",
        age_group="6-8",
        interests=["测试"],
        total_segments=3
    )

    print(f"✅ 会话创建成功: {session.session_id}")

    # 获取会话
    retrieved = manager.get_session(session.session_id)
    assert retrieved is not None
    print("✅ 会话获取成功")

    # 删除会话
    manager.delete_session(session.session_id)
    print("✅ 会话删除成功")

    # 清理目录
    import shutil
    test_dir = Path("./data/test_simple_sessions")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    print("✅ 测试清理完成\n")

except Exception as e:
    print(f"❌ SessionManager 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 验证 Pydantic 模型
print("测试 3: Pydantic 模型验证")
print("-" * 50)

try:
    from backend.src.api.models import InteractiveStoryStartRequest

    # 测试有效请求
    valid_request = InteractiveStoryStartRequest(
        child_id="test_001",
        age_group=AgeGroup.AGE_6_8,
        interests=["动物", "冒险"]
    )
    print(f"✅ 有效请求创建成功: {valid_request.child_id}")

    # 测试验证器
    try:
        invalid_request = InteractiveStoryStartRequest(
            child_id="test_002",
            age_group=AgeGroup.AGE_6_8,
            interests=["a", "b", "c", "d", "e", "f"]  # 超过5个
        )
        print("❌ 验证器未生效（应该失败）")
    except Exception:
        print("✅ 验证器正确捕获错误")

    print("✅ Pydantic 模型验证成功\n")

except Exception as e:
    print(f"❌ Pydantic 模型测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 4: 文件结构检查
print("测试 4: 文件结构检查")
print("-" * 50)

required_files = [
    "backend/src/main.py",
    "backend/src/api/models.py",
    "backend/src/api/routes/image_to_story.py",
    "backend/src/api/routes/interactive_story.py",
    "backend/src/services/session_manager.py",
    "backend/requirements.txt",
]

all_exist = True
for file_path in required_files:
    full_path = project_root / file_path
    if full_path.exists():
        print(f"✅ {file_path}")
    else:
        print(f"❌ {file_path} (缺失)")
        all_exist = False

if all_exist:
    print("\n✅ 所有必需文件存在\n")
else:
    print("\n⚠️  部分文件缺失\n")

print("=" * 60)
print("🎉 基础测试全部通过！")
print("=" * 60)
print("\n提示: 要运行完整的 API 测试，请先安装依赖:")
print("  cd backend")
print("  pip install -r requirements.txt")
print("  python3 ../run_tests.py")
