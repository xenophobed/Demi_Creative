"""
Voice session telemetry (#609 Phase D — Talk to Buddy).

Structured-event emitters for the realtime voice surface. Each emitter
writes a single flat ``logger.info(..., extra={...})`` record carrying an
``event`` discriminator plus a small set of typed fields. A downstream
JSON formatter (e.g. ``python-json-logger``) serialises them un-nested so
the ops dashboards + Parent Dashboard pipeline can scrape them with a
plain ``event=<name>`` filter.

Design rules (PRD §3.16 — child-safety):

  * **PII-free by construction.** Emitters accept IDs, durations, and
    categorical fields ONLY. There is deliberately no ``text`` /
    ``transcript`` parameter on any emitter, so a caller cannot leak a
    child's speech or the buddy's reply into the telemetry stream even
    by accident. Categories are bounded enums, never free-form content.
  * **Fire-and-forget.** Telemetry must never break a live voice turn,
    so ``_emit`` swallows any logging error. A dropped metric is always
    preferable to a crashed session.
  * **Flat fields.** No nested dicts — keeps the record cheap to index.

This sits alongside ``realtime_voice_service.log_voice_session_end``
(the cost-ops line, ``event=voice_session_end``). That helper stays the
single source of per-session COST aggregation; this module covers the
product/engagement + safety + latency events the dashboards need.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical event names — referenced by tests + the dashboard scrapers.
# ---------------------------------------------------------------------------

VOICE_SESSION_STARTED = "voice_session_started"
VOICE_SESSION_ENDED = "voice_session_ended"
VOICE_SESSION_SAFETY_REJECTION = "voice_session_safety_rejection"
VOICE_SESSION_LAUNCH_FLOW_EMITTED = "voice_session_launch_flow_emitted"
VOICE_SESSION_FIRST_AUDIO_MS = "voice_session_first_audio_ms"
VOICE_SESSION_INTERRUPTION_COUNT = "voice_session_interruption_count"

# ``direction`` is a bounded enum — anything else collapses to "unknown"
# so a wiring bug can't push a free-form string (potentially derived from
# content) into the metrics pipeline.
_VALID_DIRECTIONS = frozenset({"utterance", "reply"})


def _emit(event: str, fields: Dict[str, Any]) -> None:
    """Write one structured telemetry record. Never raises.

    The ``event`` discriminator and every field land in the record's
    ``__dict__`` via the logging ``extra`` mechanism, so a JSON handler
    serialises them flat. We log at INFO — voice sessions are infrequent
    (one per child play session) so this won't spam suppressed envs.
    """
    extra = {"event": event, **fields}
    try:
        # A compact human-readable message; the structured fields ride in
        # ``extra`` for the JSON formatter. ``%s`` pairs keep it greppable.
        message = "%s %s" % (
            event,
            " ".join(f"{k}={v}" for k, v in fields.items()),
        )
        logger.info(message, extra=extra)
    except Exception:  # pragma: no cover - telemetry must never break a turn
        pass


def emit_voice_session_started(
    *,
    session_id: str,
    age_group: Optional[str],
    agent_id: Optional[str],
    provider: Optional[str] = None,
) -> None:
    """A voice session opened. ``age_group`` + ``agent_id`` let the
    dashboard slice engagement by cohort and persona without joining
    back to the DB."""
    _emit(VOICE_SESSION_STARTED, {
        "session_id": session_id,
        "age_group": age_group,
        "agent_id": agent_id,
        "provider": provider,
    })


def emit_voice_session_ended(
    *,
    session_id: str,
    duration_seconds: int,
    ended_reason: str,
) -> None:
    """A voice session closed. ``ended_reason`` distinguishes a graceful
    goodbye from a timeout / quota / disconnect so we can alert on a
    spike in abnormal terminations."""
    _emit(VOICE_SESSION_ENDED, {
        "session_id": session_id,
        "duration_seconds": int(duration_seconds or 0),
        "ended_reason": ended_reason,
    })


def emit_voice_session_safety_rejection(
    *,
    session_id: str,
    direction: str,
    category: str,
) -> None:
    """A turn was blocked by the safety gate. ``direction`` says which
    side tripped it (``utterance`` = child speech, ``reply`` = buddy
    text); ``category`` is a bounded reason code (never content)."""
    safe_direction = direction if direction in _VALID_DIRECTIONS else "unknown"
    _emit(VOICE_SESSION_SAFETY_REJECTION, {
        "session_id": session_id,
        "direction": safe_direction,
        "category": category,
    })


def emit_voice_session_launch_flow_emitted(
    *,
    session_id: str,
    flow: str,
) -> None:
    """The buddy handed off to a launch-flow specialist (image story,
    interactive story, kids daily). ``flow`` is the target flow type —
    the key engagement signal that voice drives kids INTO creation."""
    _emit(VOICE_SESSION_LAUNCH_FLOW_EMITTED, {
        "session_id": session_id,
        "flow": flow,
    })


def emit_voice_session_first_audio_ms(
    *,
    session_id: str,
    first_audio_ms: int,
    age_group: Optional[str] = None,
) -> None:
    """Time-to-first-audio for the session's first buddy reply. Feeds the
    latency histogram behind the p50 ≤ 1500ms / p95 ≤ 2500ms AC."""
    _emit(VOICE_SESSION_FIRST_AUDIO_MS, {
        "session_id": session_id,
        "first_audio_ms": int(first_audio_ms or 0),
        "age_group": age_group,
    })


def emit_voice_session_interruption_count(
    *,
    session_id: str,
    count: int,
) -> None:
    """How many times the child barged in over the buddy during the
    session. A high count hints the replies are too long for the age
    band — a tuning signal, emitted once at session close."""
    _emit(VOICE_SESSION_INTERRUPTION_COUNT, {
        "session_id": session_id,
        "count": int(count or 0),
    })
