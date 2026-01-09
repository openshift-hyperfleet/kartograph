"""Unit tests for batched UNWIND mutation applier.

Tests the performance-optimized batch processing that uses UNWIND
to reduce round-trips when applying large numbers of mutations.
"""

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
    - ensure_all_labels_indexed
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

    # Set up ensure_all_labels_indexed
    mock_client.ensure_all_labels_indexed.return_value = 0

    return mock_client, mock_tx


class TestBatchedQueryBuilding:
    """Tests for batched Cypher query building with UNWIND."""

    def test_build_batch_create_nodes_uses_unwind(self):
        """Should build UNWIND query for batch node creation."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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
    """Tests for batched execution within transactions."""

    def test_executes_fewer_queries_than_operations(self):
        """Should execute fewer queries than total operations."""
        mock_client, mock_tx = create_mock_client_with_transaction()

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

        applier = MutationApplier(client=mock_client, batch_size=100)
        result = applier.apply_batch(operations)

        # Should execute only 1 query (all 10 in one UNWIND batch)
        assert mock_tx.execute_cypher.call_count == 1
        assert result.success is True
        assert result.operations_applied == 10

    def test_respects_batch_size_limit(self):
        """Should split into multiple batches when exceeding batch_size."""
        mock_client, mock_tx = create_mock_client_with_transaction()

        # Create 25 operations with batch_size=10
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
            for i in range(25)
        ]

        applier = MutationApplier(client=mock_client, batch_size=10)
        result = applier.apply_batch(operations)

        # Should execute 3 queries (10 + 10 + 5)
        assert mock_tx.execute_cypher.call_count == 3
        assert result.success is True
        assert result.operations_applied == 25

    def test_maintains_operation_order_across_types(self):
        """Should maintain correct execution order: DELETE edges, DELETE nodes, CREATE nodes, CREATE edges, UPDATE."""
        mock_client, mock_tx = create_mock_client_with_transaction()

        operations = [
            # Deliberately mixed order
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:1111111111111111",
                set_properties={"name": "Updated"},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:2222222222222222",
                label="knows",
                start_id="person:aaaaaaaaaaaaaaaa",
                end_id="person:bbbbbbbbbbbbbbbb",
                set_properties={
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:3333333333333333",
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:4444444444444444",
                label="person",
                set_properties={
                    "slug": "new",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.EDGE,
                id="knows:5555555555555555",
            ),
        ]

        applier = MutationApplier(client=mock_client, batch_size=100)
        applier.apply_batch(operations)

        # Extract executed queries
        executed_queries = [
            call.args[0] for call in mock_tx.execute_cypher.call_args_list
        ]

        # Verify order: DELETE edge, DELETE node, CREATE node, CREATE edge, UPDATE node
        assert "DELETE r" in executed_queries[0]  # DELETE edge first
        assert "DETACH DELETE n" in executed_queries[1]  # DELETE node second
        assert "MERGE (n:person" in executed_queries[2]  # CREATE node third
        assert "MERGE (source)-[r:knows" in executed_queries[3]  # CREATE edge fourth
        assert "SET n.`name`" in executed_queries[4]  # UPDATE node fifth

    def test_transaction_rollback_on_failure(self):
        """Should rollback entire transaction if any batch fails."""
        mock_client, mock_tx = create_mock_client_with_transaction()
        # Fail on second execute
        mock_tx.execute_cypher.side_effect = [None, Exception("Database error")]

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
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="organization:def456abc123789b",
                label="organization",  # Different label = different batch
                set_properties={
                    "slug": "acme",
                    "data_source_id": "ds-123",
                    "source_path": "orgs/acme.md",
                },
            ),
        ]

        applier = MutationApplier(client=mock_client, batch_size=100)
        result = applier.apply_batch(operations)

        assert result.success is False
        assert result.operations_applied == 0
        assert "Database error" in result.errors[0]


class TestBatchSizeConfiguration:
    """Tests for batch size configuration."""

    def test_default_batch_size(self):
        """Should use default batch size when not specified."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client)

        assert applier._batch_size == MutationApplier.DEFAULT_BATCH_SIZE

    def test_custom_batch_size(self):
        """Should use custom batch size when specified."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client, batch_size=500)

        assert applier._batch_size == 500

    def test_batch_size_of_one_degrades_to_individual(self):
        """Batch size of 1 should still work (no optimization)."""
        mock_client, mock_tx = create_mock_client_with_transaction()

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
            for i in range(3)
        ]

        applier = MutationApplier(client=mock_client, batch_size=1)
        result = applier.apply_batch(operations)

        # Should execute 3 separate queries
        assert mock_tx.execute_cypher.call_count == 3
        assert result.success is True


class TestObservability:
    """Tests for observability probes with batched operations."""

    def test_emits_batch_probe_events(self):
        """Should emit probe events for batches, not individual operations."""
        mock_client, mock_tx = create_mock_client_with_transaction()
        mock_probe = Mock()

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

        applier = MutationApplier(client=mock_client, batch_size=100, probe=mock_probe)
        applier.apply_batch(operations)

        # Should emit one batch event, not 10 individual events
        mock_probe.batch_applied.assert_called_once_with(
            operation=MutationOperationType.CREATE,
            entity_type=EntityType.NODE,
            label="person",
            count=10,
            duration_ms=ANY,
        )

        # Should emit apply_batch_completed event
        mock_probe.apply_batch_completed.assert_called_once_with(
            total_operations=10,
            total_batches=1,
            duration_ms=ANY,
            success=True,
        )


class TestUpdateWithRemoveProperties:
    """Tests for UPDATE operations with remove_properties."""

    def test_update_with_remove_falls_back_to_individual(self):
        """UPDATE with remove_properties should use individual queries."""
        mock_client, mock_tx = create_mock_client_with_transaction()

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                remove_properties=["old_field"],
            ),
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:def456abc123789a",
                set_properties={"name": "Bob"},  # This one can be batched
            ),
        ]

        applier = MutationApplier(client=mock_client, batch_size=100)
        applier.apply_batch(operations)

        # The remove operation should be executed individually
        executed_queries = [
            call.args[0] for call in mock_tx.execute_cypher.call_args_list
        ]

        # Should have at least one REMOVE query
        remove_queries = [q for q in executed_queries if "REMOVE" in q]
        assert len(remove_queries) >= 1


class TestSpecialCharacterHandling:
    """Tests for handling special characters in property values."""

    def test_escapes_single_quotes_in_batch(self):
        """Should properly escape single quotes in batched data."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client, batch_size=100)

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

        applier = MutationApplier(client=mock_client, batch_size=100)

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
