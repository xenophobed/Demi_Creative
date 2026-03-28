"""Theme recommendation engine — suggests next themes from preference history (#292).

Reads preference profile counters (themes, concepts, interests) and recent story
themes, then ranks candidates by weighted score (frequency x recency penalty) and
filters recently-used themes so suggestions feel fresh.

Parent Epic: #42
"""

import logging
import math
from typing import Any, Dict, List

from .database import preference_repo, story_repo

logger = logging.getLogger(__name__)

# Weight multipliers for each preference counter source
_WEIGHTS = {
    "themes": 1.0,
    "concepts": 0.6,
    "interests": 0.8,
}

# Number of recent stories to check for recently-used theme filtering
_RECENT_STORY_COUNT = 3


class ThemeRecommender:
    """Suggests personalised themes from a child's preference history."""

    async def get_recommendations(
        self,
        user_id: str,
        child_id: str,
        limit: int = 5,
    ) -> List[str]:
        """Return up to *limit* recommended theme strings.

        Algorithm:
        1. Load preference profile (themes / concepts / interests counters).
        2. Load themes from the last 3 stories to build a recency-exclude set.
        3. Score each candidate: ``frequency * source_weight``, penalising
           recently-used themes by removing them entirely.
        4. Rank by descending score, return the top *limit* names.
        5. Filter through safety check (non-child-safe terms are removed).
        """
        profile = await self._get_preference_profile(user_id, child_id)
        recent_themes = await self._get_recent_story_themes(user_id, child_id)

        ranked = self._rank_and_filter(
            themes=profile.get("themes", {}),
            concepts=profile.get("concepts", {}),
            interests=profile.get("interests", {}),
            recent_themes=recent_themes,
            limit=limit,
        )

        # Safety gate — drop anything that fails the child-safety word check
        safe = await self._filter_safe_themes(ranked)
        return safe

    # ------------------------------------------------------------------
    # Scoring helpers (public for unit testing)
    # ------------------------------------------------------------------

    def _score_themes(
        self,
        counter: Dict[str, int],
        recent_themes: List[str],
        weight: float = 1.0,
    ) -> Dict[str, float]:
        """Score a single counter dict.  Higher frequency => higher score."""
        scores: Dict[str, float] = {}
        for name, count in counter.items():
            if not isinstance(name, str) or not name.strip():
                continue
            token = name.strip().lower()
            scores[token] = float(count) * weight
        return scores

    def _score_all(
        self,
        themes: Dict[str, int],
        concepts: Dict[str, int],
        interests: Dict[str, int],
        recent_themes: List[str],
    ) -> Dict[str, float]:
        """Merge scores from all three counter sources."""
        merged: Dict[str, float] = {}
        for source_key, counter in [("themes", themes), ("concepts", concepts), ("interests", interests)]:
            w = _WEIGHTS.get(source_key, 1.0)
            partial = self._score_themes(counter, recent_themes, weight=w)
            for token, score in partial.items():
                merged[token] = merged.get(token, 0.0) + score
        return merged

    def _rank_and_filter(
        self,
        themes: Dict[str, int],
        concepts: Dict[str, int],
        interests: Dict[str, int],
        recent_themes: List[str],
        limit: int = 5,
    ) -> List[str]:
        """Score, filter recently-used, and return top *limit* theme names."""
        scores = self._score_all(themes, concepts, interests, recent_themes)

        # Remove recently-used themes
        recent_lower = {t.strip().lower() for t in recent_themes if isinstance(t, str)}
        for rt in recent_lower:
            scores.pop(rt, None)

        if not scores:
            return []

        # Sort by descending score, break ties alphabetically
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [name for name, _score in ranked[:limit]]

    # ------------------------------------------------------------------
    # Data access helpers (patched in unit tests)
    # ------------------------------------------------------------------

    async def _get_preference_profile(self, user_id: str, child_id: str) -> Dict[str, Any]:
        """Load the preference profile from the repository."""
        return await preference_repo.get_profile(child_id, user_id=user_id)

    async def _get_recent_story_themes(self, user_id: str, child_id: str) -> List[str]:
        """Collect distinct themes from the child's last N stories."""
        stories = await story_repo.list_by_user_and_child(
            user_id, child_id, limit=_RECENT_STORY_COUNT,
        )
        theme_set: List[str] = []
        for story in stories:
            edu = story.get("educational_value", {})
            raw_themes = edu.get("themes", [])
            if isinstance(raw_themes, list):
                for t in raw_themes:
                    if isinstance(t, str) and t.strip() and t.strip().lower() not in {
                        x.lower() for x in theme_set
                    }:
                        theme_set.append(t.strip())
        return theme_set

    async def _filter_safe_themes(self, themes: List[str]) -> List[str]:
        """Run a lightweight safety check — reject obviously unsafe terms.

        Uses a simple blocklist instead of calling the full MCP safety tool,
        because theme strings are very short and come from our own preference
        counters (already safety-checked content).  This keeps the endpoint
        fast while still providing a safety net.
        """
        _BLOCKLIST = {
            "violence", "weapons", "gore", "drugs", "alcohol",
            "gambling", "horror", "death", "murder", "blood",
            "war", "abuse", "hate", "sexual", "explicit",
        }
        safe: List[str] = []
        for t in themes:
            if t.lower() not in _BLOCKLIST:
                safe.append(t)
        return safe


# Module-level singleton
theme_recommender = ThemeRecommender()
