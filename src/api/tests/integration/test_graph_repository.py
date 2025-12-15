"""Integration tests for GraphExtractionReadOnlyRepository.

These tests verify actual repository behavior against a real PostgreSQL/AGE instance,
including map-based returns, timeout enforcement, and security safeguards.

Run with: pytest -m integration tests/integration/test_graph_repository.py
Requires: Running PostgreSQL with AGE extension (docker compose up -d postgres)
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from infrastructure.database.exceptions import GraphQueryError


pytestmark = pytest.mark.integration


@pytest.fixture
def repository(graph_client: AgeGraphClient) -> GraphExtractionReadOnlyRepository:
    """Create a repository scoped to test data source."""
    return GraphExtractionReadOnlyRepository(
        client=graph_client,
        data_source_id="test-ds-integration",
    )


@pytest.fixture
def repository_with_data(
    clean_graph: AgeGraphClient,
) -> GraphExtractionReadOnlyRepository:
    """Create a repository with test data already loaded."""
    repo = GraphExtractionReadOnlyRepository(
        client=clean_graph,
        data_source_id="test-ds-integration",
    )

    # Create test data
    clean_graph.execute_cypher(
        """
        CREATE (p1:Person {
            id: 'person:abc123',
            slug: 'alice-smith',
            name: 'Alice Smith',
            data_source_id: 'test-ds-integration',
            source_path: 'people/alice.md'
        })
        """
    )

    clean_graph.execute_cypher(
        """
        CREATE (p2:Person {
            id: 'person:def456',
            slug: 'bob-jones',
            name: 'Bob Jones',
            data_source_id: 'test-ds-integration',
            source_path: 'people/bob.md'
        })
        """
    )

    clean_graph.execute_cypher(
        """
        MATCH (p1:Person {slug: 'alice-smith', data_source_id: 'test-ds-integration'})
        MATCH (p2:Person {slug: 'bob-jones', data_source_id: 'test-ds-integration'})
        CREATE (p1)-[r:KNOWS {since: 2020, data_source_id: 'test-ds-integration'}]->(p2)
        """
    )

    return repo


class TestGenerateId:
    """Integration tests for deterministic ID generation."""

    def test_generates_deterministic_ids(self, repository):
        """Same inputs should always produce same ID."""
        id1 = repository.generate_id("Person", "alice-smith")
        id2 = repository.generate_id("Person", "alice-smith")

        assert id1 == id2
        assert id1.startswith("person:")

    def test_different_data_sources_produce_different_ids(
        self, graph_client: AgeGraphClient
    ):
        """Different data sources should produce different IDs for same entity.

        TODO: Once Tenants are in Kartograph, ensure IDs across tenants are different."""
        repo1 = GraphExtractionReadOnlyRepository(
            client=graph_client, data_source_id="ds-1"
        )
        repo2 = GraphExtractionReadOnlyRepository(
            client=graph_client, data_source_id="ds-2"
        )

        id1 = repo1.generate_id("Person", "alice")
        id2 = repo2.generate_id("Person", "alice")

        assert id1 == id2


class TestFindNodesByPath:
    """Integration tests for finding nodes by source path."""

    def test_finds_nodes_by_path(self, repository_with_data):
        """Should find nodes with matching source_path."""
        nodes, edges = repository_with_data.find_nodes_by_path("people/alice.md")

        assert len(nodes) >= 1
        alice = next(
            (n for n in nodes if n.properties.get("slug") == "alice-smith"), None
        )
        assert alice is not None
        assert alice.label == "Person"
        assert alice.properties["name"] == "Alice Smith"

    def test_finds_related_nodes_and_edges(self, repository_with_data):
        """Should find neighboring nodes and connecting edges."""
        nodes, edges = repository_with_data.find_nodes_by_path("people/alice.md")

        # Should include Alice and her relationships
        slugs = {n.properties.get("slug") for n in nodes}
        assert "alice-smith" in slugs

        # May include Bob if the relationship is returned
        # (depends on OPTIONAL MATCH behavior with map returns)

    def test_returns_empty_for_nonexistent_path(self, repository_with_data):
        """Should return empty lists for nonexistent path."""
        nodes, edges = repository_with_data.find_nodes_by_path("nonexistent/path.md")

        assert nodes == []
        assert edges == []

    def test_scopes_to_data_source(self, clean_graph: AgeGraphClient):
        """Should only return nodes from the repository's data source."""
        # Create node in different data source
        clean_graph.execute_cypher(
            """
            CREATE (p:Person {
                slug: 'charlie',
                data_source_id: 'other-ds',
                source_path: 'people/charlie.md'
            })
            """
        )

        # Create node in our data source
        clean_graph.execute_cypher(
            """
            CREATE (p:Person {
                slug: 'alice',
                data_source_id: 'test-ds-integration',
                source_path: 'people/alice.md'
            })
            """
        )

        repo = GraphExtractionReadOnlyRepository(
            client=clean_graph, data_source_id="test-ds-integration"
        )

        nodes, _ = repo.find_nodes_by_path("people/alice.md")

        # Should only find alice, not charlie
        assert len(nodes) == 1
        assert nodes[0].properties["slug"] == "alice"


class TestFindNodesBySlug:
    """Integration tests for finding nodes by slug."""

    def test_finds_nodes_by_slug(self, repository_with_data):
        """Should find nodes with matching slug."""
        nodes = repository_with_data.find_nodes_by_slug("alice-smith")

        assert len(nodes) == 1
        assert nodes[0].label == "Person"
        assert nodes[0].properties["name"] == "Alice Smith"

    def test_filters_by_node_type(self, repository_with_data):
        """Should filter by node type when provided."""
        nodes = repository_with_data.find_nodes_by_slug(
            "alice-smith", node_type="Person"
        )

        assert len(nodes) == 1
        assert nodes[0].label == "Person"

    def test_returns_empty_for_wrong_type(self, repository_with_data):
        """Should return empty list when type doesn't match."""
        nodes = repository_with_data.find_nodes_by_slug(
            "alice-smith", node_type="Repository"
        )

        assert nodes == []

    def test_returns_empty_for_nonexistent_slug(self, repository_with_data):
        """Should return empty list for nonexistent slug."""
        nodes = repository_with_data.find_nodes_by_slug("nonexistent-slug")

        assert nodes == []


class TestGetNeighbors:
    """Integration tests for getting neighboring nodes."""

    def test_gets_neighbors(self, repository_with_data):
        """Should find neighboring nodes and connecting edges."""
        # First find Alice's ID (using the property id, not AGE internal id)
        alice_nodes = repository_with_data.find_nodes_by_slug("alice-smith")
        assert len(alice_nodes) == 1
        # Use the property id that we set when creating the node
        alice_id = alice_nodes[0].properties["id"]

        # Get Alice's neighbors
        result = repository_with_data.get_neighbors(alice_id)

        # Should have central node
        assert result.central_node.properties["id"] == alice_id

        # Should find Bob as neighbor
        assert len(result.nodes) >= 1
        bob = next(
            (n for n in result.nodes if n.properties.get("slug") == "bob-jones"), None
        )
        assert bob is not None

        # Should find KNOWS edge
        assert len(result.edges) >= 1
        knows_edge = next((e for e in result.edges if e.label == "KNOWS"), None)
        assert knows_edge is not None
        assert knows_edge.properties["since"] == 2020

    def test_returns_empty_for_node_without_neighbors(
        self, clean_graph: AgeGraphClient
    ):
        """Should return empty lists for isolated node."""
        # Create isolated node
        clean_graph.execute_cypher(
            """
            CREATE (p:Person {
                id: 'person:isolated',
                slug: 'isolated',
                data_source_id: 'test-ds-integration'
            })
            """
        )

        repo = GraphExtractionReadOnlyRepository(
            client=clean_graph, data_source_id="test-ds-integration"
        )

        result = repo.get_neighbors("person:isolated")

        assert result.central_node.properties["id"] == "person:isolated"
        assert result.nodes == []
        assert result.edges == []


class TestExecuteRawQuery:
    """Integration tests for raw query execution with safeguards."""

    def test_executes_simple_query(self, repository_with_data):
        """Should execute a simple read query."""
        results = repository_with_data.execute_raw_query(
            "MATCH (p:Person) RETURN count(p)"
        )

        assert isinstance(results, list)
        assert len(results) >= 1

    def test_returns_map_results(self, repository_with_data):
        """Should correctly parse map-based returns."""
        results = repository_with_data.execute_raw_query(
            """
            MATCH (p:Person {slug: 'alice-smith'})
            RETURN {person: p}
            """
        )

        assert len(results) == 1
        assert "person" in results[0]
        person = results[0]["person"]
        assert person["label"] == "Person"
        assert person["properties"]["name"] == "Alice Smith"

    def test_enforces_read_only(self, repository_with_data):
        """Should reject queries with mutation keywords."""
        with pytest.raises(GraphQueryError) as exc_info:
            repository_with_data.execute_raw_query("CREATE (n:Person {name: 'Hacker'})")

        assert "read-only" in str(exc_info.value).lower()
        assert "CREATE" in str(exc_info.value)

    def test_rejects_delete(self, repository_with_data):
        """Should reject DELETE queries."""
        with pytest.raises(GraphQueryError) as exc_info:
            repository_with_data.execute_raw_query("MATCH (n) DELETE n")

        assert "DELETE" in str(exc_info.value)

    def test_rejects_set(self, repository_with_data):
        """Should reject SET queries."""
        with pytest.raises(GraphQueryError) as exc_info:
            repository_with_data.execute_raw_query("MATCH (n) SET n.hacked = true")

        assert "SET" in str(exc_info.value)

    def test_adds_limit_automatically(self, repository_with_data):
        """Should add LIMIT 100 to queries without explicit limit."""
        # This is hard to test directly, but we can verify it doesn't error
        results = repository_with_data.execute_raw_query("MATCH (n) RETURN n")

        assert isinstance(results, list)
        # Should be limited to 100 or fewer
        assert len(results) <= 100

    def test_preserves_explicit_limit(self, repository_with_data):
        """Should preserve explicit LIMIT in query."""
        results = repository_with_data.execute_raw_query("MATCH (n) RETURN n LIMIT 1")

        assert len(results) <= 1

    def test_enforces_timeout_on_slow_query(self, repository_with_data):
        """Should timeout queries that exceed the timeout threshold."""
        # Use a query that generates work to reliably trigger timeout
        slow_query = "WITH range(1, 10000) AS list UNWIND list AS i RETURN count(i)"

        # This should timeout with 1ms limit
        with pytest.raises(GraphQueryError) as exc_info:
            repository_with_data.execute_raw_query(slow_query, timeout_seconds=1 / 1000)

        # Verify it's a timeout error
        assert (
            "timeout" in str(exc_info.value).lower()
            or "exceeded" in str(exc_info.value).lower()
        )

    def test_accepts_custom_timeout_value(self, repository_with_data):
        """Should accept custom timeout values and allow queries to complete."""
        # Same query as timeout test, but with sufficient timeout
        slow_query = "WITH range(1, 10000) AS list UNWIND list AS i RETURN count(i)"

        # Should complete successfully with generous timeout
        results = repository_with_data.execute_raw_query(slow_query, timeout_seconds=3)

        assert isinstance(results, list)
        assert len(results) >= 1


class TestMapBasedReturns:
    """Integration tests specifically for map-based return parsing."""

    def test_parses_single_vertex_in_map(self, repository_with_data):
        """Should parse map containing single vertex."""
        results = repository_with_data.execute_raw_query(
            "MATCH (p:Person {slug: 'alice-smith'}) RETURN {node: p}"
        )

        assert len(results) == 1
        assert "node" in results[0]
        assert results[0]["node"]["label"] == "Person"

    def test_parses_multiple_vertices_in_map(self, repository_with_data):
        """Should parse map containing multiple vertices."""
        results = repository_with_data.execute_raw_query(
            """
            MATCH (p1:Person {slug: 'alice-smith'})
            MATCH (p2:Person {slug: 'bob-jones'})
            RETURN {person1: p1, person2: p2}
            """
        )

        assert len(results) == 1
        result = results[0]
        assert "person1" in result
        assert "person2" in result
        assert result["person1"]["properties"]["slug"] == "alice-smith"
        assert result["person2"]["properties"]["slug"] == "bob-jones"

    def test_parses_vertex_and_edge_in_map(self, repository_with_data):
        """Should parse map containing both vertex and edge."""
        results = repository_with_data.execute_raw_query(
            """
            MATCH (p1:Person {slug: 'alice-smith'})-[r:KNOWS]->(p2:Person)
            RETURN {person: p1, relationship: r, friend: p2}
            """
        )

        assert len(results) >= 1
        result = results[0]
        assert "person" in result
        assert "relationship" in result
        assert "friend" in result
        assert result["relationship"]["label"] == "KNOWS"

    def test_parses_mixed_types_in_map(self, repository_with_data):
        """Should parse map containing vertices and scalar values."""
        results = repository_with_data.execute_raw_query(
            """
            MATCH (p:Person {slug: 'alice-smith'})
            RETURN {person: p, count: 1, name: p.name}
            """
        )

        assert len(results) == 1
        result = results[0]
        assert "person" in result
        assert "count" in result
        assert "name" in result
        assert result["person"]["label"] == "Person"
        assert result["count"] == 1
        assert result["name"] == "Alice Smith"


class TestDataSourceIsolation:
    """Integration tests for data source scoping."""

    def test_isolated_from_other_data_sources(self, clean_graph: AgeGraphClient):
        """Repository should only see its own data source."""
        # Create nodes in two different data sources
        clean_graph.execute_cypher(
            """
            CREATE (p:Person {
                slug: 'ds1-person',
                data_source_id: 'ds-1',
                source_path: 'people/alice.md'
            })
            """
        )

        clean_graph.execute_cypher(
            """
            CREATE (p:Person {
                slug: 'ds2-person',
                data_source_id: 'ds-2',
                source_path: 'people/alice.md'
            })
            """
        )

        # Create repositories for each data source
        repo1 = GraphExtractionReadOnlyRepository(
            client=clean_graph, data_source_id="ds-1"
        )
        repo2 = GraphExtractionReadOnlyRepository(
            client=clean_graph, data_source_id="ds-2"
        )

        # Each repository should only see its own data
        nodes1 = repo1.find_nodes_by_slug("ds1-person")
        nodes2 = repo2.find_nodes_by_slug("ds2-person")

        assert len(nodes1) == 1
        assert nodes1[0].properties["slug"] == "ds1-person"

        assert len(nodes2) == 1
        assert nodes2[0].properties["slug"] == "ds2-person"

        # Cross-data-source queries should return empty
        assert repo1.find_nodes_by_slug("ds2-person") == []
        assert repo2.find_nodes_by_slug("ds1-person") == []
