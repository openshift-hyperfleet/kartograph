"""Tests for automatic graph_id stamping in MutationApplier."""

from unittest.mock import Mock

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.mutation_applier import MutationApplier


class TestGraphIdStamping:
    """Tests that MutationApplier automatically stamps graph_id."""

    def test_create_node_includes_graph_id(self):
        """Should automatically add graph_id when creating nodes."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client)

        mutation = MutationOperation(
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
        )

        query = applier._build_create(mutation)

        # Should include graph_id in SET clauses (with backticks for keyword safety)
        assert "SET n.`graph_id` = 'test_graph'" in query

    def test_create_edge_includes_graph_id(self):
        """Should automatically add graph_id when creating edges."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client)

        mutation = MutationOperation(
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
        )

        query = applier._build_create(mutation)

        # Should include graph_id in SET clauses (with backticks for keyword safety)
        assert "SET r.`graph_id` = 'test_graph'" in query

    def test_graph_id_not_in_set_properties(self):
        """graph_id should be added by infrastructure, not in set_properties."""
        mock_client = Mock()
        mock_client.graph_name = "test_graph"

        applier = MutationApplier(client=mock_client)

        # CREATE operation without graph_id in set_properties
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        query = applier._build_create(mutation)

        # graph_id should be added automatically (with backticks for keyword safety)
        assert "SET n.`graph_id` = 'test_graph'" in query
        # Should have exactly one graph_id SET clause
        assert query.count("graph_id") == 1
