"""
On-Demand Kids Daily Generation Contract Tests (#311)

Validates Pydantic model constraints and output shapes for:
- KidsDailyOnDemandRequest required fields
- KidsDailyGenerationMetadata provenance tracking (safety_score, generation_id, is_degraded)
- KidsDailyResponse structure consistency between Daily Drop and on-demand
"""

import pytest
from pydantic import ValidationError

from backend.src.api.models import (
    AgeGroup,
    KidsDailyGenerationMetadata,
    KidsDailyOnDemandRequest,
    KidsDailyResponse,
    KidsDailyEpisode,
    DialogueScript,
    DialogueLine,
    NewsCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_episode(**overrides) -> KidsDailyEpisode:
    """Build a minimal valid KidsDailyEpisode for contract assertions."""
    defaults = dict(
        episode_id="ep-001",
        child_id="child-1",
        age_group=AgeGroup.AGE_6_8,
        category=NewsCategory.SCIENCE,
        kid_title="Test Episode",
        kid_content="Some educational content.",
        why_care="It helps us learn.",
        dialogue_script=DialogueScript(
            lines=[
                DialogueLine(
                    role="curious_kid",
                    text="Why?",
                    timestamp_start=0.0,
                    timestamp_end=3.0,
                ),
                DialogueLine(
                    role="fun_expert",
                    text="Because science!",
                    timestamp_start=3.0,
                    timestamp_end=6.0,
                ),
            ],
            total_duration=6.0,
        ),
    )
    defaults.update(overrides)
    return KidsDailyEpisode(**defaults)


def _make_metadata(**overrides) -> KidsDailyGenerationMetadata:
    """Build a minimal valid KidsDailyGenerationMetadata."""
    defaults = dict(
        generation_id="gen-001",
        safety_score=0.92,
        used_mock=False,
        is_degraded=False,
    )
    defaults.update(overrides)
    return KidsDailyGenerationMetadata(**defaults)


# ---------------------------------------------------------------------------
# KidsDailyOnDemandRequest — required fields
# ---------------------------------------------------------------------------
class TestOnDemandRequestContract:
    """Contract: KidsDailyOnDemandRequest must enforce required fields."""

    def test_valid_request(self):
        """Contract: a request with child_id, category, and age_group must pass."""
        req = KidsDailyOnDemandRequest(
            child_id="child-abc",
            category=NewsCategory.SCIENCE,
            age_group=AgeGroup.AGE_6_8,
        )
        assert req.child_id == "child-abc"
        assert req.category == NewsCategory.SCIENCE
        assert req.age_group == AgeGroup.AGE_6_8

    def test_missing_child_id_rejected(self):
        """Contract: child_id is required."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                category=NewsCategory.SCIENCE,
                age_group=AgeGroup.AGE_6_8,
            )

    def test_empty_child_id_rejected(self):
        """Contract: child_id must have min_length=1."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                child_id="",
                category=NewsCategory.SCIENCE,
                age_group=AgeGroup.AGE_6_8,
            )

    def test_missing_age_group_rejected(self):
        """Contract: age_group is required."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                child_id="child-1",
                category=NewsCategory.SCIENCE,
            )

    def test_invalid_age_group_rejected(self):
        """Contract: age_group must be a valid AgeGroup enum value."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                child_id="child-1",
                category=NewsCategory.SCIENCE,
                age_group="13-15",
            )

    def test_category_defaults_to_general(self):
        """Contract: category defaults to GENERAL when omitted."""
        req = KidsDailyOnDemandRequest(
            child_id="child-1",
            age_group=AgeGroup.AGE_3_5,
        )
        assert req.category == NewsCategory.GENERAL

    def test_invalid_category_rejected(self):
        """Contract: an unknown category must fail validation."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                child_id="child-1",
                category="cooking",
                age_group=AgeGroup.AGE_6_8,
            )

    def test_child_id_max_length(self):
        """Contract: child_id must be at most 100 characters."""
        with pytest.raises(ValidationError):
            KidsDailyOnDemandRequest(
                child_id="x" * 101,
                category=NewsCategory.SCIENCE,
                age_group=AgeGroup.AGE_6_8,
            )


# ---------------------------------------------------------------------------
# KidsDailyGenerationMetadata — provenance tracking
# ---------------------------------------------------------------------------
class TestOnDemandMetadataContract:
    """Contract: on-demand output includes provenance fields matching Daily Drop."""

    def test_metadata_has_safety_score(self):
        """Contract: safety_score must exist and be within [0.0, 1.0]."""
        meta = _make_metadata(safety_score=0.95)
        assert hasattr(meta, "safety_score")
        assert 0.0 <= meta.safety_score <= 1.0

    def test_metadata_has_generation_id(self):
        """Contract: generation_id must be a non-empty string for traceability."""
        meta = _make_metadata(generation_id="gen-42")
        assert meta.generation_id == "gen-42"

    def test_metadata_has_is_degraded(self):
        """Contract: is_degraded must exist (matches Daily Drop provenance)."""
        meta = _make_metadata(is_degraded=True, degraded_reason="agent_fallback")
        assert meta.is_degraded is True
        assert meta.degraded_reason == "agent_fallback"

    def test_metadata_safety_score_below_zero_rejected(self):
        """Contract: safety_score < 0 must fail validation."""
        with pytest.raises(ValidationError):
            _make_metadata(safety_score=-0.1)

    def test_metadata_safety_score_above_one_rejected(self):
        """Contract: safety_score > 1 must fail validation."""
        with pytest.raises(ValidationError):
            _make_metadata(safety_score=1.5)

    def test_metadata_used_mock_defaults_false(self):
        """Contract: used_mock defaults to False."""
        meta = KidsDailyGenerationMetadata(
            generation_id="gen-x",
            safety_score=0.9,
        )
        assert meta.used_mock is False

    def test_metadata_is_degraded_defaults_false(self):
        """Contract: is_degraded defaults to False."""
        meta = KidsDailyGenerationMetadata(
            generation_id="gen-x",
            safety_score=0.9,
        )
        assert meta.is_degraded is False


# ---------------------------------------------------------------------------
# KidsDailyResponse — same shape for Daily Drop and on-demand
# ---------------------------------------------------------------------------
class TestOnDemandResponseContract:
    """Contract: KidsDailyResponse carries episode + metadata consistently."""

    def test_response_contains_episode_and_metadata(self):
        """Contract: response must have both episode and metadata fields."""
        resp = KidsDailyResponse(
            episode=_make_episode(),
            metadata=_make_metadata(),
        )
        assert resp.episode.episode_id == "ep-001"
        assert resp.metadata.generation_id == "gen-001"

    def test_response_safety_score_in_metadata(self):
        """Contract: safety_score lives in metadata, not directly on the response."""
        resp = KidsDailyResponse(
            episode=_make_episode(),
            metadata=_make_metadata(safety_score=0.88),
        )
        assert resp.metadata.safety_score == 0.88

    def test_response_provenance_fields_present(self):
        """Contract: generation_id and is_degraded exist in metadata for tracing."""
        resp = KidsDailyResponse(
            episode=_make_episode(is_degraded=True, degraded_reason="timeout"),
            metadata=_make_metadata(is_degraded=True, degraded_reason="timeout"),
        )
        assert resp.metadata.generation_id is not None
        assert resp.metadata.is_degraded is True
        assert resp.episode.is_degraded is True

    def test_episode_story_type_is_kids_daily(self):
        """Contract: episode.story_type must always be 'kids_daily'."""
        ep = _make_episode()
        assert ep.story_type == "kids_daily"
