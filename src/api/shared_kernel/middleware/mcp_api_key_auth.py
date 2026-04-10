"""ASGI middleware for MCP authentication.

Validates X-API-Key headers (primary) or Bearer tokens (fallback) on
incoming MCP requests and sets MCPAuthContext in a ContextVar for
downstream tool functions.

This middleware is framework-agnostic (pure ASGI) and accepts
validation callables to avoid direct imports from bounded contexts.
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


class _ValidatedBearer(Protocol):
    """Protocol for the validated Bearer token result.

    Must expose user_id and tenant_id so the middleware can build
    an MCPAuthContext without importing IAM types.
    """

    @property
    def user_id(self) -> Any: ...

    @property
    def tenant_id(self) -> Any: ...


# The validation callable signature:
# Given a secret string, returns a key-like object or None
ValidateAPIKeyFn = Callable[[str], Awaitable[_ValidatedKey | None]]

# Bearer validation callable:
# Given a raw token string and optional tenant ID header, returns a
# result with user_id and tenant_id, or None if invalid.
ValidateBearerTokenFn = Callable[[str, str | None], Awaitable[_ValidatedBearer | None]]


class MCPApiKeyAuthMiddleware:
    """ASGI middleware that validates MCP request authentication.

    Supports two authentication methods (tried in order):

    1. **X-API-Key header** (primary) — validates against the API key
       backend. The API key carries its own tenant scope.
    2. **Authorization: Bearer token** (fallback) — validates a JWT
       using the same OIDC flow as REST endpoints. Tenant comes from
       the ``X-Tenant-ID`` header.

    On successful validation, sets MCPAuthContext in a ContextVar so that
    downstream MCP tool functions can access the authenticated identity.

    On failure, returns a 401 JSON response without calling the inner app.

    Non-HTTP scopes (lifespan, websocket) pass through without auth.

    Args:
        app: The inner ASGI application to wrap.
        validate_api_key: Async callable that validates an API key secret
            and returns a key object (with id, created_by_user_id,
            tenant_id attributes) or None if invalid.
        validate_bearer_token: Optional async callable that validates a
            Bearer token + tenant ID and returns a result with user_id
            and tenant_id, or None if invalid.
        probe: Optional domain probe for observability.
    """

    def __init__(
        self,
        app: ASGIApp,
        validate_api_key: ValidateAPIKeyFn,
        validate_bearer_token: ValidateBearerTokenFn | None = None,
        probe: MCPAuthProbe | None = None,
    ) -> None:
        self._app = app
        self._validate_api_key = validate_api_key
        self._validate_bearer_token = validate_bearer_token
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

        # --- Try X-API-Key first ---
        try:
            api_key_secret = self._get_header(scope, b"x-api-key")
        except UnicodeDecodeError:
            self._probe.mcp_auth_invalid_api_key()
            await self._send_json_error(send, 401, "Invalid API key header encoding")
            return

        if api_key_secret is not None:
            auth_context = await self._authenticate_api_key(api_key_secret, send)
            if auth_context is None:
                return  # error response already sent
            await self._invoke_with_context(auth_context, scope, receive, send)
            return

        # --- Fallback to Bearer token ---
        if self._validate_bearer_token is not None:
            bearer_token = self._extract_bearer_token(scope)
            if bearer_token is not None:
                auth_context = await self._authenticate_bearer(
                    bearer_token, scope, send
                )
                if auth_context is None:
                    return  # error response already sent
                await self._invoke_with_context(auth_context, scope, receive, send)
                return

        # --- Neither auth method present ---
        self._probe.mcp_auth_missing_api_key()
        await self._send_json_error(send, 401, "X-API-Key header is required")

    # ------------------------------------------------------------------
    # API key authentication
    # ------------------------------------------------------------------

    async def _authenticate_api_key(
        self, secret: str, send: ASGISend
    ) -> MCPAuthContext | None:
        """Validate an API key and return auth context, or send error."""
        try:
            key = await self._validate_api_key(secret)
        except Exception as exc:
            self._probe.mcp_auth_validation_error(error=str(exc))
            await self._send_json_error(
                send, 503, "Authentication service temporarily unavailable"
            )
            return None

        if key is None:
            self._probe.mcp_auth_invalid_api_key()
            await self._send_json_error(send, 401, "Invalid or expired API key")
            return None

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
        return auth_context

    # ------------------------------------------------------------------
    # Bearer token authentication
    # ------------------------------------------------------------------

    async def _authenticate_bearer(
        self,
        token: str,
        scope: MutableMapping[str, Any],
        send: ASGISend,
    ) -> MCPAuthContext | None:
        """Validate a Bearer token and return auth context, or send error."""
        assert self._validate_bearer_token is not None

        tenant_id_header = self._get_header(scope, b"x-tenant-id")

        try:
            result = await self._validate_bearer_token(token, tenant_id_header)
        except Exception as exc:
            self._probe.mcp_auth_validation_error(error=str(exc))
            await self._send_json_error(
                send, 503, "Authentication service temporarily unavailable"
            )
            return None

        if result is None:
            self._probe.mcp_auth_invalid_api_key()
            await self._send_json_error(send, 401, "Invalid or expired Bearer token")
            return None

        auth_context = MCPAuthContext(
            user_id=str(result.user_id),
            tenant_id=str(result.tenant_id),
            api_key_id="bearer",
        )
        self._probe.mcp_auth_succeeded(
            user_id=auth_context.user_id,
            tenant_id=auth_context.tenant_id,
            api_key_id=auth_context.api_key_id,
        )
        return auth_context

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _invoke_with_context(
        self,
        auth_context: MCPAuthContext,
        scope: MutableMapping[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Set ContextVar and invoke the inner app."""
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
    def _extract_bearer_token(scope: MutableMapping[str, Any]) -> str | None:
        """Extract Bearer token from Authorization header."""
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == b"authorization":
                value = header_value.decode("utf-8")
                if value.lower().startswith("bearer "):
                    return value[7:]  # strip "Bearer "
        return None

    @staticmethod
    async def _send_json_error(send: ASGISend, status: int, error: str) -> None:
        """Send a JSON error response via raw ASGI send.

        For 401 responses, includes a ``WWW-Authenticate`` header
        per RFC 9110 §11.6.1 to signal accepted auth methods.
        """
        body = json.dumps({"error": error}).encode("utf-8")
        headers: list[list[bytes]] = [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ]
        if status == 401:
            headers.append([b"www-authenticate", b'ApiKey realm="kartograph"'])
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
