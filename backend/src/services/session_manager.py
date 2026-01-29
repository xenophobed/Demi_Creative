"""
Session Manager

互动故事会话管理系统，使用 JSON 文件存储会话数据
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict


@dataclass
class SessionData:
    """会话数据结构"""
    session_id: str
    child_id: str
    story_title: str
    age_group: str
    interests: List[str]
    theme: Optional[str]
    voice: str
    enable_audio: bool

    # 故事进度
    current_segment: int
    total_segments: int
    choice_history: List[str]

    # 故事内容
    segments: List[Dict[str, Any]]  # 已生成的段落

    # 元数据
    status: str  # active, completed, expired
    created_at: str
    updated_at: str
    expires_at: str

    # 教育总结（完成后）
    educational_summary: Optional[Dict[str, Any]] = None


class SessionManager:
    """会话管理器"""

    def __init__(self, sessions_dir: str = "./data/sessions"):
        """
        初始化会话管理器

        Args:
            sessions_dir: 会话数据存储目录
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # 默认过期时间：24小时
        self.default_expiry_hours = 24

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.sessions_dir / f"{session_id}.json"

    def create_session(
        self,
        child_id: str,
        story_title: str,
        age_group: str,
        interests: List[str],
        theme: Optional[str] = None,
        voice: str = "fable",
        enable_audio: bool = True,
        total_segments: int = 5
    ) -> SessionData:
        """
        创建新会话

        Args:
            child_id: 儿童ID
            story_title: 故事标题
            age_group: 年龄组
            interests: 兴趣标签
            theme: 故事主题
            voice: 语音类型
            enable_audio: 是否生成音频
            total_segments: 预计总段落数

        Returns:
            SessionData: 会话数据
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=self.default_expiry_hours)

        session_data = SessionData(
            session_id=session_id,
            child_id=child_id,
            story_title=story_title,
            age_group=age_group,
            interests=interests,
            theme=theme,
            voice=voice,
            enable_audio=enable_audio,
            current_segment=0,
            total_segments=total_segments,
            choice_history=[],
            segments=[],
            status="active",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )

        self._save_session(session_data)
        return session_data

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            SessionData 或 None（如果不存在）
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return None

        try:
            with open(session_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否过期
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now() > expires_at and data['status'] == 'active':
                data['status'] = 'expired'
                self._save_session_dict(session_id, data)

            return SessionData(**data)
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None

    def update_session(
        self,
        session_id: str,
        segment: Optional[Dict[str, Any]] = None,
        choice_id: Optional[str] = None,
        status: Optional[str] = None,
        educational_summary: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新会话数据

        Args:
            session_id: 会话ID
            segment: 新的故事段落
            choice_id: 选择的选项ID
            status: 新状态
            educational_summary: 教育总结

        Returns:
            bool: 是否更新成功
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # 更新段落
        if segment:
            session.segments.append(segment)
            session.current_segment = len(session.segments)

        # 更新选择历史
        if choice_id:
            session.choice_history.append(choice_id)

        # 更新状态
        if status:
            session.status = status

        # 更新教育总结
        if educational_summary:
            session.educational_summary = educational_summary

        # 更新时间戳
        session.updated_at = datetime.now().isoformat()

        self._save_session(session)
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return False

        try:
            session_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            return False

    def list_sessions(
        self,
        child_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[SessionData]:
        """
        列出会话

        Args:
            child_id: 按儿童ID过滤（可选）
            status: 按状态过滤（可选）

        Returns:
            List[SessionData]: 会话列表
        """
        sessions = []

        for session_path in self.sessions_dir.glob("*.json"):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 过滤条件
                if child_id and data.get('child_id') != child_id:
                    continue
                if status and data.get('status') != status:
                    continue

                sessions.append(SessionData(**data))
            except Exception as e:
                print(f"Error loading session {session_path.name}: {e}")

        # 按更新时间倒序排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            int: 清理的会话数量
        """
        cleaned = 0
        now = datetime.now()

        for session_path in self.sessions_dir.glob("*.json"):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                expires_at = datetime.fromisoformat(data['expires_at'])

                # 过期超过7天的会话删除
                if now > expires_at + timedelta(days=7):
                    session_path.unlink()
                    cleaned += 1
            except Exception as e:
                print(f"Error processing session {session_path.name}: {e}")

        return cleaned

    def _save_session(self, session: SessionData):
        """保存会话数据"""
        session_path = self._get_session_path(session.session_id)

        try:
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(session), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")
            raise

    def _save_session_dict(self, session_id: str, data: Dict[str, Any]):
        """保存会话数据（字典格式）"""
        session_path = self._get_session_path(session_id)

        try:
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving session {session_id}: {e}")
            raise


# 全局会话管理器实例
session_manager = SessionManager()
