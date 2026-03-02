"""MCP authentication context value object and ContextVar accessor.

This module contains the pure value object that represents an authenticated
MCP request context. It is framework-agnostic and contains no business logic,
making it safe for the shared kernel.

The actual authentication logic (API key validation) lives in the ASGI
middleware that sets this context.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPAuthContext:
    """Authenticated MCP request context.

    This is a shared kernel value object used by the MCP middleware
    to carry the authenticated identity into tool execution.

    Attributes:
        user_id: The user who owns the API key.
        tenant_id: The tenant the API key belongs to.
        api_key_id: The unique identifier of the validated API key.
    """

    user_id: str
    tenant_id: str
    api_key_id: str


_mcp_auth_context_var: ContextVar[MCPAuthContext] = ContextVar(
    "mcp_auth_context",
)


def get_mcp_auth_context() -> MCPAuthContext:
    """Get the current MCP auth context from the ContextVar.

    Returns:
        The MCPAuthContext set by the authentication middleware.

    Raises:
        LookupError: If no MCPAuthContext has been set (i.e., the
            middleware has not run or the request is unauthenticated).
    """
    try:
        return _mcp_auth_context_var.get()
    except LookupError:
        raise LookupError(
            "MCPAuthContext not set. Ensure the MCP API key "
            "authentication middleware has run before accessing this."
        )
