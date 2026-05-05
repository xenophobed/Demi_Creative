"""
Contract tests for the SAFETY_MOCK dev bypass in safety_check_server.

Per CLAUDE.md the safety check is non-negotiable for production.
SAFETY_MOCK=1 exists ONLY for local UX iteration when the developer's
Anthropic credits are exhausted. These tests assert:

  - SAFETY_MOCK=1 returns a passing stub WITHOUT calling Anthropic
  - SAFETY_MOCK=1 + ENVIRONMENT=production refuses to bypass
  - The stub envelope matches the real return shape
    ({ "content": [{ "type": "text", "text": "<json string>" }] })
  - The stub payload is flagged with dev_mock=true so callers /
    log readers can spot it immediately
"""

import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_safety_mock_returns_passing_stub_without_calling_anthropic(
    monkeypatch,
):
    monkeypatch.setenv("SAFETY_MOCK", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    from backend.src.mcp_servers import check_content_safety

    with patch(
        "backend.src.mcp_servers.safety_check_server.Anthropic",
        side_effect=AssertionError("Anthropic must NOT be called when SAFETY_MOCK=1"),
    ):
        result = await check_content_safety.handler(
            {
                "content_text": "Sparkle",
                "content_type": "agent_persona",
                "target_age": 4,
            }
        )

    assert "content" in result, "envelope shape regression"
    payload = json.loads(result["content"][0]["text"])
    assert payload["safety_score"] >= 0.85
    assert payload["is_safe"] is True
    assert payload.get("dev_mock") is True


@pytest.mark.asyncio
async def test_safety_mock_refuses_to_fire_in_production(monkeypatch):
    """SAFETY_MOCK=1 with ENVIRONMENT=production MUST reach the real path."""
    monkeypatch.setenv("SAFETY_MOCK", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from backend.src.mcp_servers import check_content_safety

    sentinel_calls = []

    class _StubClient:
        def __init__(self, *args, **kwargs):
            sentinel_calls.append(("init", args, kwargs))

        @property
        def messages(self):
            class _M:
                def create(_self, *a, **kw):
                    raise RuntimeError("real path reached")

            return _M()

    with patch(
        "backend.src.mcp_servers.safety_check_server.Anthropic",
        new=_StubClient,
    ):
        result = await check_content_safety.handler(
            {
                "content_text": "Sparkle",
                "content_type": "agent_persona",
                "target_age": 4,
            }
        )

    assert sentinel_calls, "production path must call Anthropic — bypass leaked"
    payload = json.loads(result["content"][0]["text"])
    assert payload.get("dev_mock") is None


@pytest.mark.asyncio
async def test_safety_mock_unset_does_not_bypass(monkeypatch):
    """Without SAFETY_MOCK=1, the real path runs even in dev."""
    monkeypatch.delenv("SAFETY_MOCK", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from backend.src.mcp_servers import check_content_safety

    sentinel_calls = []

    class _StubClient:
        def __init__(self, *args, **kwargs):
            sentinel_calls.append(("init",))

        @property
        def messages(self):
            class _M:
                def create(_self, *a, **kw):
                    raise RuntimeError("real path reached")

            return _M()

    with patch(
        "backend.src.mcp_servers.safety_check_server.Anthropic",
        new=_StubClient,
    ):
        result = await check_content_safety.handler(
            {
                "content_text": "Sparkle",
                "content_type": "agent_persona",
                "target_age": 4,
            }
        )

    assert sentinel_calls, "real path must run when SAFETY_MOCK is unset"
    payload = json.loads(result["content"][0]["text"])
    assert payload.get("dev_mock") is None
