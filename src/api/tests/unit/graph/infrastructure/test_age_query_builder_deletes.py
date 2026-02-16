"""Unit tests for AgeQueryBuilder delete operations.

Tests that delete_node_with_detach and delete_edge use scalar = %s
subqueries instead of batch = ANY(%s) to avoid catastrophic query
plans in AGE with large graphs.
"""

from unittest.mock import MagicMock

import pytest

from graph.infrastructure.age_bulk_loading.queries import AgeQueryBuilder


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = MagicMock()
    cursor.rowcount = 1
    return cursor


class TestDeleteNodeWithDetach:
    """Tests for delete_node_with_detach (single-ID scalar subquery)."""

    def test_generates_scalar_subquery_not_any(self, mock_cursor):
        """Should use scalar = %s, not = ANY(%s), for edge deletion subquery."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )

        # Inspect the SQL from the first execute call (edge deletion)
        edge_delete_sql = str(mock_cursor.execute.call_args_list[0][0][0])

        assert "= ANY" not in edge_delete_sql, (
            "Should not use = ANY(%s) pattern — causes catastrophic query plans"
        )
        assert (
            "= %s" in edge_delete_sql
            or "= %(s)s" in edge_delete_sql
            or edge_delete_sql.count("%s") >= 1
        ), "Should use scalar = %s comparison"

    def test_generates_scalar_subquery_for_node_deletion(self, mock_cursor):
        """Should use scalar = %s for the node deletion query too."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )

        # Inspect the SQL from the second execute call (node deletion)
        node_delete_sql = str(mock_cursor.execute.call_args_list[1][0][0])

        assert "= ANY" not in node_delete_sql, "Node deletion should not use = ANY(%s)"

    def test_passes_single_id_as_parameter(self, mock_cursor):
        """Should pass the single ID string as a query parameter, not a list."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )

        # Edge deletion params — should contain the ID string, not a list
        edge_params = mock_cursor.execute.call_args_list[0][0][1]
        for param in edge_params:
            assert not isinstance(param, list), (
                f"Parameters should be scalar strings, not lists: {edge_params}"
            )

        # Node deletion params
        node_params = mock_cursor.execute.call_args_list[1][0][1]
        for param in node_params:
            assert not isinstance(param, list), (
                f"Parameters should be scalar strings, not lists: {node_params}"
            )

    def test_edge_deletion_references_start_and_end_id(self, mock_cursor):
        """Edge deletion SQL should match on both start_id and end_id."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )

        edge_delete_sql = str(mock_cursor.execute.call_args_list[0][0][0])
        assert "start_id" in edge_delete_sql
        assert "end_id" in edge_delete_sql

    def test_executes_two_queries(self, mock_cursor):
        """Should execute exactly two queries: one for edges, one for node."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )

        assert mock_cursor.execute.call_count == 2, (
            "Should execute 2 queries: edge deletion + node deletion"
        )

    def test_returns_node_delete_rowcount(self, mock_cursor):
        """Should return the rowcount from the node deletion query."""
        mock_cursor.rowcount = 1
        result = AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )
        assert result == 1

    def test_returns_zero_when_node_not_found(self, mock_cursor):
        """Should return 0 when the node doesn't exist."""
        mock_cursor.rowcount = 0
        result = AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "test_graph", "person:abc123def456789a"
        )
        assert result == 0

    def test_uses_correct_graph_name_in_queries(self, mock_cursor):
        """Should use the provided graph name in all SQL identifiers."""
        AgeQueryBuilder.delete_node_with_detach(
            mock_cursor, "my_graph", "person:abc123def456789a"
        )

        edge_sql = str(mock_cursor.execute.call_args_list[0][0][0])
        node_sql = str(mock_cursor.execute.call_args_list[1][0][0])

        assert "my_graph" in edge_sql
        assert "my_graph" in node_sql


class TestDeleteEdge:
    """Tests for delete_edge (single-ID scalar subquery)."""

    def test_generates_scalar_subquery_not_any(self, mock_cursor):
        """Should use scalar = %s, not = ANY(%s)."""
        AgeQueryBuilder.delete_edge(mock_cursor, "test_graph", "knows:abc123def456789a")

        edge_delete_sql = str(mock_cursor.execute.call_args_list[0][0][0])

        assert "= ANY" not in edge_delete_sql, "Should not use = ANY(%s) pattern"

    def test_passes_single_id_as_parameter(self, mock_cursor):
        """Should pass single ID string, not a list."""
        AgeQueryBuilder.delete_edge(mock_cursor, "test_graph", "knows:abc123def456789a")

        params = mock_cursor.execute.call_args_list[0][0][1]
        for param in params:
            assert not isinstance(param, list), (
                f"Parameters should be scalar strings, not lists: {params}"
            )

    def test_executes_single_query(self, mock_cursor):
        """Should execute exactly one query."""
        AgeQueryBuilder.delete_edge(mock_cursor, "test_graph", "knows:abc123def456789a")

        assert mock_cursor.execute.call_count == 1

    def test_returns_rowcount(self, mock_cursor):
        """Should return the rowcount from the delete query."""
        mock_cursor.rowcount = 1
        result = AgeQueryBuilder.delete_edge(
            mock_cursor, "test_graph", "knows:abc123def456789a"
        )
        assert result == 1

    def test_returns_zero_when_edge_not_found(self, mock_cursor):
        """Should return 0 when the edge doesn't exist."""
        mock_cursor.rowcount = 0
        result = AgeQueryBuilder.delete_edge(
            mock_cursor, "test_graph", "knows:abc123def456789a"
        )
        assert result == 0

    def test_uses_correct_graph_name(self, mock_cursor):
        """Should use the provided graph name."""
        AgeQueryBuilder.delete_edge(mock_cursor, "my_graph", "knows:abc123def456789a")

        sql = str(mock_cursor.execute.call_args_list[0][0][0])
        assert "my_graph" in sql


class TestDeleteNodesWithDetachBatchCompat:
    """Tests that the old batch method is removed / replaced."""

    def test_old_batch_method_does_not_exist(self):
        """The old delete_nodes_with_detach (plural, batch) should no longer exist."""
        assert not hasattr(AgeQueryBuilder, "delete_nodes_with_detach"), (
            "Old batch method delete_nodes_with_detach should be replaced "
            "by single-ID delete_node_with_detach"
        )

    def test_old_batch_edges_method_does_not_exist(self):
        """The old delete_edges (plural, batch) should no longer exist."""
        assert not hasattr(AgeQueryBuilder, "delete_edges"), (
            "Old batch method delete_edges should be replaced by single-ID delete_edge"
        )
