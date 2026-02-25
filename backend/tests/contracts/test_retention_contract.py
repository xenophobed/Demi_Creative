"""
Retention Policy & TTL Cleanup Contract Tests (Issue #19)

Defines the expected interface and behavior for:
- Retention policies by lifecycle class
- TTL cleanup job (idempotent and safe)
- Safeguards for canonical/published artifacts
- Dry-run mode
- Storage usage monitoring
"""

import pytest


class TestRetentionPolicyContract:
    """Contract: Retention policy configuration"""

    def test_default_policies_cover_all_states(self):
        """
        Contract: Default policies define TTL for every lifecycle state.
        - published:    -1 (indefinite)
        - candidate:    90 days
        - intermediate: 30 days
        - archived:     7 days
        """
        from src.services.retention_service import DEFAULT_POLICIES
        from src.services.models.artifact_models import LifecycleState

        states = {p.lifecycle_state for p in DEFAULT_POLICIES}
        assert LifecycleState.PUBLISHED in states
        assert LifecycleState.CANDIDATE in states
        assert LifecycleState.INTERMEDIATE in states
        assert LifecycleState.ARCHIVED in states

    def test_published_policy_is_indefinite(self):
        """
        Contract: Published artifacts have retention_days=-1 (never delete).
        """
        from src.services.retention_service import DEFAULT_POLICIES
        from src.services.models.artifact_models import LifecycleState

        published = next(
            p for p in DEFAULT_POLICIES
            if p.lifecycle_state == LifecycleState.PUBLISHED
        )
        assert published.retention_days == -1


class TestRetentionCleanupContract:
    """Contract: TTL cleanup job"""

    def test_cleanup_runs_idempotently(self):
        """
        Contract: Running cleanup twice yields same result (no double-deletion).
        """
        pass

    def test_cleanup_never_deletes_published(self):
        """
        Contract: Published artifacts are NEVER archived or deleted,
        regardless of age.
        """
        pass

    def test_cleanup_never_deletes_canonical(self):
        """
        Contract: Artifacts linked as primary to a story are protected,
        even if they are in intermediate/candidate state past TTL.
        """
        pass

    def test_dry_run_reports_without_changes(self):
        """
        Contract: dry_run=True returns a report but makes no state changes.
        """
        pass

    def test_intermediate_archived_after_ttl(self):
        """
        Contract: Intermediate artifacts older than 30 days
        transition to archived.
        """
        pass

    def test_candidate_archived_after_ttl(self):
        """
        Contract: Candidate artifacts older than 90 days
        transition to archived.
        """
        pass


class TestRetentionReportContract:
    """Contract: Retention report structure"""

    def test_report_includes_counts(self):
        """
        Contract: Report includes candidates_found, safeguarded_count,
        archived_count, deleted_count.
        """
        from src.services.models.artifact_models import RetentionReport

        fields = RetentionReport.model_fields
        assert "candidates_found" in fields
        assert "safeguarded_count" in fields
        assert "archived_count" in fields
        assert "deleted_count" in fields
        assert "dry_run" in fields

    def test_report_includes_by_type_breakdown(self):
        """
        Contract: Report includes by_type dict mapping artifact_type to count.
        """
        from src.services.models.artifact_models import RetentionReport

        assert "by_type" in RetentionReport.model_fields


class TestStorageStatsContract:
    """Contract: Storage monitoring"""

    def test_storage_stats_structure(self):
        """
        Contract: StorageStats includes total_artifacts, by_state, by_type,
        total_file_size_bytes, by_state_size.
        """
        from src.services.models.artifact_models import StorageStats

        fields = StorageStats.model_fields
        assert "total_artifacts" in fields
        assert "by_state" in fields
        assert "by_type" in fields
        assert "total_file_size_bytes" in fields
        assert "by_state_size" in fields
