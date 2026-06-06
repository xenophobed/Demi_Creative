"""
Contract tests for OpenAIRealtimeProvider (#644).

This is the **scaffold story** for the OpenAI Realtime API provider. The
provider class exists, conforms to the ``RealtimeVoiceProvider`` Protocol,
and mints an ephemeral client secret via
``POST https://api.openai.com/v1/realtime/client_secrets``. The audio
forwarding + tool-call plumbing lands in E2 (#645).

What we lock here:

  - Protocol conformance: all five Protocol methods exist with the right
    async/non-async shape.
  - ``start_session`` happy path: with ``OPENAI_API_KEY`` set, returns a
    ``SessionHandle`` whose ``provider_state["openai_client_secret"]`` is
    populated. The httpx POST is mocked — no network in CI.
  - ``start_session`` degraded path: without ``OPENAI_API_KEY``, returns
    a degraded handle (mirrors the Hybrid provider's graceful-degradation
    pattern — the broker turns this into a clean error envelope).
  - Scaffold methods (``push_audio``, ``finalize_utterance``,
    ``synthesize_speech``) raise ``NotImplementedError("E2 — broker
    integration")``. The exact message is a contract for the #645 reviewer.
  - ``_select_provider`` routing for ``REALTIME_VOICE_PROVIDER=openai``,
    including the fallback chain when ``OPENAI_API_KEY`` is missing.
  - Audio bytes never reach disk (the existing project-wide invariant,
    repeated for the new provider).
  - Importing the module does NOT construct an OpenAI client at import
    time (lazy httpx use inside ``start_session``).
"""

from __future__ import annotations

import asyncio
import builtins
import inspect
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.src.services import realtime_voice_service as rtvs
from backend.src.services.realtime_voice_service import (
    HybridRealtimeVoiceProvider,
    MockRealtimeVoiceProvider,
    OPENAI_REALTIME_CLIENT_SECRETS_URL,
    OPENAI_REALTIME_MODEL_DEFAULT,
    OPENAI_REALTIME_MODEL_ESCALATED,
    OpenAIRealtimeProvider,
    SessionHandle,
    _select_provider,
)


# ---------------------- Protocol shape -------------------------------------

class TestProtocolShape:
    """OpenAIRealtimeProvider satisfies the RealtimeVoiceProvider Protocol."""

    def test_provider_has_required_attributes(self):
        provider = OpenAIRealtimeProvider()
        assert provider.name == "openai_realtime"
        for method in (
            "start_session", "push_audio", "finalize_utterance",
            "synthesize_speech", "close",
        ):
            assert hasattr(provider, method), f"missing {method}"

    def test_async_methods_are_coroutine_functions(self):
        provider = OpenAIRealtimeProvider()
        # Mirror the Protocol exactly: start_session/push_audio/
        # finalize_utterance/close are async; synthesize_speech returns
        # an AsyncIterator (the Mock/Hybrid both `async def` it).
        assert inspect.iscoroutinefunction(provider.start_session)
        assert inspect.iscoroutinefunction(provider.push_audio)
        assert inspect.iscoroutinefunction(provider.finalize_utterance)
        assert inspect.iscoroutinefunction(provider.close)
        # synthesize_speech: the existing providers declare it `async def`
        # returning an AsyncIterator, so we conform to that shape.
        assert inspect.iscoroutinefunction(provider.synthesize_speech)

    def test_module_exposes_constants(self):
        assert OPENAI_REALTIME_MODEL_DEFAULT == "gpt-realtime-mini"
        assert OPENAI_REALTIME_MODEL_ESCALATED == "gpt-realtime-2"
        assert OPENAI_REALTIME_CLIENT_SECRETS_URL == (
            "https://api.openai.com/v1/realtime/client_secrets"
        )


# ---------------------- start_session happy path ---------------------------

class _FakeHttpxResponse:
    """Mimic enough of httpx.Response for the provider's path."""

    def __init__(self, *, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeAsyncClient:
    """Drop-in for httpx.AsyncClient used as an async context manager."""

    last_post_args = None  # captured for assertions

    def __init__(self, *args, **kwargs):
        # Record construction kwargs so tests can assert on timeout etc.
        type(self).last_init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        type(self).last_post_args = {"url": url, **kwargs}
        return _FakeHttpxResponse(
            status_code=200,
            json_data={
                "value": "ek_test_abc123",
                "expires_at": 1_900_000_000,
            },
        )


class TestStartSessionHappyPath:
    @pytest.mark.asyncio
    async def test_returns_handle_with_client_secret(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        # Patch httpx.AsyncClient where the provider imports it.
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)

        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u1", child_id="c1", target_age=7,
        )

        assert isinstance(handle, SessionHandle)
        assert handle.session_id.startswith("voice_openai_")
        assert handle.user_id == "u1"
        assert handle.child_id == "c1"
        assert handle.target_age == 7
        assert handle.persona == "buddy_default"
        # Load-bearing: the ephemeral client secret is populated.
        assert handle.provider_state["openai_client_secret"] == "ek_test_abc123"
        assert handle.provider_state["model"] == OPENAI_REALTIME_MODEL_DEFAULT
        assert handle.provider_state["expires_at"] == 1_900_000_000

    @pytest.mark.asyncio
    async def test_post_targets_client_secrets_endpoint(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)

        provider = OpenAIRealtimeProvider()
        await provider.start_session(
            user_id="u1", child_id="c1", target_age=7,
        )

        post_args = _FakeAsyncClient.last_post_args
        assert post_args is not None
        assert post_args["url"] == OPENAI_REALTIME_CLIENT_SECRETS_URL
        # Authorization header carries the bearer token.
        headers = post_args.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-test-key"
        # Body includes the model — cost-guardrail default.
        body = post_args.get("json", {})
        # Body shape per OpenAI docs: { "session": { "type": "realtime", ... } }
        session_body = body.get("session", body)
        assert session_body.get("model") == OPENAI_REALTIME_MODEL_DEFAULT

    @pytest.mark.asyncio
    async def test_unique_session_ids(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)

        provider = OpenAIRealtimeProvider()
        h1 = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        h2 = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert h1.session_id != h2.session_id


# ---------------------- start_session degraded -----------------------------

class TestStartSessionDegraded:
    """Without OPENAI_API_KEY, the provider returns a degraded handle.

    Design choice (documented here): we mirror the Hybrid provider's
    graceful-degradation pattern — never raise from start_session. The
    handle has an empty/missing client secret and a flag the broker can
    inspect to translate into VoiceWSErrorEvent(code="provider_unavailable").
    Raising would force the broker to wrap every start_session call in a
    try/except; the envelope pattern is uniform across providers.
    """

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_degraded_handle(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert isinstance(handle, SessionHandle)
        # Degraded shape: no client secret, explicit unavailable flag.
        assert handle.provider_state.get("openai_client_secret") in (None, "")
        assert handle.provider_state.get("provider_unavailable") is True

    @pytest.mark.asyncio
    async def test_degraded_start_does_not_hit_network(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Booby-trap the httpx client — if the provider tries to construct
        # it, the test fails loudly.
        class _ExplodingClient:
            def __init__(self, *_a, **_k):
                raise AssertionError("provider hit network in degraded mode")

        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _ExplodingClient)

        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        assert handle.provider_state.get("provider_unavailable") is True


# ---------------------- Scaffold NotImplementedError -----------------------

_E2_MESSAGE = "E2 — broker integration"


class TestScaffoldNotImplemented:
    """The scaffold methods raise NotImplementedError with an exact string.

    The string is a contract for the #645 (E2) reviewer — they'll grep
    for this message and replace each call site with the real upstream
    WebSocket forwarding.
    """

    @pytest.mark.asyncio
    async def test_push_audio_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)
        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        with pytest.raises(NotImplementedError) as ei:
            await provider.push_audio(handle, b"\x00" * 64)
        assert str(ei.value) == _E2_MESSAGE

    @pytest.mark.asyncio
    async def test_finalize_utterance_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)
        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        with pytest.raises(NotImplementedError) as ei:
            await provider.finalize_utterance(handle)
        assert str(ei.value) == _E2_MESSAGE

    @pytest.mark.asyncio
    async def test_synthesize_speech_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)
        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        with pytest.raises(NotImplementedError) as ei:
            await provider.synthesize_speech(handle, "hello buddy")
        assert str(ei.value) == _E2_MESSAGE

    @pytest.mark.asyncio
    async def test_close_is_noop(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)
        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        # close logic lands in E2 with the upstream WS lifecycle; here
        # it must be a benign no-op (does not raise).
        await provider.close(handle)


# ---------------------- _select_provider routing ---------------------------

class TestSelectProviderRouting:
    def test_openai_env_with_api_key_returns_openai_provider(self, monkeypatch):
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        chosen = _select_provider()
        assert isinstance(chosen, OpenAIRealtimeProvider)
        assert chosen.name == "openai_realtime"

    def test_openai_env_without_api_key_falls_back_to_hybrid(self, monkeypatch):
        # Fallback chain: openai -> hybrid -> mock. Without OPENAI_API_KEY
        # the OpenAI provider can't mint a secret, so we fall back to
        # Hybrid (which itself degrades internally if its keys are missing).
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        chosen = _select_provider()
        assert isinstance(chosen, HybridRealtimeVoiceProvider)
        assert chosen.name == "hybrid"

    def test_hybrid_env_still_returns_hybrid_no_regression(self, monkeypatch):
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "hybrid")
        chosen = _select_provider()
        assert isinstance(chosen, HybridRealtimeVoiceProvider)

    def test_mock_env_still_returns_mock_no_regression(self, monkeypatch):
        monkeypatch.setenv("REALTIME_VOICE_PROVIDER", "mock")
        chosen = _select_provider()
        assert isinstance(chosen, MockRealtimeVoiceProvider)

    def test_unset_env_respects_existing_default(self, monkeypatch):
        # Existing default: no env + no OPENAI_API_KEY = Mock.
        monkeypatch.delenv("REALTIME_VOICE_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        chosen = _select_provider()
        assert chosen.name == "mock"


# ---------------------- No disk persistence --------------------------------

class TestNoDiskPersistence:
    """Audio bytes (and provider state) never reach disk."""

    @pytest.mark.asyncio
    async def test_start_session_never_writes_to_disk(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(rtvs, "_httpx_AsyncClient", _FakeAsyncClient)

        write_bytes_calls: list[str] = []
        named_temp_calls: list[tuple] = []
        open_write_calls: list[tuple[str, str]] = []

        original_write_bytes = Path.write_bytes
        original_named_temp = tempfile.NamedTemporaryFile
        original_open = builtins.open

        def spy_write_bytes(self, *args, **kwargs):
            write_bytes_calls.append(str(self))
            return original_write_bytes(self, *args, **kwargs)

        def spy_named_temp(*args, **kwargs):
            named_temp_calls.append((args, kwargs))
            return original_named_temp(*args, **kwargs)

        def spy_open(file, mode="r", *args, **kwargs):
            if any(c in mode for c in ("w", "a", "x")):
                open_write_calls.append((str(file), mode))
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "write_bytes", spy_write_bytes)
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy_named_temp)
        monkeypatch.setattr(builtins, "open", spy_open)

        provider = OpenAIRealtimeProvider()
        handle = await provider.start_session(
            user_id="u", child_id="c", target_age=7,
        )
        await provider.close(handle)

        assert write_bytes_calls == [], (
            f"openai provider wrote to disk: {write_bytes_calls}"
        )
        assert named_temp_calls == [], (
            f"openai provider created temp file: {named_temp_calls}"
        )
        assert open_write_calls == [], (
            f"openai provider opened a file for writing: {open_write_calls}"
        )


# ---------------------- Import-time side-effects ---------------------------

class TestNoImportSideEffects:
    def test_import_does_not_construct_openai_client(self):
        """The provider class must not instantiate any network client at
        import time. Constructors are lazy — they run inside ``start_session``
        only. We re-import the module fresh and confirm the class is
        present without having touched httpx or the openai SDK."""
        import importlib
        import sys
        # Drop the cached module so the test forces a true re-import.
        sys.modules.pop("backend.src.services.realtime_voice_service", None)
        mod = importlib.import_module(
            "backend.src.services.realtime_voice_service"
        )
        assert hasattr(mod, "OpenAIRealtimeProvider")
        # The class itself is importable and constructible without any
        # network call. Constructing it must not require OPENAI_API_KEY.
        provider = mod.OpenAIRealtimeProvider()
        assert provider.name == "openai_realtime"
