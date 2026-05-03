"""Unit tests for Query context dependencies."""

from unittest.mock import MagicMock, patch

from query.application.services import MCPQueryService
from query.dependencies import get_mcp_query_service, mcp_graph_client_context
from shared_kernel.middleware.mcp_auth import MCPAuthContext, _mcp_auth_context_var


def _make_auth_context(tenant_id: str = "test-tenant") -> MCPAuthContext:
    """Build a minimal MCPAuthContext for tests."""
    return MCPAuthContext(
        user_id="user-001",
        tenant_id=tenant_id,
        api_key_id="key-001",
    )


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

    @patch("query.dependencies.AGEGraphExistenceChecker")
    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_age_connection_pool")
    @patch("query.dependencies.get_database_settings")
    def test_returns_mcp_query_service(
        self,
        mock_get_settings,
        mock_get_pool,
        mock_client_context,
        mock_existence_checker_cls,
    ):
        """Should yield MCPQueryService instance with active connection,
        scoped to the caller's tenant graph via TenantAwareQueryGraphRepository."""
        from graph.infrastructure.age_client import AgeGraphClient

        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_pool.return_value = MagicMock()
        mock_get_settings.return_value = MagicMock()
        mock_existence_checker_cls.return_value = MagicMock()

        # The service requires the MCP auth context to be set
        auth_ctx = _make_auth_context(tenant_id="test-tenant")
        token = _mcp_auth_context_var.set(auth_ctx)
        try:
            with get_mcp_query_service() as service:
                assert isinstance(service, MCPQueryService)
                assert service._repository is not None
        finally:
            _mcp_auth_context_var.reset(token)

    @patch("query.dependencies.AGEGraphExistenceChecker")
    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_age_connection_pool")
    @patch("query.dependencies.get_database_settings")
    def test_service_uses_tenant_graph(
        self,
        mock_get_settings,
        mock_get_pool,
        mock_client_context,
        mock_existence_checker_cls,
    ):
        """Should connect to tenant_{tenant_id} graph, not the default graph.

        Spec: Query routed to tenant graph → `tenant_{tenant_id}`.
        AND queries never cross tenant boundaries regardless of query content.
        """
        from graph.infrastructure.age_client import AgeGraphClient

        tenant_id = "my-tenant-xyz"
        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_pool.return_value = MagicMock()
        mock_get_settings.return_value = MagicMock()
        mock_existence_checker_cls.return_value = MagicMock()

        auth_ctx = _make_auth_context(tenant_id=tenant_id)
        token = _mcp_auth_context_var.set(auth_ctx)
        try:
            with get_mcp_query_service():
                pass
        finally:
            _mcp_auth_context_var.reset(token)

        # The client context should have been called with the tenant's graph name
        mock_client_context.assert_called_once_with(graph_name=f"tenant_{tenant_id}")

    @patch("query.dependencies.AGEGraphExistenceChecker")
    @patch("query.dependencies.mcp_graph_client_context")
    @patch("query.dependencies.get_age_connection_pool")
    @patch("query.dependencies.get_database_settings")
    def test_different_tenants_use_different_graphs(
        self,
        mock_get_settings,
        mock_get_pool,
        mock_client_context,
        mock_existence_checker_cls,
    ):
        """Each tenant must get a completely separate AGE graph.

        Spec: AND queries never cross tenant boundaries regardless of query content.
        """
        from graph.infrastructure.age_client import AgeGraphClient

        mock_client = MagicMock(spec=AgeGraphClient)
        mock_client_context.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_pool.return_value = MagicMock()
        mock_get_settings.return_value = MagicMock()
        mock_existence_checker_cls.return_value = MagicMock()

        # Test with a completely different tenant to prove routing is dynamic
        tenant_id = "completely-different-tenant-777"
        auth_ctx = _make_auth_context(tenant_id=tenant_id)
        token = _mcp_auth_context_var.set(auth_ctx)
        try:
            with get_mcp_query_service():
                pass
        finally:
            _mcp_auth_context_var.reset(token)

        mock_client_context.assert_called_once_with(graph_name=f"tenant_{tenant_id}")
