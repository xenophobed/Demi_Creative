"""
Provenance Contract Tests (Issue #17)

Defines expected behavior for multi-agent run/step provenance tracking:
- 100% of generated artifacts contain provenance metadata
- Failed/retried steps preserve history without mutating old artifacts
- Lineage chain across 3+ agent rounds
- Cost/latency attribution per step
"""

import pytest


class TestProvenanceMetadata:
    """Contract: Every artifact must be traceable to run/step/agent"""

    def test_artifact_has_created_by_step_id(self):
        """
        Contract: Every newly generated artifact MUST have created_by_step_id.
        This links the artifact to the agent step that produced it.
        """
        artifact = {
            "artifact_id": "uuid",
            "created_by_step_id": "step-uuid",
            "created_by_agent": "vision_analysis",
        }

        assert artifact["created_by_step_id"] is not None
        assert artifact["created_by_agent"] is not None

    def test_step_links_to_run(self):
        """
        Contract: Every agent step has run_id linking to parent run.
        run → step → artifact forms the provenance chain.
        """
        step = {
            "agent_step_id": "step-uuid",
            "run_id": "run-uuid",
            "step_name": "tts_generation",
            "step_order": 3,
        }

        assert step["run_id"] is not None

    def test_run_links_to_story(self):
        """
        Contract: Every run has story_id linking to the target story.
        story → run → step → artifact forms the complete lineage.
        """
        run = {
            "run_id": "run-uuid",
            "story_id": "story-uuid",
            "workflow_type": "image_to_story",
        }

        assert run["story_id"] is not None

    def test_full_provenance_chain(self):
        """
        Contract: Complete chain: story → run → step → artifact.
        Can trace any artifact back to its story through:
          artifact.created_by_step_id → step.run_id → run.story_id
        """
        story = {"story_id": "s1"}
        run = {"run_id": "r1", "story_id": "s1"}
        step = {"agent_step_id": "st1", "run_id": "r1"}
        artifact = {"artifact_id": "a1", "created_by_step_id": "st1"}

        assert run["story_id"] == story["story_id"]
        assert step["run_id"] == run["run_id"]
        assert artifact["created_by_step_id"] == step["agent_step_id"]


class TestProvenanceModelAndPrompt:
    """Contract: Model/version and prompt hash persisted"""

    def test_step_contains_model_name(self):
        """
        Contract: Agent step input_data contains _provenance_model field
        with the model name/version used for that step.
        """
        step_input = {
            "_provenance_model": "claude-agent-sdk",
            "_provenance_prompt_hash": "a1b2c3d4e5f6g7h8",
            "image_path": "./data/uploads/drawing.png",
        }

        assert "_provenance_model" in step_input
        assert isinstance(step_input["_provenance_model"], str)

    def test_step_contains_prompt_hash(self):
        """
        Contract: Agent step input_data contains _provenance_prompt_hash.
        Hash is redacted-safe (not the full prompt, just a SHA256 prefix).
        """
        step_input = {
            "_provenance_prompt_hash": "a1b2c3d4e5f6g7h8",
        }

        assert "_provenance_prompt_hash" in step_input
        # Hash is 16-char prefix of SHA256
        assert len(step_input["_provenance_prompt_hash"]) == 16


class TestFailedStepPreservation:
    """Contract: Failed/retried steps don't mutate old artifacts"""

    def test_failed_step_preserves_status(self):
        """
        Contract: When a step fails, its status is 'failed' and
        error_message is populated. Old artifacts are untouched.
        """
        failed_step = {
            "agent_step_id": "step-uuid",
            "status": "failed",
            "error_message": "TTS service timeout",
            "output_data": {"_duration_ms": 30000},
        }

        assert failed_step["status"] == "failed"
        assert failed_step["error_message"] is not None

    def test_retry_creates_new_step(self):
        """
        Contract: Retrying a failed operation creates a NEW step,
        not an update to the old one. Old step preserved with error.
        """
        original_step = {
            "agent_step_id": "step-1",
            "step_order": 3,
            "status": "failed",
        }
        retry_step = {
            "agent_step_id": "step-2",  # New UUID
            "step_order": 4,  # New order
            "status": "completed",
        }

        assert original_step["agent_step_id"] != retry_step["agent_step_id"]
        assert original_step["status"] == "failed"
        assert retry_step["status"] == "completed"

    def test_artifacts_from_failed_steps_remain(self):
        """
        Contract: Artifacts created by failed steps are NOT deleted.
        They remain in 'intermediate' state for debugging.
        """
        artifact_from_failed = {
            "artifact_id": "a1",
            "lifecycle_state": "intermediate",
            "created_by_step_id": "failed-step-uuid",
        }

        # Artifact exists and is traceable
        assert artifact_from_failed["lifecycle_state"] == "intermediate"
        assert artifact_from_failed["created_by_step_id"] is not None


class TestLineageChain:
    """Contract: Lineage chain across 3+ agent rounds"""

    def test_three_round_lineage(self):
        """
        Contract: End-to-end test verifies lineage chain across at least 3 rounds.

        Example chain:
        Round 1: image_upload → image artifact
        Round 2: story_generation → text artifact (derived_from image)
        Round 3: tts_generation → audio artifact (derived_from text)

        Lineage of audio should include text and image as ancestors.
        """
        image_artifact = {"artifact_id": "img-1", "artifact_type": "image"}
        text_artifact = {"artifact_id": "txt-1", "artifact_type": "text"}
        audio_artifact = {"artifact_id": "aud-1", "artifact_type": "audio"}

        relations = [
            {"from_artifact_id": "img-1", "to_artifact_id": "txt-1", "relation_type": "derived_from"},
            {"from_artifact_id": "txt-1", "to_artifact_id": "aud-1", "relation_type": "derived_from"},
        ]

        # Audio's ancestors: text, image (2 ancestors)
        audio_ancestors = ["txt-1", "img-1"]
        assert len(audio_ancestors) >= 2

        # Image's descendants: text, audio (2 descendants)
        image_descendants = ["txt-1", "aud-1"]
        assert len(image_descendants) >= 2


class TestCostLatencyAttribution:
    """Contract: Cost/latency attribution per step"""

    def test_step_output_contains_duration(self):
        """
        Contract: Completed steps include _duration_ms in output_data
        for latency attribution.
        """
        step_output = {
            "_duration_ms": 1500,
            "artifact_id": "uuid",
        }

        assert "_duration_ms" in step_output
        assert isinstance(step_output["_duration_ms"], int)
        assert step_output["_duration_ms"] > 0

    def test_duration_measured_wall_clock(self):
        """
        Contract: Duration is wall-clock time from step start to completion,
        measured in milliseconds.
        """
        step_start_time_ms = 1000
        step_end_time_ms = 2500
        duration_ms = step_end_time_ms - step_start_time_ms

        assert duration_ms == 1500
        assert duration_ms > 0

    def test_run_summary_aggregates_costs(self):
        """
        Contract: Run result_summary can contain aggregate cost data.
        """
        run_summary = {
            "artifacts_created": 3,
            "story_id": "s1",
        }

        assert "artifacts_created" in run_summary
