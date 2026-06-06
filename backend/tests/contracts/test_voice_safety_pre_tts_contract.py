"""
Pre-TTS safety gate contract (#645).

The broker MUST run a safety check on the assistant's text BEFORE the
TTS audio bytes are forwarded to the client. The gate fires for both
the OpenAI Realtime provider AND the Hybrid provider so #608's reply-side
safety AC is satisfied regardless of which provider an env routes to.

Threshold table (PRD §3.16.6):

    age group   safety_score floor
    ---------   ------------------
    3-5         0.90
    6-8         0.85
    9-12        0.85

Each test forces the safety helper to return scores around the boundary
and verifies the broker either forwards the TTS chunks (passing score)
or emits ``safety_block(direction="reply")`` and drops the audio
(failing score).
"""

from __future__ import annotations

import asyncio
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
    user_id="voice_safety_parent",
    username="voice_safety_parent",
    email="parent@safety-test.com",
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
            None, "not_required", "free", "SAFETY", None, now, now,
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


class _SafetyStubProvider:
    """Parameterizable provider — drop-in for either OpenAI or Hybrid path.

    ``name`` is set per test to flip the broker into the right code path.
    """

    def __init__(
        self,
        *,
        name: str,
        transcript_text: str = "tell me a happy story",
        reply_text: str = "Once upon a time the cat smiled brightly",
        audio_chunks: Optional[List[bytes]] = None,
    ):
        self.name = name
        self.transcript_text = transcript_text
        self.reply_text = reply_text
        self.audio_chunks = audio_chunks or [b"\x01" * 32, b"\x02" * 32]

    async def start_session(
        self, *, user_id, child_id, target_age,
        persona="buddy_default",
        **_kwargs,
    ):
        # Accept (and ignore) the #648 tier-selection kwargs the broker
        # passes when name == "openai_realtime".
        return SessionHandle(
            session_id=f"voice_{self.name}_safety_{user_id}",
            user_id=user_id, child_id=child_id,
            target_age=target_age, persona=persona,
            provider_state={
                "openai_client_secret": "ek_safety",
                "model": "gpt-realtime-mini",
                "prompt_cache_hit": False,
            },
        )

    async def push_audio(self, h, b):
        pass

    async def finalize_utterance(self, h):
        return FinalTranscript(
            success=True, text=self.transcript_text,
            language="en", duration_ms=1000,
            safety_passed=True, provider=self.name,
        )

    async def synthesize_speech(self, h, text):
        chunks = list(self.audio_chunks)

        async def _g():
            for c in chunks:
                yield c

        return _g()

    async def stream_assistant_reply(self, h):
        """OpenAI-style combined stream — emitted only when ``name`` is
        ``openai_realtime``. The broker uses ``hasattr`` to detect this
        method, so the Hybrid path falls back to ``synthesize_speech``
        only when the stub *omits* this method. We always provide it
        and conditionally NOT call it for Hybrid by raising AttributeError
        if name != openai_realtime would be cleaner — but the simplest
        impl is to define it only for OpenAI and let getattr return None
        otherwise (handled below).
        """
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


# A second variant lacking ``stream_assistant_reply`` so the broker uses
# the legacy reply path (Hybrid semantics).
class _HybridSafetyStubProvider(_SafetyStubProvider):
    name = "hybrid"

    # Override to delete the OpenAI-only method so hasattr returns False.
    stream_assistant_reply = None  # type: ignore[assignment]


def _run_session_capture_events(
    *, token: str,
) -> List[Dict[str, Any]]:
    """Send one VAD-end utterance and capture events until a terminal one.

    Sync function — runs the starlette TestClient (which spawns its own
    asyncio loop). Returns the captured events in arrival order.
    """
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

        for _ in range(15):
            try:
                ev = ws.receive_json()
            except Exception:
                break
            events.append(ev)
            if ev.get("type") in ("safety_block", "session_end"):
                break
            if ev.get("type") == "audio_chunk":
                # Once we've seen at least one audio chunk in the safe
                # path, no further safety_block should arrive.
                break

        try:
            ws.send_json({"type": "client_done"})
        except Exception:
            pass
    return events


@pytest.mark.parametrize("provider_name", ["openai_realtime", "hybrid"])
class TestPreTtsSafetyGateParity:
    """The pre-TTS safety gate fires identically for both providers."""

    @pytest.mark.asyncio
    async def test_passing_reply_streams_audio(
        self, test_db, monkeypatch, provider_name,
    ):
        child_id = await _make_consented_child(
            child_id=f"child_pass_{provider_name}",
            age_group="6-8",
        )
        stub_cls = (
            _SafetyStubProvider
            if provider_name == "openai_realtime"
            else _HybridSafetyStubProvider
        )
        stub = stub_cls(
            name=provider_name,
            audio_chunks=[b"\xAA" * 16, b"\xBB" * 16],
        )

        async def _safe_check(text: str, target_age: int):
            return {"safety_score": 0.95, "passed": True}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _safe_check, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=child_id,
            provider=provider_name,
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=child_id,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_session_capture_events(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio_events = [e for e in events if e["type"] == "audio_chunk"]
        safety_blocks = [e for e in events if e["type"] == "safety_block"]
        assert audio_events, (
            f"safe reply must produce audio, got events: "
            f"{[e['type'] for e in events]}"
        )
        assert safety_blocks == [], (
            f"safe reply must NOT emit safety_block, got: {safety_blocks}"
        )

    @pytest.mark.asyncio
    async def test_failing_reply_blocks_audio_for_age_6_8(
        self, test_db, monkeypatch, provider_name,
    ):
        child_id = await _make_consented_child(
            child_id=f"child_fail68_{provider_name}",
            age_group="6-8",
        )
        stub_cls = (
            _SafetyStubProvider
            if provider_name == "openai_realtime"
            else _HybridSafetyStubProvider
        )
        stub = stub_cls(
            name=provider_name,
            audio_chunks=[b"\xCC" * 16] * 4,
        )

        async def _unsafe_check(text: str, target_age: int):
            # Below the 0.85 threshold for 6-8.
            return {"safety_score": 0.50, "passed": False}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _unsafe_check, raising=False,
        )

        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id,
            child_id=child_id,
            provider=provider_name,
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id,
            child_id=child_id,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            events = _run_session_capture_events(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio_events = [e for e in events if e["type"] == "audio_chunk"]
        safety_blocks = [
            e for e in events if e["type"] == "safety_block"
            and e.get("direction") == "reply"
        ]
        assert audio_events == [], (
            f"unsafe reply must suppress audio_chunk, got: {audio_events}"
        )
        assert safety_blocks, (
            f"unsafe reply must emit safety_block(direction=reply), "
            f"got: {[e['type'] for e in events]}"
        )


class TestAgeThresholdBoundaries:
    """Boundary tests: 0.86 must pass for 6-8 but FAIL for 3-5."""

    @pytest.mark.asyncio
    async def test_score_086_passes_for_6_8(self, test_db, monkeypatch):
        child_id = await _make_consented_child(
            child_id="child_086_68", age_group="6-8",
        )
        stub = _SafetyStubProvider(
            name="openai_realtime",
            audio_chunks=[b"\xDD" * 16, b"\xEE" * 16],
        )

        async def _check(text, age):
            return {"safety_score": 0.86, "passed": True}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _check, raising=False,
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
            events = _run_session_capture_events(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio = [e for e in events if e["type"] == "audio_chunk"]
        blocks = [e for e in events if e["type"] == "safety_block"]
        assert audio, "0.86 must pass for 6-8"
        assert blocks == [], f"0.86 must not block for 6-8, got: {blocks}"

    @pytest.mark.asyncio
    async def test_score_086_blocks_for_3_5(self, test_db, monkeypatch):
        child_id = await _make_consented_child(
            child_id="child_086_35", age_group="3-5",
        )
        stub = _SafetyStubProvider(
            name="openai_realtime",
            audio_chunks=[b"\xFF" * 16] * 3,
        )

        async def _check(text, age):
            return {"safety_score": 0.86, "passed": False}

        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _check, raising=False,
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
            events = _run_session_capture_events(token=token)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        audio = [e for e in events if e["type"] == "audio_chunk"]
        blocks = [
            e for e in events if e["type"] == "safety_block"
            and e.get("direction") == "reply"
        ]
        assert audio == [], "0.86 must block for 3-5 (threshold 0.90)"
        assert blocks, "0.86 must emit safety_block(direction=reply) for 3-5"
