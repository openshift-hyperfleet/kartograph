"""Unit tests for infrastructure settings."""

import pytest
from pydantic import ValidationError

from infrastructure.settings import (
    DatabaseSettings,
    IAMSettings,
    OIDCSettings,
    OutboxWorkerSettings,
    get_oidc_settings,
)


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
        assert "pool_max_connections" in error_str
        assert ">=" in error_str

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
        assert settings.user_id_claim == "sub"
        assert settings.username_claim == "preferred_username"

    def test_client_secret_defaults_to_empty(self, monkeypatch):
        """Should default to empty string when client_secret is not set."""
        # Ensure no env var is set (integration tests may set this)
        monkeypatch.delenv("KARTOGRAPH_OIDC_CLIENT_SECRET", raising=False)

        settings = OIDCSettings()

        assert settings.client_secret.get_secret_value() == ""

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
        monkeypatch.setenv("KARTOGRAPH_OIDC_USER_ID_CLAIM", "oid")
        monkeypatch.setenv("KARTOGRAPH_OIDC_USERNAME_CLAIM", "email")
        monkeypatch.setenv("KARTOGRAPH_OIDC_AUDIENCE", "api://kartograph")

        settings = OIDCSettings()

        assert settings.issuer_url == "https://auth.example.com/realms/prod"
        assert settings.client_id == "prod-client"
        assert settings.client_secret.get_secret_value() == "prod-secret"
        assert settings.swagger_client_id == "prod-swagger"
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


class TestIAMSettings:
    """Tests for IAM configuration settings."""

    def test_bootstrap_admin_usernames_defaults_to_empty_list(self):
        """bootstrap_admin_usernames should default to an empty list."""
        settings = IAMSettings()
        assert settings.bootstrap_admin_usernames == []

    def test_bootstrap_admin_usernames_accepts_list(self):
        """bootstrap_admin_usernames should accept a list of usernames."""
        settings = IAMSettings(
            bootstrap_admin_usernames=["alice", "bob"],
        )
        assert settings.bootstrap_admin_usernames == ["alice", "bob"]

    def test_bootstrap_admin_usernames_from_env(self, monkeypatch):
        """bootstrap_admin_usernames should be settable from environment."""
        monkeypatch.setenv(
            "KARTOGRAPH_IAM_BOOTSTRAP_ADMIN_USERNAMES", '["admin1","admin2"]'
        )
        settings = IAMSettings()
        assert settings.bootstrap_admin_usernames == ["admin1", "admin2"]


class TestIAMSettingsDefaultConfiguration:
    """Tests for IAMSettings default configuration values.

    Spec: specs/nfr/application-lifecycle.spec.md
    Requirement: Default Configuration

    Verifies that the system uses sensible defaults for single-tenant deployments.
    """

    def test_single_tenant_mode_enabled_by_default(self):
        """Single-tenant mode should be enabled by default.

        GIVEN no explicit configuration overrides
        THEN single-tenant mode is enabled
        """
        settings = IAMSettings()
        assert settings.single_tenant_mode is True

    def test_default_tenant_name_is_default(self):
        """Default tenant name should be 'default'.

        GIVEN no explicit configuration overrides
        THEN the default tenant name is "default"
        """
        settings = IAMSettings()
        assert settings.default_tenant_name == "default"

    def test_default_workspace_name_is_none(self):
        """Default workspace name should be None (falls back to tenant name).

        GIVEN no explicit configuration overrides
        THEN the default workspace name is None (triggering tenant-name fallback)
        """
        settings = IAMSettings()
        assert settings.default_workspace_name is None

    def test_workspace_name_falls_back_to_tenant_name(self):
        """Effective workspace name falls back to tenant name when not set.

        GIVEN no explicit configuration overrides
        THEN the effective workspace name equals the tenant name
        """
        settings = IAMSettings()
        # This is the fallback logic used in the application lifespan
        effective_workspace_name = (
            settings.default_workspace_name or settings.default_tenant_name
        )
        assert effective_workspace_name == settings.default_tenant_name
        assert effective_workspace_name == "default"

    def test_bootstrap_admin_usernames_empty_by_default(self):
        """Bootstrap admin usernames list should be empty by default.

        GIVEN no explicit configuration overrides
        THEN bootstrap admin usernames list is empty (no auto-admin provisioning)
        """
        settings = IAMSettings()
        assert settings.bootstrap_admin_usernames == []

    def test_single_tenant_mode_can_be_disabled(self, monkeypatch):
        """Single-tenant mode can be explicitly disabled.

        GIVEN KARTOGRAPH_IAM_SINGLE_TENANT_MODE=false
        THEN single-tenant mode is disabled
        """
        monkeypatch.setenv("KARTOGRAPH_IAM_SINGLE_TENANT_MODE", "false")
        settings = IAMSettings()
        assert settings.single_tenant_mode is False

    def test_explicit_workspace_name_overrides_fallback(self):
        """An explicit workspace name is used instead of tenant name fallback."""
        settings = IAMSettings(
            default_tenant_name="acme",
            default_workspace_name="Root",
        )
        effective_workspace_name = (
            settings.default_workspace_name or settings.default_tenant_name
        )
        assert effective_workspace_name == "Root"


class TestOutboxWorkerSettingsDefaults:
    """Tests for OutboxWorkerSettings defaults.

    Spec: specs/nfr/application-lifecycle.spec.md
    Requirement: Outbox Worker Lifecycle
    """

    def test_outbox_enabled_by_default(self):
        """Outbox processing should be enabled by default."""
        settings = OutboxWorkerSettings()
        assert settings.enabled is True

    def test_outbox_disabled_when_configured(self, monkeypatch):
        """Outbox can be disabled via environment variable."""
        monkeypatch.setenv("KARTOGRAPH_OUTBOX_ENABLED", "false")
        settings = OutboxWorkerSettings()
        assert settings.enabled is False
