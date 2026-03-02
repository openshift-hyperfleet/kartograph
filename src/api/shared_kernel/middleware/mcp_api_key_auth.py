"""ASGI middleware for MCP API key authentication.

Validates X-API-Key headers on incoming MCP requests and sets
MCPAuthContext in a ContextVar for downstream tool functions.

This middleware is framework-agnostic (pure ASGI) and accepts a
validation callable to avoid direct imports from the IAM bounded context.
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import Any, Awaitable, Callable, Protocol

from shared_kernel.middleware.mcp_auth import MCPAuthContext, _mcp_auth_context_var
from shared_kernel.middleware.observability.mcp_auth_probe import (
    DefaultMCPAuthProbe,
    MCPAuthProbe,
)


# ---------------------------------------------------------------------------
# Type aliases for ASGI (using MutableMapping to match Starlette's types)
# ---------------------------------------------------------------------------

ASGIReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
ASGISend = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[MutableMapping[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


class _ValidatedKey(Protocol):
    """Protocol for the validated API key object.

    The middleware only needs these three fields from the validated key.
    This keeps the shared kernel decoupled from the IAM aggregate.
    """

    @property
    def id(self) -> Any: ...

    @property
    def created_by_user_id(self) -> Any: ...

    @property
    def tenant_id(self) -> Any: ...


# The validation callable signature:
# Given a secret string, returns a key-like object or None
ValidateAPIKeyFn = Callable[[str], Awaitable[_ValidatedKey | None]]


class MCPApiKeyAuthMiddleware:
    """ASGI middleware that validates X-API-Key headers for MCP requests.

    On successful validation, sets MCPAuthContext in a ContextVar so that
    downstream MCP tool functions can access the authenticated identity.

    On failure, returns a 401 JSON response without calling the inner app.

    Non-HTTP scopes (lifespan, websocket) pass through without auth.

    Args:
        app: The inner ASGI application to wrap.
        validate_api_key: Async callable that validates an API key secret
            and returns a key object (with id, created_by_user_id,
            tenant_id attributes) or None if invalid.
        probe: Optional domain probe for observability.
    """

    def __init__(
        self,
        app: ASGIApp,
        validate_api_key: ValidateAPIKeyFn,
        probe: MCPAuthProbe | None = None,
    ) -> None:
        self._app = app
        self._validate_api_key = validate_api_key
        self._probe = probe or DefaultMCPAuthProbe()

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """ASGI interface: authenticate HTTP requests, pass through others."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # Extract X-API-Key header
        api_key_secret = self._get_header(scope, b"x-api-key")

        if api_key_secret is None:
            self._probe.mcp_auth_missing_api_key()
            await self._send_json_error(send, 401, "X-API-Key header is required")
            return

        # Validate the API key
        key = await self._validate_api_key(api_key_secret)

        if key is None:
            self._probe.mcp_auth_invalid_api_key()
            await self._send_json_error(send, 401, "Invalid or expired API key")
            return

        # Build auth context from the validated key
        auth_context = MCPAuthContext(
            user_id=str(key.created_by_user_id),
            tenant_id=str(key.tenant_id),
            api_key_id=str(key.id),
        )

        self._probe.mcp_auth_succeeded(
            user_id=auth_context.user_id,
            tenant_id=auth_context.tenant_id,
            api_key_id=auth_context.api_key_id,
        )

        # Set ContextVar and invoke the inner app
        token = _mcp_auth_context_var.set(auth_context)
        try:
            await self._app(scope, receive, send)
        finally:
            _mcp_auth_context_var.reset(token)

    @staticmethod
    def _get_header(scope: MutableMapping[str, Any], name: bytes) -> str | None:
        """Extract a header value from ASGI scope (case-insensitive)."""
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == name:
                return header_value.decode("utf-8")
        return None

    @staticmethod
    async def _send_json_error(send: ASGISend, status: int, error: str) -> None:
        """Send a JSON error response via raw ASGI send."""
        body = json.dumps({"error": error}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
