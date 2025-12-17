"""Integration tests for MCP query functionality.

Tests the full stack from MCPQueryService through QueryGraphRepository
to the actual database.

Run with: pytest -m integration tests/integration/test_query_mcp.py
Requires: Running PostgreSQL with AGE extension (docker compose up -d postgres)
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from query.application.services import MCPQueryService
from query.domain.value_objects import (
    CypherQueryResult,
    QueryError,
    QueryExecutionError,
    QueryForbiddenError,
)
from query.infrastructure.query_repository import QueryGraphRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def repository(graph_client: AgeGraphClient) -> QueryGraphRepository:
    """Create query repository."""
    return QueryGraphRepository(client=graph_client)


@pytest.fixture
def service(repository: QueryGraphRepository) -> MCPQueryService:
    """Create MCP query service."""
    return MCPQueryService(repository=repository)


@pytest.fixture
def repository_with_data(clean_graph: AgeGraphClient) -> QueryGraphRepository:
    """Create repository with test data."""
    repo = QueryGraphRepository(client=clean_graph)

    # Create test nodes with varied data
    clean_graph.execute_cypher(
        """
        CREATE (p1:Person {
            name: 'Alice',
            role: 'Engineer',
            data_source_id: 'source-1'
        })
        """
    )
    clean_graph.execute_cypher(
        """
        CREATE (p2:Person {
            name: 'Bob',
            role: 'Manager',
            data_source_id: 'source-1'
        })
        """
    )
    clean_graph.execute_cypher(
        """
        CREATE (p3:Person {
            name: 'Charlie',
            role: 'Designer',
            data_source_id: 'source-2'
        })
        """
    )
    clean_graph.execute_cypher(
        """
        MATCH (a:Person {name: 'Alice'})
        MATCH (b:Person {name: 'Bob'})
        CREATE (a)-[:REPORTS_TO {since: 2020}]->(b)
        """
    )

    return repo


@pytest.fixture
def service_with_data(repository_with_data: QueryGraphRepository) -> MCPQueryService:
    """Create service with test data."""
    return MCPQueryService(repository=repository_with_data)


class TestQueryGraphRepository:
    """Tests for QueryGraphRepository against real database."""

    def test_executes_simple_query(self, repository_with_data):
        """Should execute simple queries successfully."""
        results = repository_with_data.execute_cypher("MATCH (p:Person) RETURN p")

        assert len(results) == 3

    def test_returns_unscoped_results(self, repository_with_data):
        """Should return nodes from ALL data sources (unscoped)."""
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person) RETURN {name: p.name, data_source_id: p.data_source_id}"
        )

        # Should see all 3 people across both data sources
        assert len(results) == 3
        # Verify we see both data sources
        sources = [row.get("data_source_id") for row in results]
        assert "source-1" in sources
        assert "source-2" in sources

    def test_enforces_read_only(self, repository):
        """Should reject mutation queries."""
        with pytest.raises(QueryForbiddenError) as exc_info:
            repository.execute_cypher("CREATE (n:Test)")

        assert "read-only" in str(exc_info.value).lower()

    def test_auto_adds_limit(self, repository_with_data):
        """Should automatically add LIMIT to queries."""
        # Query without LIMIT should still work and be limited
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person) RETURN p", max_rows=2
        )

        # Should be limited to 2 even though 3 exist
        assert len(results) <= 2

    def test_respects_explicit_limit(self, repository_with_data):
        """Should respect explicit LIMIT in query."""
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person) RETURN p LIMIT 1"
        )

        assert len(results) == 1

    def test_handles_aggregations(self, repository_with_data):
        """Should handle aggregation queries."""
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person) RETURN count(p)"
        )

        assert len(results) == 1
        assert results[0]["value"] == 3

    def test_handles_map_returns(self, repository_with_data):
        """Should handle queries returning maps (Apache AGE requirement)."""
        results = repository_with_data.execute_cypher(
            """
            MATCH (a:Person)-[r:REPORTS_TO]->(b:Person)
            RETURN {source: a, relationship: r, target: b}
            """
        )

        assert len(results) == 1
        assert "source" in results[0]
        assert "relationship" in results[0]
        assert "target" in results[0]

    def test_timeout_enforcement(self, repository):
        """Should timeout slow queries."""
        # This query should be slow enough to timeout at 1ms
        slow_query = """
            WITH range(1, 100000) AS r
            UNWIND r AS i
            RETURN count(i)
        """

        with pytest.raises(QueryExecutionError) as exc_info:
            repository.execute_cypher(slow_query, timeout_seconds=0.001)

        error_msg = str(exc_info.value).lower()
        assert (
            "timeout" in error_msg or "exceeded" in error_msg or "failed" in error_msg
        )


class TestMCPQueryService:
    """Tests for MCPQueryService against real database."""

    def test_execute_cypher_query_success(self, service_with_data):
        """Should execute queries and return CypherQueryResult."""
        result = service_with_data.execute_cypher_query("MATCH (p:Person) RETURN p")

        assert isinstance(result, CypherQueryResult)
        assert result.row_count == 3
        assert result.truncated is False
        assert result.execution_time_ms is not None

    def test_execute_cypher_query_with_limit(self, service_with_data):
        """Should respect max_rows parameter."""
        result = service_with_data.execute_cypher_query(
            "MATCH (p:Person) RETURN p", max_rows=2
        )

        assert isinstance(result, CypherQueryResult)
        assert result.row_count <= 2

    def test_execute_cypher_query_marks_truncation(self, service_with_data):
        """Should mark results as truncated when at limit."""
        result = service_with_data.execute_cypher_query(
            "MATCH (p:Person) RETURN p", max_rows=3
        )

        # Exactly 3 results, should be marked as truncated
        assert result.row_count == 3
        assert result.truncated is True

    def test_execute_cypher_query_forbidden_error(self, service):
        """Should return QueryError for mutation attempts."""
        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.error_type == "forbidden"
        assert "read-only" in result.message.lower() or "CREATE" in result.message

    def test_execute_cypher_query_timeout_error(self, service):
        """Should return QueryError for timeouts."""
        slow_query = """
            WITH range(1, 100000) AS r
            UNWIND r AS i
            RETURN count(i)
        """
        result = service.execute_cypher_query(slow_query, timeout_seconds=0.001)

        assert isinstance(result, QueryError)
        assert result.error_type in ["timeout", "execution_error"]

    def test_execute_cypher_query_tracks_time(self, service_with_data):
        """Should track execution time."""
        result = service_with_data.execute_cypher_query("MATCH (p:Person) RETURN p")

        assert isinstance(result, CypherQueryResult)
        assert result.execution_time_ms is not None
        assert result.execution_time_ms > 0

    def test_execute_cypher_query_custom_timeout(self, service_with_data):
        """Should use custom timeout when specified."""
        result = service_with_data.execute_cypher_query(
            "MATCH (p:Person) RETURN p", timeout_seconds=10
        )

        assert isinstance(result, CypherQueryResult)

    def test_unscoped_access_sees_all_data_sources(self, service_with_data):
        """Should see data from all data sources (unscoped)."""
        result = service_with_data.execute_cypher_query(
            """
            MATCH (p:Person)
            RETURN p.data_source_id
            """
        )

        assert isinstance(result, CypherQueryResult)
        # Should see both source-1 and source-2
        sources = [row.get("value") for row in result.rows]
        assert "source-1" in sources
        assert "source-2" in sources


class TestApacheAGEConstraints:
    """Tests specific to Apache AGE single-column return requirement."""

    def test_single_node_return(self, repository_with_data):
        """Should handle single node returns."""
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person {name: 'Alice'}) RETURN p"
        )

        assert len(results) == 1
        assert "node" in results[0]
        assert results[0]["node"]["properties"]["name"] == "Alice"

    def test_single_value_return(self, repository_with_data):
        """Should handle single value returns."""
        results = repository_with_data.execute_cypher(
            "MATCH (p:Person) RETURN count(p)"
        )

        assert len(results) == 1
        assert "value" in results[0]
        assert results[0]["value"] == 3

    def test_map_return_with_multiple_values(self, repository_with_data):
        """Should handle map returns with multiple values."""
        results = repository_with_data.execute_cypher(
            """
            MATCH (p:Person {name: 'Alice'})
            RETURN {name: p.name, role: p.role}
            """
        )

        assert len(results) == 1
        assert results[0]["name"] == "Alice"
        assert results[0]["role"] == "Engineer"

    def test_map_return_with_nodes_and_edges(self, repository_with_data):
        """Should handle map returns mixing nodes and edges."""
        results = repository_with_data.execute_cypher(
            """
            MATCH (a:Person {name: 'Alice'})-[r:REPORTS_TO]->(b:Person)
            RETURN {employee: a, reports_to: r, manager: b}
            """
        )

        assert len(results) == 1
        assert "employee" in results[0]
        assert "reports_to" in results[0]
        assert "manager" in results[0]
        assert results[0]["employee"]["properties"]["name"] == "Alice"
        assert results[0]["manager"]["properties"]["name"] == "Bob"
