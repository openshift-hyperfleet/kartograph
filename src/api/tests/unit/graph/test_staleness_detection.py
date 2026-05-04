"""Unit tests for staleness-based node lifecycle detection.

Tests the domain logic for determining whether graph nodes are stale
based on timestamp comparison.

Spec coverage:
- Requirement: Staleness-Based Node Lifecycle
- Scenario: Stale node detection
- Scenario: Active node
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


from graph.domain.value_objects import (
    NODE_AUTO_TIMESTAMP_PROPERTIES,
    is_node_stale,
)


class TestStalenessDetection:
    """Tests for is_node_stale() domain function.

    Spec: GIVEN a node with last_synced_at older than data source's last_sync_at,
    THEN the node is considered stale.
    """

    def test_stale_node_when_last_synced_at_is_older(self):
        """Node is stale if last_synced_at < data_source last_sync_at."""
        data_source_last_sync_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
        node_last_synced_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)  # 1 day older

        assert is_node_stale(node_last_synced_at, data_source_last_sync_at) is True

    def test_active_node_when_last_synced_at_matches(self):
        """Node is active if last_synced_at equals data_source last_sync_at."""
        sync_time = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)

        assert is_node_stale(sync_time, sync_time) is False

    def test_active_node_when_last_synced_at_is_newer(self):
        """Node is active if last_synced_at > data_source last_sync_at.

        This should not normally occur in practice, but the comparison
        should handle it gracefully — the node is NOT stale.
        """
        data_source_last_sync_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        node_last_synced_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)  # 1 day newer

        assert is_node_stale(node_last_synced_at, data_source_last_sync_at) is False

    def test_stale_node_just_before_sync_time(self):
        """Node is stale if last_synced_at is even 1 microsecond older."""
        data_source_last_sync_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
        node_last_synced_at = data_source_last_sync_at - timedelta(microseconds=1)

        assert is_node_stale(node_last_synced_at, data_source_last_sync_at) is True

    def test_stale_node_from_previous_week(self):
        """Node from a week-old sync is stale relative to today's sync."""
        today_sync = datetime(2024, 2, 1, 10, 0, 0, tzinfo=UTC)
        last_week_sync = datetime(2024, 1, 25, 10, 0, 0, tzinfo=UTC)

        assert is_node_stale(last_week_sync, today_sync) is True


class TestNodeAutoTimestampProperties:
    """Tests that last_synced_at is declared as an auto-managed node property.

    Spec: the staleness mechanism relies on last_synced_at being automatically
    stamped on all graph nodes by the graph layer when mutations are applied.
    It is NOT required in MutationLog CREATE operations (it's auto-set).
    """

    def test_last_synced_at_in_node_auto_timestamp_properties(self):
        """last_synced_at must be declared as an auto-set timestamp property."""
        assert "last_synced_at" in NODE_AUTO_TIMESTAMP_PROPERTIES
