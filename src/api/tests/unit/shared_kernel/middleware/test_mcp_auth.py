"""Unit tests for MCPAuthContext value object, ContextVar accessor, and probe.

Tests the pure value object and ContextVar from the shared kernel,
plus the domain probe protocol and default implementation for MCP
API key authentication.
"""

from __future__ import annotations

import contextvars

import pytest

from shared_kernel.middleware.mcp_auth import (
    MCPAuthContext,
    get_mcp_auth_context,
    _mcp_auth_context_var,
)
from shared_kernel.middleware.observability.mcp_auth_probe import (
    DefaultMCPAuthProbe,
    MCPAuthProbe,
)


class TestMCPAuthContext:
    """Tests for the MCPAuthContext value object."""

    def test_is_frozen_dataclass(self) -> None:
        """MCPAuthContext should be a frozen dataclass."""
        ctx = MCPAuthContext(
            user_id="user-123",
            tenant_id="tenant-456",
            api_key_id="key-789",
        )
        with pytest.raises(AttributeError):
            ctx.user_id = "something-else"  # type: ignore[misc]

    def test_stores_all_fields(self) -> None:
        """MCPAuthContext should store user_id, tenant_id, api_key_id."""
        ctx = MCPAuthContext(
            user_id="user-123",
            tenant_id="tenant-456",
            api_key_id="key-789",
        )
        assert ctx.user_id == "user-123"
        assert ctx.tenant_id == "tenant-456"
        assert ctx.api_key_id == "key-789"

    def test_equality(self) -> None:
        """Two MCPAuthContext instances with same values should be equal."""
        a = MCPAuthContext(user_id="u", tenant_id="t", api_key_id="k")
        b = MCPAuthContext(user_id="u", tenant_id="t", api_key_id="k")
        assert a == b

    def test_inequality(self) -> None:
        """Two MCPAuthContext instances with different values should not be equal."""
        a = MCPAuthContext(user_id="u1", tenant_id="t", api_key_id="k")
        b = MCPAuthContext(user_id="u2", tenant_id="t", api_key_id="k")
        assert a != b


class TestGetMCPAuthContext:
    """Tests for the get_mcp_auth_context() ContextVar accessor."""

    def test_returns_context_when_set(self) -> None:
        """get_mcp_auth_context() should return the context when set."""
        ctx = MCPAuthContext(
            user_id="user-123",
            tenant_id="tenant-456",
            api_key_id="key-789",
        )
        token = _mcp_auth_context_var.set(ctx)
        try:
            result = get_mcp_auth_context()
            assert result == ctx
        finally:
            _mcp_auth_context_var.reset(token)

    def test_raises_when_not_set(self) -> None:
        """get_mcp_auth_context() should raise LookupError when not set."""
        # Run in a fresh context to ensure the var is not set
        new_ctx = contextvars.copy_context()

        def _check():
            with pytest.raises(LookupError, match="MCPAuthContext"):
                get_mcp_auth_context()

        new_ctx.run(_check)


class TestDefaultMCPAuthProbe:
    """Tests for the DefaultMCPAuthProbe implementation."""

    def test_conforms_to_protocol(self) -> None:
        """DefaultMCPAuthProbe should conform to MCPAuthProbe protocol."""
        probe = DefaultMCPAuthProbe()
        assert isinstance(probe, MCPAuthProbe)

    def test_all_methods_are_callable(self) -> None:
        """All protocol methods should be callable."""
        probe = DefaultMCPAuthProbe()
        assert callable(probe.mcp_auth_succeeded)
        assert callable(probe.mcp_auth_missing_api_key)
        assert callable(probe.mcp_auth_invalid_api_key)

    def test_methods_do_not_raise(self) -> None:
        """All probe methods should execute without raising exceptions."""
        probe = DefaultMCPAuthProbe()
        probe.mcp_auth_succeeded(
            user_id="user-123",
            tenant_id="tenant-456",
            api_key_id="key-789",
        )
        probe.mcp_auth_missing_api_key()
        probe.mcp_auth_invalid_api_key()
