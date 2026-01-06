"""Unit tests for Query context dependencies."""

from unittest.mock import create_autospec


from infrastructure.database.connection_pool import ConnectionPool
from query.application.services import MCPQueryService
from query.dependencies import get_mcp_graph_client, get_mcp_query_service


class TestGetMCPGraphClient:
    """Tests for get_mcp_graph_client dependency provider."""

    def test_returns_connected_client(self):
        """Should return connected AgeGraphClient."""
        from graph.infrastructure.age_client import AgeGraphClient

        mock_pool = create_autospec(ConnectionPool, instance=True)
        client_gen = get_mcp_graph_client(pool=mock_pool)

        client = next(client_gen)

        assert isinstance(client, AgeGraphClient)
        assert client.is_connected()

        # Cleanup
        try:
            next(client_gen)
        except StopIteration:
            pass


class TestGetMCPQueryService:
    """Tests for get_mcp_query_service dependency provider."""

    def test_returns_mcp_query_service(self):
        """Should return MCPQueryService instance."""
        from graph.infrastructure.age_client import AgeGraphClient
        from query.application.observability import QueryServiceProbe

        mock_client = create_autospec(AgeGraphClient, instance=True)
        mock_probe = create_autospec(QueryServiceProbe, instance=True)

        result = get_mcp_query_service(client=mock_client, probe=mock_probe)

        assert isinstance(result, MCPQueryService)
        assert result._repository is not None
