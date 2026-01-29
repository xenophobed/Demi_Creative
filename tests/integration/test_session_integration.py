"""
Session Integration Tests

会话管理器集成测试
"""

import pytest
from datetime import datetime, timedelta

from backend.src.services import SessionManager


@pytest.fixture
def session_manager():
    """创建测试会话管理器"""
    manager = SessionManager(sessions_dir="./data/test_sessions")
    yield manager

    # 清理测试会话
    import shutil
    from pathlib import Path
    test_dir = Path("./data/test_sessions")
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestSessionManager:
    """会话管理器测试"""

    def test_create_session(self, session_manager):
        """测试创建会话"""
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物", "冒险"],
            theme="森林探险",
            voice="fable",
            enable_audio=True,
            total_segments=5
        )

        assert session.session_id is not None
        assert session.child_id == "test_child_001"
        assert session.story_title == "测试故事"
        assert session.age_group == "6-8"
        assert session.interests == ["动物", "冒险"]
        assert session.status == "active"
        assert session.current_segment == 0
        assert session.total_segments == 5
        assert len(session.choice_history) == 0

    def test_get_session(self, session_manager):
        """测试获取会话"""
        # 创建会话
        created_session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 获取会话
        retrieved_session = session_manager.get_session(created_session.session_id)

        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.child_id == created_session.child_id
        assert retrieved_session.story_title == created_session.story_title

    def test_get_nonexistent_session(self, session_manager):
        """测试获取不存在的会话"""
        session = session_manager.get_session("nonexistent_id")
        assert session is None

    def test_update_session(self, session_manager):
        """测试更新会话"""
        # 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 更新会话
        segment = {
            "segment_id": 1,
            "text": "故事第一段",
            "choices": []
        }

        success = session_manager.update_session(
            session_id=session.session_id,
            segment=segment,
            choice_id="choice_0_a"
        )

        assert success is True

        # 验证更新
        updated_session = session_manager.get_session(session.session_id)
        assert len(updated_session.segments) == 1
        assert updated_session.current_segment == 1
        assert "choice_0_a" in updated_session.choice_history

    def test_delete_session(self, session_manager):
        """测试删除会话"""
        # 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 删除会话
        success = session_manager.delete_session(session.session_id)
        assert success is True

        # 验证删除
        retrieved_session = session_manager.get_session(session.session_id)
        assert retrieved_session is None

    def test_list_sessions(self, session_manager):
        """测试列出会话"""
        # 创建多个会话
        for i in range(3):
            session_manager.create_session(
                child_id=f"test_child_{i:03d}",
                story_title=f"故事 {i}",
                age_group="6-8",
                interests=["动物"]
            )

        # 列出所有会话
        all_sessions = session_manager.list_sessions()
        assert len(all_sessions) == 3

        # 按儿童ID过滤
        child_sessions = session_manager.list_sessions(child_id="test_child_001")
        assert len(child_sessions) == 1
        assert child_sessions[0].child_id == "test_child_001"

    def test_list_sessions_by_status(self, session_manager):
        """测试按状态列出会话"""
        # 创建活跃会话
        active_session = session_manager.create_session(
            child_id="test_child_001",
            story_title="活跃故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 创建已完成会话
        completed_session = session_manager.create_session(
            child_id="test_child_002",
            story_title="完成故事",
            age_group="6-8",
            interests=["冒险"]
        )

        session_manager.update_session(
            session_id=completed_session.session_id,
            status="completed"
        )

        # 按状态过滤
        active_sessions = session_manager.list_sessions(status="active")
        completed_sessions = session_manager.list_sessions(status="completed")

        assert len(active_sessions) == 1
        assert len(completed_sessions) == 1
        assert active_sessions[0].status == "active"
        assert completed_sessions[0].status == "completed"

    def test_session_expiry(self, session_manager):
        """测试会话过期"""
        # 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 手动设置过期时间为过去
        from pathlib import Path
        import json

        session_path = session_manager._get_session_path(session.session_id)
        with open(session_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 设置为1小时前过期
        past_time = datetime.now() - timedelta(hours=1)
        data['expires_at'] = past_time.isoformat()

        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 获取会话（应该自动标记为过期）
        expired_session = session_manager.get_session(session.session_id)

        assert expired_session.status == "expired"

    def test_cleanup_expired_sessions(self, session_manager):
        """测试清理过期会话"""
        # 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 设置为8天前过期
        from pathlib import Path
        import json

        session_path = session_manager._get_session_path(session.session_id)
        with open(session_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        old_time = datetime.now() - timedelta(days=8)
        data['expires_at'] = old_time.isoformat()

        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 清理过期会话
        cleaned = session_manager.cleanup_expired_sessions()

        assert cleaned == 1

        # 验证会话已删除
        retrieved_session = session_manager.get_session(session.session_id)
        assert retrieved_session is None

    def test_update_educational_summary(self, session_manager):
        """测试更新教育总结"""
        # 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="测试故事",
            age_group="6-8",
            interests=["动物"]
        )

        # 更新教育总结
        edu_summary = {
            "themes": ["勇气", "友谊"],
            "concepts": ["决策", "合作"],
            "moral": "团结就是力量"
        }

        success = session_manager.update_session(
            session_id=session.session_id,
            educational_summary=edu_summary
        )

        assert success is True

        # 验证更新
        updated_session = session_manager.get_session(session.session_id)
        assert updated_session.educational_summary is not None
        assert updated_session.educational_summary["themes"] == ["勇气", "友谊"]
        assert updated_session.educational_summary["moral"] == "团结就是力量"


class TestSessionLifecycle:
    """会话生命周期测试"""

    def test_complete_session_lifecycle(self, session_manager):
        """测试完整的会话生命周期"""
        # 1. 创建会话
        session = session_manager.create_session(
            child_id="test_child_001",
            story_title="完整故事",
            age_group="6-8",
            interests=["动物", "冒险"],
            total_segments=3
        )

        assert session.status == "active"
        assert session.current_segment == 0

        # 2. 添加第一段
        segment_1 = {
            "segment_id": 1,
            "text": "故事开始...",
            "choices": [
                {"choice_id": "c1_a", "text": "选项A", "emoji": "🅰️"},
                {"choice_id": "c1_b", "text": "选项B", "emoji": "🅱️"}
            ]
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=segment_1,
            choice_id="c1_a"
        )

        # 3. 添加第二段
        segment_2 = {
            "segment_id": 2,
            "text": "故事继续...",
            "choices": [
                {"choice_id": "c2_a", "text": "选项A", "emoji": "🅰️"}
            ]
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=segment_2,
            choice_id="c2_a"
        )

        # 4. 添加结局
        ending = {
            "segment_id": 3,
            "text": "故事结束！",
            "choices": [],
            "is_ending": True
        }

        edu_summary = {
            "themes": ["勇气"],
            "concepts": ["决策"],
            "moral": "勇敢面对挑战"
        }

        session_manager.update_session(
            session_id=session.session_id,
            segment=ending,
            status="completed",
            educational_summary=edu_summary
        )

        # 5. 验证最终状态
        final_session = session_manager.get_session(session.session_id)

        assert final_session.status == "completed"
        assert final_session.current_segment == 3
        assert len(final_session.segments) == 3
        assert len(final_session.choice_history) == 2
        assert final_session.educational_summary is not None
