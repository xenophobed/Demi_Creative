"""Story memory helper — builds cross-story reference prompt sections (#165).

Queries the last N stories for a child and formats a brief memory section
to inject into agent prompts, enabling references like
"Remember when Lightning Dog flew to the moon?"

Parent Epic: #42
"""

import json
from typing import List, Dict, Any

from .database import story_repo, character_repo


async def get_story_memory_prompt(child_id: str, limit: int = 3, *, user_id: str = "") -> str:
    """Build a story memory prompt section for a child.

    Args:
        child_id: Child profile ID.
        limit: Maximum number of recent stories to include.
        user_id: Owner's user ID — when provided, scopes stories per account (#288).

    Returns an empty string if the child has no previous stories,
    so callers can simply append without checking.
    """
    if user_id:
        stories = await story_repo.list_by_user_and_child(user_id, child_id, limit=limit)
    else:
        stories = await story_repo.list_by_child(child_id, limit=limit)
    # Fetch recurring characters deterministically (#365)
    characters: List[Dict[str, Any]] = []
    try:
        characters = await character_repo.get_characters(user_id, child_id)
    except Exception:
        pass  # Non-critical — degrade gracefully

    if not stories and not characters:
        return ""

    sections: List[str] = []

    # Story previews section
    if stories:
        lines = []
        for i, story in enumerate(stories, 1):
            text = story.get("story_text", "")
            # Build a brief summary: first 80 chars + themes
            preview = text[:80].replace("\n", " ").strip()
            if len(text) > 80:
                preview += "..."
            themes_raw = story.get("themes", "[]")
            if isinstance(themes_raw, str):
                try:
                    themes = json.loads(themes_raw)
                except json.JSONDecodeError:
                    themes = []
            else:
                themes = themes_raw if isinstance(themes_raw, list) else []
            themes_str = ", ".join(themes[:3]) if themes else ""
            line = f"{i}. {preview}"
            if themes_str:
                line += f" (themes: {themes_str})"
            lines.append(line)

        story_list = "\n".join(lines)
        sections.append(
            f"**Story Memory**:\n"
            f"This child has told stories before. Here are their recent stories:\n"
            f"{story_list}\n"
            f"Please naturally reference or continue these stories when appropriate "
            f'(e.g., "Remember when Lightning Dog went to the moon?"), '
            f"but do not repeat the same plot. Create something fresh that builds on their creative world."
        )

    # Character memory section — deterministic injection (#365)
    if characters:
        char_lines = []
        for ch in characters[:5]:  # Top 5 by appearance
            name = ch.get("name", "")
            count = ch.get("appearance_count", 1)
            traits = ch.get("traits", [])
            desc = ch.get("description", "")
            parts = [f"- **{name}** (appeared {count} times)"]
            if traits:
                parts[0] += f": {', '.join(traits[:3])}"
            if desc:
                parts.append(f"  {desc}")
            char_lines.append("\n".join(parts))

        sections.append(
            "**Recurring Characters**:\n"
            "These characters have appeared in this child's previous stories. "
            "Use them naturally in new stories to maintain continuity:\n"
            + "\n".join(char_lines)
        )

    return "\n\n" + "\n\n".join(sections) + "\n"
