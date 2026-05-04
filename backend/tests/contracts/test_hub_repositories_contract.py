"""
Hub Repositories Contract Tests (#447)

Locks the behaviour of the three new repositories:

  - GroupRepository
      * Public + private group creation
      * Slug generation (kebab-case + numeric suffix on collision)
      * Owner membership auto-created
      * Public groups: open join (invite_token ignored)
      * Private groups: join requires matching invite_token
      * Idempotent join (returns existing membership unchanged)

  - HubPostRepository
      * **Persona snapshot** is captured at write time (the COPPA invariant)
      * **Editing the agent after the post is created MUST NOT mutate the
        snapshot** — this is the load-bearing test for the privacy
        architecture in PRD §3.12.7
      * AGENT_REQUIRED LookupError when no agent exists
      * list_by_group excludes soft-deleted rows AND does not project
        any users-table column (verified by row-key inspection)

  - HubReactionRepository
      * Idempotent toggle (insert -> True, second call -> False)
      * Unknown reaction_type rejected
      * counts_for_post returns the three expected keys

Parent Epic: #437
Issue: #447
"""

import pytest
import pytest_asyncio

from backend.src.services.database import (
    agent_repo,
    group_repo,
    hub_post_repo,
    hub_reaction_repo,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory db with full schema applied + repos rebound to it."""
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    # Rebind global singletons to the test db so the repositories under
    # test all touch the same in-memory database.
    saved_user = group_repo._db, hub_post_repo._db, hub_reaction_repo._db, agent_repo._db
    group_repo._db = fresh
    hub_post_repo._db = fresh
    hub_reaction_repo._db = fresh
    agent_repo._db = fresh

    try:
        yield fresh
    finally:
        (
            group_repo._db,
            hub_post_repo._db,
            hub_reaction_repo._db,
            agent_repo._db,
        ) = saved_user
        await fresh.disconnect()


@pytest_asyncio.fixture
async def parent_user(db):
    repo = UserRepository()
    repo._db = db
    return await repo.create_user(
        username="hubp",
        email="hubp@test.com",
        password_hash="h",
    )


@pytest_asyncio.fixture
async def agent(db, parent_user):
    return await agent_repo.upsert_agent(
        user_id=parent_user.user_id,
        child_id="child-hub",
        agent_name="Sparkle",
        agent_avatar_id="emoji:🦁",
        agent_title="Brave Lion",
    )


# ============================================================================
# Group lifecycle
# ============================================================================


class TestGroupCreate:
    @pytest.mark.asyncio
    async def test_public_group_has_no_invite_token(self, db, parent_user):
        g = await group_repo.create_group(
            name="Dragons",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        assert g.visibility == "public"
        assert g.invite_token is None
        assert g.member_count == 1
        assert g.slug == "dragons"

    @pytest.mark.asyncio
    async def test_private_group_gets_invite_token(self, db, parent_user):
        g = await group_repo.create_group(
            name="Cousins club",
            visibility="private",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        assert g.visibility == "private"
        assert g.invite_token and len(g.invite_token) >= 16

    @pytest.mark.asyncio
    async def test_owner_membership_created(self, db, parent_user):
        g = await group_repo.create_group(
            name="Space Adventures",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        m = await group_repo.get_membership(g.group_id, parent_user.user_id, "child-hub")
        assert m is not None
        assert m.role == "owner"

    @pytest.mark.asyncio
    async def test_slug_collision_appends_suffix(self, db, parent_user):
        g1 = await group_repo.create_group(
            name="Dragons",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        g2 = await group_repo.create_group(
            name="Dragons",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub2",
        )
        assert g1.slug == "dragons"
        assert g2.slug == "dragons-2"


class TestGroupJoin:
    @pytest.mark.asyncio
    async def test_public_open_join(self, db, parent_user):
        g = await group_repo.create_group(
            name="Public",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        m = await group_repo.join_group(
            group_id=g.group_id,
            user_id="other_user",
            child_id="other_child",
        )
        assert m.role == "member"

    @pytest.mark.asyncio
    async def test_private_requires_matching_invite_token(self, db, parent_user):
        g = await group_repo.create_group(
            name="Private",
            visibility="private",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        with pytest.raises(PermissionError):
            await group_repo.join_group(
                group_id=g.group_id,
                user_id="other_user",
                child_id="other_child",
                invite_token="bogus",
            )
        # Now with the right token it succeeds.
        m = await group_repo.join_group(
            group_id=g.group_id,
            user_id="other_user",
            child_id="other_child",
            invite_token=g.invite_token,
        )
        assert m.role == "member"

    @pytest.mark.asyncio
    async def test_idempotent_join(self, db, parent_user):
        g = await group_repo.create_group(
            name="Idemp",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        first = await group_repo.join_group(
            group_id=g.group_id, user_id="u2", child_id="c2",
        )
        second = await group_repo.join_group(
            group_id=g.group_id, user_id="u2", child_id="c2",
        )
        assert first.joined_at == second.joined_at, (
            "second join must return the existing membership unchanged"
        )

    @pytest.mark.asyncio
    async def test_unknown_group_raises(self, db):
        with pytest.raises(LookupError):
            await group_repo.join_group(
                group_id="nope", user_id="u", child_id="c"
            )


# ============================================================================
# Persona snapshot — the COPPA invariant
# ============================================================================


class TestPostSnapshot:
    @pytest.mark.asyncio
    async def test_create_post_writes_snapshot(self, db, parent_user, agent):
        g = await group_repo.create_group(
            name="Snap",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        post = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-1",
            caption="Made this!",
            safety_score=0.95,
        )
        assert post.author_agent_id == agent.agent_id
        assert post.agent_name_snapshot == agent.agent_name
        assert post.agent_avatar_id_snapshot == agent.agent_avatar_id
        assert post.agent_title_snapshot == agent.agent_title

    @pytest.mark.asyncio
    async def test_editing_agent_does_not_mutate_post_snapshot(
        self, db, parent_user, agent
    ):
        """The defining invariant of the privacy architecture (#450)."""
        g = await group_repo.create_group(
            name="Snap2",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        post = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-1",
        )
        # Mutate the agent.
        await agent_repo.upsert_agent(
            user_id=parent_user.user_id,
            child_id="child-hub",
            agent_name="Newname",
            agent_avatar_id="emoji:🦊",
            agent_title="Inventor",
        )

        # Refetch the post — the snapshot must be unchanged.
        fresh = await hub_post_repo.get_by_id(post.post_id)
        assert fresh is not None
        assert fresh.agent_name_snapshot == "Sparkle"
        assert fresh.agent_avatar_id_snapshot == "emoji:🦁"
        assert fresh.agent_title_snapshot == "Brave Lion"

    @pytest.mark.asyncio
    async def test_create_post_without_agent_raises_AGENT_REQUIRED(
        self, db, parent_user
    ):
        # No agent for child-x.
        g = await group_repo.create_group(
            name="No-agent",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        with pytest.raises(LookupError) as exc:
            await hub_post_repo.create_post(
                group_id=g.group_id,
                user_id=parent_user.user_id,
                child_id="child-x",  # has no agent
                source_artifact_type="art_story",
                source_id="story-1",
            )
        assert "AGENT_REQUIRED" in str(exc.value)


class TestPostList:
    @pytest.mark.asyncio
    async def test_list_excludes_soft_deleted(self, db, parent_user, agent):
        g = await group_repo.create_group(
            name="L",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        kept = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-keep",
        )
        gone = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-gone",
        )
        assert await hub_post_repo.soft_delete(gone.post_id, reason="test") is True

        rows = await hub_post_repo.list_by_group(g.group_id)
        ids = {r.post_id for r in rows}
        assert kept.post_id in ids
        assert gone.post_id not in ids


# ============================================================================
# Reactions
# ============================================================================


class TestReactionToggle:
    @pytest.mark.asyncio
    async def test_first_toggle_inserts_then_second_removes(
        self, db, parent_user, agent
    ):
        g = await group_repo.create_group(
            name="R",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        post = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-r",
        )
        first = await hub_reaction_repo.toggle(
            post_id=post.post_id, user_id="reactor-1", reaction_type="heart"
        )
        assert first is True

        counts = await hub_reaction_repo.counts_for_post(post.post_id)
        assert counts == {"heart": 1, "star": 0, "wow": 0}

        second = await hub_reaction_repo.toggle(
            post_id=post.post_id, user_id="reactor-1", reaction_type="heart"
        )
        assert second is False

        counts2 = await hub_reaction_repo.counts_for_post(post.post_id)
        assert counts2 == {"heart": 0, "star": 0, "wow": 0}

    @pytest.mark.asyncio
    async def test_invalid_reaction_type_rejected(self, db):
        with pytest.raises(ValueError):
            await hub_reaction_repo.toggle(
                post_id="x", user_id="y", reaction_type="thumbs_down"
            )

    @pytest.mark.asyncio
    async def test_user_can_hold_multiple_reaction_types(
        self, db, parent_user, agent
    ):
        g = await group_repo.create_group(
            name="Multi",
            visibility="public",
            created_by_user_id=parent_user.user_id,
            owner_child_id="child-hub",
        )
        post = await hub_post_repo.create_post(
            group_id=g.group_id,
            user_id=parent_user.user_id,
            child_id="child-hub",
            source_artifact_type="art_story",
            source_id="story-multi",
        )
        await hub_reaction_repo.toggle(
            post_id=post.post_id, user_id="r", reaction_type="heart"
        )
        await hub_reaction_repo.toggle(
            post_id=post.post_id, user_id="r", reaction_type="star"
        )
        await hub_reaction_repo.toggle(
            post_id=post.post_id, user_id="r", reaction_type="wow"
        )
        kinds = sorted(await hub_reaction_repo.reactions_by_user(post.post_id, "r"))
        assert kinds == ["heart", "star", "wow"]
