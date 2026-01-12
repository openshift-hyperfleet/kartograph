"""Unit tests for batched UNWIND mutation applier.

Tests the legacy helper methods on MutationApplier that are still
available for backwards compatibility. The actual batching is now
handled by AgeBulkLoadingStrategy.
"""

from unittest.mock import MagicMock, Mock


from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    MutationResult,
)
from graph.infrastructure.mutation_applier import MutationApplier


def create_mock_strategy():
    """Create a mock bulk loading strategy."""
    mock_strategy = Mock()
    mock_strategy.apply_batch.return_value = MutationResult(
        success=True,
        operations_applied=0,
    )
    return mock_strategy


def create_mock_client_with_transaction():
    """Create a mock client with transaction support and dummy node methods.

    Sets up:
    - graph_name property
    - transaction context manager
    - execute_cypher for dummy node checks (returns empty results)

    Returns:
        Tuple of (mock_client, mock_tx, mock_strategy)
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

    # Create mock for bulk loading strategy
    mock_strategy = create_mock_strategy()

    return mock_client, mock_tx, mock_strategy


class TestBatchedQueryBuilding:
    """Tests for batched Cypher query building with UNWIND."""

    def test_build_batch_create_nodes_uses_unwind(self):
        """Should build UNWIND query for batch node creation."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

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
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:def456abc123789a",
                label="person",
                set_properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "people/bob.md",
                },
            ),
        ]

        query = applier._build_batch_create_nodes(operations)

        assert "UNWIND" in query
        assert "MERGE (n:person {id: item.id})" in query
        # AGE doesn't support SET n += item.props, so we use individual SET clauses
        assert "SET n.`slug` = item.`slug`" in query
        assert "SET n.`name` = item.`name`" in query
        assert "SET n.`graph_id` = 'test_graph'" in query

    def test_build_batch_create_nodes_includes_all_data(self):
        """Should embed all node data in the UNWIND array."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={"slug": "alice", "name": "Alice"},
            ),
        ]

        query = applier._build_batch_create_nodes(operations)

        # Should contain the node id and properties
        assert "person:abc123def456789a" in query
        assert "alice" in query
        assert "Alice" in query

    def test_build_batch_create_edges_uses_unwind(self):
        """Should build UNWIND query for batch edge creation."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:abc123def456789a",
                label="knows",
                start_id="person:aaa111bbb222ccc3",
                end_id="person:def456abc123789a",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        query = applier._build_batch_create_edges(operations)

        assert "UNWIND" in query
        assert "MATCH (source {id: item.start_id})" in query
        assert "MATCH (target {id: item.end_id})" in query
        assert "MERGE (source)-[r:knows {id: item.id}]->(target)" in query
        # AGE doesn't support SET r += item.props, so we use individual SET clauses
        assert "SET r.`since` = item.`since`" in query
        assert "SET r.`graph_id` = 'test_graph'" in query

    def test_build_batch_delete_nodes_uses_unwind(self):
        """Should build UNWIND query for batch node deletion."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:def456abc123789a",
            ),
        ]

        query = applier._build_batch_delete_nodes(operations)

        assert "UNWIND" in query
        assert "MATCH (n {id: item.id})" in query
        assert "DETACH DELETE n" in query
        assert "person:abc123def456789a" in query
        assert "person:def456abc123789a" in query

    def test_build_batch_delete_edges_uses_unwind(self):
        """Should build UNWIND query for batch edge deletion."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.EDGE,
                id="knows:abc123def456789a",
            ),
        ]

        query = applier._build_batch_delete_edges(operations)

        assert "UNWIND" in query
        assert "MATCH ()-[r {id: item.id}]->()" in query
        assert "DELETE r" in query

    def test_build_batch_update_nodes_uses_unwind(self):
        """Should build UNWIND query for batch node updates with SET."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={"name": "Alice Updated", "email": "alice@example.com"},
            ),
        ]

        query = applier._build_batch_update_nodes(operations)

        assert "UNWIND" in query
        assert "MATCH (n {id: item.id})" in query
        # AGE doesn't support SET n += item.props, so we use individual SET clauses
        assert "SET n.`name` = item.`name`" in query
        assert "SET n.`email` = item.`email`" in query

    def test_build_batch_update_edges_uses_unwind(self):
        """Should build UNWIND query for batch edge updates."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.EDGE,
                id="knows:abc123def456789a",
                set_properties={"since": 2021},
            ),
        ]

        query = applier._build_batch_update_edges(operations)

        assert "UNWIND" in query
        assert "MATCH ()-[r {id: item.id}]->()" in query
        # AGE doesn't support SET r += item.props, so we use individual SET clauses
        assert "SET r.`since` = item.`since`" in query


class TestOperationGrouping:
    """Tests for grouping operations by type and label."""

    def test_groups_create_nodes_by_label(self):
        """Should group CREATE node operations by label.

        Note: Grouping only combines consecutive operations with the same key.
        Non-consecutive operations with the same label result in separate groups.
        This is by design to preserve the sorted order.
        """
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        # Operations with same labels grouped together (consecutive)
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={"slug": "alice"},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:def456abc123789a",
                label="person",
                set_properties={"slug": "bob"},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="organization:abc123def456789b",
                label="organization",
                set_properties={"slug": "acme"},
            ),
        ]

        groups = applier._group_operations(operations)

        # Should have separate groups for person and organization
        create_node_groups = [
            g
            for g in groups
            if g["op"] == "CREATE" and g["entity_type"] == EntityType.NODE
        ]
        assert len(create_node_groups) == 2

        person_group = next(g for g in create_node_groups if g["label"] == "person")
        org_group = next(g for g in create_node_groups if g["label"] == "organization")

        assert len(person_group["operations"]) == 2
        assert len(org_group["operations"]) == 1

    def test_groups_create_edges_by_label(self):
        """Should group CREATE edge operations by label."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:abc123def456789a",
                label="knows",
                start_id="person:aaa111bbb222ccc3",
                end_id="person:bbb222ccc333ddd4",
                set_properties={},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="works_at:abc123def4567890",
                label="works_at",
                start_id="person:aaa111bbb222ccc3",
                end_id="organization:ccc333ddd444ee55",
                set_properties={},
            ),
        ]

        groups = applier._group_operations(operations)

        create_edge_groups = [
            g
            for g in groups
            if g["op"] == "CREATE" and g["entity_type"] == EntityType.EDGE
        ]
        assert len(create_edge_groups) == 2

    def test_groups_deletes_together_regardless_of_label(self):
        """DELETE operations group by entity type only, not label."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="org:def456abc123789a",
            ),
        ]

        groups = applier._group_operations(operations)

        delete_node_groups = [
            g for g in groups if g["op"] == "DELETE" and g["entity_type"] == "node"
        ]
        # All node deletes should be in one group
        assert len(delete_node_groups) == 1
        assert len(delete_node_groups[0]["operations"]) == 2

    def test_groups_updates_together_regardless_of_label(self):
        """UPDATE operations group by entity type only, not label."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={"name": "Updated"},
            ),
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="org:def456abc123789a",
                set_properties={"name": "Updated Org"},
            ),
        ]

        groups = applier._group_operations(operations)

        update_node_groups = [
            g for g in groups if g["op"] == "UPDATE" and g["entity_type"] == "node"
        ]
        assert len(update_node_groups) == 1
        assert len(update_node_groups[0]["operations"]) == 2


class TestBatchExecution:
    """Tests for delegation to BulkLoadingStrategy."""

    def test_delegates_to_strategy(self):
        """Should delegate batch execution to the strategy."""
        mock_client, mock_tx, mock_strategy = create_mock_client_with_transaction()

        # Configure strategy to return success
        mock_strategy.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=10,
        )

        # Create 10 operations of the same type/label
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=f"person:{i:016x}",
                label="person",
                set_properties={
                    "slug": f"person-{i}",
                    "data_source_id": "ds-123",
                    "source_path": f"people/{i}.md",
                },
            )
            for i in range(10)
        ]

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=mock_strategy
        )
        result = applier.apply_batch(operations)

        # Should delegate to strategy
        mock_strategy.apply_batch.assert_called_once()

        # Should pass all operations to strategy
        call_kwargs = mock_strategy.apply_batch.call_args.kwargs
        assert len(call_kwargs["operations"]) == 10

        assert result.success is True
        assert result.operations_applied == 10

    def test_passes_client_and_graph_name_to_strategy(self):
        """Should pass client and graph_name to strategy."""
        mock_client, mock_tx, mock_strategy = create_mock_client_with_transaction()
        mock_client.graph_name = "my_graph"

        mock_strategy.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=mock_strategy
        )
        applier.apply_batch(operations)

        # Should pass client and graph_name to strategy
        call_kwargs = mock_strategy.apply_batch.call_args.kwargs
        assert call_kwargs["client"] == mock_client
        assert call_kwargs["graph_name"] == "my_graph"

    def test_returns_strategy_failure_result(self):
        """Should return failure result from strategy."""
        mock_client, mock_tx, mock_strategy = create_mock_client_with_transaction()

        # Configure strategy to return failure
        mock_strategy.apply_batch.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Database error"],
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=mock_strategy
        )
        result = applier.apply_batch(operations)

        assert result.success is False
        assert result.operations_applied == 0
        assert "Database error" in result.errors[0]


class TestObservability:
    """Tests for observability probes passed to strategy."""

    def test_passes_probe_to_strategy(self):
        """Should pass probe to strategy for observability."""
        mock_client, mock_tx, mock_strategy = create_mock_client_with_transaction()
        mock_probe = Mock()

        mock_strategy.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=10,
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=f"person:{i:016x}",
                label="person",
                set_properties={
                    "slug": f"person-{i}",
                    "data_source_id": "ds-123",
                    "source_path": f"people/{i}.md",
                },
            )
            for i in range(10)
        ]

        applier = MutationApplier(
            client=mock_client,
            bulk_loading_strategy=mock_strategy,
            probe=mock_probe,
        )
        applier.apply_batch(operations)

        # Should pass probe to strategy
        call_kwargs = mock_strategy.apply_batch.call_args.kwargs
        assert call_kwargs["probe"] == mock_probe


class TestUpdateWithRemoveProperties:
    """Tests for UPDATE operations with remove_properties via legacy helpers."""

    def test_build_update_with_remove_query(self):
        """Legacy _build_update should generate REMOVE clause."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            remove_properties=["old_field"],
        )

        query = applier._build_update(operation)

        # Should have REMOVE clause
        assert "REMOVE" in query
        assert "old_field" in query


class TestSpecialCharacterHandling:
    """Tests for handling special characters in property values."""

    def test_escapes_single_quotes_in_batch(self):
        """Should properly escape single quotes in batched data."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={"name": "O'Brien", "note": "It's working"},
            ),
        ]

        query = applier._build_batch_create_nodes(operations)

        # Single quotes should be escaped
        assert "O\\'Brien" in query or "O''Brien" in query
        assert "It\\'s" in query or "It''s" in query

    def test_handles_numeric_and_boolean_values(self):
        """Should properly format numeric and boolean values in batch."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(
            client=mock_client, bulk_loading_strategy=create_mock_strategy()
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "age": 42,
                    "score": 3.14,
                    "active": True,
                    "deleted": False,
                },
            ),
        ]

        query = applier._build_batch_create_nodes(operations)

        # Numbers should not be quoted
        assert ": 42" in query or ":42" in query
        assert "3.14" in query
        # Booleans should be lowercase
        assert "true" in query
        assert "false" in query
