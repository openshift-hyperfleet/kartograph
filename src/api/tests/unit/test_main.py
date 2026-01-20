"""Unit tests for main FastAPI application configuration.

Tests for Swagger UI OAuth2/OIDC integration.
Following TDD approach - tests written before implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from pydantic import SecretStr


TEST_ISSUER = "https://auth.example.com/realms/test"
TEST_CLIENT_ID = "test-api-client"
TEST_CLIENT_SECRET = "test-secret"
TEST_SWAGGER_CLIENT_ID = "test-swagger-client"


@pytest.fixture
def mock_oidc_settings() -> MagicMock:
    """Create mock OIDC settings for testing."""
    settings = MagicMock()
    settings.issuer_url = TEST_ISSUER
    settings.client_id = TEST_CLIENT_ID
    settings.client_secret = SecretStr(TEST_CLIENT_SECRET)
    settings.swagger_client_id = TEST_SWAGGER_CLIENT_ID
    settings.auth_routes_enabled = True
    return settings


@pytest.fixture
def test_app() -> FastAPI:
    """Create a minimal test FastAPI app."""
    return FastAPI(
        title="Test API",
        version="1.0.0",
        description="Test application",
    )


class TestConfigureSwaggerOAuth2:
    """Tests for configure_swagger_oauth2 function."""

    def test_swagger_ui_init_oauth_configured_when_oidc_valid(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """Swagger UI init oauth should be configured when OIDC settings are valid."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        assert test_app.swagger_ui_init_oauth is not None
        assert test_app.swagger_ui_init_oauth["clientId"] == TEST_SWAGGER_CLIENT_ID

    def test_openapi_schema_contains_oauth2_security_scheme(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """OpenAPI schema should contain OAuth2 security scheme."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        schema = test_app.openapi()

        assert "components" in schema
        assert "securitySchemes" in schema["components"]
        assert "OAuth2" in schema["components"]["securitySchemes"]

        oauth2_scheme = schema["components"]["securitySchemes"]["OAuth2"]
        assert oauth2_scheme["type"] == "oauth2"
        assert "flows" in oauth2_scheme
        assert "authorizationCode" in oauth2_scheme["flows"]

    def test_authorization_url_matches_issuer(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """Authorization URL should be constructed from issuer URL."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        schema = test_app.openapi()
        auth_code_flow = schema["components"]["securitySchemes"]["OAuth2"]["flows"][
            "authorizationCode"
        ]

        expected_auth_url = f"{TEST_ISSUER}/protocol/openid-connect/auth"
        expected_token_url = f"{TEST_ISSUER}/protocol/openid-connect/token"

        assert auth_code_flow["authorizationUrl"] == expected_auth_url
        assert auth_code_flow["tokenUrl"] == expected_token_url

    def test_pkce_enabled_in_swagger_config(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """usePkceWithAuthorizationCodeGrant should be True."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        assert test_app.swagger_ui_init_oauth is not None
        assert (
            test_app.swagger_ui_init_oauth["usePkceWithAuthorizationCodeGrant"] is True
        )

    def test_swagger_not_configured_when_oidc_settings_fail(
        self,
        test_app: FastAPI,
    ) -> None:
        """Swagger OAuth2 should not be configured when OIDC settings fail."""
        from main import configure_swagger_oauth2

        with patch(
            "main.get_oidc_settings",
            side_effect=Exception("Missing client_secret"),
        ):
            configure_swagger_oauth2(test_app)

        # swagger_ui_init_oauth should remain None (not set)
        assert test_app.swagger_ui_init_oauth is None

    def test_openapi_schema_cached_after_first_call(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """OpenAPI schema should be cached after first call."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        # First call generates the schema
        schema1 = test_app.openapi()
        # Second call should return cached schema
        schema2 = test_app.openapi()

        assert schema1 is schema2

    def test_scopes_configured_in_swagger_init(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """Scopes should be configured in swagger_ui_init_oauth."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        assert test_app.swagger_ui_init_oauth is not None
        assert "scopes" in test_app.swagger_ui_init_oauth
        assert "openid" in test_app.swagger_ui_init_oauth["scopes"]

    def test_global_security_applied_to_schema(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """Global security should be applied to OpenAPI schema."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        schema = test_app.openapi()

        assert "security" in schema
        assert len(schema["security"]) > 0
        assert "OAuth2" in schema["security"][0]

    def test_uses_public_swagger_client_not_api_client(
        self,
        test_app: FastAPI,
        mock_oidc_settings: MagicMock,
    ) -> None:
        """Should use the public swagger_client_id, not the confidential API client."""
        from main import configure_swagger_oauth2

        with patch("main.get_oidc_settings", return_value=mock_oidc_settings):
            configure_swagger_oauth2(test_app)

        assert test_app.swagger_ui_init_oauth is not None
        # Should use swagger_client_id, not client_id
        assert test_app.swagger_ui_init_oauth["clientId"] == TEST_SWAGGER_CLIENT_ID
        assert test_app.swagger_ui_init_oauth["clientId"] != TEST_CLIENT_ID
