"""Domain probe for MCP API key authentication.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to MCP API key authentication.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog


@runtime_checkable
class MCPAuthProbe(Protocol):
    """Domain probe for MCP API key authentication operations."""

    def mcp_auth_succeeded(
        self,
        user_id: str,
        tenant_id: str,
        api_key_id: str,
    ) -> None:
        """Record that MCP authentication succeeded via API key."""
        ...

    def mcp_auth_missing_api_key(self) -> None:
        """Record that an MCP request was missing the X-API-Key header."""
        ...

    def mcp_auth_invalid_api_key(self) -> None:
        """Record that an MCP request had an invalid or expired API key."""
        ...


class DefaultMCPAuthProbe:
    """Default implementation of MCPAuthProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ):
        self._logger = logger or structlog.get_logger()

    def mcp_auth_succeeded(
        self,
        user_id: str,
        tenant_id: str,
        api_key_id: str,
    ) -> None:
        """Record that MCP authentication succeeded via API key."""
        self._logger.debug(
            "mcp_auth_succeeded",
            user_id=user_id,
            tenant_id=tenant_id,
            api_key_id=api_key_id,
        )

    def mcp_auth_missing_api_key(self) -> None:
        """Record that an MCP request was missing the X-API-Key header."""
        self._logger.warning(
            "mcp_auth_missing_api_key",
            message="X-API-Key header is required for MCP access",
        )

    def mcp_auth_invalid_api_key(self) -> None:
        """Record that an MCP request had an invalid or expired API key."""
        self._logger.warning(
            "mcp_auth_invalid_api_key",
            message="Invalid or expired API key",
        )
