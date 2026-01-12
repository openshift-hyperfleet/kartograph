"""Unit tests for MutationApplier infrastructure component."""

from unittest.mock import ANY, MagicMock, Mock


from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.mutation_applier import MutationApplier


def create_mock_client_with_transaction():
    """Create a mock client with transaction support and dummy node methods.

    Sets up:
    - graph_name property
    - transaction context manager
    - execute_cypher for dummy node checks (returns empty results)

    Returns:
        Tuple of (mock_client, mock_tx, mock_indexing_client)
    """
    mock_client = Mock()
    mock_client.graph_name = "test_graph"

    # Set up transaction context manager
    mock_tx = Mock()
    mock_client.transaction = MagicMock()
    mock_client.transaction.return_value.__enter__.return_value = mock_tx
    mock_client.transaction.return_value.__exit__.return_value = None

    # Set up execute_cypher for dummy node existence checks
    # Returns empty result (label doesn't exist yet)
    mock_result = Mock()
    mock_result.row_count = 0
    mock_result.rows = []
    mock_client.execute_cypher.return_value = mock_result

    # Create separate mock for indexing client (implements GraphIndexingProtocol)
    mock_indexing_client = Mock()
    mock_indexing_client.graph_name = "test_graph"
    mock_indexing_client.ensure_all_labels_indexed.return_value = 0

    return mock_client, mock_tx, mock_indexing_client


class TestMutationApplierQueryBuilding:
    """Tests for Cypher query building logic."""

    def test_build_create_node_query(self):
        """Should build MERGE query for CREATE node operation."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice-smith",
                "name": "Alice Smith",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should use MERGE for idempotency
        assert "MERGE" in query
        assert "(n:person {id: 'person:abc123def456789a'})" in query
        # Property names are escaped with backticks to avoid reserved keyword conflicts
        assert "SET n.`slug` = 'alice-smith'" in query
        assert "SET n.`name` = 'Alice Smith'" in query
        assert "SET n.`data_source_id` = 'ds-123'" in query
        assert "SET n.`source_path` = 'people/alice.md'" in query

    def test_build_create_edge_query(self):
        """Should build MERGE query for CREATE edge operation."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.EDGE,
            id="knows:abc123def456789a",
            label="knows",
            start_id="person:abc123def456789a",
            end_id="person:def456abc123789a",
            set_properties={
                "since": 2020,
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should match source/target nodes and MERGE the relationship
        assert "MATCH (source {id: 'person:abc123def456789a'})" in query
        assert "MATCH (target {id: 'person:def456abc123789a'})" in query
        assert (
            "MERGE (source)-[r:knows {id: 'knows:abc123def456789a'}]->(target)" in query
        )
        # Property names are escaped with backticks
        assert "SET r.`since` = 2020" in query
        assert "SET r.`data_source_id` = 'ds-123'" in query

    def test_build_update_with_set_properties_query(self):
        """Should build SET query for UPDATE operation."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            set_properties={
                "name": "Alice Updated",
                "email": "alice@example.com",
            },
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        assert "MATCH (n {id: 'person:abc123def456789a'})" in query
        assert "SET" in query
        # Property names are escaped with backticks
        assert "n.`name` = 'Alice Updated'" in query
        assert "n.`email` = 'alice@example.com'" in query

    def test_build_update_with_remove_properties_query(self):
        """Should build REMOVE query for UPDATE operation."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            remove_properties=["middle_name", "old_email"],
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        assert "MATCH (n {id: 'person:abc123def456789a'})" in query
        # Property names are escaped with backticks
        assert "REMOVE n.`middle_name`, n.`old_email`" in query

    def test_build_update_with_both_set_and_remove_query(self):
        """Should build both SET and REMOVE for UPDATE operation."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            set_properties={"name": "Alice Smith"},
            remove_properties=["nickname"],
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        assert "MATCH (n {id: 'person:abc123def456789a'})" in query
        # Property names are escaped with backticks
        assert "SET n.`name` = 'Alice Smith'" in query
        assert "REMOVE n.`nickname`" in query

    def test_build_delete_query(self):
        """Should build DETACH DELETE query for DELETE operation."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should use DETACH DELETE to cascade edges
        assert "MATCH (n {id: 'person:abc123def456789a'})" in query
        assert "DETACH DELETE n" in query

    def test_build_delete_edge_query(self):
        """Should build DELETE query for edge using relationship syntax."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type=EntityType.EDGE,
            id="knows:abc123def456789a",
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should use relationship syntax for edges
        assert "MATCH ()-[r {id: 'knows:abc123def456789a'}]->()" in query
        assert "DELETE r" in query

    def test_build_update_edge_query(self):
        """Should build UPDATE query for edge using relationship syntax."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.EDGE,
            id="knows:abc123def456789a",
            set_properties={"since": 2020},
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should use relationship syntax for edges
        assert "MATCH ()-[r {id: 'knows:abc123def456789a'}]->()" in query
        # Property names are escaped with backticks
        assert "SET r.`since` = 2020" in query

    def test_build_update_edge_remove_properties(self):
        """Should build REMOVE query for edge using relationship syntax."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.EDGE,
            id="knows:abc123def456789a",
            remove_properties=["old_field", "temp_prop"],
        )

        applier = MutationApplier(client=Mock())
        query = applier._build_query(mutation)

        assert query is not None

        # Should use relationship syntax for edges
        assert "MATCH ()-[r {id: 'knows:abc123def456789a'}]->()" in query
        # Property names are escaped with backticks
        assert "REMOVE r.`old_field`, r.`temp_prop`" in query

    def test_format_string_value(self):
        """Should properly escape string values."""
        applier = MutationApplier(client=Mock())

        assert applier._format_value("test") == "'test'"
        assert applier._format_value("it's") == "'it\\'s'"

    def test_format_numeric_value(self):
        """Should format numeric values without quotes."""
        applier = MutationApplier(client=Mock())

        assert applier._format_value(42) == "42"
        assert applier._format_value(3.14) == "3.14"

    def test_format_boolean_value(self):
        """Should format boolean values as lowercase."""
        applier = MutationApplier(client=Mock())

        assert applier._format_value(True) == "true"
        assert applier._format_value(False) == "false"

    def test_format_none_value(self):
        """Should format None as null."""
        applier = MutationApplier(client=Mock())

        assert applier._format_value(None) == "null"

    def test_format_list_value(self):
        """Should format list values as Cypher arrays."""
        applier = MutationApplier(client=Mock())

        assert applier._format_value(["a", "b", "c"]) == "['a', 'b', 'c']"
        assert applier._format_value([1, 2, 3]) == "[1, 2, 3]"
        assert applier._format_value([]) == "[]"

    def test_format_list_with_special_characters(self):
        """Should escape special characters in list items."""
        applier = MutationApplier(client=Mock())

        result = applier._format_value(["it's", 'a "test"'])
        assert result == "['\\'s', 'a \"test\"']" or "it\\'s" in result

    def test_format_dict_converts_to_array(self):
        """Should convert dict to array of 'key: value' strings.

        AGE has issues with map keys containing special characters like '-' or '.',
        so we normalize dicts to arrays.
        """
        applier = MutationApplier(client=Mock())

        result = applier._format_value({"-t": "Tag option", ".": "Current dir"})
        # Dict is converted to array of "key: value" strings
        assert "[" in result
        assert "-t: Tag option" in result
        assert ".: Current dir" in result

    def test_format_nested_list(self):
        """Should handle nested lists."""
        applier = MutationApplier(client=Mock())

        result = applier._format_value([["a", "b"], ["c"]])
        assert result == "[['a', 'b'], ['c']]"


class TestMutationApplierBatchExecution:
    """Tests for batch mutation application."""

    def test_sorts_operations_correctly(self):
        """Should sort operations into correct execution order."""
        # Create operations in random order
        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.EDGE,
                id="edge:1111111111111111",
                set_properties={"name": "test"},
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="node:2222222222222222",
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="edge:3333333333333333",
                label="test",
                start_id="node:aaaaaaaaaaaaaaaa",
                end_id="node:bbbbbbbbbbbbbbbb",
                set_properties={
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="node:4444444444444444",
                set_properties={"name": "test"},
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.EDGE,
                id="edge:5555555555555555",
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="node:6666666666666666",
                label="test",
                set_properties={
                    "slug": "test",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.DEFINE,
                type=EntityType.NODE,
                label="test",
                description="Test",
                required_properties=set(),
            ),
        ]

        applier = MutationApplier(client=Mock())
        sorted_ops = applier._sort_operations(operations)

        # Verify order: DEFINE, DELETE edge, DELETE node, CREATE node, CREATE edge, UPDATE node, UPDATE edge
        assert sorted_ops[0].op == MutationOperationType.DEFINE
        assert (
            sorted_ops[1].op == MutationOperationType.DELETE
            and sorted_ops[1].type == EntityType.EDGE
        )
        assert (
            sorted_ops[2].op == MutationOperationType.DELETE
            and sorted_ops[2].type == EntityType.NODE
        )
        assert (
            sorted_ops[3].op == MutationOperationType.CREATE
            and sorted_ops[3].type == EntityType.NODE
        )
        assert (
            sorted_ops[4].op == MutationOperationType.CREATE
            and sorted_ops[4].type == EntityType.EDGE
        )
        assert (
            sorted_ops[5].op == MutationOperationType.UPDATE
            and sorted_ops[5].type == EntityType.NODE
        )
        assert (
            sorted_ops[6].op == MutationOperationType.UPDATE
            and sorted_ops[6].type == EntityType.EDGE
        )

    def test_apply_batch_success(self):
        """Should apply all operations in a transaction."""
        mock_client, mock_tx, mock_indexing = create_mock_client_with_transaction()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={"email": "alice@example.com"},
            ),
        ]

        applier = MutationApplier(client=mock_client, indexing_client=mock_indexing)
        result = applier.apply_batch(operations)

        # Should use transaction context manager
        mock_client.transaction.assert_called_once()

        # Should execute both operations
        assert mock_tx.execute_cypher.call_count == 2

        # Should return success result
        assert result.success is True
        assert result.operations_applied == 2
        assert result.errors == []

    def test_apply_batch_failure_rolls_back(self):
        """Should rollback transaction on failure."""
        mock_client, mock_tx, mock_indexing = create_mock_client_with_transaction()
        mock_tx.execute_cypher.side_effect = Exception("Database error")

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
            ),
        ]

        applier = MutationApplier(client=mock_client, indexing_client=mock_indexing)
        result = applier.apply_batch(operations)

        # Should return failure result
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) == 1
        assert "Database error" in result.errors[0]

    def test_apply_batch_validates_operations(self):
        """Should validate operations before applying."""
        mock_client = Mock()

        # Invalid operation (missing label for CREATE)
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={
                    "slug": "alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        applier = MutationApplier(client=mock_client)
        result = applier.apply_batch(operations)

        # Should fail validation before executing
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) > 0

    def test_apply_empty_batch(self):
        """Should handle empty operation list."""
        mock_client = Mock()

        applier = MutationApplier(client=mock_client)
        result = applier.apply_batch([])

        assert result.success is True
        assert result.operations_applied == 0
        assert result.errors == []


class TestMutationApplierObservability:
    """Tests for domain-oriented observability."""

    def test_emits_probe_events(self):
        """Should emit batch probe events for mutations."""
        mock_client, mock_tx, mock_indexing = create_mock_client_with_transaction()
        mock_probe = Mock()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        applier = MutationApplier(
            client=mock_client, probe=mock_probe, indexing_client=mock_indexing
        )
        applier.apply_batch(operations)

        # Should emit batch probe event with timing
        mock_probe.batch_applied.assert_called_once_with(
            operation=MutationOperationType.CREATE,
            entity_type=EntityType.NODE,
            label="person",
            count=1,
            duration_ms=ANY,
        )

        # Should emit apply_batch_completed event
        mock_probe.apply_batch_completed.assert_called_once_with(
            total_operations=1,
            total_batches=1,
            duration_ms=ANY,
            success=True,
        )
