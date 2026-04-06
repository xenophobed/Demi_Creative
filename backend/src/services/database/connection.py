"""
Database Connection Manager

Backward-compatible facade over the adapter pattern.
Selects SQLite (dev) or PostgreSQL (prod) based on DATABASE_URL env var.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .adapter import CursorResult, DatabaseAdapter, create_adapter


class DatabaseManager:
    """
    Backward-compatible database manager.

    Wraps a DatabaseAdapter (SQLite or PostgreSQL) selected by create_adapter().
    All existing code that imports DatabaseManager or db_manager keeps working.
    """

    def __init__(self, db_path: str = None, database_url: str = None):
        """
        Initialize with optional explicit config.

        Args:
            db_path: SQLite file path (legacy — forces SQLite adapter)
            database_url: PostgreSQL connection string (forces Postgres adapter)
        """
        if db_path:
            from .sqlite_adapter import SQLiteAdapter

            self._adapter: DatabaseAdapter = SQLiteAdapter(db_path)
        else:
            self._adapter = create_adapter(database_url)

    async def connect(self) -> None:
        await self._adapter.connect()

    async def disconnect(self) -> None:
        await self._adapter.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._adapter.is_connected

    @property
    def dialect(self) -> str:
        return self._adapter.dialect

    async def execute(self, sql: str, parameters: tuple = ()) -> CursorResult:
        return await self._adapter.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: list) -> CursorResult:
        return await self._adapter.executemany(sql, parameters)

    async def fetchone(
        self, sql: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        return await self._adapter.fetchone(sql, parameters)

    async def fetchall(
        self, sql: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]:
        return await self._adapter.fetchall(sql, parameters)

    async def commit(self) -> None:
        await self._adapter.commit()

    @asynccontextmanager
    async def transaction(self):
        async with self._adapter.transaction() as ctx:
            yield ctx

    @property
    def connection(self):
        """Direct access to aiosqlite connection — SQLite only."""
        if hasattr(self._adapter, "connection"):
            return self._adapter.connection
        raise AttributeError(
            "Direct connection access is not available on PostgreSQL. "
            "Use the adapter methods (execute, fetchone, fetchall) instead."
        )


# Global database manager instance
db_manager = DatabaseManager()
