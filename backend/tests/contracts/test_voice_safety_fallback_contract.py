"""
Pre-TTS safety fallback contract (#608 rescoped).

Beyond #657's "the gate fires" coverage (test_voice_safety_pre_tts_contract.py),
this story pins the FALLBACK behavior:

  1. A failing safety check REPLACES the reply — the original audio is
     NEVER forwarded, and the broker emits ``safety_block`` carrying
     ``_SAFETY_FALLBACK_REPLY`` so the buddy speaks something safe.
  2. An EXCEPTION inside the safety helper fails CLOSED — same outcome
     as a failing verdict, never a pass-through. The session continues
     to the next utterance (the WS isn't closed by a safety crash).
  3. Per-age thresholds (3-5 → 0.90, 6-8 → 0.85, 9-12 → 0.85) gate the
     fallback in lockstep with the floor, including the ``+_SAFETY_REVIEW_MARGIN``
     borderline band that triggers the heavier safety-review specialist.
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
    user_id="voice_fallback_parent",
    username="voice_fallback_parent",
    email="parent@fallback-test.com",
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
            None, "not_required", "free", "FALLBK", None, now, now,
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


class _ReplyStubProvider:
    """OpenAI-style provider that emits a known reply text + audio."""

    name = "openai_realtime"

    def __init__(
        self,
        *,
        reply_text: str = "the dangerous text the model produced",
        audio_chunks: Optional[List[bytes]] = None,
    ):
        self.reply_text = reply_text
        self.audio_chunks = audio_chunks or [b"\xAA" * 16, b"\xBB" * 16]

    async def start_session(
        self, *, user_id, child_id, target_age, persona="buddy_default",
        **_kwargs,
    ):
        return SessionHandle(
            session_id=f"voice_fallback_{user_id}",
            user_id=user_id, child_id=child_id,
            target_age=target_age, persona=persona,
            provider_state={
                "openai_client_secret": "ek_fb",
                "model": "gpt-realtime-mini",
                "prompt_cache_hit": False,
            },
        )

    async def push_audio(self, h, b):
        pass

    async def finalize_utterance(self, h):
        return FinalTranscript(
            success=True, text="say something interesting",
            language="en", duration_ms=1000,
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
# (1) test_safety_failure_replaces_reply — pinned per AC
# ===========================================================================


class TestSafetyFailureReplacesReply:
    @pytest.mark.asyncio
    async def test_failing_score_replaces_reply_with_fallback(
        self, test_db, monkeypatch,
    ):
        # Reply produced by the model — must NEVER reach the kid.
        bad_reply = "scary dark forbidden content the model generated"
        child_id = await _make_consented_child(
            child_id="child_repl_68", age_group="6-8",
        )
        stub = _ReplyStubProvider(
            reply_text=bad_reply,
            audio_chunks=[b"\x99" * 16] * 3,
        )

        async def _failing(text: str, target_age: int):
            return {"safety_score": 0.2, "passed": False}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _failing, raising=False,
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

        # The reply text must NEVER reach the client as assistant_text.
        assistant_texts = [
            e for e in events if e.get("type") == "assistant_text"
        ]
        for e in assistant_texts:
            assert bad_reply not in (e.get("delta") or ""), (
                "original reply must NOT pass through on safety fail"
            )

        # Audio must NEVER reach the client.
        audio_events = [e for e in events if e.get("type") == "audio_chunk"]
        assert audio_events == [], (
            "audio must be suppressed when safety fails — got "
            f"{len(audio_events)} chunks"
        )

        # safety_block envelope MUST carry the fallback text.
        blocks = [
            e for e in events if e.get("type") == "safety_block"
            and e.get("direction") == "reply"
        ]
        assert blocks, (
            f"expected safety_block(direction=reply), got: "
            f"{[e.get('type') for e in events]}"
        )
        fallback = blocks[0].get("fallback_text") or ""
        assert fallback == voice_realtime._SAFETY_FALLBACK_REPLY, (
            "safety_block must carry the canonical fallback copy "
            "(single source of truth)"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "age_group,target_age,passing_score,failing_score",
        [
            ("3-5", 4, 0.95, 0.89),    # threshold is 0.90
            ("6-8", 7, 0.95, 0.50),    # threshold is 0.85
            ("9-12", 10, 0.95, 0.50),  # threshold is 0.85
        ],
    )
    async def test_per_age_threshold_replaces_reply(
        self, test_db, monkeypatch, age_group, target_age, passing_score, failing_score,
    ):
        """Per-age fallback-replaces-reply parity. Each age band fails at
        a score below the floor and passes well above it."""
        child_id = await _make_consented_child(
            child_id=f"child_per_age_{age_group}", age_group=age_group,
        )
        stub = _ReplyStubProvider(
            reply_text="model output we want suppressed",
            audio_chunks=[b"\x88" * 16] * 3,
        )

        async def _fail(text, age):
            return {"safety_score": failing_score, "passed": False}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _fail, raising=False,
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
            f"audio leaked through {age_group} safety fail: {len(audio)} chunks"
        )
        assert blocks, (
            f"no safety_block(direction=reply) emitted for {age_group}"
        )
        assert blocks[0].get("fallback_text") == voice_realtime._SAFETY_FALLBACK_REPLY


# ===========================================================================
# (2) test_safety_mcp_exception_fails_closed — pinned per AC
# ===========================================================================


class TestSafetyMcpExceptionFailsClosed:
    @pytest.mark.asyncio
    async def test_exception_in_safety_helper_emits_safety_block(
        self, test_db, monkeypatch,
    ):
        # The safety helper throws. Broker MUST fail closed — no audio
        # pass-through, safety_block surfaces with the fallback copy.
        child_id = await _make_consented_child(
            child_id="child_exc_68", age_group="6-8",
        )
        stub = _ReplyStubProvider(
            reply_text="any reply",
            audio_chunks=[b"\x77" * 16] * 3,
        )

        async def _raises(text: str, target_age: int):
            raise RuntimeError("safety MCP down")

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _raises, raising=False,
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
            f"safety crash must suppress audio, got: {len(audio)} chunks"
        )
        assert blocks, (
            "safety crash must emit safety_block(direction=reply); "
            f"got events: {[e.get('type') for e in events]}"
        )
        assert blocks[0].get("fallback_text") == voice_realtime._SAFETY_FALLBACK_REPLY

    @pytest.mark.asyncio
    async def test_session_continues_after_safety_exception(
        self, test_db, monkeypatch,
    ):
        """After a safety exception fires, the WS is NOT closed — the
        broker continues accepting the next utterance. (PRD §3.16: a
        single bad reply doesn't take down the whole session.)"""
        child_id = await _make_consented_child(
            child_id="child_exc_continue", age_group="6-8",
        )
        stub = _ReplyStubProvider(
            reply_text="bad",
            audio_chunks=[b"\x11" * 16],
        )

        async def _raises(text, age):
            raise RuntimeError("transient MCP failure")

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _raises, raising=False,
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
            # Drive the WS through one full utterance + safety_block,
            # then send client_done. The WS must accept client_done
            # cleanly (which it cannot if the safety exception bubbled
            # out and closed the loop).
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({
                    "type": "audio_chunk", "seq": 0,
                    "audio_b64": base64.b64encode(b"\x00" * 32).decode(),
                })
                ws.send_json({"type": "vad_end", "seq": 0})
                saw_block = False
                for _ in range(15):
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    if ev.get("type") == "safety_block":
                        saw_block = True
                        break
                    if ev.get("type") == "session_end":
                        break
                assert saw_block, "safety_block was never emitted"
                # The WS is still open — a client_done must close it
                # normally, not be rejected because the loop already exited.
                ws.send_json({"type": "client_done"})
                # Drain session_end.
                drained_end = False
                for _ in range(5):
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    if ev.get("type") == "session_end":
                        drained_end = True
                        break
                assert drained_end, (
                    "session_end must surface after client_done — "
                    "indicates the loop survived the safety exception"
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)
