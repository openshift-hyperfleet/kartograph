"""Integration tests for graph indexing functionality.

These tests verify actual index creation against a real PostgreSQL/AGE instance.

Run with: pytest -m integration tests/integration/test_graph_indexing.py
Requires: Running PostgreSQL with AGE extension
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient


pytestmark = pytest.mark.integration


class TestVertexIndexCreation:
    """Tests for vertex label index creation."""

    def test_creates_indexes_for_vertex_label(self, clean_graph: AgeGraphClient):
        """Should create all recommended indexes for a vertex label."""
        # Create a vertex to establish the label
        clean_graph.execute_cypher(
            "CREATE (n:IndexTestPerson {id: 'person:test1', name: 'Alice'})"
        )

        # Create indexes
        created = clean_graph.ensure_label_indexes("indextestperson", kind="v")

        # Should have created indexes
        assert created >= 1, "Should create at least one index"

        # Verify indexes exist by querying pg_indexes
        with clean_graph._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s
                AND tablename = %s
                """,
                (clean_graph.graph_name, "indextestperson"),
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

    def test_indexes_improve_lookup_performance(self, clean_graph: AgeGraphClient):
        """Indexed lookups should use index scan (verify with EXPLAIN)."""
        # Create vertices
        for i in range(100):
            clean_graph.execute_cypher(
                f"CREATE (n:PerfTestPerson {{id: 'person:perf{i:03d}', name: 'Person{i}'}})"
            )

        # Create indexes
        clean_graph.ensure_label_indexes("perftestperson", kind="v")

        # Query should use index - we can't easily verify this in a unit test,
        # but we can at least verify the query works
        result = clean_graph.execute_cypher(
            "MATCH (n:PerfTestPerson {id: 'person:perf050'}) RETURN n"
        )
        assert result.row_count == 1


class TestEdgeIndexCreation:
    """Tests for edge label index creation."""

    def test_creates_indexes_for_edge_label(self, clean_graph: AgeGraphClient):
        """Should create all recommended indexes for an edge label."""
        # Create nodes and edge to establish the label
        clean_graph.execute_cypher(
            """
            CREATE (a:IndexTestNode {id: 'node:a'})
            CREATE (b:IndexTestNode {id: 'node:b'})
            """
        )
        clean_graph.execute_cypher(
            """
            MATCH (a:IndexTestNode {id: 'node:a'})
            MATCH (b:IndexTestNode {id: 'node:b'})
            CREATE (a)-[r:INDEX_TEST_EDGE {id: 'edge:test1', weight: 1.0}]->(b)
            """
        )

        # Create indexes for edge label
        created = clean_graph.ensure_label_indexes("index_test_edge", kind="e")

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
                (clean_graph.graph_name, "index_test_edge"),
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

    def test_indexes_all_labels(self, clean_graph: AgeGraphClient):
        """Should create indexes for all vertex and edge labels."""
        # Create multiple labels
        clean_graph.execute_cypher("CREATE (n:AllIdxPerson {id: 'person:1'})")
        clean_graph.execute_cypher("CREATE (n:AllIdxCompany {id: 'company:1'})")
        clean_graph.execute_cypher(
            """
            MATCH (p:AllIdxPerson {id: 'person:1'})
            MATCH (c:AllIdxCompany {id: 'company:1'})
            CREATE (p)-[r:ALL_IDX_WORKS_AT {id: 'works:1'}]->(c)
            """
        )

        # Index all labels
        created = clean_graph.ensure_all_labels_indexed()

        # Should have created indexes for all labels
        assert created >= 3, (
            f"Should create indexes for multiple labels. Created: {created}"
        )


class TestIndexIdempotency:
    """Tests for index creation idempotency."""

    def test_ensure_label_indexes_is_idempotent(self, clean_graph: AgeGraphClient):
        """Running ensure_label_indexes multiple times should be safe."""
        # Create a vertex
        clean_graph.execute_cypher("CREATE (n:IdempotentTest {id: 'test:1'})")

        # First call should create indexes
        first_created = clean_graph.ensure_label_indexes("idempotenttest", kind="v")
        assert first_created >= 1

        # Second call should create 0 (already exist)
        second_created = clean_graph.ensure_label_indexes("idempotenttest", kind="v")
        assert second_created == 0

        # Third call should also create 0
        third_created = clean_graph.ensure_label_indexes("idempotenttest", kind="v")
        assert third_created == 0

    def test_ensure_all_labels_indexed_is_idempotent(self, clean_graph: AgeGraphClient):
        """Running ensure_all_labels_indexed multiple times should be safe."""
        # Create some labels
        clean_graph.execute_cypher("CREATE (n:IdempotentAll {id: 'test:1'})")

        # First call
        first_created = clean_graph.ensure_all_labels_indexed()

        # Second call should create fewer or same
        second_created = clean_graph.ensure_all_labels_indexed()
        assert second_created <= first_created
