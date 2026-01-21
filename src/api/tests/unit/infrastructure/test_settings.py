"""Unit tests for infrastructure settings."""

import pytest
from pydantic import ValidationError

from infrastructure.settings import DatabaseSettings, OIDCSettings, get_oidc_settings


class TestDatabaseSettingsPoolConfiguration:
    """Tests for connection pool configuration."""

    def test_default_pool_settings(self):
        """Should have sensible pool defaults."""
        settings = DatabaseSettings()
        assert settings.pool_min_connections >= 1
        assert settings.pool_max_connections >= settings.pool_min_connections
        assert settings.pool_max_connections <= 20

    def test_pool_settings_from_fields(self):
        """Should accept pool settings via constructor."""
        settings = DatabaseSettings(
            pool_min_connections=5,
            pool_max_connections=15,
        )
        assert settings.pool_min_connections == 5
        assert settings.pool_max_connections == 15

    def test_pool_max_must_be_greater_than_or_equal_to_min(self):
        """Should validate max >= min."""
        with pytest.raises(ValidationError) as exc_info:
            DatabaseSettings(pool_min_connections=10, pool_max_connections=5)

        error_str = str(exc_info.value)
        assert "pool_max_connections" in error_str or "greater" in error_str.lower()

    def test_pool_max_equal_to_min_is_valid(self):
        """Should allow max == min."""
        settings = DatabaseSettings(pool_min_connections=5, pool_max_connections=5)
        assert settings.pool_min_connections == 5
        assert settings.pool_max_connections == 5

    def test_pool_min_must_be_positive(self):
        """Pool min connections must be >= 1."""
        with pytest.raises(ValidationError):
            DatabaseSettings(pool_min_connections=0)

    def test_pool_max_respects_upper_limit(self):
        """Pool max should not exceed reasonable limit."""
        with pytest.raises(ValidationError):
            DatabaseSettings(pool_max_connections=101)


class TestOIDCSettings:
    """Tests for OIDC configuration settings."""

    def test_default_values_are_set_correctly(self):
        """Should have sensible defaults for OIDC settings."""
        settings = OIDCSettings(client_secret="test-secret")

        assert settings.issuer_url == "http://localhost:8080/realms/kartograph"
        assert settings.client_id == "kartograph-api"
        assert settings.swagger_client_id == "kartograph-swagger"
        assert settings.auth_routes_enabled is True
        assert settings.user_id_claim == "sub"
        assert settings.username_claim == "preferred_username"

    def test_client_secret_is_required(self, monkeypatch):
        """Should raise ValidationError when client_secret is missing."""
        # Ensure no env var is set (integration tests may set this)
        monkeypatch.delenv("KARTOGRAPH_OIDC_CLIENT_SECRET", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            OIDCSettings()

        error_str = str(exc_info.value)
        assert "client_secret" in error_str

    def test_client_secret_is_secret_str(self):
        """Client secret should be masked as SecretStr."""
        settings = OIDCSettings(client_secret="super-secret-value")

        # SecretStr should not expose the value in string representation
        assert "super-secret-value" not in str(settings.client_secret)
        assert settings.client_secret.get_secret_value() == "super-secret-value"

    def test_audience_defaults_to_client_id_when_none(self):
        """Audience should default to client_id when not explicitly set."""
        settings = OIDCSettings(client_secret="test-secret")

        assert settings.audience is None
        assert settings.effective_audience == "kartograph-api"

    def test_audience_uses_explicit_value_when_set(self):
        """Audience should use explicit value when provided."""
        settings = OIDCSettings(
            client_secret="test-secret",
            audience="custom-audience",
        )

        assert settings.audience == "custom-audience"
        assert settings.effective_audience == "custom-audience"

    def test_env_vars_override_defaults(self, monkeypatch):
        """Environment variables should override default values."""
        monkeypatch.setenv(
            "KARTOGRAPH_OIDC_ISSUER_URL", "https://auth.example.com/realms/prod"
        )
        monkeypatch.setenv("KARTOGRAPH_OIDC_CLIENT_ID", "prod-client")
        monkeypatch.setenv("KARTOGRAPH_OIDC_CLIENT_SECRET", "prod-secret")
        monkeypatch.setenv("KARTOGRAPH_OIDC_SWAGGER_CLIENT_ID", "prod-swagger")
        monkeypatch.setenv("KARTOGRAPH_OIDC_AUTH_ROUTES_ENABLED", "false")
        monkeypatch.setenv("KARTOGRAPH_OIDC_USER_ID_CLAIM", "oid")
        monkeypatch.setenv("KARTOGRAPH_OIDC_USERNAME_CLAIM", "email")
        monkeypatch.setenv("KARTOGRAPH_OIDC_AUDIENCE", "api://kartograph")

        settings = OIDCSettings()

        assert settings.issuer_url == "https://auth.example.com/realms/prod"
        assert settings.client_id == "prod-client"
        assert settings.client_secret.get_secret_value() == "prod-secret"
        assert settings.swagger_client_id == "prod-swagger"
        assert settings.auth_routes_enabled is False
        assert settings.user_id_claim == "oid"
        assert settings.username_claim == "email"
        assert settings.audience == "api://kartograph"

    def test_get_oidc_settings_returns_cached_instance(self, monkeypatch):
        """get_oidc_settings should return cached instance."""
        monkeypatch.setenv("KARTOGRAPH_OIDC_CLIENT_SECRET", "cached-secret")

        # Clear the cache first
        get_oidc_settings.cache_clear()

        settings1 = get_oidc_settings()
        settings2 = get_oidc_settings()

        assert settings1 is settings2
