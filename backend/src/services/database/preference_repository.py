"""Persistent child preference repository."""

import json
from datetime import datetime
from typing import Any, Dict, List

from .connection import db_manager


class PreferenceRepository:
    def __init__(self):
        self._db = db_manager

    async def update_from_story_result(self, child_id: str, story_result: Dict[str, Any]) -> None:
        profile = await self._get_profile(child_id)
        self._bump(profile["themes"], story_result.get("themes", []), 1)
        self._bump(profile["concepts"], self._extract_concepts(story_result.get("concepts", [])), 1)
        await self._save_profile(child_id, profile)

    async def update_from_choices(self, child_id: str, choice_history: List[str], session_data: Dict[str, Any]) -> None:
        profile = await self._get_profile(child_id)
        self._bump(profile["interests"], session_data.get("interests", []), 2)
        if isinstance(session_data.get("theme"), str) and session_data["theme"].strip():
            self._bump(profile["themes"], [session_data["theme"].strip()], 2)
        profile["recent_choices"] = [str(choice) for choice in (choice_history or [])[-20:]]
        await self._save_profile(child_id, profile)

    async def update_from_news(self, child_id: str, category: str, key_concepts: List[Dict[str, Any]]) -> None:
        profile = await self._get_profile(child_id)
        if isinstance(category, str) and category.strip():
            self._bump(profile["themes"], [category.strip()], 1)
        concepts = []
        for item in key_concepts or []:
            if isinstance(item, dict) and isinstance(item.get("term"), str):
                concepts.append(item["term"])
        self._bump(profile["concepts"], concepts, 1)
        await self._save_profile(child_id, profile)

    async def update_from_morning_show(
        self,
        child_id: str,
        topic: str,
        event_type: str,
        progress: float,
    ) -> float:
        """
        Update preference profile from Morning Show playback events (#102).

        Returns:
            float: updated engagement score for the topic.
        """
        profile = await self._get_profile(child_id)

        morning = profile.setdefault("morning_show", {})
        topic_scores = morning.setdefault("topic_scores", {})
        topic_stats = morning.setdefault("topic_stats", {})

        current_score = float(topic_scores.get(topic, 0.0))
        stats = topic_stats.get(topic, {"started": 0, "completed": 0, "abandoned": 0})

        if event_type == "start":
            stats["started"] = int(stats.get("started", 0)) + 1
            current_score += 0.2
        elif event_type == "complete" or progress >= 0.8:
            stats["completed"] = int(stats.get("completed", 0)) + 1
            current_score += 1.0
            self._bump(profile["themes"], [topic], 2)
            self._bump(profile["interests"], [topic], 2)
        elif event_type == "abandon" or progress < 0.5:
            stats["abandoned"] = int(stats.get("abandoned", 0)) + 1
            current_score -= 0.6
        else:
            current_score += 0.05

        topic_stats[topic] = stats
        topic_scores[topic] = round(max(-5.0, min(20.0, current_score)), 3)
        morning["last_event_at"] = datetime.now().isoformat()

        await self._save_profile(child_id, profile)
        return topic_scores[topic]

    async def get_profile(self, child_id: str) -> Dict[str, Any]:
        return await self._get_profile(child_id)

    async def _get_profile(self, child_id: str) -> Dict[str, Any]:
        row = await self._db.fetchone(
            "SELECT profile_json FROM child_preferences WHERE child_id = ?",
            (child_id,),
        )
        if not row:
            return self._empty_profile()

        try:
            loaded = json.loads(row.get("profile_json") or "{}")
        except json.JSONDecodeError:
            loaded = {}

        return self._normalize_profile(loaded)

    async def _save_profile(self, child_id: str, profile: Dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        payload = self._normalize_profile(profile)

        await self._db.execute(
            """
            INSERT INTO child_preferences (child_id, profile_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(child_id)
            DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at
            """,
            (child_id, json.dumps(payload, ensure_ascii=False), now),
        )
        await self._db.commit()

    def _empty_profile(self) -> Dict[str, Any]:
        return {
            "themes": {},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
            "morning_show": {
                "topic_scores": {},
                "topic_stats": {},
                "last_event_at": None,
            },
        }

    def _normalize_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._empty_profile()
        if isinstance(profile, dict):
            normalized.update(profile)

        for key in ["themes", "concepts", "interests"]:
            if not isinstance(normalized.get(key), dict):
                normalized[key] = {}
        if not isinstance(normalized.get("recent_choices"), list):
            normalized["recent_choices"] = []
        if not isinstance(normalized.get("morning_show"), dict):
            normalized["morning_show"] = self._empty_profile()["morning_show"]
        else:
            morning = normalized["morning_show"]
            if not isinstance(morning.get("topic_scores"), dict):
                morning["topic_scores"] = {}
            if not isinstance(morning.get("topic_stats"), dict):
                morning["topic_stats"] = {}

        return normalized

    def _extract_concepts(self, concepts: Any) -> List[str]:
        if not isinstance(concepts, list):
            return []
        extracted = []
        for concept in concepts:
            if isinstance(concept, str):
                extracted.append(concept)
            elif isinstance(concept, dict) and isinstance(concept.get("term"), str):
                extracted.append(concept["term"])
        return extracted

    def _bump(self, scores: Dict[str, int], labels: Any, delta: int) -> None:
        if not isinstance(labels, list):
            return
        for label in labels:
            if not isinstance(label, str):
                continue
            token = label.strip()
            if not token:
                continue
            scores[token] = int(scores.get(token, 0)) + delta


preference_repo = PreferenceRepository()
