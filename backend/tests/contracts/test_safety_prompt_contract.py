"""
Safety Prompt Contract Tests

Ensures that agent prompts explicitly instruct safety check invocation.
Content safety is non-negotiable (CLAUDE.md, PRD §1.2) — the agent MUST be
told to call check_content_safety, not just have it in allowed_tools.

Related: #105
"""

import re
import pytest


SAFETY_TOOL = "mcp__safety-check__check_content_safety"
IMPROVEMENT_TOOL = "mcp__safety-check__suggest_content_improvements"


def _build_image_to_story_prompt(child_age: int = 7) -> str:
    """Build the inline prompt the same way image_to_story_agent does."""
    from src.agents.image_to_story_agent import (
        image_to_story,
        stream_image_to_story,
    )
    import inspect

    # Extract prompt string from source to avoid needing real files / SDK
    source = inspect.getsource(image_to_story)
    return source


def _build_stream_prompt() -> str:
    from src.agents.image_to_story_agent import stream_image_to_story
    import inspect
    return inspect.getsource(stream_image_to_story)


class TestImageToStorySafetyPromptContract:
    """The inline prompt in image_to_story_agent MUST instruct the agent to
    call the safety check tool explicitly."""

    def test_prompt_references_safety_check_tool(self):
        """The prompt text must mention the safety check tool by full MCP name."""
        source = _build_image_to_story_prompt()
        assert SAFETY_TOOL in source, (
            f"image_to_story prompt must reference {SAFETY_TOOL}"
        )

    def test_prompt_contains_mandatory_safety_instruction(self):
        """The prompt must contain a MUST/mandatory instruction to run safety."""
        source = _build_image_to_story_prompt()
        # Look for mandatory language near the safety tool reference
        has_mandatory = bool(
            re.search(
                r"(MUST|必须|mandatory|required|一定).{0,120}"
                + re.escape(SAFETY_TOOL),
                source,
                re.IGNORECASE | re.DOTALL,
            )
            or re.search(
                re.escape(SAFETY_TOOL)
                + r".{0,120}(MUST|必须|mandatory|required|一定)",
                source,
                re.IGNORECASE | re.DOTALL,
            )
        )
        assert has_mandatory, (
            "image_to_story prompt must use mandatory language (MUST/必须) "
            "when instructing the agent to call the safety check tool"
        )

    def test_prompt_references_improvement_tool(self):
        """The prompt should reference suggest_content_improvements for failures."""
        source = _build_image_to_story_prompt()
        assert IMPROVEMENT_TOOL in source, (
            f"image_to_story prompt must reference {IMPROVEMENT_TOOL} "
            "for handling safety check failures"
        )

    def test_stream_prompt_references_safety_check_tool(self):
        """stream_image_to_story must also instruct safety check."""
        source = _build_stream_prompt()
        assert SAFETY_TOOL in source, (
            f"stream_image_to_story prompt must reference {SAFETY_TOOL}"
        )

    def test_stream_prompt_contains_mandatory_safety_instruction(self):
        """stream_image_to_story must also use mandatory language for safety."""
        source = _build_stream_prompt()
        has_mandatory = bool(
            re.search(
                r"(MUST|必须|mandatory|required|一定).{0,120}"
                + re.escape(SAFETY_TOOL),
                source,
                re.IGNORECASE | re.DOTALL,
            )
            or re.search(
                re.escape(SAFETY_TOOL)
                + r".{0,120}(MUST|必须|mandatory|required|一定)",
                source,
                re.IGNORECASE | re.DOTALL,
            )
        )
        assert has_mandatory, (
            "stream_image_to_story prompt must use mandatory language "
            "when instructing the agent to call the safety check tool"
        )
