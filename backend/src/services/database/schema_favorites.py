"""
Favorites Schema

Defines the favorites table for bookmarking library content.
Follows the same pattern as schema_artifacts.py.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import DatabaseManager


# ============================================================================
# Favorites Table
# ============================================================================

FAVORITES_TABLE = """
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, item_type, item_id)
);
"""

FAVORITES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_type ON favorites(user_id, item_type);
CREATE INDEX IF NOT EXISTS idx_favorites_item ON favorites(item_type, item_id);
CREATE INDEX IF NOT EXISTS idx_favorites_created_at ON favorites(created_at DESC);
"""


# ============================================================================
# Schema Initialization
# ============================================================================

async def init_favorites_schema(db: "DatabaseManager") -> None:
    """
    Initialize favorites schema.

    Creates the favorites table and indexes.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).
    """
    await db.execute(FAVORITES_TABLE)
    for stmt in FAVORITES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass  # Index might already exist

    await db.commit()
