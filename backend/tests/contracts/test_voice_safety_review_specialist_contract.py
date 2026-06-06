"""
Safety-review-specialist invocation contract (#608 rescoped).

Beyond ``_safety_check_text`` (the fast per-utterance gate), PRD §3.16
calls for a heavier safety review of *uncertain* assistant text — the
``safety-review-specialist`` AgentDefinition lives in
``my_agent_proxy._build_subagents`` for the text proxy; this story wires
its voice-side analogue.

Implementation contract:

  1. A clear pass (well above the per-age floor) DOES NOT invoke the
     specialist — first-audio latency stays low for the common case.
  2. A borderline pass (within ``_SAFETY_REVIEW_MARGIN`` of the floor)
     DOES invoke the specialist; the specialist's verdict overrides.
  3. A failing primary gate skips the specialist entirely — already a
     hard fail, no second look needed.
  4. The specialist hook is monkeypatchable on ``voice_realtime`` so
     future PRs can swap the stub for the full Claude Agent SDK
     orchestration without touching the broker.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services.database import (
    db_manager,
    voice_session_repo,
)
from backend.src.services.database.child_profile_repository import (
    ChildProfileRepository,
)
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.realtime_voice_service import (
    FinalTranscript,
    SessionHandle,
)
from backend.src.services.user_service import UserData
from backend.src.services.voice_ephemeral_token import (
    _reset_nonce_store_for_tests,
    mint_voice_token,
)


PARENT_USER = UserData(
    user_id="voice_specialist_parent",
    username="voice_specialist_parent",
    email="parent@spec-test.com",
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
            None, "not_required", "free", "SPECRV", None, now, now,
        ),
    )
    await db_manager.commit()
    _reset_nonce_store_for_tests()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


async def _make_consented_child(*, child_id: str, age_group: str) -> str:
    repo = ChildProfileRepository(db_manager)
    profile = await repo.create(
        user_id=PARENT_USER.user_id,
        child_id=child_id,
        name="Ada",
        age_group=age_group,
        is_default=True,
    )
    await repo.update_consent(
        user_id=PARENT_USER.user_id,
        child_id=profile.child_id,
        microphone_consent=True,
        voice_conversation_consent=True,
        voice_session_quota_seconds=10_000,
    )
    return profile.child_id


class _ReplyStub:
    name = "openai_realtime"

    def __init__(self, reply_text="ok reply", audio=None):
        self.reply_text = reply_text
        self.audio_chunks = audio or [b"\x11" * 16, b"\x22" * 16]

    async def start_session(
        self, *, user_id, child_id, target_age, persona="buddy_default",
        **_kwargs,
    ):
        return SessionHandle(
            session_id=f"voice_spec_{user_id}",
            user_id=user_id, child_id=child_id,
            target_age=target_age, persona=persona,
            provider_state={
                "openai_client_secret": "ek_spec",
                "model": "gpt-realtime-mini",
                "prompt_cache_hit": False,
            },
        )

    async def push_audio(self, h, b):
        pass

    async def finalize_utterance(self, h):
        return FinalTranscript(
            success=True, text="hi", language="en", duration_ms=500,
            safety_passed=True, provider=self.name,
        )

    async def stream_assistant_reply(self, h):
        from backend.src.services.realtime_voice_service import ReplyEvent
        reply_text = self.reply_text
        chunks = list(self.audio_chunks)

        async def _g():
            yield ReplyEvent(kind="text_delta", text=reply_text)
            yield ReplyEvent(kind="text_done", text=reply_text)
            for c in chunks:
                yield ReplyEvent(kind="audio_chunk", audio=c)
            yield ReplyEvent(kind="response_done")

        return _g()

    async def close(self, h):
        pass


def _run_one_utterance(*, token: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    client = TestClient(app)
    with client.websocket_connect(
        f"/api/v1/me/agent/voice/stream?token={token}"
    ) as ws:
        ws.send_json({
            "type": "audio_chunk", "seq": 0,
            "audio_b64": base64.b64encode(b"\x00" * 32).decode(),
        })
        ws.send_json({"type": "vad_end", "seq": 0})
        for _ in range(20):
            try:
                ev = ws.receive_json()
            except Exception:
                break
            events.append(ev)
            if ev.get("type") in ("safety_block", "session_end"):
                break
            if ev.get("type") == "audio_chunk":
                break
        try:
            ws.send_json({"type": "client_done"})
        except Exception:
            pass
    return events


# ===========================================================================
# Integration point exists and is monkeypatchable
# ===========================================================================


class TestSpecialistHook:
    def test_specialist_hook_is_module_level(self):
        # The hook MUST be importable at module level so tests / future
        # orchestration can swap it in via monkeypatch. Same pattern as
        # the ``_safety_check_text`` seam (#657).
        assert hasattr(voice_realtime, "_safety_review_specialist")
        assert callable(voice_realtime._safety_review_specialist)

    def test_safety_review_margin_constant_documented(self):
        # The borderline band the specialist gates is a published
        # constant so the ops team can audit / tune it.
        assert hasattr(voice_realtime, "_SAFETY_REVIEW_MARGIN")
        margin = voice_realtime._SAFETY_REVIEW_MARGIN
        assert 0.0 < margin < 0.5, (
            f"_SAFETY_REVIEW_MARGIN={margin!r} is unreasonable; "
            "should be a small positive band above the per-age floor"
        )


# ===========================================================================
# Routing semantics — when does the specialist actually fire?
# ===========================================================================


class TestSpecialistRouting:
    @pytest.mark.asyncio
    async def test_clear_pass_skips_specialist(self, test_db, monkeypatch):
        """Well above the floor → primary gate alone. The specialist
        does NOT run (latency optimisation)."""
        child_id = await _make_consented_child(
            child_id="child_clear_pass", age_group="6-8",
        )
        stub = _ReplyStub(reply_text="happy reply")
        specialist_calls: List[str] = []

        async def _primary(text, age):
            # Well above the 0.85 floor + 0.05 margin → no specialist call.
            return {"safety_score": 0.99, "passed": True}

        async def _specialist(text, age):
            specialist_calls.append(text)
            return True

        monkeypatch.setattr(voice_realtime, "_safety_check_text", _primary, raising=False)
        monkeypatch.setattr(
            voice_realtime, "_safety_review_specialist", _specialist, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id, child_id=child_id,
            provider="openai_realtime",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id, child_id=child_id,
        )
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_one_utterance(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        assert specialist_calls == [], (
            "specialist must NOT run on a clear primary-gate pass"
        )
        audio = [e for e in events if e.get("type") == "audio_chunk"]
        assert audio, "clear pass must let audio through"

    @pytest.mark.asyncio
    async def test_borderline_pass_invokes_specialist(self, test_db, monkeypatch):
        """Within the margin above the floor → specialist DOES run. If
        it agrees, audio flows. If it rejects, fallback fires."""
        child_id = await _make_consented_child(
            child_id="child_border_pass", age_group="6-8",
        )
        stub = _ReplyStub(reply_text="borderline reply", audio=[b"\xDD" * 16])
        specialist_calls: List[tuple] = []

        async def _primary(text, age):
            # 0.86 — passes 0.85 floor by hairs, within 0.05 margin band.
            return {"safety_score": 0.86, "passed": True}

        async def _specialist(text, age):
            specialist_calls.append((text, age))
            return True  # specialist agrees

        monkeypatch.setattr(voice_realtime, "_safety_check_text", _primary, raising=False)
        monkeypatch.setattr(
            voice_realtime, "_safety_review_specialist", _specialist, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id, child_id=child_id,
            provider="openai_realtime",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id, child_id=child_id,
        )
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_one_utterance(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        assert len(specialist_calls) == 1, (
            f"specialist MUST run on borderline pass; calls={specialist_calls}"
        )
        # Specialist agreed → audio flows.
        audio = [e for e in events if e.get("type") == "audio_chunk"]
        assert audio, "specialist-agreed borderline pass must let audio through"

    @pytest.mark.asyncio
    async def test_specialist_rejection_overrides_primary_pass(
        self, test_db, monkeypatch,
    ):
        """Primary gate says 0.86 (above floor) → borderline. Specialist
        rejects → audio MUST be suppressed; safety_block fires."""
        child_id = await _make_consented_child(
            child_id="child_spec_reject", age_group="6-8",
        )
        stub = _ReplyStub(reply_text="risky", audio=[b"\xEE" * 16] * 3)

        async def _primary(text, age):
            return {"safety_score": 0.86, "passed": True}

        async def _specialist(text, age):
            return False

        monkeypatch.setattr(voice_realtime, "_safety_check_text", _primary, raising=False)
        monkeypatch.setattr(
            voice_realtime, "_safety_review_specialist", _specialist, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id, child_id=child_id,
            provider="openai_realtime",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id, child_id=child_id,
        )
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_one_utterance(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio = [e for e in events if e.get("type") == "audio_chunk"]
        blocks = [
            e for e in events if e.get("type") == "safety_block"
            and e.get("direction") == "reply"
        ]
        assert audio == [], (
            "specialist rejection MUST suppress audio (overrides primary pass)"
        )
        assert blocks, (
            "specialist rejection MUST emit safety_block(direction=reply)"
        )

    @pytest.mark.asyncio
    async def test_specialist_failure_fails_closed(self, test_db, monkeypatch):
        """An exception inside the specialist hook MUST fail closed —
        same outcome as a primary-gate exception."""
        child_id = await _make_consented_child(
            child_id="child_spec_crash", age_group="6-8",
        )
        stub = _ReplyStub(reply_text="anything", audio=[b"\xFF" * 16])

        async def _primary(text, age):
            return {"safety_score": 0.86, "passed": True}

        async def _specialist(text, age):
            raise RuntimeError("specialist crashed")

        monkeypatch.setattr(voice_realtime, "_safety_check_text", _primary, raising=False)
        monkeypatch.setattr(
            voice_realtime, "_safety_review_specialist", _specialist, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id, child_id=child_id,
            provider="openai_realtime",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id, child_id=child_id,
        )
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_one_utterance(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio = [e for e in events if e.get("type") == "audio_chunk"]
        blocks = [
            e for e in events if e.get("type") == "safety_block"
            and e.get("direction") == "reply"
        ]
        assert audio == [], "specialist crash MUST suppress audio"
        assert blocks, "specialist crash MUST emit safety_block(direction=reply)"
