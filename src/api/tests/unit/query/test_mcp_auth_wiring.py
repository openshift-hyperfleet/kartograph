"""Unit tests for MCP API key authentication wiring.

Tests that the MCP HTTP app is wrapped with the MCPApiKeyAuthMiddleware
and that authentication is enforced at the ASGI layer.
"""

from __future__ import annotations


from shared_kernel.middleware.mcp_api_key_auth import MCPApiKeyAuthMiddleware


class TestMCPAppHasAuthMiddleware:
    """Tests that the MCP HTTP app is wrapped with auth middleware."""

    def test_query_mcp_app_is_wrapped_with_auth_middleware(self) -> None:
        """The query_mcp_app should be an MCPApiKeyAuthMiddleware wrapping the MCP app."""
        from query.presentation.mcp import query_mcp_app

        assert isinstance(query_mcp_app, MCPApiKeyAuthMiddleware)
