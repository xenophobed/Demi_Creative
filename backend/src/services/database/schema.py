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
    story_length_mode TEXT DEFAULT 'short',
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
    parent_email TEXT,
    consent_status TEXT DEFAULT 'not_required',
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

CHILD_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS child_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    age_group TEXT NOT NULL DEFAULT '6-8',
    interests TEXT NOT NULL DEFAULT '[]',
    avatar TEXT,
    is_default INTEGER DEFAULT 0,
    archived_at TEXT,
    camera_consent INTEGER DEFAULT 0,
    microphone_consent INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, child_id)
);
"""

CHILD_PROFILES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_child_profiles_user ON child_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_child_profiles_user_default ON child_profiles(user_id, is_default);
CREATE INDEX IF NOT EXISTS idx_child_profiles_user_archived ON child_profiles(user_id, archived_at);
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
# User Agents Table (#438) — foundation for Epic #436 (My Agent persona)
# ============================================================================

USER_AGENTS_TABLE = """
CREATE TABLE IF NOT EXISTS user_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    agent_avatar_id TEXT NOT NULL,
    agent_title TEXT NOT NULL,
    tone TEXT NOT NULL DEFAULT 'warm_curious',
    interaction_style TEXT NOT NULL DEFAULT 'guided_playful',
    enabled_skills TEXT NOT NULL DEFAULT '["image_story","interactive_story","kids_daily","audio_narration"]',
    favorite_topics TEXT NOT NULL DEFAULT '[]',
    learning_goals TEXT NOT NULL DEFAULT '[]',
    custom_instructions TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, child_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

USER_AGENTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_user_agents_user ON user_agents(user_id);
"""


AGENT_CHAT_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    sdk_session_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    last_message_preview TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

AGENT_CHAT_SESSIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_agent_chat_sessions_user_child ON agent_chat_sessions(user_id, child_id);
"""

AGENT_CHAT_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS agent_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    input_modality TEXT NOT NULL DEFAULT 'text',
    output_modality TEXT NOT NULL DEFAULT 'text',
    result_metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES agent_chat_sessions(session_id) ON DELETE CASCADE
);
"""

AGENT_CHAT_MESSAGES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_agent_chat_messages_session_created ON agent_chat_messages(session_id, created_at);
"""


# ============================================================================
# Hub Tables (#446) — foundation for Epic #437 (Content Hub)
# Tables use the `hub_` prefix to namespace clearly and avoid SQL keyword
# collisions (e.g. `groups` is a SQL reserved word in some dialects).
# ============================================================================

HUB_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS hub_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    theme TEXT,
    visibility TEXT NOT NULL CHECK (visibility IN ('public','private')),
    invite_token TEXT,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(created_by_user_id) REFERENCES users(user_id)
);
"""

HUB_GROUPS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_hub_groups_visibility_created ON hub_groups(visibility, created_at DESC);
"""

HUB_GROUP_MEMBERSHIPS_TABLE = """
CREATE TABLE IF NOT EXISTS hub_group_memberships (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner','member')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY(group_id, user_id, child_id),
    FOREIGN KEY(group_id) REFERENCES hub_groups(group_id) ON DELETE CASCADE
);
"""

HUB_GROUP_MEMBERSHIPS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_hub_group_memberships_user ON hub_group_memberships(user_id, child_id);
"""

HUB_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS hub_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL UNIQUE,
    group_id TEXT NOT NULL,
    author_user_id TEXT NOT NULL,
    author_child_id TEXT NOT NULL,
    author_agent_id TEXT NOT NULL,
    agent_name_snapshot TEXT NOT NULL,
    agent_avatar_id_snapshot TEXT NOT NULL,
    agent_title_snapshot TEXT NOT NULL,
    source_artifact_type TEXT NOT NULL CHECK (source_artifact_type IN ('art_story','interactive_story','kids_daily')),
    source_id TEXT NOT NULL,
    caption TEXT,
    safety_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    removed_at TEXT,
    removed_reason TEXT,
    FOREIGN KEY(group_id) REFERENCES hub_groups(group_id),
    FOREIGN KEY(author_agent_id) REFERENCES user_agents(agent_id)
);
"""

HUB_POSTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_hub_posts_group_created ON hub_posts(group_id, created_at DESC);
"""

HUB_POST_REACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS hub_post_reactions (
    post_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    reaction_type TEXT NOT NULL CHECK (reaction_type IN ('heart','star','wow')),
    created_at TEXT NOT NULL,
    PRIMARY KEY(post_id, user_id, reaction_type),
    FOREIGN KEY(post_id) REFERENCES hub_posts(post_id) ON DELETE CASCADE
);
"""

HUB_POST_REACTIONS_INDEXES = ""


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
    await _migrate_add_parent_registration_columns(db)
    await _migrate_backfill_word_counts(db)
    await _migrate_characters_user_id(db)
    await _migrate_add_styled_image_url(db)
    await _migrate_add_referral_columns(db)
    await _migrate_add_story_length_mode(db)
    await _migrate_add_onboarding_columns(db)
    await _migrate_create_child_profiles_table(db)
    await _migrate_add_child_profile_consent_columns(db)
    await _migrate_add_voice_realtime_columns(db)
    await _migrate_add_voice_premium_columns(db)
    await _migrate_create_voice_sessions_table(db)
    await _migrate_add_voice_session_cost_columns(db)
    await _migrate_add_voice_session_transport_column(db)
    await _migrate_create_user_agents_table(db)
    await _migrate_add_user_agent_config_columns(db)
    await _migrate_create_agent_chat_tables(db)
    await _migrate_add_agent_chat_session_columns(db)
    await _migrate_add_agent_chat_message_modality_columns(db)
    await _migrate_create_hub_groups_table(db)
    await _migrate_create_hub_group_memberships_table(db)
    await _migrate_create_hub_posts_table(db)
    await _migrate_create_hub_post_reactions_table(db)
    await _migrate_hub_posts_allow_kids_daily(db)

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

    # Initialize achievement badge schema (#536)
    from .schema_achievements import init_achievement_schema
    await init_achievement_schema(db)

    # Initialize pgvector schema (#342) — only on PostgreSQL
    from .schema_vectors import init_vector_schema
    await init_vector_schema(db)

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


async def _migrate_add_parent_registration_columns(db: "DatabaseManager") -> None:
    """Migration: Add parent-owned registration fields."""
    changed = False
    if not await column_exists(db, "users", "parent_email"):
        await db.execute("ALTER TABLE users ADD COLUMN parent_email TEXT")
        changed = True
    if not await column_exists(db, "users", "consent_status"):
        await db.execute(
            "ALTER TABLE users ADD COLUMN consent_status TEXT DEFAULT 'not_required'"
        )
        changed = True
    if changed:
        await db.execute(
            """
            UPDATE users
            SET consent_status = CASE
                WHEN role = 'parent' THEN 'not_required'
                ELSE 'pending_parent_consent'
            END
            WHERE consent_status IS NULL OR consent_status = ''
            """
        )
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
    # Decide whether to recreate the table:
    #   - SQLite: inspect the original CREATE TABLE SQL for the UNIQUE clause
    #     (PRAGMA gives no other reliable way to see composite uniques).
    #   - Postgres: query pg_indexes for a unique index covering user_id —
    #     `table_create_sql` on Postgres only reconstructs columns, not
    #     constraints, so the SQLite check would false-positive here every
    #     time and corrupt the table (leaves orphaned `characters_new`).
    needs_migration = True
    if db.dialect == "postgresql":
        # Defensive: if a previous run failed mid-migration we may have
        # an orphaned `characters_new` lying around. Drop it before
        # deciding anything else.
        await db.execute("DROP TABLE IF EXISTS characters_new")
        rows = await db.fetchall(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='characters'"
        )
        for r in rows:
            idx = (r.get("indexdef") or "").lower()
            if "unique" in idx and "user_id" in idx and "child_id" in idx and "name" in idx:
                needs_migration = False
                break
    else:
        create_sql = await table_create_sql(db, "characters")
        if create_sql and 'user_id' in create_sql and 'UNIQUE(user_id' in create_sql.replace(' ', ''):
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


async def _migrate_add_story_length_mode(db: "DatabaseManager") -> None:
    """Migration: Add story_length_mode column to sessions table (#331)."""
    if not await column_exists(db, "sessions", "story_length_mode"):
        print("Migrating sessions table: adding story_length_mode column...")
        await db.execute(
            "ALTER TABLE sessions ADD COLUMN story_length_mode TEXT DEFAULT 'short'"
        )
        await db.commit()
        print("Sessions story_length_mode migration completed")


async def _migrate_add_onboarding_columns(db: "DatabaseManager") -> None:
    """Migration: Add onboarding columns to users table (#438).

    Adds nullable columns that capture onboarding state and parent identity:
    - nickname: friendly name shown in UI
    - onboarded_at: timestamp the user finished onboarding
    - parent_consent_at: timestamp the parent granted consent
    - default_child_id: the active child profile to bind agent persona to

    All columns are NULLABLE to keep this migration non-destructive — existing
    rows are unaffected and stay valid.
    """
    columns = [
        ("nickname", "ALTER TABLE users ADD COLUMN nickname TEXT"),
        ("onboarded_at", "ALTER TABLE users ADD COLUMN onboarded_at TEXT"),
        ("parent_consent_at", "ALTER TABLE users ADD COLUMN parent_consent_at TEXT"),
        ("default_child_id", "ALTER TABLE users ADD COLUMN default_child_id TEXT"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "users", column_name):
            if not added:
                print("Migrating users table: adding onboarding columns (#438)...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Users onboarding migration completed")


async def _migrate_add_child_profile_consent_columns(db: "DatabaseManager") -> None:
    """Migration: Add camera_consent and microphone_consent columns to child_profiles (#587).

    Gates camera and microphone surfaces in epic #579 (tablet/mobile capture).
    Both columns default to 0 (False) because consent must be granted explicitly
    by a parent — children cannot bootstrap their own consent. Existing rows
    inherit the default via the column-level DEFAULT, so no backfill is needed.

    Reversal: column-add is non-destructive; reverting the application code
    leaves the columns intact but unread. A true drop would require a follow-up
    migration if ever needed.
    """
    columns = [
        ("camera_consent", "ALTER TABLE child_profiles ADD COLUMN camera_consent INTEGER DEFAULT 0"),
        ("microphone_consent", "ALTER TABLE child_profiles ADD COLUMN microphone_consent INTEGER DEFAULT 0"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "child_profiles", column_name):
            if not added:
                print("Migrating child_profiles table: adding consent columns (#587)...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Child profile consent migration completed")


async def _migrate_add_voice_realtime_columns(db: "DatabaseManager") -> None:
    """Migration: Add Talk-to-Buddy realtime voice columns to child_profiles (#611).

    Companion to #587 microphone_consent. While microphone_consent gates
    short STT clips (push-to-record voice input), voice_conversation_consent
    gates the new full-duplex spoken channel under PRD §3.16. Voice persona
    binds the buddy's TTS voice; quota_seconds tracks the daily voice budget.

    All three columns default to 0/'buddy_default' so existing rows inherit
    safe defaults via the column-level DEFAULT. No backfill needed.
    """
    columns = [
        ("voice_conversation_consent", "ALTER TABLE child_profiles ADD COLUMN voice_conversation_consent INTEGER DEFAULT 0"),
        ("voice_persona", "ALTER TABLE child_profiles ADD COLUMN voice_persona TEXT DEFAULT 'buddy_default'"),
        ("voice_session_quota_seconds", "ALTER TABLE child_profiles ADD COLUMN voice_session_quota_seconds INTEGER DEFAULT 0"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "child_profiles", column_name):
            if not added:
                print("Migrating child_profiles: adding voice-realtime columns (#611)...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Child profile voice-realtime migration completed")


async def _migrate_add_voice_premium_columns(db: "DatabaseManager") -> None:
    """Migration: Add premium-voice tier-selection flags to child_profiles (#648).

    The tier-selection policy escalates from ``gpt-realtime-mini`` to
    ``gpt-realtime-2`` only when BOTH of these flags are set:

      - ``voice_premium_voice``         — per-child opt-in (parent UI)
      - ``voice_premium_voice_consent`` — parent's explicit consent

    Default 0 (off) so every existing child stays on the cheap mini tier
    until a parent opts in. Idempotent — re-running on a migrated schema
    is a no-op.
    """
    columns = [
        ("voice_premium_voice", "ALTER TABLE child_profiles ADD COLUMN voice_premium_voice INTEGER DEFAULT 0"),
        ("voice_premium_voice_consent", "ALTER TABLE child_profiles ADD COLUMN voice_premium_voice_consent INTEGER DEFAULT 0"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "child_profiles", column_name):
            if not added:
                print("Migrating child_profiles: adding voice premium tier columns (#648)...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Child profile voice-premium migration completed")


VOICE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS voice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER,
    transcript_safety_score REAL,
    termination_reason TEXT,
    provider TEXT,
    model TEXT,
    cost_estimate_usd REAL,
    prompt_cache_hit INTEGER,
    transport TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

VOICE_SESSIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_voice_sessions_user_child ON voice_sessions(user_id, child_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_started_at ON voice_sessions(started_at DESC);
"""


async def _migrate_create_voice_sessions_table(db: "DatabaseManager") -> None:
    """Migration: Create voice_sessions table for Talk-to-Buddy audit + quota (#611).

    Each row tracks one realtime voice session: who, when, how long, how it
    ended, and what provider served it. termination_reason values include
    'user_ended', 'timeout', 'quota', 'safety_fail', 'provider_error',
    'consent_revoked'. Audio bytes are NEVER persisted; only the moderated
    transcript_safety_score is kept for audit.

    #648 adds three cost-telemetry columns: ``model``, ``cost_estimate_usd``,
    ``prompt_cache_hit``. They are NULL for legacy rows and for non-OpenAI
    providers — the broker only populates them when the provider exposes
    a model in its ``provider_state``.
    """
    await db.execute(translate_ddl(VOICE_SESSIONS_TABLE, db.dialect))
    for stmt in VOICE_SESSIONS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_add_voice_session_cost_columns(db: "DatabaseManager") -> None:
    """Migration: Add cost telemetry columns to voice_sessions (#648).

    Idempotent — only adds the columns when missing. Existing rows get
    NULL values which the repository surfaces as ``None`` in the
    ``VoiceSessionData`` dataclass. Hybrid / Mock provider sessions also
    keep NULL since the broker only computes cost for OpenAI sessions.
    """
    columns = [
        ("model", "ALTER TABLE voice_sessions ADD COLUMN model TEXT"),
        ("cost_estimate_usd", "ALTER TABLE voice_sessions ADD COLUMN cost_estimate_usd REAL"),
        ("prompt_cache_hit", "ALTER TABLE voice_sessions ADD COLUMN prompt_cache_hit INTEGER"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "voice_sessions", column_name):
            if not added:
                print("Migrating voice_sessions: adding cost telemetry columns (#648)...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Voice session cost-telemetry migration completed")


async def _migrate_add_voice_session_transport_column(db: "DatabaseManager") -> None:
    """Migration: Add the ``transport`` column to voice_sessions (#647).

    Records whether a session used the WS server-relay path (``ws``) or
    the browser-direct WebRTC path (``webrtc``). Existing rows backfill
    to NULL — the Phase D dashboard treats NULL as ``ws`` since that was
    the only transport before this migration. Idempotent.
    """
    if not await column_exists(db, "voice_sessions", "transport"):
        print("Migrating voice_sessions: adding transport column (#647)...")
        await db.execute("ALTER TABLE voice_sessions ADD COLUMN transport TEXT")
        await db.commit()
        print("Voice session transport migration completed")


async def _migrate_create_child_profiles_table(db: "DatabaseManager") -> None:
    """Migration: Create parent-owned child profile table and backfill defaults."""
    from datetime import datetime

    await db.execute(translate_ddl(CHILD_PROFILES_TABLE, db.dialect))
    for stmt in CHILD_PROFILES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass

    rows = await db.fetchall(
        """
        SELECT user_id, default_child_id, nickname, display_name, created_at, updated_at
        FROM users
        WHERE default_child_id IS NOT NULL AND default_child_id != ''
        """
    )
    for row in rows:
        await db.execute(
            "UPDATE child_profiles SET is_default = 0 WHERE user_id = ?",
            (row["user_id"],),
        )
        existing = await db.fetchone(
            "SELECT 1 FROM child_profiles WHERE user_id = ? AND child_id = ?",
            (row["user_id"], row["default_child_id"]),
        )
        if existing:
            await db.execute(
                """
                UPDATE child_profiles
                SET is_default = 1, updated_at = ?
                WHERE user_id = ? AND child_id = ? AND archived_at IS NULL
                """,
                (
                    row.get("updated_at") or datetime.now().isoformat(),
                    row["user_id"],
                    row["default_child_id"],
                ),
            )
            continue

        now = row.get("created_at") or datetime.now().isoformat()
        name = row.get("nickname") or row.get("display_name") or "Child"
        await db.execute(
            """
            INSERT INTO child_profiles (
                child_id, user_id, name, age_group, interests, avatar,
                is_default, archived_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["default_child_id"],
                row["user_id"],
                name,
                "6-8",
                "[]",
                None,
                1,
                None,
                now,
                row.get("updated_at") or now,
            ),
        )
    await db.commit()


async def _migrate_create_user_agents_table(db: "DatabaseManager") -> None:
    """Migration: Create user_agents table + indexes (#438).

    Foundation for Epic #436 (My Agent — personalized buddy persona). Uses
    CREATE TABLE IF NOT EXISTS so the migration is idempotent across reruns.
    """
    await db.execute(translate_ddl(USER_AGENTS_TABLE, db.dialect))
    for stmt in USER_AGENTS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_add_user_agent_config_columns(db: "DatabaseManager") -> None:
    """Migration: Add guided My Agent configuration columns."""
    columns = [
        ("tone", "ALTER TABLE user_agents ADD COLUMN tone TEXT NOT NULL DEFAULT 'warm_curious'"),
        ("interaction_style", "ALTER TABLE user_agents ADD COLUMN interaction_style TEXT NOT NULL DEFAULT 'guided_playful'"),
        ("enabled_skills", "ALTER TABLE user_agents ADD COLUMN enabled_skills TEXT NOT NULL DEFAULT '[\"image_story\",\"interactive_story\",\"kids_daily\",\"audio_narration\"]'"),
        ("favorite_topics", "ALTER TABLE user_agents ADD COLUMN favorite_topics TEXT NOT NULL DEFAULT '[]'"),
        ("learning_goals", "ALTER TABLE user_agents ADD COLUMN learning_goals TEXT NOT NULL DEFAULT '[]'"),
        ("custom_instructions", "ALTER TABLE user_agents ADD COLUMN custom_instructions TEXT NOT NULL DEFAULT ''"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "user_agents", column_name):
            if not added:
                print("Migrating user_agents table: adding My Agent config columns...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("User agents config migration completed")


async def _migrate_create_agent_chat_tables(db: "DatabaseManager") -> None:
    """Migration: Create lightweight My Agent chat state tables."""
    await db.execute(translate_ddl(AGENT_CHAT_SESSIONS_TABLE, db.dialect))
    for stmt in AGENT_CHAT_SESSIONS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.execute(translate_ddl(AGENT_CHAT_MESSAGES_TABLE, db.dialect))
    for stmt in AGENT_CHAT_MESSAGES_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_add_agent_chat_session_columns(db: "DatabaseManager") -> None:
    """Migration: Add multi-topic session columns to agent_chat_sessions (#566)."""
    columns = [
        ("title", "ALTER TABLE agent_chat_sessions ADD COLUMN title TEXT NOT NULL DEFAULT ''"),
        ("last_message_preview", "ALTER TABLE agent_chat_sessions ADD COLUMN last_message_preview TEXT NOT NULL DEFAULT ''"),
        ("archived_at", "ALTER TABLE agent_chat_sessions ADD COLUMN archived_at TEXT"),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "agent_chat_sessions", column_name):
            if not added:
                print("Migrating agent_chat_sessions: adding multi-topic session columns...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Agent chat session columns migration completed")


async def _migrate_add_agent_chat_message_modality_columns(db: "DatabaseManager") -> None:
    """Migration: tag My Agent chat messages by input/output modality (#668)."""
    columns = [
        (
            "input_modality",
            "ALTER TABLE agent_chat_messages ADD COLUMN input_modality TEXT NOT NULL DEFAULT 'text'",
        ),
        (
            "output_modality",
            "ALTER TABLE agent_chat_messages ADD COLUMN output_modality TEXT NOT NULL DEFAULT 'text'",
        ),
    ]
    added = False
    for column_name, ddl in columns:
        if not await column_exists(db, "agent_chat_messages", column_name):
            if not added:
                print("Migrating agent_chat_messages: adding modality columns...")
                added = True
            await db.execute(ddl)
    if added:
        await db.commit()
        print("Agent chat message modality migration completed")


async def _migrate_create_hub_groups_table(db: "DatabaseManager") -> None:
    """Migration: Create hub_groups table + indexes (#446).

    Foundation for Epic #437 (Content Hub). Uses CREATE TABLE IF NOT EXISTS
    so the migration is idempotent across reruns.
    """
    await db.execute(translate_ddl(HUB_GROUPS_TABLE, db.dialect))
    for stmt in HUB_GROUPS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_create_hub_group_memberships_table(db: "DatabaseManager") -> None:
    """Migration: Create hub_group_memberships table + indexes (#446)."""
    await db.execute(translate_ddl(HUB_GROUP_MEMBERSHIPS_TABLE, db.dialect))
    for stmt in HUB_GROUP_MEMBERSHIPS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_create_hub_posts_table(db: "DatabaseManager") -> None:
    """Migration: Create hub_posts table + indexes (#446).

    Stores per-post agent persona snapshots so feed reads never need to
    join `users` — preserves the COPPA invariant in #450.
    """
    await db.execute(translate_ddl(HUB_POSTS_TABLE, db.dialect))
    for stmt in HUB_POSTS_INDEXES.strip().split(";"):
        if stmt.strip():
            try:
                await db.execute(stmt)
            except Exception:
                pass
    await db.commit()


async def _migrate_create_hub_post_reactions_table(db: "DatabaseManager") -> None:
    """Migration: Create hub_post_reactions table (#446).

    No additional indexes — the composite primary key
    (post_id, user_id, reaction_type) covers all access patterns.
    """
    await db.execute(translate_ddl(HUB_POST_REACTIONS_TABLE, db.dialect))
    if HUB_POST_REACTIONS_INDEXES.strip():
        for stmt in HUB_POST_REACTIONS_INDEXES.strip().split(";"):
            if stmt.strip():
                try:
                    await db.execute(stmt)
                except Exception:
                    pass
    await db.commit()


async def _migrate_hub_posts_allow_kids_daily(db: "DatabaseManager") -> None:
    """Extend the hub_posts.source_artifact_type CHECK to include 'kids_daily'.

    SQLite cannot modify a CHECK in place — we have to rebuild the table
    when the existing CHECK is the older two-value form. The function is
    idempotent: it inspects sqlite_master.sql and skips when the CHECK
    already includes 'kids_daily'. Postgres path uses ALTER CONSTRAINT
    via translate_ddl-equivalent direct SQL.
    """
    if db.dialect == "sqlite":
        row = await db.fetchone(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='hub_posts'"
        )
        sql = (row["sql"] if row else "") or ""
        if "kids_daily" in sql or not sql:
            return  # already migrated, or table doesn't exist (fresh install ran the new constant)
        # Rebuild: copy rows into a new table with the expanded CHECK,
        # drop the old one, rename. Indexes are recreated because they
        # also drop with the table.
        print("Migrating hub_posts CHECK to allow kids_daily...")
        await db.execute(
            """
            CREATE TABLE hub_posts__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL UNIQUE,
                group_id TEXT NOT NULL,
                author_user_id TEXT NOT NULL,
                author_child_id TEXT NOT NULL,
                author_agent_id TEXT NOT NULL,
                agent_name_snapshot TEXT NOT NULL,
                agent_avatar_id_snapshot TEXT NOT NULL,
                agent_title_snapshot TEXT NOT NULL,
                source_artifact_type TEXT NOT NULL CHECK (source_artifact_type IN ('art_story','interactive_story','kids_daily')),
                source_id TEXT NOT NULL,
                caption TEXT,
                safety_score REAL NOT NULL,
                created_at TEXT NOT NULL,
                removed_at TEXT,
                removed_reason TEXT,
                FOREIGN KEY(group_id) REFERENCES hub_groups(group_id),
                FOREIGN KEY(author_agent_id) REFERENCES user_agents(agent_id)
            )
            """
        )
        await db.execute(
            "INSERT INTO hub_posts__new SELECT * FROM hub_posts"
        )
        await db.execute("DROP TABLE hub_posts")
        await db.execute("ALTER TABLE hub_posts__new RENAME TO hub_posts")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_hub_posts_group_created ON hub_posts(group_id, created_at DESC)"
        )
        await db.commit()
        print("hub_posts CHECK migration completed")
    else:
        # Postgres: drop the constraint by name and re-add. Postgres
        # auto-generates constraint names as <table>_<col>_check — but
        # we wrap in try/except so a name mismatch (older migration
        # wrote a different name) doesn't blow up startup.
        try:
            await db.execute(
                "ALTER TABLE hub_posts DROP CONSTRAINT IF EXISTS hub_posts_source_artifact_type_check"
            )
            await db.execute(
                "ALTER TABLE hub_posts ADD CONSTRAINT hub_posts_source_artifact_type_check "
                "CHECK (source_artifact_type IN ('art_story','interactive_story','kids_daily'))"
            )
            await db.commit()
        except Exception:
            # Idempotent: if we can't drop/add (e.g. constraint already
            # has the new shape), continue silently.
            pass


# ============================================================================
# Data Migration
# ============================================================================

async def migrate_json_sessions(db: "DatabaseManager", sessions_dir: str = "./data/sessions") -> int:
    """
    Migrate JSON session files to SQLite database

    Args:
        db: Database manager instance
        sessions_dir: JSON session files directory

    Returns:
        int: Number of migrated sessions
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

            # Check if already migrated (by querying database)
            existing = await db.fetchone(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (data['session_id'],)
            )
            if existing:
                continue

            # Insert session data
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

            # Insert story segments
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

            # Rename migrated files
            migrated_file = json_file.with_suffix('.json.migrated')
            json_file.rename(migrated_file)

            migrated += 1

        except Exception as e:
            print(f"⚠️ Error migrating {json_file.name}: {e}")
            continue

    if migrated > 0:
        print(f"✅ Migrated {migrated} sessions from JSON to SQLite")

    return migrated
