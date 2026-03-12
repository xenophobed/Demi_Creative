"""
Morning Show Live SDK Integration Test (#137)

Validates end-to-end generation using the real Claude Agent SDK.
Skipped when ANTHROPIC_API_KEY is not set.
"""

import os

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set — skipping live SDK test",
    ),
]


async def test_live_sdk_generates_valid_episode():
    """Integration: live SDK call produces a valid DialogueScript with safety_score >= 0.85."""
    from unittest.mock import patch

    from backend.src.agents.morning_show_agent import generate_morning_show_dialogue
    from backend.src.api.models import DialogueScript

    # Bypass pytest detection so the real SDK path runs
    with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}, clear=False):
        with patch(
            "backend.src.agents.morning_show_agent._should_use_mock",
            return_value=False,
        ):
            result = await generate_morning_show_dialogue(
                news_text=(
                    "Scientists at NASA discovered a new type of ice on Europa, "
                    "one of Jupiter's moons. The ice glows blue in the dark and "
                    "may contain signs of microscopic life."
                ),
                age_group="6-8",
            )

    # Output shape
    assert "dialogue_script" in result
    assert "safety_score" in result
    assert "used_mock" in result
    assert "guest_character" in result

    # Script validity
    script = DialogueScript(**result["dialogue_script"])
    assert len(script.lines) >= 4, f"Expected at least 4 lines, got {len(script.lines)}"
    assert script.total_duration > 0

    # Role coverage
    roles = {line.role for line in script.lines}
    assert "curious_kid" in roles
    assert "fun_expert" in roles

    # Safety
    assert result["safety_score"] >= 0.85, (
        f"Live SDK safety_score {result['safety_score']} is below threshold 0.85"
    )

    # Timestamps monotonic
    for i in range(1, len(script.lines)):
        assert script.lines[i].timestamp_start >= script.lines[i - 1].timestamp_end, (
            f"Line {i} starts before line {i-1} ends"
        )
