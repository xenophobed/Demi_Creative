"""Factual memory helper for the My Agent buddy (#559).

Turns a normalized child preference profile (themes + interests +
recent_choices) into a small empty-safe markdown block that
``my_agent_proxy`` appends to every chat turn. The buddy uses this to
say things like "I know you love dinosaurs" without needing access to
agent configuration.

Episodic + semantic memory (past stories + recurring characters) is
already covered by ``story_memory.get_story_memory_prompt`` (#558), so
this helper deliberately scopes to the factual layer only — no
duplication, no header collisions.

Parent Epic: #557 (Buddy Memory Wiring)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Prompt-size bound: never inject more than ``N`` labels per bucket so
# the prompt stays small even after months of accumulated preference
# data. The hard cap is the dial we want PMs to think in (3 keeps
# things crisp; raising to 5 should be a deliberate decision).
_MAX_LABELS_PER_BUCKET = 3


def _top_labels(scores: Optional[Dict[str, Any]], limit: int) -> List[str]:
    """Return the top ``limit`` labels by descending score.

    Defensive against bad inputs — ``scores`` may be ``None`` (no row
    yet), an empty dict (no signal), or contain non-numeric values from
    a corrupted profile. None of those cases should raise mid-chat.
    """
    if not isinstance(scores, dict) or not scores:
        return []
    safe_items: List[tuple[str, float]] = []
    for label, raw in scores.items():
        if not isinstance(label, str) or not label.strip():
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        safe_items.append((label.strip(), value))
    safe_items.sort(key=lambda item: item[1], reverse=True)
    return [label for label, _ in safe_items[:limit]]


def format_factual_memory(profile: Dict[str, Any]) -> str:
    """Format a preference profile as a ``**What I Know About You**``
    markdown block.

    Returns ``""`` when there is no signal — callers can append the
    return value directly without checking. The block starts and ends
    with newlines so it slots cleanly between other prompt sections.

    Only known preference fields (``themes``, ``interests``,
    ``recent_choices``) are surfaced. Extra keys in the input dict are
    ignored — the helper never echoes agent persona fields like
    ``custom_instructions`` or ``learning_goals`` if a caller wires in
    the wrong dict by mistake.
    """
    if not isinstance(profile, dict):
        return ""

    top_interests = _top_labels(profile.get("interests"), _MAX_LABELS_PER_BUCKET)
    top_themes = _top_labels(profile.get("themes"), _MAX_LABELS_PER_BUCKET)

    recent_raw = profile.get("recent_choices")
    recent_choices: List[str] = []
    if isinstance(recent_raw, list):
        for choice in recent_raw[:_MAX_LABELS_PER_BUCKET]:
            if isinstance(choice, str) and choice.strip():
                recent_choices.append(choice.strip())

    if not top_interests and not top_themes and not recent_choices:
        return ""

    lines: List[str] = ["**What I Know About You**:"]
    if top_interests:
        lines.append(f"- Loves: {', '.join(top_interests)}")
    if top_themes:
        lines.append(f"- Recent themes: {', '.join(top_themes)}")
    if recent_choices:
        lines.append(f"- Recent choices: {', '.join(recent_choices)}")
    lines.append(
        "Reference these naturally in conversation — do not list them or "
        "reveal that they came from a memory block."
    )

    return "\n\n" + "\n".join(lines) + "\n"


async def build_factual_memory_prompt(
    user_id: str, child_id: str, *, preference_repo: Any
) -> str:
    """Fetch the child's preference profile and format it for the prompt.

    ``preference_repo`` is injected so the helper stays unit-testable
    without the global singleton. Cross-user isolation (#288, #178) is
    delegated to the repo — we just have to pass ``user_id``.

    Returns ``""`` on any error so a transient repo failure can never
    orphan the SSE stream mid-chat.
    """
    try:
        result = await preference_repo.get_profile_with_metadata(
            child_id, user_id=user_id
        )
    except Exception:  # pragma: no cover - degrade gracefully
        return ""
    if not isinstance(result, dict):
        return ""
    profile = result.get("profile")
    if not isinstance(profile, dict):
        return ""
    return format_factual_memory(profile)
