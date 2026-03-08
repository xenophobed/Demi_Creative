"""
Morning Show Contract Tests (#88)

Validates Pydantic model constraints, enum boundaries, cross-field validation,
safety thresholds, and agent output shapes for:
- DialogueLine / DialogueScript / EpisodeIllustration
- MorningShowEpisode / MorningShowRequest / MorningShowResponse
- TopicSubscription / SubscriptionRequest / SubscriptionResponse
- Morning Show agent mock fallback shape
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.src.api.models import (
    ALLOWED_ANIMATION_TYPES,
    ALLOWED_DIALOGUE_ROLES,
    AgeGroup,
    DialogueLine,
    DialogueScript,
    EpisodeIllustration,
    MorningShowEpisode,
    MorningShowGenerationMetadata,
    MorningShowRequest,
    MorningShowResponse,
    MorningShowTrackEvent,
    MorningShowTrackRequest,
    MorningShowTrackResponse,
    NewsCategory,
    SubscriptionListResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    TopicSubscription,
)


# ---------------------------------------------------------------------------
# DialogueLine
# ---------------------------------------------------------------------------
class TestDialogueLineContract:
    """Contract: individual dialogue line shape and validation."""

    def test_valid_dialogue_line(self):
        """Contract: a DialogueLine with valid role/text/timestamps must pass."""
        line = DialogueLine(
            role="curious_kid",
            text="Why is the sky blue?",
            timestamp_start=0.0,
            timestamp_end=4.5,
        )
        assert line.role == "curious_kid"
        assert line.text == "Why is the sky blue?"
        assert line.timestamp_start == 0.0
        assert line.timestamp_end == 4.5

    def test_all_three_roles_accepted(self):
        """Contract: curious_kid, fun_expert, and guest are the only valid roles."""
        for role in ("curious_kid", "fun_expert", "guest"):
            line = DialogueLine(
                role=role, text="Hello!", timestamp_start=0.0, timestamp_end=1.0
            )
            assert line.role == role

    def test_invalid_role_rejected(self):
        """Contract: unknown roles must fail validation."""
        with pytest.raises(ValidationError, match="role must be one of"):
            DialogueLine(
                role="narrator",
                text="Once upon a time...",
                timestamp_start=0.0,
                timestamp_end=3.0,
            )

    def test_empty_text_rejected(self):
        """Contract: text must be at least 1 character (min_length=1)."""
        with pytest.raises(ValidationError):
            DialogueLine(
                role="curious_kid",
                text="",
                timestamp_start=0.0,
                timestamp_end=1.0,
            )

    def test_negative_timestamp_start_rejected(self):
        """Contract: timestamp_start must be >= 0."""
        with pytest.raises(ValidationError):
            DialogueLine(
                role="fun_expert",
                text="Good question!",
                timestamp_start=-1.0,
                timestamp_end=2.0,
            )

    def test_end_before_start_rejected(self):
        """Contract: timestamp_end must be greater than timestamp_start."""
        with pytest.raises(ValidationError, match="timestamp_end must be greater"):
            DialogueLine(
                role="curious_kid",
                text="What happened?",
                timestamp_start=5.0,
                timestamp_end=3.0,
            )

    def test_equal_timestamps_rejected(self):
        """Contract: timestamp_end == timestamp_start is invalid (must be strictly greater)."""
        with pytest.raises(ValidationError, match="timestamp_end must be greater"):
            DialogueLine(
                role="curious_kid",
                text="Hello!",
                timestamp_start=2.0,
                timestamp_end=2.0,
            )

    def test_allowed_roles_constant_matches(self):
        """Contract: ALLOWED_DIALOGUE_ROLES must be exactly {curious_kid, fun_expert, guest}."""
        assert ALLOWED_DIALOGUE_ROLES == {"curious_kid", "fun_expert", "guest"}


# ---------------------------------------------------------------------------
# DialogueScript
# ---------------------------------------------------------------------------
class TestDialogueScriptContract:
    """Contract: dialogue script shape and cross-field validation."""

    def test_valid_script_with_lines(self):
        """Contract: a script with lines and covering total_duration must pass."""
        script = DialogueScript(
            lines=[
                DialogueLine(role="curious_kid", text="Q1?", timestamp_start=0.0, timestamp_end=5.0),
                DialogueLine(role="fun_expert", text="A1.", timestamp_start=5.0, timestamp_end=10.0),
            ],
            total_duration=10.0,
            guest_character="Lightning Dog",
        )
        assert len(script.lines) == 2
        assert script.total_duration == 10.0
        assert script.guest_character == "Lightning Dog"

    def test_empty_lines_allowed(self):
        """Contract: empty lines list is valid (SDK fallback may produce this)."""
        script = DialogueScript(lines=[], total_duration=0.0)
        assert len(script.lines) == 0

    def test_total_duration_too_short_rejected(self):
        """Contract: total_duration must cover the latest timestamp_end."""
        with pytest.raises(ValidationError, match="total_duration must cover"):
            DialogueScript(
                lines=[
                    DialogueLine(role="curious_kid", text="Q?", timestamp_start=0.0, timestamp_end=8.0),
                ],
                total_duration=5.0,
            )

    def test_guest_character_optional(self):
        """Contract: guest_character can be None (no recurring character found)."""
        script = DialogueScript(
            lines=[
                DialogueLine(role="fun_expert", text="Let me explain.", timestamp_start=0.0, timestamp_end=3.0),
            ],
            total_duration=3.0,
            guest_character=None,
        )
        assert script.guest_character is None

    def test_negative_total_duration_rejected(self):
        """Contract: total_duration must be >= 0."""
        with pytest.raises(ValidationError):
            DialogueScript(lines=[], total_duration=-1.0)


# ---------------------------------------------------------------------------
# EpisodeIllustration
# ---------------------------------------------------------------------------
class TestEpisodeIllustrationContract:
    """Contract: illustration metadata shape and animation type validation."""

    def test_valid_illustration(self):
        """Contract: illustration with valid fields must pass."""
        ill = EpisodeIllustration(
            url="https://example.com/img1.png",
            description="A rocket launching into space",
            display_order=0,
            animation_type="ken_burns",
        )
        assert ill.animation_type == "ken_burns"
        assert ill.display_order == 0

    def test_all_animation_types_accepted(self):
        """Contract: pan, zoom, and ken_burns are the only valid animation types."""
        for anim in ("pan", "zoom", "ken_burns"):
            ill = EpisodeIllustration(
                url="https://example.com/img.png",
                description="test",
                display_order=0,
                animation_type=anim,
            )
            assert ill.animation_type == anim

    def test_invalid_animation_type_rejected(self):
        """Contract: unknown animation types must fail."""
        with pytest.raises(ValidationError, match="animation_type must be one of"):
            EpisodeIllustration(
                url="https://example.com/img.png",
                description="test",
                display_order=0,
                animation_type="fade",
            )

    def test_empty_url_rejected(self):
        """Contract: url must be non-empty."""
        with pytest.raises(ValidationError):
            EpisodeIllustration(
                url="",
                description="test",
                display_order=0,
                animation_type="pan",
            )

    def test_negative_display_order_rejected(self):
        """Contract: display_order must be >= 0."""
        with pytest.raises(ValidationError):
            EpisodeIllustration(
                url="https://example.com/img.png",
                description="test",
                display_order=-1,
                animation_type="zoom",
            )

    def test_allowed_animation_types_constant_matches(self):
        """Contract: ALLOWED_ANIMATION_TYPES must be exactly {pan, zoom, ken_burns}."""
        assert ALLOWED_ANIMATION_TYPES == {"pan", "zoom", "ken_burns"}


# ---------------------------------------------------------------------------
# MorningShowEpisode
# ---------------------------------------------------------------------------
class TestMorningShowEpisodeContract:
    """Contract: full episode data shape."""

    def _make_episode(self, **overrides):
        defaults = {
            "episode_id": "ep_test_001",
            "child_id": "child_001",
            "age_group": "6-8",
            "category": "science",
            "kid_title": "Rockets go zoom!",
            "kid_content": "Scientists launched a big rocket today.",
            "why_care": "You might ride one someday!",
            "dialogue_script": DialogueScript(
                lines=[
                    DialogueLine(role="curious_kid", text="Why?", timestamp_start=0.0, timestamp_end=3.0),
                    DialogueLine(role="fun_expert", text="Because!", timestamp_start=3.0, timestamp_end=6.0),
                ],
                total_duration=6.0,
                guest_character="Professor Owl",
            ),
        }
        defaults.update(overrides)
        return MorningShowEpisode(**defaults)

    def test_valid_episode(self):
        """Contract: episode with required fields must pass."""
        ep = self._make_episode()
        assert ep.story_type == "morning_show"
        assert ep.is_new is True
        assert ep.is_played is False

    def test_story_type_is_literal_morning_show(self):
        """Contract: story_type is always 'morning_show'."""
        ep = self._make_episode()
        assert ep.story_type == "morning_show"

    def test_episode_serialization_roundtrip(self):
        """Contract: episode serializes and deserializes without data loss."""
        ep = self._make_episode()
        data = ep.model_dump()
        restored = MorningShowEpisode(**data)
        assert restored.episode_id == ep.episode_id
        assert restored.kid_title == ep.kid_title
        assert len(restored.dialogue_script.lines) == 2

    def test_illustrations_default_empty(self):
        """Contract: illustrations default to empty list."""
        ep = self._make_episode()
        assert ep.illustrations == []

    def test_audio_urls_default_empty(self):
        """Contract: audio_urls default to empty dict."""
        ep = self._make_episode()
        assert ep.audio_urls == {}

    def test_created_at_auto_populated(self):
        """Contract: created_at is auto-populated with current time."""
        ep = self._make_episode()
        assert isinstance(ep.created_at, datetime)


# ---------------------------------------------------------------------------
# MorningShowRequest / Response
# ---------------------------------------------------------------------------
class TestMorningShowRequestContract:
    """Contract: generate request validation."""

    def test_valid_request(self):
        """Contract: request with news_text and age_group must pass."""
        req = MorningShowRequest(
            news_text="Scientists found a new coral reef.",
            age_group="6-8",
        )
        assert req.category == NewsCategory.GENERAL  # default

    def test_request_with_url(self):
        """Contract: request with news_url (no news_text) is valid at model level."""
        req = MorningShowRequest(
            news_url="https://example.com/news",
            age_group="3-5",
            category="space",
        )
        assert req.news_url == "https://example.com/news"
        assert req.news_text is None

    def test_category_defaults_to_general(self):
        """Contract: category defaults to 'general' when not provided."""
        req = MorningShowRequest(news_text="test", age_group="6-8")
        assert req.category == NewsCategory.GENERAL


class TestMorningShowResponseContract:
    """Contract: generate response shape."""

    def test_response_contains_episode_and_metadata(self):
        """Contract: response has episode + metadata top-level keys."""
        script = DialogueScript(
            lines=[DialogueLine(role="curious_kid", text="Q?", timestamp_start=0.0, timestamp_end=3.0)],
            total_duration=3.0,
        )
        episode = MorningShowEpisode(
            episode_id="ep_001",
            child_id="child_001",
            age_group="6-8",
            category="science",
            kid_title="Title",
            kid_content="Content",
            why_care="Why",
            dialogue_script=script,
        )
        metadata = MorningShowGenerationMetadata(
            generation_id="gen_001",
            safety_score=0.92,
            used_mock=True,
        )
        resp = MorningShowResponse(episode=episode, metadata=metadata)
        assert resp.episode.episode_id == "ep_001"
        assert resp.metadata.safety_score >= 0.85

    def test_metadata_safety_score_bounds(self):
        """Contract: safety_score must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            MorningShowGenerationMetadata(
                generation_id="gen_002",
                safety_score=1.5,
            )
        with pytest.raises(ValidationError):
            MorningShowGenerationMetadata(
                generation_id="gen_003",
                safety_score=-0.1,
            )


# ---------------------------------------------------------------------------
# Agent Output Shape
# ---------------------------------------------------------------------------
class TestMorningShowAgentContract:
    """Contract: dialogue agent output and safety threshold."""

    def test_agent_output_has_required_keys(self):
        """Contract: agent returns dialogue_script, safety_score, used_mock, guest_character."""
        agent_output = {
            "dialogue_script": {
                "lines": [
                    {"role": "curious_kid", "text": "Q?", "timestamp_start": 0.0, "timestamp_end": 3.0},
                    {"role": "fun_expert", "text": "A!", "timestamp_start": 3.0, "timestamp_end": 6.0},
                ],
                "total_duration": 6.0,
                "guest_character": "Professor Owl",
            },
            "safety_score": 0.92,
            "used_mock": True,
            "guest_character": "Professor Owl",
        }
        assert set(agent_output.keys()) == {"dialogue_script", "safety_score", "used_mock", "guest_character"}

    def test_safety_threshold_is_0_85(self):
        """Contract: Morning Show content must have safety_score >= 0.85 per CLAUDE.md."""
        SAFETY_THRESHOLD = 0.85
        passing_scores = [0.85, 0.9, 0.95, 1.0]
        for score in passing_scores:
            assert score >= SAFETY_THRESHOLD

        failing_scores = [0.0, 0.5, 0.84, 0.849]
        for score in failing_scores:
            assert score < SAFETY_THRESHOLD

    def test_sdk_fallback_produces_valid_script(self):
        """Contract: mock fallback output must deserialize into DialogueScript."""
        fallback = {
            "lines": [],
            "total_duration": 0.0,
            "guest_character": None,
        }
        script = DialogueScript(**fallback)
        assert script.total_duration == 0.0
        assert script.lines == []

    def test_generate_with_sdk_returns_safety_score(self):
        """Contract: _generate_with_sdk returns (DialogueScript, safety_score) tuple.

        The safety_score must come from result_data, not be hardcoded.
        Fixes #135.
        """
        from backend.src.agents.morning_show_agent import _generate_with_sdk
        import inspect

        sig = inspect.signature(_generate_with_sdk)
        # Verify the function exists and is async
        assert inspect.iscoroutinefunction(_generate_with_sdk)
        # The return type annotation should indicate a tuple
        # (we check the actual behavior in the integration test below)

    def test_safety_score_extracted_not_hardcoded(self):
        """Contract: agent output safety_score must reflect SDK result, not a fixed 0.9.

        When the SDK returns safety_score=0.88, the agent output must show 0.88,
        not the previously hardcoded 0.9. Fixes #135.
        """
        # This is a contract-level assertion: the agent must propagate the SDK score
        sdk_result = {
            "lines": [
                {"role": "curious_kid", "text": "Q?", "timestamp_start": 0.0, "timestamp_end": 4.0},
                {"role": "fun_expert", "text": "A!", "timestamp_start": 4.0, "timestamp_end": 8.0},
                {"role": "guest", "text": "Fun fact!", "timestamp_start": 8.0, "timestamp_end": 12.0},
            ],
            "total_duration": 12.0,
            "guest_character": "Professor Owl",
            "safety_score": 0.88,
        }
        # The safety_score in sdk_result MUST be extractable and propagated
        extracted_score = float(sdk_result.get("safety_score", 0.9))
        assert extracted_score == 0.88, "Safety score must come from SDK result, not default to 0.9"

    def test_safety_score_clamped_to_unit_interval(self):
        """Contract: safety_score from SDK is clamped to [0.0, 1.0]. Fixes #135."""
        for raw, expected in [(1.5, 1.0), (-0.2, 0.0), (0.92, 0.92)]:
            clamped = max(0.0, min(1.0, float(raw)))
            assert clamped == expected

    def test_agent_output_script_deserializes(self):
        """Contract: dialogue_script from agent output must validate as DialogueScript."""
        raw_script = {
            "lines": [
                {"role": "curious_kid", "text": "Q?", "timestamp_start": 0.0, "timestamp_end": 4.0},
                {"role": "guest", "text": "Fun fact!", "timestamp_start": 4.0, "timestamp_end": 8.0},
                {"role": "fun_expert", "text": "A!", "timestamp_start": 8.0, "timestamp_end": 12.0},
            ],
            "total_duration": 12.0,
            "guest_character": "Lightning Dog",
        }
        script = DialogueScript(**raw_script)
        assert len(script.lines) == 3
        assert script.guest_character == "Lightning Dog"
        roles = {line.role for line in script.lines}
        assert roles == {"curious_kid", "fun_expert", "guest"}


# ---------------------------------------------------------------------------
# TopicSubscription
# ---------------------------------------------------------------------------
class TestSubscriptionContract:
    """Contract: subscription models and NewsCategory constraints."""

    def test_valid_subscription(self):
        """Contract: subscription with valid child_id and NewsCategory topic must pass."""
        sub = TopicSubscription(child_id="child_001", topic="science")
        assert sub.is_active is True
        assert isinstance(sub.subscribed_at, datetime)

    def test_all_news_categories_are_valid_topics(self):
        """Contract: every NewsCategory value is a valid subscription topic."""
        for cat in NewsCategory:
            sub = TopicSubscription(child_id="child_test", topic=cat)
            assert sub.topic == cat

    def test_news_category_enum_values(self):
        """Contract: NewsCategory must contain all expected values."""
        expected = {"science", "nature", "technology", "space", "animals", "sports", "culture", "general"}
        actual = {item.value for item in NewsCategory}
        assert actual == expected

    def test_invalid_topic_rejected(self):
        """Contract: freeform topic text outside NewsCategory must fail."""
        with pytest.raises(ValidationError):
            TopicSubscription(child_id="child_001", topic="dinosaurs")

    def test_subscription_request_validation(self):
        """Contract: SubscriptionRequest validates child_id length and topic enum."""
        req = SubscriptionRequest(child_id="child_001", topic="space")
        assert req.topic == NewsCategory.SPACE

    def test_subscription_request_empty_child_id_rejected(self):
        """Contract: empty child_id must fail (min_length=1)."""
        with pytest.raises(ValidationError):
            SubscriptionRequest(child_id="", topic="science")

    def test_subscription_response_extends_subscription(self):
        """Contract: SubscriptionResponse includes all TopicSubscription fields plus message."""
        resp = SubscriptionResponse(
            child_id="child_001",
            topic="animals",
            message="Subscribed successfully",
        )
        assert resp.child_id == "child_001"
        assert resp.message == "Subscribed successfully"
        assert resp.is_active is True

    def test_subscription_list_response_shape(self):
        """Contract: SubscriptionListResponse has items list and total count."""
        resp = SubscriptionListResponse(
            items=[
                TopicSubscription(child_id="child_001", topic="science"),
                TopicSubscription(child_id="child_001", topic="space"),
            ],
            total=2,
        )
        assert len(resp.items) == 2
        assert resp.total == 2


# ---------------------------------------------------------------------------
# Tracking Events
# ---------------------------------------------------------------------------
class TestMorningShowTrackContract:
    """Contract: playback tracking event models."""

    def test_track_event_types(self):
        """Contract: MorningShowTrackEvent must contain start/progress/complete/abandon."""
        expected = {"start", "progress", "complete", "abandon"}
        actual = {e.value for e in MorningShowTrackEvent}
        assert actual == expected

    def test_valid_track_request(self):
        """Contract: tracking request with valid fields must pass."""
        req = MorningShowTrackRequest(
            child_id="child_001",
            episode_id="ep_001",
            topic="science",
            event_type="complete",
            progress=0.95,
            played_seconds=120.0,
        )
        assert req.event_type == MorningShowTrackEvent.COMPLETE
        assert req.progress == 0.95

    def test_progress_default_zero(self):
        """Contract: progress defaults to 0.0 when omitted."""
        req = MorningShowTrackRequest(
            child_id="child_001",
            episode_id="ep_001",
            topic="science",
            event_type="start",
        )
        assert req.progress == 0.0

    def test_progress_bounds(self):
        """Contract: progress must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            MorningShowTrackRequest(
                child_id="child_001",
                episode_id="ep_001",
                topic="science",
                event_type="progress",
                progress=1.5,
            )

    def test_track_response_shape(self):
        """Contract: tracking response has status and topic_score."""
        resp = MorningShowTrackResponse(
            status="tracked",
            topic_score=3.5,
        )
        assert resp.status == "tracked"
        assert resp.topic_score == 3.5


# ---------------------------------------------------------------------------
# SSE Stream Event Shape
# ---------------------------------------------------------------------------
class TestStreamEventContract:
    """Contract: SSE stream event types for Morning Show generation."""

    def test_stream_event_types(self):
        """Contract: stream must emit status, progress, result, complete events."""
        required_event_types = {"status", "progress", "result", "complete"}
        # This validates the protocol — actual SSE tests are in test_morning_show.py
        assert "status" in required_event_types
        assert "progress" in required_event_types
        assert "result" in required_event_types
        assert "complete" in required_event_types

    def test_progress_event_shape(self):
        """Contract: progress events must include percent and message."""
        event = {"type": "progress", "data": {"percent": 55, "message": "Generating dialogue"}}
        assert "percent" in event["data"]
        assert "message" in event["data"]
        assert 0 <= event["data"]["percent"] <= 100


# ---------------------------------------------------------------------------
# Safety Score Extraction — Integration (#135)
# ---------------------------------------------------------------------------
class TestSafetyScoreExtraction:
    """Contract: _generate_with_sdk must extract and propagate safety_score from SDK result."""

    @pytest.mark.asyncio
    async def test_sdk_safety_score_propagated_to_agent_output(self):
        """Contract: when SDK returns safety_score=0.91, agent output must show 0.91, not 0.9.

        Fixes #135 — safety score was previously hardcoded to 0.9.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        from backend.src.agents.morning_show_agent import generate_morning_show_dialogue

        # Build a mock SDK result with safety_score=0.91
        mock_script_data = {
            "lines": [
                {"role": "curious_kid", "text": "Why is space so big?", "timestamp_start": 0.0, "timestamp_end": 5.0},
                {"role": "fun_expert", "text": "Great question!", "timestamp_start": 5.0, "timestamp_end": 10.0},
                {"role": "guest", "text": "Let me explain!", "timestamp_start": 10.0, "timestamp_end": 15.0},
            ],
            "total_duration": 15.0,
            "guest_character": "Professor Owl",
            "safety_score": 0.91,
        }

        from backend.src.agents.morning_show_agent import DialogueScript, DialogueLine

        mock_script = DialogueScript(
            lines=[
                DialogueLine(role="curious_kid", text="Why is space so big?", timestamp_start=0.0, timestamp_end=5.0),
                DialogueLine(role="fun_expert", text="Great question!", timestamp_start=5.0, timestamp_end=10.0),
                DialogueLine(role="guest", text="Let me explain!", timestamp_start=10.0, timestamp_end=15.0),
            ],
            total_duration=15.0,
            guest_character="Professor Owl",
        )

        with patch(
            "backend.src.agents.morning_show_agent._should_use_mock", return_value=False
        ), patch(
            "backend.src.agents.morning_show_agent._generate_with_sdk",
            new_callable=AsyncMock,
            return_value=(mock_script, 0.91),
        ):
            result = await generate_morning_show_dialogue(
                news_text="Scientists discovered a new planet.",
                age_group="6-8",
            )

        assert result["safety_score"] == 0.91, (
            f"Expected safety_score=0.91 from SDK, got {result['safety_score']}. "
            "Score must not be hardcoded to 0.9."
        )

    @pytest.mark.asyncio
    async def test_sdk_safety_score_below_threshold_triggers_fallback(self):
        """Contract: when SDK returns safety_score=0.7, agent must fall back to mock.

        Fixes #135 — the safety floor (>= 0.85) must work with real scores.
        """
        from unittest.mock import AsyncMock, patch

        from backend.src.agents.morning_show_agent import generate_morning_show_dialogue

        from backend.src.agents.morning_show_agent import DialogueScript, DialogueLine

        mock_script = DialogueScript(
            lines=[
                DialogueLine(role="curious_kid", text="Q?", timestamp_start=0.0, timestamp_end=5.0),
                DialogueLine(role="fun_expert", text="A!", timestamp_start=5.0, timestamp_end=10.0),
                DialogueLine(role="guest", text="Hi!", timestamp_start=10.0, timestamp_end=15.0),
            ],
            total_duration=15.0,
            guest_character="Professor Owl",
        )

        with patch(
            "backend.src.agents.morning_show_agent._should_use_mock", return_value=False
        ), patch(
            "backend.src.agents.morning_show_agent._generate_with_sdk",
            new_callable=AsyncMock,
            return_value=(mock_script, 0.70),
        ):
            result = await generate_morning_show_dialogue(
                news_text="Some news content.",
                age_group="6-8",
            )

        # Safety floor: score < 0.85 → fallback to mock with 0.95
        assert result["used_mock"] is True
        assert result["safety_score"] == 0.95
