"""
PostgreSQL Adapter

asyncpg implementation of DatabaseAdapter — used for production (Supabase).
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .adapter import CursorResult

try:
    import asyncpg  # type: ignore[import-untyped]
except ImportError:
    asyncpg = None  # type: ignore[assignment]


def _translate_placeholders(sql: str) -> str:
    """Convert SQLite-style ? placeholders to asyncpg-style $1, $2, ..."""
    counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        return f"${counter}"

    return re.sub(r"\?", _replace, sql)


def _parse_rowcount(status: str) -> int:
    """
    Parse asyncpg command status string to extract affected row count.

    Examples: 'DELETE 3', 'UPDATE 1', 'INSERT 0 1', 'SELECT 5', 'CREATE TABLE'
    """
    if not status:
        return 0
    parts = status.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    return 0


class PostgresAdapter:
    """PostgreSQL database adapter using asyncpg with connection pooling."""

    def __init__(self, database_url: str, min_size: int = 2, max_size: int = 10):
        if asyncpg is None:
            raise ImportError(
                "asyncpg is required for PostgreSQL support. "
                "Install it with: pip install asyncpg"
            )
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            statement_cache_size=0,
        )

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    @property
    def dialect(self) -> str:
        return "postgresql"

    async def execute(self, sql: str, parameters: tuple = ()) -> CursorResult:
        translated = _translate_placeholders(sql)
        status = await self.pool.execute(translated, *parameters)
        return CursorResult(rowcount=_parse_rowcount(status))

    async def executemany(self, sql: str, parameters: list) -> CursorResult:
        translated = _translate_placeholders(sql)
        await self.pool.executemany(translated, parameters)
        return CursorResult(rowcount=len(parameters))

    async def fetchone(
        self, sql: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        translated = _translate_placeholders(sql)
        row = await self.pool.fetchrow(translated, *parameters)
        if row:
            return dict(row)
        return None

    async def fetchall(
        self, sql: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]:
        translated = _translate_placeholders(sql)
        rows = await self.pool.fetch(translated, *parameters)
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        pass

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield _ConnectionAdapter(conn)


class _ConnectionAdapter:
    """
    Wraps a single asyncpg connection inside a transaction,
    exposing the same execute/fetchone/fetchall interface as PostgresAdapter.
    """

    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    @property
    def dialect(self) -> str:
        return "postgresql"

    async def execute(self, sql: str, parameters: tuple = ()) -> CursorResult:
        translated = _translate_placeholders(sql)
        status = await self._conn.execute(translated, *parameters)
        return CursorResult(rowcount=_parse_rowcount(status))

    async def fetchone(
        self, sql: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        translated = _translate_placeholders(sql)
        row = await self._conn.fetchrow(translated, *parameters)
        if row:
            return dict(row)
        return None

    async def fetchall(
        self, sql: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]:
        translated = _translate_placeholders(sql)
        rows = await self._conn.fetch(translated, *parameters)
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        pass
