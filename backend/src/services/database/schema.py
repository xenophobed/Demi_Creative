"""
Database Schema

Database table definitions and migration functions.

Design Principles:
- Foreign keys ensure referential integrity between users, stories, and sessions
- Indexes optimize common query patterns (user lookup, date sorting)
- child_id is a profile identifier within a user account (allows multiple children per user)
- user_id links content to the authenticated user who created it
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import DatabaseManager


# ============================================================================
# Schema SQL
# ============================================================================

STORIES_TABLE = """
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    child_id TEXT NOT NULL,
    age_group TEXT NOT NULL,
    story_text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    themes TEXT,
    concepts TEXT,
    moral TEXT,
    characters TEXT,
    analysis TEXT,
    safety_score REAL DEFAULT 0.9,
    image_path TEXT,
    image_url TEXT,
    audio_url TEXT,
    story_type TEXT DEFAULT 'image_to_story',
    created_at TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
"""

STORIES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_stories_child_id ON stories(child_id);
CREATE INDEX IF NOT EXISTS idx_stories_user_id ON stories(user_id);
CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at DESC);
"""

SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    child_id TEXT NOT NULL,
    story_title TEXT NOT NULL,
    age_group TEXT NOT NULL,
    interests TEXT,
    theme TEXT,
    voice TEXT DEFAULT 'fable',
    enable_audio INTEGER DEFAULT 1,
    current_segment INTEGER DEFAULT 0,
    total_segments INTEGER DEFAULT 5,
    choice_history TEXT,
    audio_urls TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    educational_summary TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
"""

SESSIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sessions_child_id ON sessions(child_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);
"""

STORY_SEGMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS story_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    segment_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    audio_url TEXT,
    is_ending INTEGER DEFAULT 0,
    choices TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE(session_id, segment_id)
);
"""

STORY_SEGMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_segments_session_id ON story_segments(session_id);
"""

# ============================================================================
# Users Table
# ============================================================================

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    is_active INTEGER DEFAULT 1,
    is_verified INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
"""

USERS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
"""

# ============================================================================
# Tokens Table
# ============================================================================

TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

TOKENS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tokens_user_id ON tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_tokens_expires_at ON tokens(expires_at);
"""

CHILD_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS child_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT UNIQUE NOT NULL,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CHILD_PREFERENCES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_child_preferences_child_id ON child_preferences(child_id);
CREATE INDEX IF NOT EXISTS idx_child_preferences_updated_at ON child_preferences(updated_at DESC);
"""


# ============================================================================
# Schema Initialization
# ============================================================================

async def init_schema(db: "DatabaseManager") -> None:
    """
    Initialize database schema.

    Creates all tables and indexes. For existing databases, runs migrations
    to add new columns (user_id) while preserving existing data.

    Args:
        db: Database manager instance
    """
    # Enable foreign keys (important for SQLite)
    await db.execute("PRAGMA foreign_keys = ON")

    # Create users table first (referenced by other tables)
    await db.execute(USERS_TABLE)
    for stmt in USERS_INDEXES.strip().split(";"):
        if stmt.strip():
            await db.execute(stmt)

    # Create stories table (basic structure)
    await db.execute(STORIES_TABLE)

    # Create sessions table (basic structure)
    await db.execute(SESSIONS_TABLE)

    # Create story segments table
    await db.execute(STORY_SEGMENTS_TABLE)
    await db.execute(STORY_SEGMENTS_INDEX)

    # Create tokens table
    await db.execute(TOKENS_TABLE)
    for stmt in TOKENS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create child preferences table
    await db.execute(CHILD_PREFERENCES_TABLE)
    for stmt in CHILD_PREFERENCES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    await db.commit()

    # Run migrations FIRST to add user_id columns if they don't exist
    await _migrate_add_user_id(db)
    await _migrate_add_story_type(db)

    # Now create all indexes (including user_id indexes) after migration
    for stmt in STORIES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass  # Index might already exist

    for stmt in SESSIONS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass  # Index might already exist

    await db.commit()

    # Initialize artifact graph schema (Phase 2 of Issue #13)
    from .schema_artifacts import init_artifact_schema
    await init_artifact_schema(db)

    # Initialize favorites schema (#49 My Library)
    from .schema_favorites import init_favorites_schema
    await init_favorites_schema(db)

    print("Database schema initialized")


async def _migrate_add_user_id(db: "DatabaseManager") -> None:
    """
    Migration: Add user_id column to stories and sessions tables.

    This migration handles existing databases that don't have user_id columns.
    Uses ALTER TABLE which is safe for SQLite (adds column if not exists pattern).
    """
    # Check if user_id column exists in stories table
    stories_info = await db.fetchall("PRAGMA table_info(stories)")
    stories_columns = [col['name'] for col in stories_info]

    if 'user_id' not in stories_columns:
        print("Migrating stories table: adding user_id column...")
        await db.execute("ALTER TABLE stories ADD COLUMN user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stories_user_id ON stories(user_id)")
        await db.commit()
        print("Stories table migration completed")

    # Check if user_id column exists in sessions table
    sessions_info = await db.fetchall("PRAGMA table_info(sessions)")
    sessions_columns = [col['name'] for col in sessions_info]

    if 'user_id' not in sessions_columns:
        print("Migrating sessions table: adding user_id column...")
        await db.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        await db.commit()
        print("Sessions table migration completed")


async def _migrate_add_story_type(db: "DatabaseManager") -> None:
    """Migration: Add story_type column to stories table."""
    stories_info = await db.fetchall("PRAGMA table_info(stories)")
    stories_columns = [col['name'] for col in stories_info]

    if 'story_type' not in stories_columns:
        await db.execute("ALTER TABLE stories ADD COLUMN story_type TEXT DEFAULT 'image_to_story'")
        await db.commit()


# ============================================================================
# Data Migration
# ============================================================================

async def migrate_json_sessions(db: "DatabaseManager", sessions_dir: str = "./data/sessions") -> int:
    """
    将JSON会话文件迁移到SQLite数据库

    Args:
        db: 数据库管理器实例
        sessions_dir: JSON会话文件目录

    Returns:
        int: 迁移的会话数量
    """
    from datetime import datetime

    sessions_path = Path(sessions_dir)
    if not sessions_path.exists():
        print("📂 No sessions directory found, skipping migration")
        return 0

    migrated = 0
    backup_dir = sessions_path.parent / "sessions_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for json_file in sessions_path.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否已迁移（通过查询数据库）
            existing = await db.fetchone(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (data['session_id'],)
            )
            if existing:
                continue

            # 插入会话数据
            await db.execute(
                """
                INSERT INTO sessions (
                    session_id, child_id, story_title, age_group, interests,
                    theme, voice, enable_audio, current_segment, total_segments,
                    choice_history, audio_urls, status, created_at, updated_at,
                    expires_at, educational_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data['session_id'],
                    data['child_id'],
                    data['story_title'],
                    data['age_group'],
                    json.dumps(data.get('interests', []), ensure_ascii=False),
                    data.get('theme'),
                    data.get('voice', 'fable'),
                    1 if data.get('enable_audio', True) else 0,
                    data.get('current_segment', 0),
                    data.get('total_segments', 5),
                    json.dumps(data.get('choice_history', []), ensure_ascii=False),
                    json.dumps(data.get('audio_urls', {}), ensure_ascii=False),
                    data.get('status', 'active'),
                    data['created_at'],
                    data['updated_at'],
                    data['expires_at'],
                    json.dumps(data.get('educational_summary'), ensure_ascii=False) if data.get('educational_summary') else None
                )
            )

            # 插入故事段落
            for segment in data.get('segments', []):
                await db.execute(
                    """
                    INSERT INTO story_segments (
                        session_id, segment_id, text, audio_url, is_ending,
                        choices, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data['session_id'],
                        segment.get('segment_id', 0),
                        segment.get('text', ''),
                        segment.get('audio_url'),
                        1 if segment.get('is_ending', False) else 0,
                        json.dumps(segment.get('choices', []), ensure_ascii=False),
                        datetime.now().isoformat()
                    )
                )

            await db.commit()

            # 重命名已迁移的文件
            migrated_file = json_file.with_suffix('.json.migrated')
            json_file.rename(migrated_file)

            migrated += 1

        except Exception as e:
            print(f"⚠️ Error migrating {json_file.name}: {e}")
            continue

    if migrated > 0:
        print(f"✅ Migrated {migrated} sessions from JSON to SQLite")

    return migrated
