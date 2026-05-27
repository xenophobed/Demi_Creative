"""My Agent Buddy Memory Injection Contract Tests (#558, #559).

Locks down the contract that ``my_agent_proxy`` injects the child's
prior memory into every buddy chat turn:

  - ``_build_user_prompt`` accepts a ``story_memory`` kwarg and appends
    it only when non-empty (no empty-header leakage).
  - ``stream_my_agent_chat`` calls ``get_story_memory_prompt`` with the
    active ``child_id`` and ``user_id`` so the buddy sees the same
    episodic + recurring-character memory the specialist agents already
    see.
  - The injected text reaches the prompt passed to the SDK ``query()``
    call — i.e. the model actually sees it, not just an unused local.

Parent Epic: #557 (Buddy Memory Wiring)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.src.agents import my_agent_proxy
from backend.src.services.database import db_manager
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema

from .test_my_agent_proxy import (
    _TEST_CHILD_ID,
    _TEST_USER_ID,
    _FakeSDKClient,
    _fake_agent,
    _fake_result_message,
    _parse_sse_events,
)


# ---------------------------------------------------------------------------
# Pure helper: _build_user_prompt
# ---------------------------------------------------------------------------


class TestBuildUserPromptEpisodicMemory:
    """``_build_user_prompt`` must accept the ``story_memory`` kwarg and
    append the block only when non-empty — empty calls must NOT leak a
    ``**Story Memory**`` header into the prompt (the model would try to
    address it and confuse the child)."""

    def test_empty_story_memory_does_not_leak_header(self):
        prompt = my_agent_proxy._build_user_prompt(
            my_agent_context="ctx",
            history="",
            image_path=None,
            message="hi",
            story_memory="",
        )
        assert "**Story Memory**" not in prompt
        assert "**Recurring Characters**" not in prompt

    def test_story_memory_block_appended_when_populated(self):
        block = (
            "\n\n**Story Memory**:\n"
            "1. Lightning Dog flew to the moon (themes: space, friendship)\n"
        )
        prompt = my_agent_proxy._build_user_prompt(
            my_agent_context="ctx",
            history="",
            image_path=None,
            message="hi",
            story_memory=block,
        )
        assert "**Story Memory**" in prompt
        assert "Lightning Dog flew to the moon" in prompt

    def test_story_memory_block_appears_with_other_sections(self):
        """The memory block must coexist with history + profile sections
        without clobbering them."""
        prompt = my_agent_proxy._build_user_prompt(
            my_agent_context="ctx",
            history="user: hi\nassistant: hello",
            image_path=None,
            message="continue our story",
            child_id="c1",
            age_group="6-8",
            interests=["dragons"],
            story_memory="\n\n**Story Memory**:\n1. The dragon adventure...\n",
        )
        assert "Recent chat:" in prompt
        assert "Active child profile:" in prompt
        assert "**Story Memory**" in prompt
        assert "The dragon adventure" in prompt


# ---------------------------------------------------------------------------
# Wiring: stream_my_agent_chat -> get_story_memory_prompt -> SDK prompt
# ---------------------------------------------------------------------------


import pytest_asyncio


@pytest_asyncio.fixture
async def test_db():
    """Mirror of the fixture in test_my_agent_proxy — same shape so the
    proxy's chat repo / agent repo can reach an in-memory db."""
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    from datetime import datetime as _dt

    now = _dt.now().isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (
            user_id, username, email, password_hash, display_name,
            is_active, is_verified, role,
            membership_tier, referral_code, referred_by,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _TEST_USER_ID,
            "proxy_test_user",
            "proxy@test.com",
            "h",
            "Proxy",
            1,
            1,
            "child",
            "free",
            "TESTPROXY",
            None,
            now,
            now,
        ),
    )
    await db_manager.commit()

    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


class _PromptCapturingSDKClient(_FakeSDKClient):
    """Captures the prompt string passed to ``client.query(...)`` so the
    test can assert the buddy actually sees the injected memory."""

    def __init__(self, *, messages):
        super().__init__(messages=messages)
        self.captured_prompt: str | None = None

    async def query(self, prompt):  # type: ignore[override]
        self.captured_prompt = prompt
        return None


async def _drive_chat_with_memory(
    *,
    story_memory_return: str,
    message: str = "hi buddy",
):
    """Drive ``stream_my_agent_chat`` with a fake SDK + patched
    ``get_story_memory_prompt`` and return (captured_prompt, mock).

    The safety MCP is stubbed to a passing envelope so the reply (and any
    behaviour gated on safety) is exercised end-to-end without spinning
    a real subagent.
    """
    fake_client = _PromptCapturingSDKClient(
        messages=[_fake_result_message("Hi there!")]
    )
    fake_agent = _fake_agent(
        enabled_skills=["image_story", "interactive_story", "kids_daily", "audio_narration"]
    )
    safe_envelope = {"content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]}
    story_memory_mock = AsyncMock(return_value=story_memory_return)

    with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=fake_agent)), \
         patch.object(my_agent_proxy, "ClaudeSDKClient", lambda *a, **kw: fake_client), \
         patch.object(
             my_agent_proxy,
             "build_my_agent_context",
             new=AsyncMock(return_value="ctx"),
         ), \
         patch.object(
             my_agent_proxy,
             "get_story_memory_prompt",
             new=story_memory_mock,
         ), \
         patch(
             "backend.src.agents.my_agent_proxy.check_content_safety.handler",
             new=AsyncMock(return_value=safe_envelope),
         ):
        chunks: list[str] = []
        async for chunk in my_agent_proxy.stream_my_agent_chat(
            user_id=_TEST_USER_ID,
            child_id=_TEST_CHILD_ID,
            message=message,
        ):
            chunks.append(chunk)

    return fake_client.captured_prompt, story_memory_mock, _parse_sse_events("".join(chunks))


class TestStoryMemoryFetchedPerTurn:
    """``stream_my_agent_chat`` must fetch the child's episodic memory
    every turn and pass it into ``_build_user_prompt``."""

    @pytest.mark.asyncio
    async def test_get_story_memory_prompt_called_with_user_and_child_scope(self, test_db):
        """Cross-user isolation precedent (#288): always scope by user_id."""
        _, mock, _ = await _drive_chat_with_memory(story_memory_return="")
        mock.assert_awaited_once()
        # Accept either positional (child_id) or keyword form, since the
        # helper signature is ``get_story_memory_prompt(child_id, *, user_id="")``.
        args, kwargs = mock.call_args
        # child_id is positional or kw
        if args:
            assert args[0] == _TEST_CHILD_ID
        else:
            assert kwargs.get("child_id") == _TEST_CHILD_ID
        assert kwargs.get("user_id") == _TEST_USER_ID

    @pytest.mark.asyncio
    async def test_empty_memory_does_not_leak_into_prompt(self, test_db):
        prompt, _, _ = await _drive_chat_with_memory(story_memory_return="")
        assert prompt is not None
        assert "**Story Memory**" not in prompt
        assert "**Recurring Characters**" not in prompt

    @pytest.mark.asyncio
    async def test_populated_memory_reaches_sdk_prompt(self, test_db):
        block = (
            "\n\n**Story Memory**:\n"
            "1. Lightning Dog flew to the moon (themes: space, friendship)\n"
            "\n\n**Recurring Characters**:\n"
            "- **Lightning Dog** (appeared 3 times): brave, curious\n"
        )
        prompt, _, _ = await _drive_chat_with_memory(story_memory_return=block)
        assert prompt is not None
        assert "**Story Memory**" in prompt
        assert "Lightning Dog flew to the moon" in prompt
        assert "**Recurring Characters**" in prompt
        assert "Lightning Dog" in prompt


# ---------------------------------------------------------------------------
# Factual memory injection (#559) — preferences from PreferenceRepository
# ---------------------------------------------------------------------------


from backend.src.services import my_agent_memory  # noqa: E402


class TestBuildFactualMemoryPrompt:
    """The factual-memory helper must turn a normalized preference profile
    into an empty-safe markdown block. The buddy uses this to say things
    like "I know you love dinosaurs" without rehearsing internal config."""

    def test_empty_profile_returns_empty_string(self):
        block = my_agent_memory.format_factual_memory(
            {
                "themes": {},
                "concepts": {},
                "interests": {},
                "recent_choices": [],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
            }
        )
        assert block == ""

    def test_populated_profile_renders_what_i_know_section(self):
        block = my_agent_memory.format_factual_memory(
            {
                "themes": {"friendship": 5, "space": 3, "ocean": 1},
                "concepts": {},
                "interests": {"dinosaurs": 4, "dragons": 2},
                "recent_choices": ["space", "friendship"],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
            }
        )
        assert "**What I Know About You**" in block
        assert "friendship" in block
        assert "space" in block
        assert "dinosaurs" in block

    def test_caps_themes_and_interests_at_three(self):
        """Prompt-size bound: we never inject more than three labels per
        bucket so the prompt stays small after months of history."""
        themes = {f"theme_{i}": 100 - i for i in range(10)}
        block = my_agent_memory.format_factual_memory(
            {
                "themes": themes,
                "concepts": {},
                "interests": {},
                "recent_choices": [],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
            }
        )
        assert "theme_0" in block
        assert "theme_1" in block
        assert "theme_2" in block
        assert "theme_3" not in block

    def test_ignores_unknown_extra_fields(self):
        """If a future caller passes the wrong dict by mistake, the helper
        must not echo agent config like ``custom_instructions`` or
        ``learning_goals`` into the prompt — structural defense against
        accidental persona leakage."""
        block = my_agent_memory.format_factual_memory(
            {
                "themes": {"friendship": 5},
                "interests": {},
                "concepts": {},
                "recent_choices": [],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
                "custom_instructions": "secret-prompt-injection-bait",
                "learning_goals": ["leak-me"],
            }
        )
        assert "secret-prompt-injection-bait" not in block
        assert "leak-me" not in block


class TestFactualMemoryWiredIntoProxy:
    """``stream_my_agent_chat`` must fetch the child's preference profile
    every turn and pass it into ``_build_user_prompt``."""

    @pytest.mark.asyncio
    async def test_populated_preferences_reach_sdk_prompt(self, test_db):
        fake_client = _PromptCapturingSDKClient(
            messages=[_fake_result_message("Hi!")]
        )
        fake_agent = _fake_agent(
            enabled_skills=["image_story", "interactive_story", "kids_daily", "audio_narration"]
        )
        safe_envelope = {
            "content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]
        }
        populated_profile = {
            "profile": {
                "themes": {"friendship": 5, "space": 3},
                "concepts": {},
                "interests": {"dinosaurs": 4},
                "recent_choices": ["space"],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
            },
            "data_collected_since": "2026-01-01T00:00:00",
            "last_updated_at": "2026-05-01T00:00:00",
        }

        with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=fake_agent)), \
             patch.object(my_agent_proxy, "ClaudeSDKClient", lambda *a, **kw: fake_client), \
             patch.object(
                 my_agent_proxy,
                 "build_my_agent_context",
                 new=AsyncMock(return_value="ctx"),
             ), \
             patch.object(
                 my_agent_proxy,
                 "get_story_memory_prompt",
                 new=AsyncMock(return_value=""),
             ), \
             patch.object(
                 my_agent_proxy.preference_repo,
                 "get_profile_with_metadata",
                 new=AsyncMock(return_value=populated_profile),
             ), \
             patch(
                 "backend.src.agents.my_agent_proxy.check_content_safety.handler",
                 new=AsyncMock(return_value=safe_envelope),
             ):
            async for _ in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="hi",
            ):
                pass

        prompt = fake_client.captured_prompt
        assert prompt is not None
        assert "**What I Know About You**" in prompt
        assert "friendship" in prompt
        assert "dinosaurs" in prompt

    @pytest.mark.asyncio
    async def test_empty_preferences_do_not_leak_header(self, test_db):
        fake_client = _PromptCapturingSDKClient(
            messages=[_fake_result_message("Hi!")]
        )
        fake_agent = _fake_agent(
            enabled_skills=["image_story", "interactive_story", "kids_daily", "audio_narration"]
        )
        safe_envelope = {
            "content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]
        }
        empty_profile = {
            "profile": {
                "themes": {},
                "concepts": {},
                "interests": {},
                "recent_choices": [],
                "kids_daily": {
                    "topic_scores": {},
                    "topic_stats": {},
                    "last_event_at": None,
                },
            },
            "data_collected_since": None,
            "last_updated_at": None,
        }

        with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=fake_agent)), \
             patch.object(my_agent_proxy, "ClaudeSDKClient", lambda *a, **kw: fake_client), \
             patch.object(
                 my_agent_proxy,
                 "build_my_agent_context",
                 new=AsyncMock(return_value="ctx"),
             ), \
             patch.object(
                 my_agent_proxy,
                 "get_story_memory_prompt",
                 new=AsyncMock(return_value=""),
             ), \
             patch.object(
                 my_agent_proxy.preference_repo,
                 "get_profile_with_metadata",
                 new=AsyncMock(return_value=empty_profile),
             ), \
             patch(
                 "backend.src.agents.my_agent_proxy.check_content_safety.handler",
                 new=AsyncMock(return_value=safe_envelope),
             ):
            async for _ in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="hi",
            ):
                pass

        prompt = fake_client.captured_prompt
        assert prompt is not None
        assert "**What I Know About You**" not in prompt

    @pytest.mark.asyncio
    async def test_preference_fetch_scoped_by_user_id(self, test_db):
        """Cross-user isolation precedent (#288, #178): preference fetch
        must scope by user_id so user A's themes never leak to user B."""
        fake_client = _PromptCapturingSDKClient(
            messages=[_fake_result_message("Hi!")]
        )
        fake_agent = _fake_agent(
            enabled_skills=["image_story", "interactive_story", "kids_daily", "audio_narration"]
        )
        safe_envelope = {
            "content": [{"type": "text", "text": json.dumps({"safety_score": 0.99})}]
        }
        pref_mock = AsyncMock(
            return_value={
                "profile": {
                    "themes": {},
                    "concepts": {},
                    "interests": {},
                    "recent_choices": [],
                    "kids_daily": {
                        "topic_scores": {},
                        "topic_stats": {},
                        "last_event_at": None,
                    },
                },
                "data_collected_since": None,
                "last_updated_at": None,
            }
        )

        with patch.object(my_agent_proxy.agent_repo, "get_agent", new=AsyncMock(return_value=fake_agent)), \
             patch.object(my_agent_proxy, "ClaudeSDKClient", lambda *a, **kw: fake_client), \
             patch.object(
                 my_agent_proxy,
                 "build_my_agent_context",
                 new=AsyncMock(return_value="ctx"),
             ), \
             patch.object(
                 my_agent_proxy,
                 "get_story_memory_prompt",
                 new=AsyncMock(return_value=""),
             ), \
             patch.object(
                 my_agent_proxy.preference_repo,
                 "get_profile_with_metadata",
                 new=pref_mock,
             ), \
             patch(
                 "backend.src.agents.my_agent_proxy.check_content_safety.handler",
                 new=AsyncMock(return_value=safe_envelope),
             ):
            async for _ in my_agent_proxy.stream_my_agent_chat(
                user_id=_TEST_USER_ID,
                child_id=_TEST_CHILD_ID,
                message="hi",
            ):
                pass

        pref_mock.assert_awaited_once()
        args, kwargs = pref_mock.call_args
        if args:
            assert args[0] == _TEST_CHILD_ID
        else:
            assert kwargs.get("child_id") == _TEST_CHILD_ID
        assert kwargs.get("user_id") == _TEST_USER_ID
