"""
enabled_skills server-side validation contract (#608 rescoped).

Two layers of defense for parent-disabled skills on the voice surface:

  1. Token-mint guard — refuse to mint a voice token (HTTP 409) when
     the persona has ALL three launch-flow skills disabled. The voice
     channel has nothing useful to do in that state.
  2. Tool-set filter — ``filter_tool_definitions_by_skills`` strips
     launch tools the persona has disabled, so even a partially-enabled
     persona never exposes a disabled tool to the OpenAI Realtime model.

The model can't call a tool it doesn't know about; this is defense in
depth on top of the agent-proxy ``_enabled`` check that fires when a
specialist actually runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services.database import (
    agent_repo,
    child_profile_repo,
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.realtime_voice_service import (
    MockRealtimeVoiceProvider,
    SessionHandle,
)
from backend.src.services.realtime_voice_tools import (
    TOOL_SKILL_REQUIREMENTS,
    filter_tool_definitions_by_skills,
    get_tool_definitions,
)
from backend.src.services.user_service import UserData


PARENT_USER = UserData(
    user_id="voice_skills_parent",
    username="voice_skills_parent",
    email="parent@skills-test.com",
    password_hash="h",
    display_name="Parent",
    role="parent",
    created_at="",
    updated_at="",
)


async def _override_current_user() -> UserData:
    return PARENT_USER


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)
    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    now = datetime.now().isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (user_id, username, email, password_hash, display_name,
                           is_active, is_verified, role, parent_email, consent_status,
                           membership_tier, referral_code, referred_by,
                           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            PARENT_USER.user_id, PARENT_USER.username, PARENT_USER.email,
            PARENT_USER.password_hash, PARENT_USER.display_name, 1, 1, "parent",
            None, "not_required", "free", "SKILLZ", None, now, now,
        ),
    )
    await db_manager.commit()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


async def _make_consented_child(*, child_id: str = "child_alpha") -> str:
    repo = ChildProfileRepository(db_manager)
    profile = await repo.create(
        user_id=PARENT_USER.user_id,
        child_id=child_id,
        name="Ada",
        age_group="6-8",
        is_default=True,
    )
    await repo.update_consent(
        user_id=PARENT_USER.user_id,
        child_id=profile.child_id,
        microphone_consent=True,
        voice_conversation_consent=True,
        voice_session_quota_seconds=600,
    )
    return profile.child_id


async def _make_agent(*, child_id: str, enabled_skills: List[str]) -> None:
    await agent_repo.upsert_agent(
        user_id=PARENT_USER.user_id,
        child_id=child_id,
        agent_name="Buddy",
        agent_avatar_id="avatar_1",
        agent_title="Friend",
        enabled_skills=enabled_skills,
    )


@pytest_asyncio.fixture
async def client(test_db):
    app.dependency_overrides[get_current_user] = _override_current_user
    voice_realtime._set_test_provider_override(MockRealtimeVoiceProvider())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)
    voice_realtime._set_test_provider_override(None)


# ===========================================================================
# (1) Pure helper — filter_tool_definitions_by_skills
# ===========================================================================


class TestFilterToolDefinitionsBySkills:
    """The pure helper the broker uses to gate ``session.update``."""

    def test_skill_requirements_map_covers_every_tool(self):
        # If a future tool is added, the requirements map MUST be
        # updated or the filter defaults to "allow everything" which
        # would silently re-expose a disabled flow.
        names = {d["name"] for d in get_tool_definitions()}
        assert names == set(TOOL_SKILL_REQUIREMENTS.keys()), (
            f"TOOL_SKILL_REQUIREMENTS drift: "
            f"missing={names - set(TOOL_SKILL_REQUIREMENTS.keys())}, "
            f"extra={set(TOOL_SKILL_REQUIREMENTS.keys()) - names}"
        )

    def test_unconditional_tools_always_present(self):
        # recall_memory / safety_review_reply / end_call are always
        # exposed — kids must be able to look up their own stories,
        # the model must always be able to ask for a safety check, and
        # the kid must always be able to say goodbye.
        for skills in ([], ["image_story"], None):
            out = filter_tool_definitions_by_skills(skills)
            names = {d["name"] for d in out}
            assert "recall_memory" in names
            assert "safety_review_reply" in names
            assert "end_call" in names

    def test_full_skill_set_yields_full_tool_list(self):
        all_skills = [
            "image_story", "interactive_story", "kids_daily", "audio_narration",
        ]
        out = filter_tool_definitions_by_skills(all_skills)
        assert {d["name"] for d in out} == {
            "launch_image_story",
            "launch_interactive_story",
            "launch_kids_daily",
            "recall_memory",
            "safety_review_reply",
            "end_call",
        }

    def test_disabled_image_story_strips_launch_image_story(self):
        # Parent disabled image-story but left the others on.
        out = filter_tool_definitions_by_skills(
            ["interactive_story", "kids_daily"]
        )
        names = {d["name"] for d in out}
        assert "launch_image_story" not in names
        assert "launch_interactive_story" in names
        assert "launch_kids_daily" in names

    def test_disabled_interactive_story_strips_launch_interactive(self):
        out = filter_tool_definitions_by_skills(["image_story", "kids_daily"])
        names = {d["name"] for d in out}
        assert "launch_interactive_story" not in names
        assert "launch_image_story" in names
        assert "launch_kids_daily" in names

    def test_disabled_kids_daily_strips_launch_kids_daily(self):
        out = filter_tool_definitions_by_skills(
            ["image_story", "interactive_story"]
        )
        names = {d["name"] for d in out}
        assert "launch_kids_daily" not in names
        assert "launch_image_story" in names
        assert "launch_interactive_story" in names

    def test_empty_skills_strips_all_launch_tools(self):
        out = filter_tool_definitions_by_skills([])
        names = {d["name"] for d in out}
        assert "launch_image_story" not in names
        assert "launch_interactive_story" not in names
        assert "launch_kids_daily" not in names
        # But unconditional ones survive — see test above.
        assert "recall_memory" in names
        assert "end_call" in names

    def test_none_preserves_pre_608_behavior(self):
        # Legacy callers (no persona context) get the full surface.
        out = filter_tool_definitions_by_skills(None)
        assert {d["name"] for d in out} == {d["name"] for d in get_tool_definitions()}


# ===========================================================================
# (2) Token-mint guard — REST /session refuses zero-launch-skill personas
# ===========================================================================


class TestTokenMintEnabledSkillsGuard:
    @pytest.mark.asyncio
    async def test_session_minted_with_all_launch_skills(self, client, test_db):
        child_id = await _make_consented_child(child_id="child_full")
        await _make_agent(
            child_id=child_id,
            enabled_skills=[
                "image_story", "interactive_story", "kids_daily", "audio_narration",
            ],
        )
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": child_id},
        )
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_session_minted_with_partial_launch_skills(self, client, test_db):
        # Only kids_daily enabled — voice still works, the broker just
        # exposes a smaller tool set to the model.
        child_id = await _make_consented_child(child_id="child_partial")
        await _make_agent(
            child_id=child_id,
            enabled_skills=["kids_daily", "audio_narration"],
        )
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": child_id},
        )
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_session_refused_when_all_launch_skills_disabled(
        self, client, test_db,
    ):
        # Parent disabled every launch-flow skill. Buddy can't hand off
        # to anything, so the broker refuses the token mint.
        child_id = await _make_consented_child(child_id="child_locked")
        await _make_agent(
            child_id=child_id,
            enabled_skills=["audio_narration"],  # no launch skills
        )
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": child_id},
        )
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "VOICE_SKILL_DISABLED"
        # The refusal code identifies which guard fired so future tests
        # / clients can branch on it without parsing prose.
        assert detail["skill"] == "all_launch_skills_disabled"

    @pytest.mark.asyncio
    async def test_session_minted_when_no_persona_exists(self, client, test_db):
        # No persona row at all → defaults apply, voice is allowed.
        # Pre-608 behavior preserved.
        child_id = await _make_consented_child(child_id="child_no_persona")
        response = await client.post(
            "/api/v1/me/agent/voice/session",
            json={"child_id": child_id},
        )
        assert response.status_code == 200, response.text


# ===========================================================================
# (3) Provider session.update receives the filtered tool list
# ===========================================================================


class _StubOpenAIProviderCapturingTools:
    """Provider stub that records the ``enabled_skills`` it receives."""

    name = "openai_realtime"

    def __init__(self):
        self.captured_enabled_skills: Optional[List[str]] = None
        self.captured_filtered_tools: Optional[List[Dict[str, Any]]] = None

    async def start_session(
        self, *, user_id, child_id, target_age, persona="buddy_default",
        enabled_skills=None, **_kwargs,
    ):
        # Capture the inputs so the test can assert the broker forwarded
        # the persona's enabled_skills + the resulting filtered tool list.
        self.captured_enabled_skills = (
            list(enabled_skills) if enabled_skills is not None else None
        )
        self.captured_filtered_tools = filter_tool_definitions_by_skills(
            enabled_skills,
        )
        return SessionHandle(
            session_id=f"voice_skills_{user_id}",
            user_id=user_id, child_id=child_id,
            target_age=target_age, persona=persona,
            provider_state={
                "openai_client_secret": "ek_skills",
                "model": "gpt-realtime-mini",
                "prompt_cache_hit": False,
            },
        )

    async def close(self, h):
        pass


class TestBrokerForwardsEnabledSkills:
    """The WS broker must forward the persona's ``enabled_skills`` to the
    provider's ``start_session`` so the tool filter fires before
    ``session.update``."""

    @pytest.mark.asyncio
    async def test_broker_forwards_partial_enabled_skills(self, client, test_db):
        from backend.src.services.voice_ephemeral_token import (
            _reset_nonce_store_for_tests,
            mint_voice_token,
        )
        from fastapi.testclient import TestClient

        _reset_nonce_store_for_tests()

        child_id = await _make_consented_child(child_id="child_partial_forward")
        await _make_agent(
            child_id=child_id,
            enabled_skills=["image_story", "kids_daily"],  # interactive_story disabled
        )

        stub = _StubOpenAIProviderCapturingTools()
        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=child_id,
            provider="openai_realtime",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=child_id,
        )

        voice_realtime._set_test_provider_override(stub)
        try:
            sync_client = TestClient(app)
            with sync_client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({"type": "client_done"})
                # Drain a few events so the broker reaches the finally block.
                for _ in range(3):
                    try:
                        ws.receive_json()
                    except Exception:
                        break
        finally:
            voice_realtime._set_test_provider_override(
                MockRealtimeVoiceProvider()
            )

        assert stub.captured_enabled_skills is not None, (
            "broker did not forward enabled_skills to provider.start_session"
        )
        assert set(stub.captured_enabled_skills) == {"image_story", "kids_daily"}
        assert stub.captured_filtered_tools is not None
        names = {t["name"] for t in stub.captured_filtered_tools}
        # interactive_story is disabled → its launch tool is filtered out
        assert "launch_interactive_story" not in names, (
            f"disabled launch tool leaked to session.update: {names}"
        )
        assert "launch_image_story" in names
        assert "launch_kids_daily" in names
        # Unconditional tools survive
        assert "recall_memory" in names
        assert "end_call" in names
