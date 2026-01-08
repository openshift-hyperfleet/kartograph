"""Unit tests for Query context dependencies."""

from unittest.mock import MagicMock, patch

from query.application.services import MCPQueryService
from query.dependencies import get_mcp_query_service, mcp_graph_client_context


class TestMCPGraphClientContext:
    """Tests for mcp_graph_client_context context manager."""

    @patch("query.dependencies.get_age_connection_pool")
    @patch("query.dependencies.get_database_settings")
    def test_returns_connected_client(self, mock_get_settings, mock_get_pool):
        """Should yield connected AgeGraphClient and disconnect on exit."""
        from graph.infrastructure.age_client import AgeGraphClient

        mock_get_pool.return_value = MagicMock()
        mock_get_settings.return_value = MagicMock()

        with mcp_graph_client_context() as client:
            assert isinstance(client, AgeGraphClient)
            assert client.is_connected()

        # After context exit, client should be disconnected
        assert not client.is_connected()


class TestGetMCPQueryService:
    """Tests for get_mcp_query_service dependency provider."""

    @patch("query.dependencies.mcp_graph_client_context")
    def test_returns_mcp_query_service(self, mock_client_context):
        """Should yield MCPQueryService instance with active connection."""
        from graph.infrastructure.age_client import AgeGraphClient

        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)

        with get_mcp_query_service() as service:
            assert isinstance(service, MCPQueryService)
            assert service._repository is not None
