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

from .sql_compat import column_exists, table_create_sql, translate_ddl

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
    styled_image_url TEXT,
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
    role TEXT DEFAULT 'child',
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

TOPIC_SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS topic_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    subscribed_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, child_id, topic)
);
"""

TOPIC_SUBSCRIPTIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_topic_subscriptions_user_child ON topic_subscriptions(user_id, child_id);
CREATE INDEX IF NOT EXISTS idx_topic_subscriptions_topic ON topic_subscriptions(topic);
CREATE INDEX IF NOT EXISTS idx_topic_subscriptions_is_active ON topic_subscriptions(is_active);
"""

# ============================================================================
# Characters Table (#160)
# ============================================================================

CHARACTERS_TABLE = """
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT '',
    child_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    visual_features TEXT,
    traits TEXT,
    appearance_count INTEGER DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(user_id, child_id, name)
);
"""

CHARACTERS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_characters_user_child ON characters(user_id, child_id);
CREATE INDEX IF NOT EXISTS idx_characters_child_name ON characters(user_id, child_id, name);
CREATE INDEX IF NOT EXISTS idx_characters_appearance ON characters(appearance_count DESC);
"""

# ============================================================================
# Cloned Voices Table (#150)
# ============================================================================

CLONED_VOICES_TABLE = """
CREATE TABLE IF NOT EXISTS cloned_voices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    replicate_voice_id TEXT NOT NULL,
    voice_file_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

CLONED_VOICES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_cloned_voices_user_id ON cloned_voices(user_id);
CREATE INDEX IF NOT EXISTS idx_cloned_voices_child_id ON cloned_voices(child_id);
CREATE INDEX IF NOT EXISTS idx_cloned_voices_active ON cloned_voices(is_active);
"""

# ============================================================================
# Daily Usage Table (#314)
# ============================================================================

DAILY_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS daily_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    feature TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, usage_date, feature)
);
"""

DAILY_USAGE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_daily_usage_user_date ON daily_usage(user_id, usage_date);
"""

# ============================================================================
# Referrals Table (#347)
# ============================================================================

REFERRALS_TABLE = """
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_user_id TEXT NOT NULL,
    referred_user_id TEXT NOT NULL UNIQUE,
    referral_code TEXT NOT NULL,
    is_qualified INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    qualified_at TEXT,
    FOREIGN KEY (referrer_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (referred_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

REFERRALS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code);
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
    # Enable foreign keys (SQLite only — PostgreSQL enforces by default)
    if db.dialect == "sqlite":
        await db.execute("PRAGMA foreign_keys = ON")

    d = db.dialect  # shorthand for translate_ddl calls

    # Create users table first (referenced by other tables)
    await db.execute(translate_ddl(USERS_TABLE, d))
    for stmt in USERS_INDEXES.strip().split(";"):
        if stmt.strip():
            await db.execute(stmt)

    # Create stories table (basic structure)
    await db.execute(translate_ddl(STORIES_TABLE, d))

    # Create sessions table (basic structure)
    await db.execute(translate_ddl(SESSIONS_TABLE, d))

    # Create story segments table
    await db.execute(translate_ddl(STORY_SEGMENTS_TABLE, d))
    await db.execute(STORY_SEGMENTS_INDEX)

    # Create tokens table
    await db.execute(translate_ddl(TOKENS_TABLE, d))
    for stmt in TOKENS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create child preferences table
    await db.execute(translate_ddl(CHILD_PREFERENCES_TABLE, d))
    for stmt in CHILD_PREFERENCES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create topic subscriptions table (#94)
    await db.execute(translate_ddl(TOPIC_SUBSCRIPTIONS_TABLE, d))
    for stmt in TOPIC_SUBSCRIPTIONS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create characters table (#160)
    await db.execute(translate_ddl(CHARACTERS_TABLE, d))
    for stmt in CHARACTERS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create cloned voices table (#150)
    await db.execute(translate_ddl(CLONED_VOICES_TABLE, d))
    for stmt in CLONED_VOICES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create daily usage quota table (#314)
    await db.execute(translate_ddl(DAILY_USAGE_TABLE, d))
    for stmt in DAILY_USAGE_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    # Create referrals table (#347)
    await db.execute(translate_ddl(REFERRALS_TABLE, d))
    for stmt in REFERRALS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    await db.commit()

    # Run migrations FIRST to add user_id columns if they don't exist
    await _migrate_add_user_id(db)
    await _migrate_add_story_type(db)
    await _migrate_add_user_role(db)
    await _migrate_backfill_word_counts(db)
    await _migrate_characters_user_id(db)
    await _migrate_add_styled_image_url(db)
    await _migrate_add_referral_columns(db)

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
    if not await column_exists(db, "stories", "user_id"):
        print("Migrating stories table: adding user_id column...")
        await db.execute("ALTER TABLE stories ADD COLUMN user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stories_user_id ON stories(user_id)")
        await db.commit()
        print("Stories table migration completed")

    # Check if user_id column exists in sessions table
    if not await column_exists(db, "sessions", "user_id"):
        print("Migrating sessions table: adding user_id column...")
        await db.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        await db.commit()
        print("Sessions table migration completed")


async def _migrate_add_story_type(db: "DatabaseManager") -> None:
    """Migration: Add story_type column to stories table."""
    if not await column_exists(db, "stories", "story_type"):
        await db.execute("ALTER TABLE stories ADD COLUMN story_type TEXT DEFAULT 'image_to_story'")
        await db.commit()


async def _migrate_add_user_role(db: "DatabaseManager") -> None:
    """Migration: Add role column to users table (#232)."""
    if not await column_exists(db, "users", "role"):
        await db.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'child'")
        await db.commit()


async def _migrate_backfill_word_counts(db: "DatabaseManager") -> None:
    """Migration: Recompute word counts for CJK text (#78).

    The original word count used len(text.split()) which produces wrong results
    for Chinese/Japanese/Korean text. This migration recomputes word counts
    using the CJK-aware count_words utility.
    """
    from ...utils.text import count_words

    rows = await db.fetchall(
        "SELECT story_id, story_text, word_count FROM stories WHERE story_text != ''"
    )
    updated = 0
    for row in rows:
        correct = count_words(row['story_text'])
        if correct != row['word_count']:
            await db.execute(
                "UPDATE stories SET word_count = ? WHERE story_id = ?",
                (correct, row['story_id'])
            )
            updated += 1
    if updated > 0:
        await db.commit()
        print(f"📝 Backfilled word counts for {updated} stories")


async def _migrate_characters_user_id(db: "DatabaseManager") -> None:
    """Migration: Add user_id column to characters table (#288).

    SQLite cannot ALTER UNIQUE constraints, so we recreate the table
    with the new UNIQUE(user_id, child_id, name) constraint.
    Existing rows get user_id='' (empty string) for backward compatibility.
    """
    # Check if the UNIQUE constraint includes user_id by inspecting the CREATE TABLE SQL.
    # We need to handle both cases: (1) table has no user_id column at all,
    # (2) user_id was added via ALTER TABLE but UNIQUE still only covers (child_id, name).
    create_sql = await table_create_sql(db, "characters")
    needs_migration = True
    if create_sql:
        # If the CREATE TABLE already has UNIQUE(user_id, child_id, name), no migration needed
        if 'user_id' in create_sql and 'UNIQUE(user_id' in create_sql.replace(' ', ''):
            needs_migration = False

    if needs_migration:
        print("Migrating characters table: adding user_id column (#288)...")
        # SQLite requires table recreation to change UNIQUE constraints
        await db.execute(translate_ddl(
            """
            CREATE TABLE characters_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT '',
                child_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                visual_features TEXT,
                traits TEXT,
                appearance_count INTEGER DEFAULT 1,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(user_id, child_id, name)
            )
            """,
            db.dialect,
        ))
        await db.execute(
            """
            INSERT INTO characters_new
                (id, user_id, child_id, name, description, visual_features,
                 traits, appearance_count, first_seen_at, last_seen_at)
            SELECT id, '', child_id, name, description, visual_features,
                   traits, appearance_count, first_seen_at, last_seen_at
            FROM characters
            """
        )
        await db.execute("DROP TABLE characters")
        await db.execute("ALTER TABLE characters_new RENAME TO characters")
        # Recreate indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_characters_user_child ON characters(user_id, child_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_characters_child_name ON characters(user_id, child_id, name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_characters_appearance ON characters(appearance_count DESC)")
        await db.commit()
        print("Characters table migration completed")


async def _migrate_add_styled_image_url(db: "DatabaseManager") -> None:
    """Migration: Add styled_image_url column to stories table.

    Persists the styled/cover image URL so it can be returned in GET responses.
    Backfills from analysis.styled_image for existing stories.
    """
    if not await column_exists(db, "stories", "styled_image_url"):
        print("Migrating stories table: adding styled_image_url column...")
        await db.execute("ALTER TABLE stories ADD COLUMN styled_image_url TEXT")

        # Backfill from analysis JSON for existing stories
        rows = await db.fetchall(
            "SELECT story_id, analysis FROM stories WHERE analysis IS NOT NULL"
        )
        import json as _json
        backfilled = 0
        for row in rows:
            try:
                analysis = _json.loads(row['analysis'] or '{}')
                styled_image = analysis.get('styled_image', '')
                if styled_image:
                    # Convert path to URL format
                    from pathlib import Path as _Path
                    url = f"/data/styled/{_Path(styled_image).name}"
                    await db.execute(
                        "UPDATE stories SET styled_image_url = ? WHERE story_id = ?",
                        (url, row['story_id']),
                    )
                    backfilled += 1
            except Exception:
                pass
        await db.commit()
        print(f"Stories styled_image_url migration completed (backfilled {backfilled} rows)")


async def _migrate_add_referral_columns(db: "DatabaseManager") -> None:
    """Migration: Add membership_tier, referral_code, referred_by to users (#347)."""
    import secrets
    import string

    if not await column_exists(db, "users", "membership_tier"):
        print("Migrating users table: adding referral columns (#347)...")
        await db.execute(
            "ALTER TABLE users ADD COLUMN membership_tier TEXT DEFAULT 'free'"
        )
        await db.execute(
            "ALTER TABLE users ADD COLUMN referral_code TEXT DEFAULT ''"
        )
        await db.execute(
            "ALTER TABLE users ADD COLUMN referred_by TEXT"
        )

        alphabet = string.ascii_lowercase + string.digits
        rows = await db.fetchall(
            "SELECT user_id FROM users WHERE referral_code IS NULL OR referral_code = ''"
        )
        for row in rows:
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            await db.execute(
                "UPDATE users SET referral_code = ?, membership_tier = 'free' WHERE user_id = ?",
                (code, row['user_id'])
            )

        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)"
        )
        await db.commit()
        print(f"Users referral migration completed (backfilled {len(rows)} users)")


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
