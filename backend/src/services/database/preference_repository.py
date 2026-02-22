"""In-memory child preference repository."""

from typing import Any, Dict, List


class PreferenceRepository:
    def __init__(self):
        self._profiles: Dict[str, Dict[str, Any]] = {}

    async def update_from_story_result(self, child_id: str, story_result: Dict[str, Any]) -> None:
        profile = self._get_or_create_profile(child_id)
        self._bump(profile["themes"], story_result.get("themes", []), 1)
        self._bump(profile["concepts"], self._extract_concepts(story_result.get("concepts", [])), 1)

    async def update_from_choices(self, child_id: str, choice_history: List[str], session_data: Dict[str, Any]) -> None:
        profile = self._get_or_create_profile(child_id)
        self._bump(profile["interests"], session_data.get("interests", []), 2)
        if isinstance(session_data.get("theme"), str) and session_data["theme"].strip():
            self._bump(profile["themes"], [session_data["theme"].strip()], 2)
        profile["recent_choices"] = [str(choice) for choice in (choice_history or [])[-20:]]

    async def update_from_news(self, child_id: str, category: str, key_concepts: List[Dict[str, Any]]) -> None:
        profile = self._get_or_create_profile(child_id)
        if isinstance(category, str) and category.strip():
            self._bump(profile["themes"], [category.strip()], 1)
        concepts = []
        for item in key_concepts or []:
            if isinstance(item, dict) and isinstance(item.get("term"), str):
                concepts.append(item["term"])
        self._bump(profile["concepts"], concepts, 1)

    async def get_profile(self, child_id: str) -> Dict[str, Any]:
        return self._profiles.get(child_id, self._empty_profile())

    def _get_or_create_profile(self, child_id: str) -> Dict[str, Any]:
        if child_id not in self._profiles:
            self._profiles[child_id] = self._empty_profile()
        return self._profiles[child_id]

    def _empty_profile(self) -> Dict[str, Any]:
        return {
            "themes": {},
            "concepts": {},
            "interests": {},
            "recent_choices": [],
        }

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
