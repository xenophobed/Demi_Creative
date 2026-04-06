"""
Database Adapter Protocol

Defines the interface all database adapters must implement.
Supports dual-driver architecture: SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class CursorResult:
    """Normalized result from execute/executemany — works across both drivers."""

    rowcount: int


@runtime_checkable
class DatabaseAdapter(Protocol):
    """Protocol that SQLiteAdapter and PostgresAdapter both implement."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...

    async def execute(self, sql: str, parameters: tuple = ()) -> CursorResult: ...

    async def executemany(self, sql: str, parameters: list) -> CursorResult: ...

    async def fetchone(
        self, sql: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]: ...

    async def fetchall(
        self, sql: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]: ...

    async def commit(self) -> None: ...

    def transaction(self): ...

    @property
    def dialect(self) -> str:
        """Return 'sqlite' or 'postgresql' — lets callers branch on driver."""
        ...


def create_adapter(database_url: str | None = None) -> DatabaseAdapter:
    """
    Factory: build the right adapter based on DATABASE_URL.

    - postgresql://... → PostgresAdapter (asyncpg)
    - Anything else / None → SQLiteAdapter (aiosqlite, uses DB_PATH)
    """
    url = database_url or os.environ.get("DATABASE_URL")

    if url and url.startswith(("postgresql://", "postgres://")):
        from .postgres_adapter import PostgresAdapter

        return PostgresAdapter(url)

    from .sqlite_adapter import SQLiteAdapter

    return SQLiteAdapter()
