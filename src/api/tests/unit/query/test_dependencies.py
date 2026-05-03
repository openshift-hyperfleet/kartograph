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

    @patch("query.dependencies.get_age_connection_pool")
    @patch("query.dependencies.get_database_settings")
    def test_accepts_graph_name_override(self, mock_get_settings, mock_get_pool):
        """Should create client with the specified graph_name override.

        Spec: Per-Tenant Graph Routing → graph_name passed as tenant_{tenant_id}.
        """
        from graph.infrastructure.age_client import AgeGraphClient

        mock_get_pool.return_value = MagicMock()
        mock_get_settings.return_value = MagicMock()

        with mcp_graph_client_context(graph_name="tenant_test-tenant") as client:
            assert isinstance(client, AgeGraphClient)
            # Client must target the specified tenant graph
            assert client.graph_name == "tenant_test-tenant"


class TestGetMCPQueryService:
    """Tests for get_mcp_query_service dependency provider."""

    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_mcp_auth_context")
    def test_returns_mcp_query_service(
        self, mock_get_auth_context, mock_client_context
    ):
        """Should yield MCPQueryService instance with active connection."""
        from graph.infrastructure.age_client import AgeGraphClient
        from shared_kernel.middleware.mcp_auth import MCPAuthContext

        mock_get_auth_context.return_value = MCPAuthContext(
            user_id="user-1",
            tenant_id="tenant-xyz",
            api_key_id="key-1",
        )
        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)

        with get_mcp_query_service() as service:
            assert isinstance(service, MCPQueryService)
            assert service._repository is not None


class TestTenantGraphRouting:
    """Tests for per-tenant graph routing in dependency injection.

    Spec: Per-Tenant Graph Routing — the service factory MUST create a graph client
    targeting the authenticated tenant's AGE graph (tenant_{tenant_id}).
    """

    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_mcp_auth_context")
    def test_creates_client_with_tenant_graph_name(
        self, mock_get_auth_context, mock_client_context
    ):
        """Should create MCPQueryService targeting tenant_{tenant_id} AGE graph.

        Spec: Query routed to tenant graph → `tenant_{tenant_id}`.
        The dependency factory MUST pass `graph_name=f"tenant_{tenant_id}"` to
        the graph client context so the client is bound to the correct graph.
        """
        from graph.infrastructure.age_client import AgeGraphClient
        from shared_kernel.middleware.mcp_auth import MCPAuthContext

        tenant_id = "abc-def-123-xyz"
        mock_get_auth_context.return_value = MCPAuthContext(
            user_id="user-1",
            tenant_id=tenant_id,
            api_key_id="key-1",
        )
        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)

        with get_mcp_query_service():
            pass

        # The client context MUST be called with the tenant-specific graph name
        mock_client_context.assert_called_once_with(graph_name=f"tenant_{tenant_id}")

    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_mcp_auth_context")
    def test_tenant_routing_uses_auth_context_tenant_id(
        self, mock_get_auth_context, mock_client_context
    ):
        """Graph name must be derived from the auth context tenant_id, not hard-coded.

        Spec: AND queries never cross tenant boundaries regardless of query content.
        Each tenant gets their own isolated graph.
        """
        from graph.infrastructure.age_client import AgeGraphClient
        from shared_kernel.middleware.mcp_auth import MCPAuthContext

        # Test with a different tenant_id to prove it's dynamic
        tenant_id = "completely-different-tenant-777"
        mock_get_auth_context.return_value = MCPAuthContext(
            user_id="user-2",
            tenant_id=tenant_id,
            api_key_id="key-2",
        )
        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)

        with get_mcp_query_service():
            pass

        mock_client_context.assert_called_once_with(graph_name=f"tenant_{tenant_id}")
