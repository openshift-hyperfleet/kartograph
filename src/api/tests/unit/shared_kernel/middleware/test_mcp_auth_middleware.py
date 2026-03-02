"""Unit tests for MCPApiKeyAuthMiddleware ASGI middleware.

Tests the ASGI middleware that validates X-API-Key headers for MCP requests
and sets MCPAuthContext in a ContextVar for downstream tool functions.
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from shared_kernel.middleware.mcp_api_key_auth import MCPApiKeyAuthMiddleware
from shared_kernel.middleware.mcp_auth import MCPAuthContext, _mcp_auth_context_var


# ---------------------------------------------------------------------------
# Fake APIKey-like object returned by the validation callable
# ---------------------------------------------------------------------------


@dataclass
class FakeAPIKey:
    """Minimal stand-in for the IAM APIKey aggregate in tests."""

    id: str
    created_by_user_id: str
    tenant_id: str


# ---------------------------------------------------------------------------
# ASGI test helpers
# ---------------------------------------------------------------------------


async def _dummy_app(scope: MutableMapping[str, Any], receive: Any, send: Any) -> None:
    """A minimal ASGI app that echoes MCPAuthContext if available."""
    if scope["type"] == "http":
        try:
            ctx = _mcp_auth_context_var.get()
            body = json.dumps(
                {
                    "user_id": ctx.user_id,
                    "tenant_id": ctx.tenant_id,
                    "api_key_id": ctx.api_key_id,
                }
            ).encode()
        except LookupError:
            body = b'{"error": "no auth context"}'

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send({"type": "http.response.body", "body": body})
    elif scope["type"] == "lifespan":
        # Pass through lifespan events
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


def _make_http_scope(
    headers: list[tuple[bytes, bytes]] | None = None,
) -> MutableMapping[str, Any]:
    """Create a minimal HTTP ASGI scope."""
    return {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": headers or [],
    }


def _make_lifespan_scope() -> MutableMapping[str, Any]:
    """Create a minimal lifespan ASGI scope."""
    return {"type": "lifespan"}


class _ResponseCapture:
    """Captures ASGI send() calls for assertion."""

    def __init__(self) -> None:
        self.messages: list[MutableMapping[str, Any]] = []

    async def __call__(self, message: MutableMapping[str, Any]) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int:
        return self.messages[0]["status"]

    @property
    def body(self) -> bytes:
        return self.messages[1]["body"]

    @property
    def json(self) -> dict:
        return json.loads(self.body)

    @property
    def headers(self) -> dict[str, str]:
        return {k.decode(): v.decode() for k, v in self.messages[0].get("headers", [])}


async def _noop_receive() -> MutableMapping[str, Any]:
    return {"type": "http.request", "body": b""}


# ---------------------------------------------------------------------------
# Validation callable factory
# ---------------------------------------------------------------------------


def _make_validate_fn(
    return_value: FakeAPIKey | None = None,
):
    """Create an async validation callable that returns the given value."""

    async def validate(secret: str) -> FakeAPIKey | None:
        return return_value

    return validate


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMCPApiKeyAuthMiddleware401WhenMissing:
    """Tests that the middleware returns 401 when X-API-Key header is missing."""

    @pytest.mark.asyncio
    async def test_returns_401_when_header_missing(self) -> None:
        """Should return 401 JSON response when X-API-Key header is absent."""
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=None),
            probe=probe,
        )

        scope = _make_http_scope(headers=[])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        assert capture.status == 401
        assert capture.json == {"error": "X-API-Key header is required"}
        assert capture.headers["content-type"] == "application/json"
        assert capture.headers["www-authenticate"] == 'ApiKey realm="kartograph"'

    @pytest.mark.asyncio
    async def test_calls_probe_on_missing_header(self) -> None:
        """Should call probe.mcp_auth_missing_api_key when header is absent."""
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=None),
            probe=probe,
        )

        scope = _make_http_scope(headers=[])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        probe.mcp_auth_missing_api_key.assert_called_once()


class TestMCPApiKeyAuthMiddleware401WhenInvalid:
    """Tests that the middleware returns 401 when API key is invalid."""

    @pytest.mark.asyncio
    async def test_returns_401_when_key_invalid(self) -> None:
        """Should return 401 JSON response when API key validation fails."""
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=None),
            probe=probe,
        )

        scope = _make_http_scope(headers=[(b"x-api-key", b"karto_invalid_key")])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        assert capture.status == 401
        assert capture.json == {"error": "Invalid or expired API key"}
        assert capture.headers["www-authenticate"] == 'ApiKey realm="kartograph"'

    @pytest.mark.asyncio
    async def test_calls_probe_on_invalid_key(self) -> None:
        """Should call probe.mcp_auth_invalid_api_key when key is invalid."""
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=None),
            probe=probe,
        )

        scope = _make_http_scope(headers=[(b"x-api-key", b"karto_invalid_key")])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        probe.mcp_auth_invalid_api_key.assert_called_once()


class TestMCPApiKeyAuthMiddlewareSuccess:
    """Tests that valid API keys are accepted and context is set."""

    @pytest.mark.asyncio
    async def test_sets_auth_context_on_valid_key(self) -> None:
        """Should set MCPAuthContext in ContextVar when key is valid."""
        fake_key = FakeAPIKey(
            id="key-789",
            created_by_user_id="user-123",
            tenant_id="tenant-456",
        )
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=fake_key),
            probe=probe,
        )

        scope = _make_http_scope(headers=[(b"x-api-key", b"karto_valid_secret")])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        # The dummy app echoes the MCPAuthContext
        assert capture.status == 200
        assert capture.json == {
            "user_id": "user-123",
            "tenant_id": "tenant-456",
            "api_key_id": "key-789",
        }

    @pytest.mark.asyncio
    async def test_calls_probe_on_success(self) -> None:
        """Should call probe.mcp_auth_succeeded when key is valid."""
        fake_key = FakeAPIKey(
            id="key-789",
            created_by_user_id="user-123",
            tenant_id="tenant-456",
        )
        probe = MagicMock()
        middleware = MCPApiKeyAuthMiddleware(
            app=_dummy_app,
            validate_api_key=_make_validate_fn(return_value=fake_key),
            probe=probe,
        )

        scope = _make_http_scope(headers=[(b"x-api-key", b"karto_valid_secret")])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        probe.mcp_auth_succeeded.assert_called_once_with(
            user_id="user-123",
            tenant_id="tenant-456",
            api_key_id="key-789",
        )

    @pytest.mark.asyncio
    async def test_auth_context_has_correct_fields(self) -> None:
        """MCPAuthContext should carry correct user_id, tenant_id, api_key_id."""
        fake_key = FakeAPIKey(
            id="key-abc",
            created_by_user_id="user-def",
            tenant_id="tenant-ghi",
        )
        probe = MagicMock()

        captured_context: MCPAuthContext | None = None

        async def context_capturing_app(scope, receive, send):
            nonlocal captured_context
            captured_context = _mcp_auth_context_var.get()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b""})

        middleware = MCPApiKeyAuthMiddleware(
            app=context_capturing_app,
            validate_api_key=_make_validate_fn(return_value=fake_key),
            probe=probe,
        )

        scope = _make_http_scope(headers=[(b"x-api-key", b"karto_valid_secret")])
        capture = _ResponseCapture()
        await middleware(scope, _noop_receive, capture)

        assert captured_context is not None
        assert captured_context.user_id == "user-def"
        assert captured_context.tenant_id == "tenant-ghi"
        assert captured_context.api_key_id == "key-abc"


class TestMCPApiKeyAuthMiddlewareNonHTTP:
    """Tests that non-HTTP scopes pass through without auth."""

    @pytest.mark.asyncio
    async def test_passes_through_lifespan_scope(self) -> None:
        """Should pass through lifespan scope without authentication."""
        probe = MagicMock()

        # Track whether the inner app was called
        inner_called = False

        async def lifespan_app(scope, receive, send):
            nonlocal inner_called
            inner_called = True

        middleware = MCPApiKeyAuthMiddleware(
            app=lifespan_app,
            validate_api_key=_make_validate_fn(return_value=None),
            probe=probe,
        )

        scope = _make_lifespan_scope()

        async def noop_receive():
            return {}

        async def noop_send(msg):
            pass

        await middleware(scope, noop_receive, noop_send)

        assert inner_called is True
        probe.mcp_auth_missing_api_key.assert_not_called()
        probe.mcp_auth_invalid_api_key.assert_not_called()
