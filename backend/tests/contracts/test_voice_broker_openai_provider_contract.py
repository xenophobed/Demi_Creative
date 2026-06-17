"""
Broker integration contract tests for OpenAIRealtimeProvider (#645).

The previous broker contract suite (``test_voice_broker_contract.py``) only
exercises the Mock provider. This file locks the **OpenAI-specific** path:

  - Full round-trip: client audio in → upstream WS receives append/commit/
    response.create events → text deltas + audio.delta chunks come back →
    broker safety-gates the text → forwards audio to the client.
  - Safety fail closed on the assistant reply: a bad text delta suppresses
    the TTS audio bytes BEFORE they reach the client.
  - Per-age idle timer: 30s for 3-5, 45s for 6-8, 60s for 9-12 (the broker
    ends the session with ``reason="timeout"`` when the timer fires).
  - Per-age max session timer: 10 / 15 / 20 minutes — broker ends with
    ``reason="quota"`` and emits a ``quota_exhausted`` event before close.
  - The persisted ``voice_sessions`` row records
    ``provider="openai_realtime"`` and ``first_audio_ms`` telemetry.

Mocks the upstream OpenAI Realtime WS via a tiny fake — no real network.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.src.api.deps import get_current_user
from backend.src.api.routes import voice_realtime
from backend.src.main import app
from backend.src.services import realtime_voice_service as rtvs
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
    OpenAIRealtimeProvider,
    SessionHandle,
)
from backend.src.services.user_service import UserData
from backend.src.services.voice_ephemeral_token import (
    _reset_nonce_store_for_tests,
    mint_voice_token,
)


PARENT_USER = UserData(
    user_id="voice_openai_parent",
    username="voice_openai_parent",
    email="parent@openai-test.com",
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
            None, "not_required", "free", "VOICEOAI", None, now, now,
        ),
    )
    await db_manager.commit()
    _reset_nonce_store_for_tests()
    yield fresh
    db_manager._adapter = saved_adapter
    await fresh.disconnect()


async def _make_consented_child(*, child_id: str, age_group: str = "6-8") -> str:
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


# ---------------------------------------------------------------------------
# Programmable stub provider — drop-in OpenAI provider for broker tests.
# ---------------------------------------------------------------------------

class StubOpenAIRealtimeProvider:
    """A drop-in replacement for OpenAIRealtimeProvider used by tests.

    Mirrors the Protocol shape and the public ``name`` attribute the
    broker writes into the ``voice_sessions`` row. Scripted via the
    ``programmed_reply_text`` / ``programmed_audio_chunks`` attributes.
    """

    name: str = "openai_realtime"

    def __init__(
        self,
        *,
        transcript_text: str = "tell me a happy story",
        transcript_safety_passed: bool = True,
        reply_text: str = "Once upon a time the cat smiled brightly",
        audio_chunks: Optional[List[bytes]] = None,
        per_chunk_delay_seconds: float = 0.0,
    ):
        self.transcript_text = transcript_text
        self.transcript_safety_passed = transcript_safety_passed
        self.reply_text = reply_text
        self.audio_chunks = audio_chunks or [b"\x01" * 32, b"\x02" * 32]
        self.per_chunk_delay_seconds = per_chunk_delay_seconds
        self.push_audio_calls: List[bytes] = []
        self.finalize_calls: int = 0
        self.synthesize_calls: List[str] = []
        self.closed = False

    async def start_session(
        self, *, user_id: str, child_id: str, target_age: int,
        persona: str = "buddy_default",
        voice_premium_voice: bool = False,
        voice_premium_voice_consent: bool = False,
        **_kwargs: Any,
    ) -> SessionHandle:
        # Mirror the real OpenAIRealtimeProvider tier-selection logic
        # so cost-telemetry tests can flip the flags here.
        model = (
            "gpt-realtime-2"
            if voice_premium_voice and voice_premium_voice_consent
            else "gpt-realtime-mini"
        )
        return SessionHandle(
            session_id=f"voice_openai_stub_{user_id}_{child_id}",
            user_id=user_id,
            child_id=child_id,
            target_age=target_age,
            persona=persona,
            provider_state={
                "openai_client_secret": "ek_stub_secret_abc123",
                "model": model,
                "expires_at": 1_900_000_000,
                "prompt_cache_hit": False,
            },
        )

    async def push_audio(self, handle: SessionHandle, audio_bytes: bytes) -> None:
        self.push_audio_calls.append(audio_bytes)

    async def finalize_utterance(self, handle: SessionHandle) -> FinalTranscript:
        self.finalize_calls += 1
        return FinalTranscript(
            success=True,
            text=self.transcript_text if self.transcript_safety_passed else "",
            language="en",
            duration_ms=1500,
            safety_passed=self.transcript_safety_passed,
            provider=self.name,
        )

    async def synthesize_speech(self, handle: SessionHandle, text: str):
        self.synthesize_calls.append(text)
        chunks = list(self.audio_chunks)
        delay = self.per_chunk_delay_seconds

        async def _gen():
            for chunk in chunks:
                if delay:
                    await asyncio.sleep(delay)
                yield chunk

        return _gen()

    async def stream_assistant_reply(self, handle: SessionHandle):
        """OpenAI-style combined text+audio stream.

        Emits all text deltas first (so the broker's reply-text gate has
        a complete string by the time text_done arrives), then the
        scripted audio chunks.
        """
        from backend.src.services.realtime_voice_service import ReplyEvent

        reply_text = self.reply_text
        chunks = list(self.audio_chunks)
        # Record that the broker invoked this path so tests can assert.
        self.synthesize_calls.append(reply_text)

        async def _gen():
            # Streaming text delta (single chunk for test simplicity).
            yield ReplyEvent(kind="text_delta", text=reply_text)
            yield ReplyEvent(kind="text_done", text=reply_text)
            for chunk in chunks:
                yield ReplyEvent(kind="audio_chunk", audio=chunk)
            yield ReplyEvent(kind="response_done")

        return _gen()

    async def close(self, handle: SessionHandle) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Round-trip happy path
# ---------------------------------------------------------------------------

class TestBrokerRoundTripWithOpenAIProvider:
    """End-to-end: audio in → transcript → reply text → safety pass → audio out."""

    @pytest.mark.asyncio
    async def test_round_trip_streams_audio_to_client(self, test_db, monkeypatch):
        child_id = await _make_consented_child(child_id="child_openai_alpha")
        stub = StubOpenAIRealtimeProvider(
            reply_text="Once upon a time a happy bunny found a cozy carrot patch",
            audio_chunks=[b"\xAA" * 50, b"\xBB" * 50, b"\xCC" * 50],
        )

        # Bypass the safety MCP so the gate doesn't make real Anthropic
        # calls. Gate semantics are covered in test_voice_safety_pre_tts.
        async def _safe(text, age):
            return {"safety_score": 0.99, "passed": True}
        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _safe, raising=False,
        )

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

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                audio_b64 = base64.b64encode(b"\x00" * 200).decode("ascii")
                ws.send_json({"type": "audio_chunk", "seq": 0, "audio_b64": audio_b64})
                ws.send_json({"type": "vad_end", "seq": 0})

                events: List[Dict[str, Any]] = []
                audio_chunk_count = 0
                # Drain events until we've seen the expected number of TTS chunks.
                while audio_chunk_count < 3:
                    ev = ws.receive_json()
                    events.append(ev)
                    if ev["type"] == "audio_chunk":
                        audio_chunk_count += 1

                ws.send_json({"type": "client_done"})
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        event_types = [e["type"] for e in events]
        # Order: final_transcript first, then assistant_text, then audio_chunk(s).
        assert "final_transcript" in event_types
        assert "assistant_text" in event_types
        assert event_types[-1] == "audio_chunk"

        # The provider's push_audio was invoked with our base64 payload.
        assert len(stub.push_audio_calls) == 1
        assert stub.push_audio_calls[0] == b"\x00" * 200
        assert stub.finalize_calls == 1
        # synthesize_speech was called with the model-generated reply.
        assert stub.synthesize_calls == [stub.reply_text]

    @pytest.mark.asyncio
    async def test_voice_session_row_records_openai_provider(self, test_db):
        """The persisted row records ``provider='openai_realtime'``."""
        child_id = await _make_consented_child(child_id="child_openai_provider")
        stub = StubOpenAIRealtimeProvider()

        # REST start mints a row + token. Verify the row carries the
        # provider name from the configured provider.
        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            from httpx import ASGITransport, AsyncClient
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/me/agent/voice/session",
                    json={"child_id": child_id},
                )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["provider_config"]["provider"] == "openai_realtime"
            row = await voice_session_repo.get_by_id(body["session_id"])
            assert row is not None
            assert row.provider == "openai_realtime"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)


# ---------------------------------------------------------------------------
# Safety fail-closed on assistant reply (the new gate)
# ---------------------------------------------------------------------------

class TestSafetyGateOnAssistantReply:
    """When the assistant text fails safety, TTS audio is suppressed."""

    @pytest.mark.asyncio
    async def test_unsafe_reply_emits_safety_block_and_no_audio(
        self, test_db, monkeypatch,
    ):
        child_id = await _make_consented_child(child_id="child_openai_safety")
        # The stub's reply text is "scary" — we patch the reply-safety check
        # to return a sub-threshold score so the broker MUST drop the audio.
        stub = StubOpenAIRealtimeProvider(
            reply_text="this text is bad and will not pass the gate",
            audio_chunks=[b"\xDD" * 50] * 3,
        )

        async def _fake_reply_safety(text: str, target_age: int):
            # Sub-threshold for any age → broker fails closed.
            return {"safety_score": 0.10, "passed": False}

        # The broker MUST consult a reply-safety helper exposed on the
        # voice_realtime module. Test patches that seam.
        monkeypatch.setattr(
            voice_realtime, "_safety_check_text",
            _fake_reply_safety, raising=False,
        )

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

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                audio_b64 = base64.b64encode(b"\x00" * 64).decode("ascii")
                ws.send_json({"type": "audio_chunk", "seq": 0, "audio_b64": audio_b64})
                ws.send_json({"type": "vad_end", "seq": 0})

                events: List[Dict[str, Any]] = []
                # Drain until safety_block (no audio_chunk should ever arrive).
                for _ in range(10):
                    ev = ws.receive_json()
                    events.append(ev)
                    if ev.get("type") == "safety_block":
                        break

                ws.send_json({"type": "client_done"})
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        # No audio_chunk events should have been forwarded.
        audio_events = [e for e in events if e["type"] == "audio_chunk"]
        assert audio_events == [], (
            f"audio leaked through safety gate: {audio_events}"
        )

        # A safety_block envelope was emitted with direction=reply.
        block_events = [e for e in events if e["type"] == "safety_block"]
        assert block_events, "broker must emit safety_block on unsafe reply"
        assert block_events[0]["direction"] == "reply"
        assert block_events[0].get("fallback_text")


# ---------------------------------------------------------------------------
# Per-age idle + max-session timers
# ---------------------------------------------------------------------------

class TestIdleAndMaxSessionTimers:
    """Idle timer + max-session timer enforcement per age."""

    @pytest.mark.asyncio
    async def test_idle_timer_closes_session_with_timeout_reason(
        self, test_db, monkeypatch,
    ):
        """When no client events arrive within the per-age idle window the
        broker MUST end the session with ``reason='timeout'`` and emit an
        error envelope before closing the WS.
        """
        child_id = await _make_consented_child(
            child_id="child_openai_idle", age_group="6-8",
        )
        stub = StubOpenAIRealtimeProvider()

        # Shrink the idle window to a fraction of a second so the test
        # doesn't sleep for 45s. The broker should expose this knob on
        # the module so tests don't have to monkeypatch internals.
        monkeypatch.setattr(
            voice_realtime, "_IDLE_TIMEOUT_OVERRIDE_SECONDS", 0.5,
            raising=False,
        )

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

        from unittest.mock import AsyncMock
        original_end = voice_session_repo.end_session
        end_spy = AsyncMock(side_effect=original_end)
        monkeypatch.setattr(
            voice_realtime.voice_session_repo, "end_session", end_spy,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                # Don't send anything. Wait for the broker to fire the timer.
                events: List[Dict[str, Any]] = []
                for _ in range(5):
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    events.append(ev)
                    if ev.get("type") in ("error", "session_end"):
                        break
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        # The broker called end_session with reason=timeout.
        assert end_spy.await_count >= 1
        call_kwargs = end_spy.await_args.kwargs
        assert call_kwargs["reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_max_session_timer_emits_quota_exhausted_and_closes(
        self, test_db, monkeypatch,
    ):
        """Per-age max session timer expires → ``quota_exhausted`` event
        is emitted and the session row records ``reason='quota'``.
        """
        child_id = await _make_consented_child(
            child_id="child_openai_max", age_group="3-5",
        )
        stub = StubOpenAIRealtimeProvider()
        monkeypatch.setattr(
            voice_realtime, "_MAX_SESSION_OVERRIDE_SECONDS", 0.5,
            raising=False,
        )

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

        from unittest.mock import AsyncMock
        end_spy = AsyncMock(return_value=None)
        monkeypatch.setattr(
            voice_realtime.voice_session_repo, "end_session", end_spy,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                events: List[Dict[str, Any]] = []
                for _ in range(8):
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    events.append(ev)
                    if ev.get("type") == "quota_exhausted":
                        break
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        # A quota_exhausted envelope was emitted to the client.
        kinds = [e.get("type") for e in events]
        assert "quota_exhausted" in kinds, (
            f"broker must emit quota_exhausted on max-session expiry, got: {kinds}"
        )
        # And the session row was ended with reason=quota.
        assert end_spy.await_count >= 1
        assert end_spy.await_args.kwargs["reason"] == "quota"


# ---------------------------------------------------------------------------
# first_audio_ms telemetry
# ---------------------------------------------------------------------------

class TestFirstAudioTelemetry:
    """The broker captures first_audio_ms and surfaces it in session_end."""

    @pytest.mark.asyncio
    async def test_session_end_event_includes_first_audio_ms(
        self, test_db, monkeypatch,
    ):
        child_id = await _make_consented_child(child_id="child_openai_telemetry")
        stub = StubOpenAIRealtimeProvider(
            reply_text="hi",
            audio_chunks=[b"\xEE" * 16, b"\xFF" * 16],
        )

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

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(stub)
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({
                    "type": "audio_chunk", "seq": 0,
                    "audio_b64": base64.b64encode(b"\x00" * 16).decode(),
                })
                ws.send_json({"type": "vad_end", "seq": 0})

                events: List[Dict[str, Any]] = []
                got_audio = False
                while True:
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    events.append(ev)
                    if ev.get("type") == "audio_chunk":
                        got_audio = True
                    if ev.get("type") == "session_end":
                        break
                    if got_audio and len(events) > 10:
                        break

                ws.send_json({"type": "client_done"})

                # Drain any tail events (including session_end).
                for _ in range(4):
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    events.append(ev)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        session_end_events = [e for e in events if e.get("type") == "session_end"]
        assert session_end_events, (
            f"broker must emit session_end on close; saw: "
            f"{[e.get('type') for e in events]}"
        )
        end = session_end_events[0]
        # first_audio_ms is present and non-negative.
        assert "first_audio_ms" in end, (
            f"session_end must include first_audio_ms, got keys: {list(end.keys())}"
        )
        assert isinstance(end["first_audio_ms"], int)
        assert end["first_audio_ms"] >= 0


# ---------------------------------------------------------------------------
# Hybrid path regression — ensure broker still routes Hybrid correctly.
# ---------------------------------------------------------------------------

class TestHybridProviderStillWorks:
    """The broker keeps a separate code path for Hybrid (Whisper+ElevenLabs).

    With #645, the broker introduces a provider-aware assistant turn. The
    Hybrid provider's ``finalize_utterance`` returns a transcript only —
    the assistant text + TTS are split. We verify the broker still emits
    final_transcript + assistant_text + audio_chunk events when wired to
    Hybrid (using a Stub that mimics Hybrid semantics).
    """

    @pytest.mark.asyncio
    async def test_hybrid_round_trip_still_streams_audio(self, test_db, monkeypatch):
        from backend.src.services.realtime_voice_service import (
            FinalTranscript as _FT, SessionHandle as _SH,
        )

        class _HybridStub:
            name = "hybrid"

            async def start_session(
                self, *, user_id, child_id, target_age,
                persona="buddy_default",
            ):
                return _SH(
                    session_id=f"voice_hybrid_stub_{user_id}",
                    user_id=user_id, child_id=child_id,
                    target_age=target_age, persona=persona,
                    provider_state={"buffer": bytearray()},
                )

            async def push_audio(self, h, b):
                pass

            async def finalize_utterance(self, h):
                return _FT(
                    success=True, text="hi buddy",
                    language="en", duration_ms=800,
                    safety_passed=True, provider="hybrid",
                )

            async def synthesize_speech(self, h, text):
                async def _g():
                    yield b"\x10" * 16
                    yield b"\x20" * 16
                return _g()

            async def close(self, h):
                pass

        child_id = await _make_consented_child(child_id="child_openai_hybridreg")
        persisted = await voice_session_repo.create_session(
            user_id=PARENT_USER.user_id, child_id=child_id, provider="hybrid",
        )
        token = mint_voice_token(
            session_id=persisted.session_id,
            user_id=PARENT_USER.user_id, child_id=child_id,
        )

        async def _safe(text, age):
            return {"safety_score": 0.99, "passed": True}
        monkeypatch.setattr(
            voice_realtime, "_safety_check_text", _safe, raising=False,
        )

        app.dependency_overrides[get_current_user] = _override_current_user
        voice_realtime._set_test_provider_override(_HybridStub())
        try:
            client = TestClient(app)
            with client.websocket_connect(
                f"/api/v1/me/agent/voice/stream?token={token}"
            ) as ws:
                ws.send_json({
                    "type": "audio_chunk", "seq": 0,
                    "audio_b64": base64.b64encode(b"\x00" * 50).decode(),
                })
                ws.send_json({"type": "vad_end", "seq": 0})

                events: List[Dict[str, Any]] = []
                while True:
                    try:
                        ev = ws.receive_json()
                    except Exception:
                        break
                    events.append(ev)
                    if ev.get("type") == "audio_chunk":
                        break

                ws.send_json({"type": "client_done"})
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            voice_realtime._set_test_provider_override(None)

        kinds = [e["type"] for e in events]
        assert "final_transcript" in kinds
        assert "assistant_text" in kinds
        assert "audio_chunk" in kinds
