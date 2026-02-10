"""
Database Connection Manager

异步SQLite数据库连接管理
"""

import aiosqlite
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from ...paths import DB_PATH


class DatabaseManager:
    """数据库连接管理器"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """建立数据库连接"""
        # 确保数据目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(str(self.db_path))

        # 启用WAL模式以提高并发性能
        await self._connection.execute("PRAGMA journal_mode=WAL")

        # 启用外键约束
        await self._connection.execute("PRAGMA foreign_keys=ON")

        # 设置行工厂为返回字典
        self._connection.row_factory = aiosqlite.Row

        await self._connection.commit()

    async def disconnect(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """获取数据库连接"""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connection is not None

    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器"""
        try:
            yield self.connection
            await self.connection.commit()
        except Exception:
            await self.connection.rollback()
            raise

    async def execute(self, sql: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """执行SQL语句"""
        return await self.connection.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: list) -> aiosqlite.Cursor:
        """批量执行SQL语句"""
        return await self.connection.executemany(sql, parameters)

    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[dict]:
        """执行查询并返回单行结果"""
        cursor = await self.connection.execute(sql, parameters)
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def fetchall(self, sql: str, parameters: tuple = ()) -> list:
        """执行查询并返回所有结果"""
        cursor = await self.connection.execute(sql, parameters)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        """提交事务"""
        await self.connection.commit()


# 全局数据库管理器实例
db_manager = DatabaseManager()
