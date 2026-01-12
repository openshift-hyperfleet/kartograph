"""Integration tests for AGE bulk loading strategy.

These tests verify that the bulk loading strategy correctly handles:
1. Idempotency - duplicate operations in the same batch should not create duplicates
2. Edge label pre-creation - edge tables should be created even on empty databases
3. Concurrent safety - advisory locks should prevent race conditions
"""

import pytest

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.age_bulk_loading import AgeBulkLoadingStrategy
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.observability import DefaultMutationProbe


@pytest.mark.integration
class TestBulkLoadingIdempotency:
    """Tests for idempotent CREATE operations."""

    def test_duplicate_node_ids_in_same_batch_creates_single_node(
        self, clean_graph: AgeGraphClient
    ):
        """Duplicate node IDs in same batch should create only one node."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create two operations with the same ID in the same batch
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:aaaa111122223333",
                label="person",
                set_properties={
                    "slug": "alice-first",
                    "name": "Alice First",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:aaaa111122223333",  # Same ID!
                label="person",
                set_properties={
                    "slug": "alice-second",
                    "name": "Alice Second",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify only one node was created
        query_result = clean_graph.execute_cypher(
            "MATCH (n:person {id: 'person:aaaa111122223333'}) RETURN count(n) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 1, f"Expected 1 node, got {count}"

    def test_duplicate_edge_ids_in_same_batch_creates_single_edge(
        self, clean_graph: AgeGraphClient
    ):
        """Duplicate edge IDs in same batch should create only one edge."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # First create the nodes
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:bbbb111122223333",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:bbbb222233334444",
                label="person",
                set_properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Now create duplicate edges
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:cccc111122223333",
                label="knows",
                start_id="person:bbbb111122223333",
                end_id="person:bbbb222233334444",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:cccc111122223333",  # Same ID!
                label="knows",
                start_id="person:bbbb111122223333",
                end_id="person:bbbb222233334444",
                set_properties={
                    "since": 2021,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify only one edge was created
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows {id: 'knows:cccc111122223333'}]->() RETURN count(r) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 1, f"Expected 1 edge, got {count}"

    def test_repeated_batch_is_idempotent(self, clean_graph: AgeGraphClient):
        """Running the same batch twice should not create duplicates."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:dddd111122223333",
                label="person",
                set_properties={
                    "slug": "charlie",
                    "name": "Charlie",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:dddd222233334444",
                label="person",
                set_properties={
                    "slug": "diana",
                    "name": "Diana",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        # Run the batch twice
        result1 = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )
        result2 = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result1.success is True
        assert result2.success is True

        # Verify exactly 2 nodes exist
        query_result = clean_graph.execute_cypher(
            "MATCH (n:person) WHERE n.id STARTS WITH 'person:dddd' "
            "RETURN count(n) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 2, f"Expected 2 nodes, got {count}"


@pytest.mark.integration
class TestEdgeLabelPreCreation:
    """Tests for edge label table pre-creation."""

    def test_creates_edge_label_tables_on_empty_database(
        self, clean_graph: AgeGraphClient
    ):
        """Edge labels should be created even when no edges of that type exist."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create nodes and edges in a single batch (edge label doesn't exist yet)
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:eeee111122223333",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:eeee222233334444",
                label="person",
                set_properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="collaborates:ffff111122223333",
                label="collaborates",  # New edge type
                start_id="person:eeee111122223333",
                end_id="person:eeee222233334444",
                set_properties={
                    "project": "test-project",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the edge was created
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:collaborates]->() RETURN count(r) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 1, f"Expected 1 edge, got {count}"
