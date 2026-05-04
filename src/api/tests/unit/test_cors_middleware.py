"""Unit tests for CORS middleware wiring in the FastAPI application.

Covers spec: specs/nfr/cors.spec.md

Requirement: Configurable CORS Origins
  - Scenario: Origins configured  → CORS headers present, credentials allowed
  - Scenario: No origins configured → CORS middleware not installed, no headers

Requirement: CORS Defaults
  - Scenario: Default policy → all methods and headers allowed in preflight
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.settings import CORSSettings


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_app_with_cors(settings: CORSSettings) -> FastAPI:
    """Create a minimal FastAPI app with CORS configured via configure_cors."""
    from main import configure_cors

    test_app = FastAPI()

    @test_app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    configure_cors(test_app, settings)
    return test_app


# ---------------------------------------------------------------------------
# Scenario: Origins configured
# ---------------------------------------------------------------------------


class TestCORSWithOriginsConfigured:
    """CORS headers appear when origins are configured and the request origin matches."""

    ALLOWED_ORIGIN = "https://app.example.com"

    @pytest.fixture
    def client(self) -> TestClient:
        settings = CORSSettings(origins=[self.ALLOWED_ORIGIN])
        app = _make_app_with_cors(settings)
        return TestClient(app, raise_server_exceptions=True)

    def test_cors_headers_present_for_allowed_origin(self, client: TestClient) -> None:
        """Response includes Access-Control-Allow-Origin for an allowed origin."""
        response = client.get("/ping", headers={"Origin": self.ALLOWED_ORIGIN})

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == self.ALLOWED_ORIGIN

    def test_credentials_allowed_in_cors_response(self, client: TestClient) -> None:
        """Access-Control-Allow-Credentials must be 'true' for credentialed requests."""
        response = client.get("/ping", headers={"Origin": self.ALLOWED_ORIGIN})

        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_wildcard_not_used_in_origin_header(self, client: TestClient) -> None:
        """Response must not reflect '*' as the origin when credentials are allowed."""
        response = client.get("/ping", headers={"Origin": self.ALLOWED_ORIGIN})

        origin_header = response.headers.get("access-control-allow-origin", "")
        assert origin_header != "*", (
            "Access-Control-Allow-Origin must not be '*' when credentials are allowed"
        )


# ---------------------------------------------------------------------------
# Scenario: No origins configured
# ---------------------------------------------------------------------------


class TestCORSWithNoOriginsConfigured:
    """When no origins are set the middleware must not be installed."""

    @pytest.fixture
    def client(self) -> TestClient:
        settings = CORSSettings(origins=[])  # CORS disabled
        app = _make_app_with_cors(settings)
        return TestClient(app)

    def test_no_cors_headers_when_origins_not_configured(
        self, client: TestClient
    ) -> None:
        """Cross-origin request receives no CORS headers when middleware is absent."""
        response = client.get("/ping", headers={"Origin": "https://evil.example.com"})

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_no_allow_credentials_header_when_cors_disabled(
        self, client: TestClient
    ) -> None:
        """Access-Control-Allow-Credentials must not appear when CORS is off."""
        response = client.get("/ping", headers={"Origin": "https://evil.example.com"})

        assert "access-control-allow-credentials" not in response.headers


# ---------------------------------------------------------------------------
# Scenario: Default policy
# ---------------------------------------------------------------------------


class TestCORSDefaultPolicy:
    """Preflight responses must permit all methods and all request headers."""

    ALLOWED_ORIGIN = "https://app.example.com"

    @pytest.fixture
    def client(self) -> TestClient:
        settings = CORSSettings(origins=[self.ALLOWED_ORIGIN])
        app = _make_app_with_cors(settings)
        return TestClient(app)

    def test_preflight_allows_requested_method(self, client: TestClient) -> None:
        """Preflight response must echo back any requested HTTP method."""
        response = client.options(
            "/ping",
            headers={
                "Origin": self.ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 200
        allow_methods = response.headers.get("access-control-allow-methods", "")
        # Starlette echoes the requested method or returns '*'
        assert "DELETE" in allow_methods or "*" in allow_methods

    def test_preflight_allows_requested_headers(self, client: TestClient) -> None:
        """Preflight response must echo back any requested headers."""
        response = client.options(
            "/ping",
            headers={
                "Origin": self.ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Custom-Header, Authorization",
            },
        )

        assert response.status_code == 200
        allow_headers = response.headers.get("access-control-allow-headers", "")
        # Starlette echoes the requested headers when allow_headers=['*']
        assert (
            "x-custom-header" in allow_headers.lower()
            or "authorization" in allow_headers.lower()
            or "*" in allow_headers
        )


# ---------------------------------------------------------------------------
# configure_cors function contract
# ---------------------------------------------------------------------------


class TestConfigureCorsFunction:
    """Direct tests for the configure_cors helper function."""

    def test_middleware_added_when_origins_configured(self) -> None:
        """configure_cors installs CORSMiddleware when origins are present."""
        from fastapi.middleware.cors import CORSMiddleware
        from main import configure_cors

        app = FastAPI()
        settings = CORSSettings(origins=["https://app.example.com"])
        configure_cors(app, settings)

        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_middleware_not_added_when_origins_empty(self) -> None:
        """configure_cors does not install CORSMiddleware when origins are empty."""
        from fastapi.middleware.cors import CORSMiddleware
        from main import configure_cors

        app = FastAPI()
        settings = CORSSettings(origins=[])
        configure_cors(app, settings)

        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware not in middleware_classes
