"""Centralized Claude model selection helpers.

Defaults are tuned for cost-efficient testing and can be overridden by env vars.
"""

from __future__ import annotations

import os

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"


def get_claude_agent_model() -> str:
    """Model for Claude Agent SDK orchestration."""
    return (
        os.getenv("CLAUDE_AGENT_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
        or DEFAULT_CLAUDE_MODEL
    )


def get_safety_model() -> str:
    """Model for safety-check MCP server."""
    return (
        os.getenv("SAFETY_CHECK_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
        or DEFAULT_CLAUDE_MODEL
    )


def get_vision_model() -> str:
    """Model for vision-analysis MCP server."""
    return (
        os.getenv("VISION_ANALYSIS_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
        or DEFAULT_CLAUDE_MODEL
    )
