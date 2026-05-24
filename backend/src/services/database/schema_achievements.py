"""Achievement badge schema (#536)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .sql_compat import translate_ddl

if TYPE_CHECKING:
    from .connection import DatabaseManager


CHILD_ACHIEVEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS child_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    source_event TEXT NOT NULL,
    awarded_at TEXT NOT NULL,
    UNIQUE(user_id, child_id, achievement_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

CHILD_ACHIEVEMENTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_child_achievements_user_child
ON child_achievements(user_id, child_id);
CREATE INDEX IF NOT EXISTS idx_child_achievements_awarded_at
ON child_achievements(awarded_at DESC);
"""


async def init_achievement_schema(db: "DatabaseManager") -> None:
    """Create achievement tables and indexes."""
    await db.execute(translate_ddl(CHILD_ACHIEVEMENTS_TABLE, db.dialect))
    for stmt in CHILD_ACHIEVEMENTS_INDEXES.strip().split(";"):
        if stmt.strip():
            await db.execute(stmt)
    await db.commit()
