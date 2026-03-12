"""Story memory helper — builds cross-story reference prompt sections (#165).

Queries the last N stories for a child and formats a brief memory section
to inject into agent prompts, enabling references like
"Remember when Lightning Dog flew to the moon?"

Parent Epic: #42
"""

import json
from typing import List, Dict, Any

from .database import story_repo


async def get_story_memory_prompt(child_id: str, limit: int = 3) -> str:
    """Build a story memory prompt section for a child.

    Returns an empty string if the child has no previous stories,
    so callers can simply append without checking.
    """
    stories = await story_repo.list_by_child(child_id, limit=limit)
    if not stories:
        return ""

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

    return f"""
**Story Memory**:
This child has told stories before. Here are their recent stories:
{story_list}
Please naturally reference or continue these stories when appropriate (e.g., "Remember when Lightning Dog went to the moon?"), but do not repeat the same plot. Create something fresh that builds on their creative world.
"""
