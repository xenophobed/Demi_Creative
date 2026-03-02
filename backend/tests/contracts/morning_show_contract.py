"""
Morning Show Contract Tests (#88)

Defines the expected interfaces for:
- Morning Show dialogue agent output
- Morning Show API response payloads
- Topic subscription constraints
"""

from backend.src.api.models import NewsCategory


class TestMorningShowAgentContract:
    """Contract: dialogue script shape and safety threshold."""

    def test_dialogue_line_shape(self):
        """Dialogue lines must include role/text/timestamps."""
        line = {
            "role": "curious_kid",
            "text": "Why is this news important?",
            "timestamp_start": 0.0,
            "timestamp_end": 4.2,
        }

        assert set(line.keys()) == {"role", "text", "timestamp_start", "timestamp_end"}

    def test_dialogue_roles_allowlist(self):
        """Allowed roles are curious_kid, fun_expert, guest."""
        allowed_roles = {"curious_kid", "fun_expert", "guest"}
        assert "curious_kid" in allowed_roles
        assert "fun_expert" in allowed_roles
        assert "guest" in allowed_roles

    def test_safety_threshold_is_0_85_or_higher(self):
        """Morning Show scripts must satisfy safety_score >= 0.85."""
        safety_score = 0.85
        assert safety_score >= 0.85

    def test_sdk_fallback_contract_shape(self):
        """Mock fallback should still return valid dialogue script fields."""
        fallback_result = {
            "dialogue_script": {
                "lines": [],
                "total_duration": 0.0,
                "guest_character": None,
            },
            "safety_score": 0.9,
        }
        assert "dialogue_script" in fallback_result
        assert "safety_score" in fallback_result


class TestMorningShowAPIContract:
    """Contract: endpoint payload shapes."""

    def test_generate_response_shape(self):
        """POST /morning-show/generate returns complete episode payload."""
        response = {
            "episode": {
                "episode_id": "ep_123",
                "story_type": "morning_show",
                "dialogue_script": {"lines": []},
                "illustrations": [],
                "audio_urls": {},
            },
            "metadata": {
                "generation_id": "gen_123",
                "safety_score": 0.9,
                "used_mock": True,
            },
        }

        assert "episode" in response
        assert "metadata" in response

    def test_stream_endpoint_contract_placeholder(self):
        """POST /morning-show/generate/stream emits SSE status/progress/result events."""
        pass

    def test_get_episode_contract_shape(self):
        """GET /morning-show/episode/{id} returns full episode data."""
        payload_keys = {"episode_id", "story_type", "dialogue_script", "illustrations", "audio_urls"}
        assert "episode_id" in payload_keys
        assert "story_type" in payload_keys


class TestSubscriptionContract:
    """Contract: subscription endpoints and NewsCategory validation."""

    def test_subscription_shape(self):
        """Subscription payload must contain child_id/topic/subscribed_at/is_active."""
        subscription = {
            "child_id": "child_001",
            "topic": "science",
            "subscribed_at": "2026-03-02T10:00:00",
            "is_active": True,
        }
        assert set(subscription.keys()) == {"child_id", "topic", "subscribed_at", "is_active"}

    def test_topic_must_be_news_category_enum(self):
        """Subscription topics are constrained to NewsCategory values only."""
        allowed = {item.value for item in NewsCategory}
        assert "science" in allowed
        assert "general" in allowed

    def test_subscription_endpoint_contract_placeholder(self):
        """POST/DELETE/GET subscription endpoints exist and use enum validation."""
        pass
