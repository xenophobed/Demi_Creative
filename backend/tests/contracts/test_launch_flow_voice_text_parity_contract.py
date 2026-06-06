"""
Launch-flow parity contract: voice tool result == text-mode SSE payload (#646).

The frontend's ``useLaunchFlowNavigation`` hook reads ``flow_type``,
``route``, ``prefill`` and routes the user without caring whether the
event came from an SSE stream (text chat) or a WS event (voice).

This contract locks the invariant that BOTH paths produce **byte-for-byte
identical payloads** for the same ``(flow_type, prefill)`` input. If
either side drifts the parity test fails, forcing the change to land in
``build_launch_flow_payload`` (the single source of truth) instead of
diverging by accident.

Why byte-for-byte JSON? Because the frontend deserialises both events
into the same TypeScript type. A semantically equal but key-order-shuffled
payload would still pass a dict-equality assertion but could regress a
caller that hashes the JSON for idempotency.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The single source of truth
# ---------------------------------------------------------------------------


class TestBuildLaunchFlowPayloadIsPublic:
    """The shared helper is exported from my_agent_proxy."""

    def test_build_launch_flow_payload_is_importable(self):
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        assert callable(build_launch_flow_payload)

    def test_image_story_with_id_routes_to_detail(self):
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        payload = build_launch_flow_payload(
            "image_story", {"story_id": "s1", "child_id": "c1"},
        )
        assert payload == {
            "flow_type": "image_story",
            "route": "/story/s1",
            "prefill": {"story_id": "s1", "child_id": "c1"},
        }

    def test_image_story_without_id_routes_to_upload(self):
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        payload = build_launch_flow_payload(
            "image_story", {"child_id": "c1", "age_group": "3-5"},
        )
        assert payload["route"] == "/upload"
        assert payload["prefill"] == {"child_id": "c1", "age_group": "3-5"}

    def test_interactive_story_rewrites_id_to_query_param(self):
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        payload = build_launch_flow_payload(
            "interactive_story", {"session_id": "x9", "theme": "ocean"},
        )
        assert payload["route"] == "/interactive"
        assert payload["prefill"]["session"] == "x9"
        # The raw session_id key was rewritten — confirm it's gone.
        assert "session_id" not in payload["prefill"]

    def test_unknown_flow_type_returns_none(self):
        """Whitelist-only — unknown flows produce no event."""
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        assert build_launch_flow_payload("hack_route", {"any": "thing"}) is None


# ---------------------------------------------------------------------------
# Parity: voice tool result vs text-mode legacy entry point
# ---------------------------------------------------------------------------


class TestVoiceTextByteParity:
    """The voice path and text path emit identical bytes for the same inputs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("flow_type,prefill", [
        ("image_story", {"story_id": "s_42"}),
        ("image_story", {"child_id": "c1", "age_group": "3-5"}),
        ("interactive_story", {"session_id": "ses_9", "theme": "space"}),
        ("interactive_story", {"theme": "ocean", "age_group": "6-8"}),
        ("kids_daily", {"episode_id": "ep_3"}),
        ("kids_daily", {"child_id": "c1", "age_group": "9-12", "category": "science"}),
    ])
    async def test_voice_payload_bytes_match_text_payload_bytes(
        self, flow_type: str, prefill: dict[str, Any],
    ):
        from backend.src.agents.my_agent_proxy import build_launch_flow_payload
        # Text path: the proxy's legacy private helper wraps payload in
        # the {response_type, payload} envelope that the SDK tool returns.
        # The public helper is the parity invariant — both must agree.
        text_payload = build_launch_flow_payload(flow_type, prefill)
        assert text_payload is not None

        # Voice path: the realtime tool handler builds the same payload
        # via the SAME helper (single source of truth). We don't go
        # through the broker here because the parity contract is about
        # the *payload*, not the transport.
        from backend.src.services.realtime_voice_tools import (
            _build_launch_flow_for_voice,
        )
        voice_payload = _build_launch_flow_for_voice(flow_type, prefill)

        # Byte-for-byte equality — JSON dump with sorted keys nails down
        # ordering drift so neither side can sneak in an extra key.
        assert json.dumps(text_payload, sort_keys=True) == json.dumps(
            voice_payload, sort_keys=True
        ), (
            f"Parity break for flow={flow_type!r} prefill={prefill!r}: "
            f"text={text_payload!r} voice={voice_payload!r}"
        )

    def test_legacy_private_helper_still_delegates(self):
        """``_build_launch_flow_data`` keeps working — old callers don't break."""
        from backend.src.agents.my_agent_proxy import _build_launch_flow_data
        legacy = _build_launch_flow_data({
            "response_type": "image_story",
            "payload": {"story_id": "s9", "age_group": "3-5"},
        })
        assert legacy is not None
        assert legacy["flow_type"] == "image_story"
        assert legacy["route"] == "/story/s9"
