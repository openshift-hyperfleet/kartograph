"""Unit tests for ingestion domain events.

Tests verify all lifecycle events (JobPackageProduced, IngestionFailed)
are immutable, carry correct fields, and are structurally sound.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ingestion.domain.events.sync import IngestionFailed, JobPackageProduced


class TestJobPackageProduced:
    """Tests for the JobPackageProduced domain event."""

    def test_is_immutable(self):
        """JobPackageProduced should be a frozen dataclass (immutable)."""
        event = JobPackageProduced(
            sync_run_id="run-001",
            data_source_id="ds-001",
            knowledge_graph_id="kg-001",
            job_package_id="pkg-001",
            occurred_at=datetime.now(UTC),
        )
        with pytest.raises(Exception):
            event.sync_run_id = "mutated"  # type: ignore[misc]

    def test_has_required_fields(self):
        """JobPackageProduced should have all required lifecycle fields."""
        occurred = datetime.now(UTC)
        event = JobPackageProduced(
            sync_run_id="run-001",
            data_source_id="ds-001",
            knowledge_graph_id="kg-001",
            job_package_id="pkg-001",
            occurred_at=occurred,
        )
        assert event.sync_run_id == "run-001"
        assert event.data_source_id == "ds-001"
        assert event.knowledge_graph_id == "kg-001"
        assert event.job_package_id == "pkg-001"
        assert event.occurred_at == occurred


class TestIngestionFailed:
    """Tests for the IngestionFailed domain event."""

    def test_is_immutable(self):
        """IngestionFailed should be a frozen dataclass (immutable)."""
        event = IngestionFailed(
            sync_run_id="run-001",
            data_source_id="ds-001",
            error="credentials expired",
            occurred_at=datetime.now(UTC),
        )
        with pytest.raises(Exception):
            event.error = "mutated"  # type: ignore[misc]

    def test_has_required_fields(self):
        """IngestionFailed should carry sync_run_id, data_source_id, and error."""
        occurred = datetime.now(UTC)
        event = IngestionFailed(
            sync_run_id="run-001",
            data_source_id="ds-001",
            error="source unreachable: timeout after 30s",
            occurred_at=occurred,
        )
        assert event.sync_run_id == "run-001"
        assert event.data_source_id == "ds-001"
        assert event.error == "source unreachable: timeout after 30s"
        assert event.occurred_at == occurred
