"""Unit tests for StagingTableManager.

Tests for bulk-loading.spec.md:

Requirement: Staging-Based Ingestion
  - Scenario: Node bulk create
    Data loaded into a temporary staging table via COPY
    Staging table has ON COMMIT DROP (dropped on commit)

  - Scenario: Edge bulk create with ID resolution
    Graphid lookup table built from union of pre-existing nodes and nodes
    created earlier in the same batch (same-transaction visibility)

Requirement: Duplicate and Orphan Detection
  - Scenario: Duplicate IDs in batch
    Duplicates detected and reported via probe, then raised as ValueError

  - Scenario: Orphaned edges
    Orphaned edges detected and reported via probe, then raised as ValueError
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from graph.infrastructure.age_bulk_loading.staging import StagingTableManager


@pytest.fixture
def manager() -> StagingTableManager:
    return StagingTableManager()


@pytest.fixture
def mock_cursor() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_probe() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# Requirement: Staging-Based Ingestion
# Scenario: Node bulk create — staging table with ON COMMIT DROP
# ---------------------------------------------------------------------------


class TestNodeStagingTableCreation:
    """The node staging table MUST use ON COMMIT DROP."""

    def test_node_staging_table_uses_on_commit_drop(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Node staging table DDL must include ON COMMIT DROP."""
        manager.create_node_staging_table(mock_cursor, "abc123")

        executed_sql = str(mock_cursor.execute.call_args[0][0])
        assert "ON COMMIT DROP" in executed_sql, (
            "Node staging table must use ON COMMIT DROP to auto-clean on commit"
        )

    def test_node_staging_table_is_temp(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Node staging table must be a TEMP table."""
        manager.create_node_staging_table(mock_cursor, "abc123")

        executed_sql = str(mock_cursor.execute.call_args[0][0])
        assert "TEMP" in executed_sql or "TEMPORARY" in executed_sql, (
            "Node staging table must be TEMP or TEMPORARY"
        )

    def test_node_staging_table_name_contains_session_id(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Node staging table name must incorporate the session ID for uniqueness."""
        table_name = manager.create_node_staging_table(mock_cursor, "mySess123")
        assert "mySess123" in table_name, (
            f"Staging table name must include session_id, got: {table_name}"
        )

    def test_node_staging_table_returns_name(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """create_node_staging_table must return the table name."""
        table_name = manager.create_node_staging_table(mock_cursor, "abc123")
        assert isinstance(table_name, str) and len(table_name) > 0


class TestEdgeStagingTableCreation:
    """The edge staging table MUST use ON COMMIT DROP."""

    def test_edge_staging_table_uses_on_commit_drop(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Edge staging table DDL must include ON COMMIT DROP."""
        manager.create_edge_staging_table(mock_cursor, "abc123")

        executed_sql = str(mock_cursor.execute.call_args[0][0])
        assert "ON COMMIT DROP" in executed_sql, (
            "Edge staging table must use ON COMMIT DROP to auto-clean on commit"
        )

    def test_edge_staging_table_is_temp(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Edge staging table must be a TEMP table."""
        manager.create_edge_staging_table(mock_cursor, "abc123")

        executed_sql = str(mock_cursor.execute.call_args[0][0])
        assert "TEMP" in executed_sql or "TEMPORARY" in executed_sql, (
            "Edge staging table must be TEMP or TEMPORARY"
        )

    def test_edge_staging_table_has_graphid_columns(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Edge staging table must have start_graphid and end_graphid for resolution."""
        manager.create_edge_staging_table(mock_cursor, "abc123")

        executed_sql = str(mock_cursor.execute.call_args[0][0])
        assert "start_graphid" in executed_sql, (
            "Edge staging table must include start_graphid column"
        )
        assert "end_graphid" in executed_sql, (
            "Edge staging table must include end_graphid column"
        )


# ---------------------------------------------------------------------------
# Requirement: Staging-Based Ingestion
# Scenario: Edge bulk create — graphid lookup table is ON COMMIT DROP
# ---------------------------------------------------------------------------


class TestGraphidLookupTableCreation:
    """The graphid lookup table MUST use ON COMMIT DROP and index logical_id."""

    def test_lookup_table_uses_on_commit_drop(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Graphid lookup table must use ON COMMIT DROP."""
        # Mock: COUNT(*) = 5
        mock_cursor.fetchone.return_value = (5,)

        manager.create_graphid_lookup_table(mock_cursor, "my_graph", "sess42")

        # The first execute call creates the table (SELECT INTO / CREATE TEMP TABLE AS)
        create_sql = str(mock_cursor.execute.call_args_list[0][0][0])
        assert "ON COMMIT DROP" in create_sql, (
            "Graphid lookup table must use ON COMMIT DROP"
        )

    def test_lookup_table_queries_ag_label_vertex(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Lookup table must query _ag_label_vertex to include all nodes (including same-batch)."""
        mock_cursor.fetchone.return_value = (10,)

        manager.create_graphid_lookup_table(mock_cursor, "my_graph", "sess42")

        create_sql = str(mock_cursor.execute.call_args_list[0][0][0])
        assert "_ag_label_vertex" in create_sql, (
            "Lookup table must query _ag_label_vertex so same-batch nodes are included"
        )

    def test_lookup_table_creates_index_on_logical_id(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """Lookup table must have an index on logical_id for fast edge resolution."""
        mock_cursor.fetchone.return_value = (0,)

        manager.create_graphid_lookup_table(mock_cursor, "my_graph", "sess42")

        all_sqls = [str(c[0][0]) for c in mock_cursor.execute.call_args_list]
        index_sqls = [s for s in all_sqls if "CREATE INDEX" in s and "logical_id" in s]
        assert len(index_sqls) >= 1, (
            "Lookup table must have an index on logical_id for fast edge resolution"
        )

    def test_returns_tuple_of_name_and_row_count(
        self, manager: StagingTableManager, mock_cursor: MagicMock
    ) -> None:
        """create_graphid_lookup_table must return (table_name, row_count)."""
        mock_cursor.fetchone.return_value = (42,)

        result = manager.create_graphid_lookup_table(mock_cursor, "my_graph", "sess42")

        assert isinstance(result, tuple) and len(result) == 2, (
            "Must return a tuple of (table_name, row_count)"
        )
        table_name, row_count = result
        assert isinstance(table_name, str) and len(table_name) > 0
        assert row_count == 42


# ---------------------------------------------------------------------------
# Requirement: Duplicate and Orphan Detection
# Scenario: Duplicate IDs in batch
# ---------------------------------------------------------------------------


class TestDuplicateIdDetection:
    """Duplicate IDs in a batch MUST be detected and reported."""

    def test_raises_value_error_on_duplicate_ids(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """check_for_duplicate_ids must raise ValueError when duplicates are found."""
        # Simulate duplicates found: ID appears twice
        mock_cursor.fetchall.return_value = [
            ("node:abc123def4560001", 2),
        ]

        with pytest.raises(ValueError, match="Duplicate"):
            manager.check_for_duplicate_ids(
                mock_cursor, "_staging_nodes_test", "node", mock_probe
            )

    def test_calls_probe_with_duplicate_ids(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """probe.duplicate_ids_detected must be called with the duplicate IDs."""
        duplicate_id = "node:abc123def4560001"
        mock_cursor.fetchall.return_value = [(duplicate_id, 2)]

        with pytest.raises(ValueError):
            manager.check_for_duplicate_ids(
                mock_cursor, "_staging_nodes_test", "node", mock_probe
            )

        mock_probe.duplicate_ids_detected.assert_called_once()
        call_args = mock_probe.duplicate_ids_detected.call_args[0]
        # First arg should be the list of duplicate IDs
        assert duplicate_id in call_args[0], "Probe must receive the duplicate ID"

    def test_reports_multiple_duplicate_ids(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """All duplicate IDs must be reported, not just the first one."""
        mock_cursor.fetchall.return_value = [
            ("node:abc123def4560001", 3),
            ("node:abc123def4560002", 2),
        ]

        with pytest.raises(ValueError) as exc_info:
            manager.check_for_duplicate_ids(
                mock_cursor, "_staging_nodes_test", "node", mock_probe
            )

        # Error message should reference duplicate IDs
        error_msg = str(exc_info.value)
        assert (
            "node:abc123def4560001" in error_msg or "node:abc123def4560002" in error_msg
        ), "Error message must include the duplicate IDs"

    def test_no_error_when_no_duplicates(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """No error when no duplicate IDs exist."""
        mock_cursor.fetchall.return_value = []

        # Must not raise
        manager.check_for_duplicate_ids(
            mock_cursor, "_staging_nodes_test", "node", mock_probe
        )

        mock_probe.duplicate_ids_detected.assert_not_called()

    def test_entity_type_passed_to_probe(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Probe must receive the entity type so observers can distinguish node vs edge dupes."""
        mock_cursor.fetchall.return_value = [("edge:abc123def4560002", 2)]

        with pytest.raises(ValueError):
            manager.check_for_duplicate_ids(
                mock_cursor, "_staging_edges_test", "edge", mock_probe
            )

        call_args = mock_probe.duplicate_ids_detected.call_args[0]
        # Second arg should be entity_type
        assert call_args[1] == "edge", "Probe must receive entity type"


# ---------------------------------------------------------------------------
# Requirement: Duplicate and Orphan Detection
# Scenario: Orphaned edges
# ---------------------------------------------------------------------------


class TestOrphanedEdgeDetection:
    """Orphaned edges (missing start/end nodes) MUST be detected and reported."""

    def test_raises_value_error_on_orphaned_edges(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """check_for_orphaned_edges must raise ValueError when orphans are found."""
        # Simulate: edge with start_graphid resolved but end_graphid is NULL
        mock_cursor.fetchall.return_value = [
            ("edge:abc123def4560002", "node:start001", "node:missing002", 999, None),
        ]

        with pytest.raises(ValueError, match="[Oo]rphaned"):
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

    def test_calls_probe_with_orphaned_edge_ids(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """probe.orphaned_edges_detected must be called with orphaned edge IDs."""
        orphaned_edge_id = "edge:abc123def4560002"
        mock_cursor.fetchall.return_value = [
            (orphaned_edge_id, "node:start001", "node:missing002", 999, None),
        ]

        with pytest.raises(ValueError):
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

        mock_probe.orphaned_edges_detected.assert_called_once()
        call_args = mock_probe.orphaned_edges_detected.call_args[0]
        assert orphaned_edge_id in call_args[0], (
            "Probe must receive the orphaned edge ID"
        )

    def test_reports_missing_node_ids(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Missing node IDs must be included in probe call and error message."""
        missing_node_id = "node:missing002"
        mock_cursor.fetchall.return_value = [
            ("edge:abc123def4560002", "node:start001", missing_node_id, 999, None),
        ]

        with pytest.raises(ValueError) as exc_info:
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

        # Error message must name the missing node
        assert missing_node_id in str(exc_info.value), (
            "Error message must include the missing node ID"
        )

        # Probe must also receive the missing node ID
        probe_args = mock_probe.orphaned_edges_detected.call_args[0]
        assert missing_node_id in probe_args[1], (
            "Probe must receive the missing node IDs"
        )

    def test_detects_missing_start_node(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Edges with unresolved start_graphid (NULL) are orphaned."""
        mock_cursor.fetchall.return_value = [
            ("edge:abc123def4560002", "node:missing_start", "node:end001", None, 888),
        ]

        with pytest.raises(ValueError):
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

    def test_detects_missing_end_node(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Edges with unresolved end_graphid (NULL) are orphaned."""
        mock_cursor.fetchall.return_value = [
            ("edge:abc123def4560002", "node:start001", "node:missing_end", 777, None),
        ]

        with pytest.raises(ValueError):
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

    def test_no_error_when_no_orphans(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """No error when all edges have resolved endpoints."""
        mock_cursor.fetchall.return_value = []

        # Must not raise
        manager.check_for_orphaned_edges(mock_cursor, "_staging_edges_test", mock_probe)

        mock_probe.orphaned_edges_detected.assert_not_called()

    def test_reports_multiple_orphaned_edges(
        self,
        manager: StagingTableManager,
        mock_cursor: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """All orphaned edges should be reported, not just the first."""
        mock_cursor.fetchall.return_value = [
            ("edge:abc123def4560001", "node:start001", "node:miss001", 111, None),
            ("edge:abc123def4560002", "node:miss002", "node:end001", None, 222),
        ]

        with pytest.raises(ValueError):
            manager.check_for_orphaned_edges(
                mock_cursor, "_staging_edges_test", mock_probe
            )

        probe_args = mock_probe.orphaned_edges_detected.call_args[0]
        orphaned_edge_ids = probe_args[0]
        assert len(orphaned_edge_ids) == 2, "All orphaned edges must be reported"
