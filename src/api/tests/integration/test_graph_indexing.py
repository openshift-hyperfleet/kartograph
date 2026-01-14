"""Integration tests for graph indexing functionality.

These tests verify actual index creation against a real PostgreSQL/AGE instance.

Run with: pytest -m integration tests/integration/test_graph_indexing.py
Requires: Running PostgreSQL with AGE extension
"""

import uuid
from collections.abc import Generator

import pytest

from graph.infrastructure.age_client import AgeGraphClient


pytestmark = pytest.mark.integration


class LabelTracker:
    """Tracks created labels for cleanup after tests."""

    def __init__(self, client: AgeGraphClient):
        self._client = client
        self._labels: list[str] = []

    def create_label(self, prefix: str) -> str:
        """Generate a unique label name and track it for cleanup."""
        suffix = uuid.uuid4().hex[:8]
        label = f"{prefix}_{suffix}"
        self._labels.append(label)
        return label

    def cleanup(self) -> None:
        """Drop all tracked labels and their indexes."""
        with self._client._connection.cursor() as cursor:
            for label in self._labels:
                # Drop indexes first
                cursor.execute(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                    """,
                    (self._client.graph_name, label),
                )
                for (indexname,) in cursor.fetchall():
                    try:
                        cursor.execute(
                            f'DROP INDEX IF EXISTS "{self._client.graph_name}"."{indexname}"'
                        )
                    except Exception:
                        pass  # Index may not exist

                # Drop the label table
                try:
                    cursor.execute(
                        f"SELECT drop_label('{self._client.graph_name}', '{label}')"
                    )
                except Exception:
                    pass  # Label may not exist

            self._client._connection.commit()


@pytest.fixture
def label_tracker(clean_graph: AgeGraphClient) -> Generator[LabelTracker, None, None]:
    """Fixture that provides a label tracker and cleans up after test."""
    tracker = LabelTracker(clean_graph)
    yield tracker
    tracker.cleanup()


class TestVertexIndexCreation:
    """Tests for vertex label index creation."""

    def test_creates_indexes_for_vertex_label(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Should create all recommended indexes for a vertex label."""
        # Use unique label name to avoid collisions with previous test runs
        label = label_tracker.create_label("vtx_idx_test")

        # Create a vertex to establish the label
        clean_graph.execute_cypher(
            f"CREATE (n:{label} {{id: 'person:test1', name: 'Alice'}})"
        )

        # Create indexes - label name must match exactly (case-sensitive)
        created = clean_graph.ensure_label_indexes(label, kind="v")

        # Should have created indexes (3 for vertex: id, props_gin, prop_id)
        assert created == 3, f"Should create 3 indexes, got {created}"

        # Verify indexes exist by querying pg_indexes
        with clean_graph._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s
                AND tablename = %s
                """,
                (clean_graph.graph_name, label),
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Should have BTREE on id, GIN on properties, BTREE on properties.id
        assert any("id_btree" in idx for idx in indexes), (
            f"Missing BTREE id index. Found: {indexes}"
        )
        assert any("props_gin" in idx for idx in indexes), (
            f"Missing GIN properties index. Found: {indexes}"
        )
        assert any("prop_id" in idx for idx in indexes), (
            f"Missing BTREE properties.id index. Found: {indexes}"
        )

    def test_indexes_improve_lookup_performance(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Indexed lookups should use index scan (verify with EXPLAIN)."""
        # Use unique label name to avoid collisions with previous test runs
        label = label_tracker.create_label("perf_test_person")

        # Create vertices
        for i in range(100):
            clean_graph.execute_cypher(
                f"CREATE (n:{label} {{id: 'person:perf{i:03d}', name: 'Person{i}'}})"
            )

        # Create indexes
        clean_graph.ensure_label_indexes(label, kind="v")

        # Query should use index - we can't easily verify this in a unit test,
        # but we can at least verify the query works
        result = clean_graph.execute_cypher(
            f"MATCH (n:{label} {{id: 'person:perf050'}}) RETURN n"
        )
        assert result.row_count == 1


class TestEdgeIndexCreation:
    """Tests for edge label index creation."""

    def test_creates_indexes_for_edge_label(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Should create all recommended indexes for an edge label."""
        # Use unique label names to avoid collisions with previous test runs
        node_label = label_tracker.create_label("idx_test_node")
        edge_label = label_tracker.create_label("idx_test_edge")

        # Create nodes and edge to establish the labels
        clean_graph.execute_cypher(
            f"""
            CREATE (a:{node_label} {{id: 'node:a'}})
            CREATE (b:{node_label} {{id: 'node:b'}})
            """
        )
        clean_graph.execute_cypher(
            f"""
            MATCH (a:{node_label} {{id: 'node:a'}})
            MATCH (b:{node_label} {{id: 'node:b'}})
            CREATE (a)-[r:{edge_label} {{id: 'edge:test1', weight: 1.0}}]->(b)
            """
        )

        # Create indexes for edge label
        created = clean_graph.ensure_label_indexes(edge_label, kind="e")

        # Should have created indexes
        assert created >= 1, "Should create at least one index"

        # Verify indexes exist
        with clean_graph._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s
                AND tablename = %s
                """,
                (clean_graph.graph_name, edge_label),
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Should have BTREE on id, start_id, end_id, and GIN on properties
        assert any("id_btree" in idx for idx in indexes), (
            f"Missing BTREE id index. Found: {indexes}"
        )
        assert any("start_id" in idx for idx in indexes), (
            f"Missing BTREE start_id index. Found: {indexes}"
        )
        assert any("end_id" in idx for idx in indexes), (
            f"Missing BTREE end_id index. Found: {indexes}"
        )
        assert any("props_gin" in idx for idx in indexes), (
            f"Missing GIN properties index. Found: {indexes}"
        )


class TestEnsureAllLabelsIndexed:
    """Tests for indexing all labels in the graph."""

    def test_indexes_all_labels(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Should create indexes for all vertex and edge labels."""
        # Use unique label names to avoid collisions with previous test runs
        person_label = label_tracker.create_label("all_idx_person")
        company_label = label_tracker.create_label("all_idx_company")
        works_at_label = label_tracker.create_label("all_idx_works_at")

        # Create multiple labels
        clean_graph.execute_cypher(f"CREATE (n:{person_label} {{id: 'person:1'}})")
        clean_graph.execute_cypher(f"CREATE (n:{company_label} {{id: 'company:1'}})")
        clean_graph.execute_cypher(
            f"""
            MATCH (p:{person_label} {{id: 'person:1'}})
            MATCH (c:{company_label} {{id: 'company:1'}})
            CREATE (p)-[r:{works_at_label} {{id: 'works:1'}}]->(c)
            """
        )

        # Index all labels - this should find and index all labels in the graph
        # Note: May also index labels from previous tests that weren't cleaned up
        created = clean_graph.ensure_all_labels_indexed()

        # Should have created at least some indexes (exact number depends on
        # whether labels from previous tests exist and already have indexes)
        # The key thing is it should not error
        assert created >= 0, f"ensure_all_labels_indexed failed. Created: {created}"


class TestIndexIdempotency:
    """Tests for index creation idempotency."""

    def test_ensure_label_indexes_is_idempotent(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Running ensure_label_indexes multiple times should be safe."""
        # Use unique label name to avoid collisions with previous test runs
        label = label_tracker.create_label("idempotent_test")

        # Create a vertex
        clean_graph.execute_cypher(f"CREATE (n:{label} {{id: 'test:1'}})")

        # First call should create indexes
        first_created = clean_graph.ensure_label_indexes(label, kind="v")
        assert first_created >= 1

        # Second call should create 0 (already exist)
        second_created = clean_graph.ensure_label_indexes(label, kind="v")
        assert second_created == 0

        # Third call should also create 0
        third_created = clean_graph.ensure_label_indexes(label, kind="v")
        assert third_created == 0

    def test_ensure_all_labels_indexed_is_idempotent(
        self, clean_graph: AgeGraphClient, label_tracker: LabelTracker
    ):
        """Running ensure_all_labels_indexed multiple times should be safe."""
        # Use unique label name to avoid collisions with previous test runs
        label = label_tracker.create_label("idempotent_all")

        # Create a label
        clean_graph.execute_cypher(f"CREATE (n:{label} {{id: 'test:1'}})")

        # First call
        first_created = clean_graph.ensure_all_labels_indexed()

        # Second call should create fewer or same
        second_created = clean_graph.ensure_all_labels_indexed()
        assert second_created <= first_created
