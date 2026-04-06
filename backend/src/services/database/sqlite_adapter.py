"""
SQLite Adapter

aiosqlite implementation of DatabaseAdapter — used for local development.
Extracted from the original DatabaseManager with identical behavior.
"""

import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...paths import DB_PATH
from .adapter import CursorResult


class SQLiteAdapter:
    """SQLite database adapter using aiosqlite."""

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(str(self.db_path))
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.row_factory = aiosqlite.Row
        await self._connection.commit()

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Direct access to aiosqlite connection — SQLite-only."""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def dialect(self) -> str:
        return "sqlite"

    async def execute(self, sql: str, parameters: tuple = ()) -> CursorResult:
        cursor = await self.connection.execute(sql, parameters)
        return CursorResult(rowcount=cursor.rowcount)

    async def executemany(self, sql: str, parameters: list) -> CursorResult:
        cursor = await self.connection.executemany(sql, parameters)
        return CursorResult(rowcount=cursor.rowcount)

    async def fetchone(
        self, sql: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        cursor = await self.connection.execute(sql, parameters)
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def fetchall(
        self, sql: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute(sql, parameters)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        await self.connection.commit()

    @asynccontextmanager
    async def transaction(self):
        try:
            yield self
            await self.connection.commit()
        except Exception:
            await self.connection.rollback()
            raise
