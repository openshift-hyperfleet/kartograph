"""Unit tests for AgeBulkLoadingStrategy._execute_deletes.

Tests that _execute_deletes iterates per-ID, calling the query builder
once per ID rather than batching all IDs into a single call.
"""

from unittest.mock import MagicMock, patch

import pytest

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.age_bulk_loading.strategy import AgeBulkLoadingStrategy


@pytest.fixture
def strategy():
    """Create an AgeBulkLoadingStrategy with mocked dependencies."""
    return AgeBulkLoadingStrategy()


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    return MagicMock()


@pytest.fixture
def mock_probe():
    """Create a mock MutationProbe."""
    return MagicMock()


def _make_delete_op(entity_type: EntityType, entity_id: str) -> MutationOperation:
    """Helper to create a DELETE MutationOperation."""
    return MutationOperation(
        op=MutationOperationType.DELETE,
        type=entity_type,
        id=entity_id,
    )


class TestExecuteDeletesIteratesPerID:
    """Tests that _execute_deletes calls query builder once per ID."""

    def test_calls_delete_node_once_per_id(self, strategy, mock_cursor, mock_probe):
        """Should call delete_node_with_detach once for each node ID."""
        ops = [
            _make_delete_op(EntityType.NODE, "person:abc123def456789a"),
            _make_delete_op(EntityType.NODE, "person:def456789abc1230"),
            _make_delete_op(EntityType.NODE, "person:789abc123def4560"),
        ]

        with patch.object(
            strategy._queries,
            "delete_node_with_detach",
            return_value=1,
        ) as mock_delete:
            strategy._execute_deletes(
                mock_cursor, ops, EntityType.NODE, mock_probe, "test_graph"
            )

            assert mock_delete.call_count == 3, (
                "Should call delete_node_with_detach once per ID"
            )

            # Verify each call received a single ID string, not a list
            for c in mock_delete.call_args_list:
                args = c[0]
                # args should be (cursor, graph_name, id)
                assert isinstance(args[2], str), (
                    f"Third argument should be a single ID string, got {type(args[2])}"
                )

    def test_calls_delete_edge_once_per_id(self, strategy, mock_cursor, mock_probe):
        """Should call delete_edge once for each edge ID."""
        ops = [
            _make_delete_op(EntityType.EDGE, "knows:abc123def456789a"),
            _make_delete_op(EntityType.EDGE, "knows:def456789abc1230"),
        ]

        with patch.object(
            strategy._queries,
            "delete_edge",
            return_value=1,
        ) as mock_delete:
            strategy._execute_deletes(
                mock_cursor, ops, EntityType.EDGE, mock_probe, "test_graph"
            )

            assert mock_delete.call_count == 2, "Should call delete_edge once per ID"

    def test_emits_probe_event_per_id(self, strategy, mock_cursor, mock_probe):
        """Should emit a probe batch_applied event for each ID."""
        ops = [
            _make_delete_op(EntityType.NODE, "person:abc123def456789a"),
            _make_delete_op(EntityType.NODE, "person:def456789abc1230"),
        ]

        with patch.object(
            strategy._queries,
            "delete_node_with_detach",
            return_value=1,
        ):
            strategy._execute_deletes(
                mock_cursor, ops, EntityType.NODE, mock_probe, "test_graph"
            )

            assert mock_probe.batch_applied.call_count == 2, (
                "Should emit probe event for each ID"
            )

    def test_returns_correct_batch_count(self, strategy, mock_cursor, mock_probe):
        """Should return the total number of IDs processed."""
        ops = [
            _make_delete_op(EntityType.NODE, "person:abc123def456789a"),
            _make_delete_op(EntityType.NODE, "person:def456789abc1230"),
            _make_delete_op(EntityType.NODE, "person:789abc123def4560"),
        ]

        with patch.object(
            strategy._queries,
            "delete_node_with_detach",
            return_value=1,
        ):
            batches = strategy._execute_deletes(
                mock_cursor, ops, EntityType.NODE, mock_probe, "test_graph"
            )

            assert batches == 3

    def test_handles_empty_operations(self, strategy, mock_cursor, mock_probe):
        """Should handle empty operations list gracefully."""
        batches = strategy._execute_deletes(
            mock_cursor, [], EntityType.NODE, mock_probe, "test_graph"
        )
        assert batches == 0

    def test_raises_on_missing_id(self, strategy, mock_cursor, mock_probe):
        """Should raise ValueError when an operation has no ID."""
        # MutationOperation with op=DELETE requires id, but we test the
        # strategy's own validation
        op = MutationOperation(
            op=MutationOperationType.DELETE,
            type=EntityType.NODE,
            id=None,
        )

        with pytest.raises(ValueError, match="missing an ID"):
            strategy._execute_deletes(
                mock_cursor, [op], EntityType.NODE, mock_probe, "test_graph"
            )

    def test_no_batch_grouping_for_nodes(self, strategy, mock_cursor, mock_probe):
        """Should NOT group IDs into batches — each ID is processed individually."""
        ops = [_make_delete_op(EntityType.NODE, f"person:{i:016x}") for i in range(5)]

        with patch.object(
            strategy._queries,
            "delete_node_with_detach",
            return_value=1,
        ) as mock_delete:
            strategy._execute_deletes(
                mock_cursor, ops, EntityType.NODE, mock_probe, "test_graph"
            )

            # Each call should receive the cursor, graph_name, and a SINGLE id
            assert mock_delete.call_count == 5
            for c in mock_delete.call_args_list:
                id_arg = c[0][2]
                assert isinstance(id_arg, str), (
                    "Each call should receive a single string ID"
                )
