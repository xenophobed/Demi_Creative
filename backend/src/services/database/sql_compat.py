"""
SQL Compatibility Layer

Dialect-aware helpers that produce correct SQL for both SQLite and PostgreSQL.
Used by schema files, repositories, and routes that contain dialect-specific SQL.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .connection import DatabaseManager


def translate_ddl(sql: str, dialect: str) -> str:
    """
    Translate SQLite DDL to PostgreSQL DDL.

    Handles:
    - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    - Keeps everything else unchanged (CREATE TABLE IF NOT EXISTS, FOREIGN KEY,
      UNIQUE, DEFAULT, INDEX syntax are all compatible).
    """
    if dialect == "sqlite":
        return sql

    # PostgreSQL: replace AUTOINCREMENT pattern
    result = re.sub(
        r"(\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        r"\1 SERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    return result


async def column_exists(db: "DatabaseManager", table: str, column: str) -> bool:
    """
    Check if a column exists in a table — works on both SQLite and PostgreSQL.
    """
    if db.dialect == "sqlite":
        rows = await db.fetchall(f"PRAGMA table_info({table})")
        return any(row["name"] == column for row in rows)
    else:
        row = await db.fetchone(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = ?",
            (table, column),
        )
        return row is not None


async def table_create_sql(db: "DatabaseManager", table: str) -> str:
    """
    Get the CREATE TABLE SQL for a table — works on both SQLite and PostgreSQL.

    Returns empty string if the table doesn't exist.
    """
    if db.dialect == "sqlite":
        rows = await db.fetchall(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return rows[0]["sql"] if rows else ""
    else:
        # PostgreSQL: reconstruct from information_schema (simplified)
        rows = await db.fetchall(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = ? "
            "ORDER BY ordinal_position",
            (table,),
        )
        if not rows:
            return ""
        cols = ", ".join(
            f"{r['column_name']} {r['data_type']}" for r in rows
        )
        return f"CREATE TABLE {table} ({cols})"


async def get_table_columns(db: "DatabaseManager", table: str) -> List[str]:
    """Return list of column names for a table."""
    if db.dialect == "sqlite":
        rows = await db.fetchall(f"PRAGMA table_info({table})")
        return [row["name"] for row in rows]
    else:
        rows = await db.fetchall(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            (table,),
        )
        return [row["column_name"] for row in rows]


def json_value(column: str, key: str, dialect: str) -> str:
    """
    Generate SQL to extract a JSON text value.

    SQLite:     json_extract(column, '$.key')
    PostgreSQL: column::jsonb->>'key'
    """
    if dialect == "sqlite":
        return f"json_extract({column}, '$.{key}')"
    return f"{column}::jsonb->>'{key}'"


def date_format_sql(column: str, fmt: str, dialect: str) -> str:
    """
    Generate SQL to format a date/timestamp column.

    Translates SQLite strftime format codes to PostgreSQL to_char format.
    Supports: %Y-%m (month), %Y-W%W (week).
    """
    if dialect == "sqlite":
        return f"strftime('{fmt}', {column})"

    # Map SQLite format codes to PostgreSQL to_char
    pg_fmt = fmt.replace("%Y", "YYYY").replace("%m", "MM").replace("%W", '"W"IW')
    return f"to_char({column}::timestamp, '{pg_fmt}')"


def ci_equals(column: str, dialect: str) -> str:
    """
    Generate a case-insensitive equality clause for a column.

    SQLite:     column = ? COLLATE NOCASE
    PostgreSQL: LOWER(column) = LOWER(?)
    """
    if dialect == "sqlite":
        return f"{column} = ? COLLATE NOCASE"
    return f"LOWER({column}) = LOWER(?)"


def insert_or_ignore(table: str, columns: list[str], dialect: str) -> str:
    """
    Generate INSERT OR IGNORE / ON CONFLICT DO NOTHING SQL.

    Both dialects use ? placeholders (adapter translates for asyncpg).
    """
    cols = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))

    if dialect == "sqlite":
        return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"

    return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
