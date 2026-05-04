"""
Hub Schema Contract Tests

Locks the schema contract for the four hub_* tables introduced in issue #446.
These tables form the persistence layer for Epic #437 (Content Hub):

  - hub_groups
  - hub_group_memberships
  - hub_posts
  - hub_post_reactions

Repository classes land in #447; here we cover the schema-level invariants
those repositories will rely on:

  - All four tables created by init_schema.
  - hub_groups.group_id and hub_groups.slug are UNIQUE.
  - hub_group_memberships composite PK rejects duplicate
    (group_id, user_id, child_id).
  - hub_post_reactions composite PK rejects duplicate
    (post_id, user_id, reaction_type).
  - ON DELETE CASCADE: deleting a hub_groups row removes its
    hub_group_memberships rows.
  - ON DELETE CASCADE: deleting a hub_posts row removes its
    hub_post_reactions rows.
  - hub_posts.author_agent_id FK rejects unknown agent_id values.
  - init_schema is idempotent (run twice without error).

Parent Epic: #437
Issue: #446
"""

import pytest
import pytest_asyncio

from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory database with full schema applied."""
    manager = DatabaseManager(":memory:")
    await manager.connect()
    await init_schema(manager)
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def user_repo(db):
    repo = UserRepository()
    repo._db = db
    return repo


@pytest_asyncio.fixture
async def parent_user(user_repo):
    """A real user row to satisfy FKs that point at users.user_id."""
    return await user_repo.create_user(
        username="hubparent",
        email="hubparent@test.com",
        password_hash="h",
    )


@pytest_asyncio.fixture
async def parent_agent(db, parent_user):
    """A real user_agents row to satisfy hub_posts.author_agent_id FK."""
    await db.execute(
        """
        INSERT INTO user_agents (
            agent_id, user_id, child_id, agent_name,
            agent_avatar_id, agent_title, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "agt_hubparent01",
            parent_user.user_id,
            "child-hub",
            "Sparkle",
            "emoji:🦁",
            "Brave Lion",
            "2026-01-01T00:00:00",
            "2026-01-01T00:00:00",
        ),
    )
    await db.commit()
    return "agt_hubparent01"


async def _insert_group(
    db: DatabaseManager,
    *,
    group_id: str,
    slug: str,
    created_by_user_id: str,
    name: str = "Dragons",
    visibility: str = "public",
    invite_token: str | None = None,
    created_at: str = "2026-01-01T00:00:00",
) -> None:
    await db.execute(
        """
        INSERT INTO hub_groups (
            group_id, slug, name, description, theme,
            visibility, invite_token, created_by_user_id, created_at, member_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            group_id,
            slug,
            name,
            None,
            "fantasy",
            visibility,
            invite_token,
            created_by_user_id,
            created_at,
            0,
        ),
    )
    await db.commit()


async def _insert_membership(
    db: DatabaseManager,
    *,
    group_id: str,
    user_id: str,
    child_id: str,
    role: str = "member",
    joined_at: str = "2026-01-02T00:00:00",
) -> None:
    await db.execute(
        """
        INSERT INTO hub_group_memberships (
            group_id, user_id, child_id, role, joined_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (group_id, user_id, child_id, role, joined_at),
    )
    await db.commit()


async def _insert_post(
    db: DatabaseManager,
    *,
    post_id: str,
    group_id: str,
    author_user_id: str,
    author_child_id: str,
    author_agent_id: str,
    agent_name_snapshot: str = "Sparkle",
    agent_avatar_id_snapshot: str = "emoji:🦁",
    agent_title_snapshot: str = "Brave Lion",
    source_artifact_type: str = "art_story",
    source_id: str = "story-1",
    caption: str | None = None,
    safety_score: float = 0.95,
    created_at: str = "2026-01-03T00:00:00",
) -> None:
    await db.execute(
        """
        INSERT INTO hub_posts (
            post_id, group_id, author_user_id, author_child_id, author_agent_id,
            agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot,
            source_artifact_type, source_id, caption, safety_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            group_id,
            author_user_id,
            author_child_id,
            author_agent_id,
            agent_name_snapshot,
            agent_avatar_id_snapshot,
            agent_title_snapshot,
            source_artifact_type,
            source_id,
            caption,
            safety_score,
            created_at,
        ),
    )
    await db.commit()


async def _insert_reaction(
    db: DatabaseManager,
    *,
    post_id: str,
    user_id: str,
    reaction_type: str = "heart",
    created_at: str = "2026-01-04T00:00:00",
) -> None:
    await db.execute(
        """
        INSERT INTO hub_post_reactions (
            post_id, user_id, reaction_type, created_at
        ) VALUES (?, ?, ?, ?)
        """,
        (post_id, user_id, reaction_type, created_at),
    )
    await db.commit()


# ============================================================================
# Contract: tables exist
# ============================================================================


class TestHubTablesExist:
    @pytest.mark.asyncio
    async def test_hub_groups_exists(self, db):
        rows = await db.fetchall("PRAGMA table_info(hub_groups)")
        assert len(rows) > 0, "hub_groups table not created"

    @pytest.mark.asyncio
    async def test_hub_group_memberships_exists(self, db):
        rows = await db.fetchall("PRAGMA table_info(hub_group_memberships)")
        assert len(rows) > 0, "hub_group_memberships table not created"

    @pytest.mark.asyncio
    async def test_hub_posts_exists(self, db):
        rows = await db.fetchall("PRAGMA table_info(hub_posts)")
        assert len(rows) > 0, "hub_posts table not created"

    @pytest.mark.asyncio
    async def test_hub_post_reactions_exists(self, db):
        rows = await db.fetchall("PRAGMA table_info(hub_post_reactions)")
        assert len(rows) > 0, "hub_post_reactions table not created"

    @pytest.mark.asyncio
    async def test_hub_posts_has_persona_snapshot_columns(self, db):
        rows = await db.fetchall("PRAGMA table_info(hub_posts)")
        cols = {row["name"] for row in rows}
        for required in (
            "agent_name_snapshot",
            "agent_avatar_id_snapshot",
            "agent_title_snapshot",
            "author_agent_id",
        ):
            assert required in cols, f"missing column {required}"


# ============================================================================
# Contract: UNIQUE on hub_groups
# ============================================================================


class TestHubGroupsUnique:
    @pytest.mark.asyncio
    async def test_unique_group_id(self, db, parent_user):
        await _insert_group(
            db, group_id="grp-1", slug="dragons", created_by_user_id=parent_user.user_id
        )
        with pytest.raises(Exception):
            await _insert_group(
                db,
                group_id="grp-1",
                slug="dragons-2",
                created_by_user_id=parent_user.user_id,
            )

    @pytest.mark.asyncio
    async def test_unique_slug(self, db, parent_user):
        await _insert_group(
            db, group_id="grp-2", slug="space", created_by_user_id=parent_user.user_id
        )
        with pytest.raises(Exception):
            await _insert_group(
                db,
                group_id="grp-3",
                slug="space",
                created_by_user_id=parent_user.user_id,
            )


# ============================================================================
# Contract: composite PRIMARY KEYs
# ============================================================================


class TestCompositePrimaryKeys:
    @pytest.mark.asyncio
    async def test_membership_pk_rejects_duplicate(self, db, parent_user):
        await _insert_group(
            db,
            group_id="grp-pk-1",
            slug="pk-1",
            created_by_user_id=parent_user.user_id,
        )
        await _insert_membership(
            db,
            group_id="grp-pk-1",
            user_id=parent_user.user_id,
            child_id="child-1",
            role="owner",
        )
        with pytest.raises(Exception):
            await _insert_membership(
                db,
                group_id="grp-pk-1",
                user_id=parent_user.user_id,
                child_id="child-1",
                role="member",
            )

    @pytest.mark.asyncio
    async def test_reactions_pk_rejects_duplicate(
        self, db, parent_user, parent_agent
    ):
        await _insert_group(
            db,
            group_id="grp-pk-2",
            slug="pk-2",
            created_by_user_id=parent_user.user_id,
        )
        await _insert_post(
            db,
            post_id="post-pk-1",
            group_id="grp-pk-2",
            author_user_id=parent_user.user_id,
            author_child_id="child-hub",
            author_agent_id=parent_agent,
        )
        await _insert_reaction(
            db,
            post_id="post-pk-1",
            user_id=parent_user.user_id,
            reaction_type="heart",
        )
        with pytest.raises(Exception):
            await _insert_reaction(
                db,
                post_id="post-pk-1",
                user_id=parent_user.user_id,
                reaction_type="heart",
            )


# ============================================================================
# Contract: ON DELETE CASCADE
# ============================================================================


class TestCascade:
    @pytest.mark.asyncio
    async def test_group_delete_cascades_to_memberships(self, db, parent_user):
        await _insert_group(
            db,
            group_id="grp-cas-1",
            slug="cas-1",
            created_by_user_id=parent_user.user_id,
        )
        await _insert_membership(
            db,
            group_id="grp-cas-1",
            user_id=parent_user.user_id,
            child_id="child-cas-a",
        )
        before = await db.fetchone(
            "SELECT 1 FROM hub_group_memberships WHERE group_id = ?",
            ("grp-cas-1",),
        )
        assert before is not None

        await db.execute(
            "DELETE FROM hub_groups WHERE group_id = ?", ("grp-cas-1",)
        )
        await db.commit()

        after = await db.fetchone(
            "SELECT 1 FROM hub_group_memberships WHERE group_id = ?",
            ("grp-cas-1",),
        )
        assert after is None, (
            "ON DELETE CASCADE did not remove hub_group_memberships rows"
        )

    @pytest.mark.asyncio
    async def test_post_delete_cascades_to_reactions(
        self, db, parent_user, parent_agent
    ):
        await _insert_group(
            db,
            group_id="grp-cas-2",
            slug="cas-2",
            created_by_user_id=parent_user.user_id,
        )
        await _insert_post(
            db,
            post_id="post-cas-1",
            group_id="grp-cas-2",
            author_user_id=parent_user.user_id,
            author_child_id="child-hub",
            author_agent_id=parent_agent,
        )
        await _insert_reaction(
            db,
            post_id="post-cas-1",
            user_id=parent_user.user_id,
            reaction_type="star",
        )
        before = await db.fetchone(
            "SELECT 1 FROM hub_post_reactions WHERE post_id = ?",
            ("post-cas-1",),
        )
        assert before is not None

        await db.execute(
            "DELETE FROM hub_posts WHERE post_id = ?", ("post-cas-1",)
        )
        await db.commit()

        after = await db.fetchone(
            "SELECT 1 FROM hub_post_reactions WHERE post_id = ?",
            ("post-cas-1",),
        )
        assert after is None, (
            "ON DELETE CASCADE did not remove hub_post_reactions rows"
        )


# ============================================================================
# Contract: FK on hub_posts.author_agent_id
# ============================================================================


class TestAuthorAgentIdFK:
    @pytest.mark.asyncio
    async def test_unknown_agent_id_rejected(self, db, parent_user):
        await _insert_group(
            db,
            group_id="grp-fk-1",
            slug="fk-1",
            created_by_user_id=parent_user.user_id,
        )
        with pytest.raises(Exception):
            await _insert_post(
                db,
                post_id="post-fk-1",
                group_id="grp-fk-1",
                author_user_id=parent_user.user_id,
                author_child_id="child-hub",
                author_agent_id="agt_doesnotexist",
            )


# ============================================================================
# Contract: idempotency
# ============================================================================


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_init_schema_runs_twice(self, db):
        # `db` fixture already ran init_schema once. Run it again — must not error.
        await init_schema(db)


# ============================================================================
# Contract: index on hub_posts(group_id, created_at)
# ============================================================================


class TestHubPostsIndex:
    @pytest.mark.asyncio
    async def test_group_created_index_exists(self, db):
        rows = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='hub_posts'"
        )
        names = {row["name"] for row in rows}
        assert "idx_hub_posts_group_created" in names
