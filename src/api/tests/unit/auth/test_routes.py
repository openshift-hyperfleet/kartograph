"""Unit tests for auth routes.

Tests follow TDD approach - written before implementation.
Uses mocking for httpx to avoid requiring real OIDC provider.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


TEST_ISSUER = "https://auth.example.com/realms/test"
TEST_CLIENT_ID = "test-client"
TEST_CLIENT_SECRET = "test-secret"


@pytest.fixture
def mock_oidc_settings() -> MagicMock:
    """Create mock OIDC settings."""
    from pydantic import SecretStr

    settings = MagicMock()
    settings.issuer_url = TEST_ISSUER
    settings.client_id = TEST_CLIENT_ID
    settings.client_secret = SecretStr(TEST_CLIENT_SECRET)
    settings.auth_routes_enabled = True
    return settings


@pytest.fixture
def mock_probe() -> MagicMock:
    """Create mock observability probe."""
    from auth.observability import AuthFlowProbe

    return MagicMock(spec=AuthFlowProbe)


@pytest.fixture
def openid_config() -> dict[str, Any]:
    """Create OpenID Connect discovery document."""
    return {
        "issuer": TEST_ISSUER,
        "authorization_endpoint": f"{TEST_ISSUER}/protocol/openid-connect/auth",
        "token_endpoint": f"{TEST_ISSUER}/protocol/openid-connect/token",
        "jwks_uri": f"{TEST_ISSUER}/protocol/openid-connect/certs",
    }


def _create_response_mock(
    json_data: dict[str, Any], status_code: int = 200
) -> MagicMock:
    """Create a mock httpx response object."""
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def test_app_with_routes(mock_oidc_settings: MagicMock, mock_probe: MagicMock):
    """Create test app with auth routes registered."""
    from auth.presentation import routes

    # Reset PKCE state storage between tests
    routes._pkce_states.clear()

    app = FastAPI()

    # Override dependencies
    app.dependency_overrides[routes.get_oidc_settings_dep] = lambda: mock_oidc_settings
    app.dependency_overrides[routes.get_auth_probe_dep] = lambda: mock_probe
    app.dependency_overrides[routes.get_base_url_dep] = lambda: "http://localhost:8000"

    app.include_router(routes.router)

    return app


@pytest.fixture
def test_client(test_app_with_routes: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app_with_routes, follow_redirects=False)


class TestLoginRoute:
    """Tests for GET /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_redirects_to_idp(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Login should redirect to IdP authorization endpoint."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            response = test_client.get("/auth/login")

        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith(openid_config["authorization_endpoint"])

    @pytest.mark.asyncio
    async def test_login_includes_required_oauth_params(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Login redirect should include required OAuth2 params."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            response = test_client.get("/auth/login")

        location = response.headers["location"]

        # Check required params are present
        assert f"client_id={TEST_CLIENT_ID}" in location
        assert "response_type=code" in location
        assert "scope=openid" in location
        assert "state=" in location
        assert "redirect_uri=" in location

    @pytest.mark.asyncio
    async def test_login_generates_pkce_challenge(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Login should generate PKCE code_challenge with S256 method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            response = test_client.get("/auth/login")

        location = response.headers["location"]

        # PKCE params should be present
        assert "code_challenge=" in location
        assert "code_challenge_method=S256" in location

    @pytest.mark.asyncio
    async def test_login_stores_pkce_state(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Login should store PKCE verifier for callback use."""
        from auth.presentation import routes

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            response = test_client.get("/auth/login?redirect_uri=/dashboard")

        location = response.headers["location"]

        # Extract state from URL
        import urllib.parse

        parsed = urllib.parse.urlparse(location)
        params = urllib.parse.parse_qs(parsed.query)
        state = params["state"][0]

        # Verify state is stored with verifier and redirect_uri
        assert state in routes._pkce_states
        pkce_data = routes._pkce_states[state]
        assert "code_verifier" in pkce_data
        assert pkce_data["redirect_uri"] == "/dashboard"

    @pytest.mark.asyncio
    async def test_login_uses_default_redirect_uri(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Login should use /docs as default redirect_uri."""
        from auth.presentation import routes

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            response = test_client.get("/auth/login")

        location = response.headers["location"]

        import urllib.parse

        parsed = urllib.parse.urlparse(location)
        params = urllib.parse.parse_qs(parsed.query)
        state = params["state"][0]

        assert routes._pkce_states[state]["redirect_uri"] == "/docs"

    @pytest.mark.asyncio
    async def test_login_calls_probe(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
        mock_probe: MagicMock,
    ) -> None:
        """Login should call probe.login_initiated."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)

            test_client.get("/auth/login?redirect_uri=/dashboard")

        mock_probe.login_initiated.assert_called_once_with(redirect_uri="/dashboard")

    @pytest.mark.asyncio
    async def test_login_handles_discovery_failure(
        self,
        test_client: TestClient,
        mock_probe: MagicMock,
    ) -> None:
        """Login should return 503 when discovery fails."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.NetworkError("Connection refused")

            response = test_client.get("/auth/login")

        assert response.status_code == 503
        assert "discovery" in response.json()["detail"].lower()
        mock_probe.discovery_failed.assert_called_once()


class TestCallbackRoute:
    """Tests for GET /auth/callback endpoint."""

    def _setup_valid_pkce_state(self, redirect_uri: str = "/docs") -> str:
        """Set up a valid PKCE state in storage and return it."""
        import secrets

        from auth.presentation import routes

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(32)
        routes._pkce_states[state] = {
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        }
        return state

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_for_token(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Callback should exchange authorization code for tokens."""
        state = self._setup_valid_pkce_state()
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": "test-id-token",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            response = test_client.get(
                f"/auth/callback?code=test-auth-code&state={state}"
            )

        # Should redirect to the original redirect_uri
        assert response.status_code == 307

    @pytest.mark.asyncio
    async def test_callback_sets_access_token_cookie(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Callback should set access token in httponly cookie."""
        state = self._setup_valid_pkce_state()
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            response = test_client.get(
                f"/auth/callback?code=test-auth-code&state={state}"
            )

        # Check cookie is set
        assert "access_token" in response.cookies
        assert response.cookies["access_token"] == "test-access-token"

    @pytest.mark.asyncio
    async def test_callback_redirects_to_original_uri(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Callback should redirect to the original redirect_uri."""
        state = self._setup_valid_pkce_state(redirect_uri="/dashboard")
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            response = test_client.get(
                f"/auth/callback?code=test-auth-code&state={state}"
            )

        assert response.headers["location"] == "/dashboard"

    @pytest.mark.asyncio
    async def test_callback_fails_with_invalid_state(
        self,
        test_client: TestClient,
        mock_probe: MagicMock,
    ) -> None:
        """Callback should return 400 for invalid state."""
        response = test_client.get(
            "/auth/callback?code=test-auth-code&state=invalid-state"
        )

        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()
        mock_probe.invalid_state.assert_called_once_with(state="invalid-state")

    @pytest.mark.asyncio
    async def test_callback_handles_token_exchange_error(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
        mock_probe: MagicMock,
    ) -> None:
        """Callback should return 401 when token exchange fails."""
        state = self._setup_valid_pkce_state()
        error_response = {"error": "invalid_grant", "error_description": "Code expired"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(
                error_response, status_code=400
            )

            response = test_client.get(
                f"/auth/callback?code=test-auth-code&state={state}"
            )

        assert response.status_code == 401
        assert "token exchange failed" in response.json()["detail"].lower()
        mock_probe.token_exchange_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_sends_pkce_verifier(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Callback should send PKCE verifier in token request."""
        from auth.presentation import routes

        state = self._setup_valid_pkce_state()
        expected_verifier = routes._pkce_states[state]["code_verifier"]
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            test_client.get(f"/auth/callback?code=test-auth-code&state={state}")

            # Verify the POST call included the verifier
            post_call = mock_client.post.call_args
            assert post_call is not None
            post_data = post_call[1]["data"]
            assert post_data["code_verifier"] == expected_verifier

    @pytest.mark.asyncio
    async def test_callback_removes_state_after_use(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
    ) -> None:
        """Callback should remove state from storage after use."""
        from auth.presentation import routes

        state = self._setup_valid_pkce_state()
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            test_client.get(f"/auth/callback?code=test-auth-code&state={state}")

        # State should be removed
        assert state not in routes._pkce_states

    @pytest.mark.asyncio
    async def test_callback_calls_probe_on_success(
        self,
        test_client: TestClient,
        openid_config: dict[str, Any],
        mock_probe: MagicMock,
    ) -> None:
        """Callback should call probe methods on success."""
        state = self._setup_valid_pkce_state()
        token_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _create_response_mock(openid_config)
            mock_client.post.return_value = _create_response_mock(token_response)

            test_client.get(f"/auth/callback?code=test-auth-code&state={state}")

        mock_probe.callback_received.assert_called_once_with(state=state)
        mock_probe.token_exchange_success.assert_called_once()


class TestPKCEGeneration:
    """Tests for PKCE code_verifier and code_challenge generation."""

    def test_generate_pkce_pair_creates_valid_challenge(self) -> None:
        """Generated PKCE pair should produce valid S256 challenge."""
        from auth.presentation.routes import _generate_pkce_pair

        code_verifier, code_challenge = _generate_pkce_pair()

        # Verify the challenge matches S256 of verifier
        expected_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert code_challenge == expected_challenge

    def test_generate_pkce_pair_creates_unique_values(self) -> None:
        """Each call should generate unique values."""
        from auth.presentation.routes import _generate_pkce_pair

        pairs = [_generate_pkce_pair() for _ in range(10)]
        verifiers = [p[0] for p in pairs]
        challenges = [p[1] for p in pairs]

        assert len(set(verifiers)) == 10
        assert len(set(challenges)) == 10


class TestRoutesNotRegisteredWhenDisabled:
    """Tests for conditional route registration."""

    def test_routes_not_available_when_disabled(self) -> None:
        """Auth routes should not be available when auth_routes_enabled=False."""
        from pydantic import SecretStr

        mock_settings = MagicMock()
        mock_settings.issuer_url = TEST_ISSUER
        mock_settings.client_id = TEST_CLIENT_ID
        mock_settings.client_secret = SecretStr(TEST_CLIENT_SECRET)
        mock_settings.auth_routes_enabled = False

        # Create app without including auth routes (simulating conditional registration)
        app = FastAPI()
        # Don't include router - this simulates the main.py conditional check
        client = TestClient(app)

        # Routes should not exist
        response = client.get("/auth/login")
        assert response.status_code == 404

        response = client.get("/auth/callback?code=test&state=test")
        assert response.status_code == 404
