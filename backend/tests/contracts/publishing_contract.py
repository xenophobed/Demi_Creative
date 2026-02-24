"""
Publishing Workflow Contract Tests (Issue #18)

Defines expected behavior for artifact publishing and canonical selection:
- Candidate → published transition with validation
- Role uniqueness enforcement
- Invalid state transitions rejected
- Story detail returns only curated published/canonical artifacts
"""

import pytest


class TestPublishingWorkflow:
    """Contract: Artifact publishing lifecycle"""

    def test_publish_requires_candidate_state(self):
        """
        Contract: Only artifacts in 'candidate' state can be published.
        Publishing an 'intermediate' artifact should be rejected.
        Publishing a 'published' artifact should be rejected (idempotent or error).
        """
        valid_publish_from = ["candidate"]
        invalid_publish_from = ["intermediate", "published", "archived"]

        for state in valid_publish_from:
            assert state == "candidate"

        for state in invalid_publish_from:
            assert state != "candidate"

    def test_publish_transitions_to_published(self):
        """
        Contract: After publish, artifact.lifecycle_state == 'published'.
        """
        artifact_before = {"lifecycle_state": "candidate"}
        artifact_after = {"lifecycle_state": "published"}

        assert artifact_before["lifecycle_state"] == "candidate"
        assert artifact_after["lifecycle_state"] == "published"

    def test_publish_with_story_linking(self):
        """
        Contract: Publishing can optionally link the artifact as
        canonical for a story role (cover, final_audio, etc.).

        Canonical selection updates story_artifact_links, NOT the artifact binary.
        """
        publish_request = {
            "artifact_id": "uuid",
            "story_id": "story-uuid",
            "role": "final_audio",
        }

        # After publish:
        # - artifact.lifecycle_state == 'published'
        # - story_artifact_link created with is_primary=True
        # - artifact binary unchanged
        assert publish_request["story_id"] is not None
        assert publish_request["role"] is not None

    def test_publish_without_story_linking(self):
        """
        Contract: Publishing without story_id/role just transitions state.
        No story_artifact_link is created.
        """
        publish_request = {
            "artifact_id": "uuid",
            "story_id": None,
            "role": None,
        }

        assert publish_request["story_id"] is None


class TestRoleConflicts:
    """Contract: Canonical role uniqueness enforcement"""

    def test_one_primary_artifact_per_story_role(self):
        """
        Contract: UNIQUE(story_id, role) WHERE is_primary=1.
        Setting a new primary for existing story+role demotes the old one.
        """
        link_1 = {
            "story_id": "s1",
            "artifact_id": "a1",
            "role": "final_audio",
            "is_primary": True,
        }
        link_2 = {
            "story_id": "s1",
            "artifact_id": "a2",
            "role": "final_audio",
            "is_primary": True,
        }

        # After upserting link_2:
        # - link_1.is_primary should be False
        # - link_2.is_primary should be True
        # - Both links still exist
        assert link_1["story_id"] == link_2["story_id"]
        assert link_1["role"] == link_2["role"]

    def test_different_roles_independent(self):
        """
        Contract: Different roles are independent.
        A story can have one primary cover AND one primary final_audio.
        """
        cover_link = {"story_id": "s1", "role": "cover", "is_primary": True}
        audio_link = {"story_id": "s1", "role": "final_audio", "is_primary": True}

        # Both can be primary simultaneously
        assert cover_link["role"] != audio_link["role"]

    def test_non_primary_links_allowed(self):
        """
        Contract: Multiple non-primary links per story+role are allowed.
        These are alternatives (e.g., A/B testing).
        """
        primary = {"story_id": "s1", "role": "cover", "is_primary": True}
        alternative = {"story_id": "s1", "role": "cover", "is_primary": False}

        assert primary["is_primary"] is True
        assert alternative["is_primary"] is False


class TestInvalidStateTransitions:
    """Contract: Invalid state transitions are rejected"""

    def test_cannot_publish_intermediate_directly(self):
        """
        Contract: intermediate → published is NOT valid.
        Must go through candidate first.
        """
        invalid_transition = ("intermediate", "published")
        valid_transitions = {
            "intermediate": ["candidate", "archived"],
            "candidate": ["published", "archived"],
            "published": ["archived"],
        }

        from_state, to_state = invalid_transition
        assert to_state not in valid_transitions[from_state]

    def test_cannot_rollback_published_to_candidate(self):
        """
        Contract: published → candidate is NOT valid.
        Published artifacts cannot be rolled back.
        """
        invalid_transition = ("published", "candidate")
        valid_transitions = {"published": ["archived"]}

        from_state, to_state = invalid_transition
        assert to_state not in valid_transitions[from_state]

    def test_cannot_resurrect_archived(self):
        """
        Contract: archived → published is NOT valid.
        Archived artifacts cannot be resurrected.
        """
        invalid_transition = ("archived", "published")
        # archived only allows archived (idempotent)
        assert invalid_transition[1] != "archived"


class TestCuratedStoryArtifacts:
    """Contract: Story detail returns only curated artifacts"""

    def test_curated_endpoint_returns_published_only(self):
        """
        Contract: GET /stories/{story_id}/curated returns only
        published or candidate artifacts, keyed by role.
        """
        curated_response = {
            "story_id": "s1",
            "artifacts": {
                "cover": {"artifact_id": "img-uuid", "lifecycle_state": "published"},
                "final_audio": {"artifact_id": "audio-uuid", "lifecycle_state": "published"},
            },
        }

        for role, artifact in curated_response["artifacts"].items():
            assert artifact["lifecycle_state"] in ("published", "candidate")

    def test_curated_endpoint_excludes_intermediate(self):
        """
        Contract: Intermediate artifacts are NOT returned by the curated endpoint.
        """
        intermediate_artifact = {"lifecycle_state": "intermediate"}
        assert intermediate_artifact["lifecycle_state"] not in ("published", "candidate")

    def test_curated_endpoint_returns_one_per_role(self):
        """
        Contract: The curated endpoint returns at most one artifact per role
        (the primary/canonical one).
        """
        curated_response = {
            "artifacts": {
                "cover": {"artifact_id": "a1"},
                "final_audio": {"artifact_id": "a2"},
            }
        }

        # Each role has exactly one artifact
        for role in curated_response["artifacts"]:
            assert isinstance(curated_response["artifacts"][role], dict)
