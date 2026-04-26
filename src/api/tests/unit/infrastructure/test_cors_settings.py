"""Unit tests for CORSSettings configuration.

Covers spec: specs/nfr/cors.spec.md

Requirement: Configurable CORS Origins
Requirement: CORS Defaults
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from infrastructure.settings import CORSSettings


class TestCORSSettingsIsEnabled:
    """Tests for the is_enabled property.

    Scenario: Origins configured → middleware should activate.
    Scenario: No origins configured → middleware must not be installed.
    """

    def test_is_enabled_when_origins_configured(self) -> None:
        """is_enabled returns True when at least one origin is provided."""
        settings = CORSSettings(origins=["https://app.example.com"])

        assert settings.is_enabled is True

    def test_is_enabled_with_multiple_origins(self) -> None:
        """is_enabled returns True when multiple origins are configured."""
        settings = CORSSettings(
            origins=["https://app.example.com", "https://admin.example.com"]
        )

        assert settings.is_enabled is True

    def test_is_disabled_when_origins_empty(self) -> None:
        """is_enabled returns False when origins list is empty."""
        settings = CORSSettings(origins=[])

        assert settings.is_enabled is False

    def test_is_disabled_by_default(self) -> None:
        """CORS is disabled by default (no origins pre-configured)."""
        settings = CORSSettings()

        assert settings.is_enabled is False


class TestCORSSettingsDefaults:
    """Tests for CORS default values.

    Scenario: Default policy → all HTTP methods and all request headers allowed.
    """

    def test_allow_credentials_defaults_to_true(self) -> None:
        """Credentials should be allowed by default."""
        settings = CORSSettings(origins=["https://app.example.com"])

        assert settings.allow_credentials is True

    def test_allow_methods_permits_all_http_methods(self) -> None:
        """All HTTP methods should be allowed (wildcard or comprehensive list).

        Starlette interprets ['*'] as allowing any method, echoing back the
        requested method in preflight responses.
        """
        settings = CORSSettings(origins=["https://app.example.com"])

        # Either a wildcard or a comprehensive explicit list satisfies "all methods".
        # We verify all common RFC 7231 methods are covered.
        allow_methods = settings.allow_methods
        if "*" in allow_methods:
            # Wildcard explicitly covers all methods.
            pass
        else:
            required_methods = {"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"}
            assert required_methods.issubset(set(allow_methods)), (
                f"allow_methods must include all standard HTTP methods, got: {allow_methods}"
            )

    def test_allow_methods_uses_wildcard_for_all_methods(self) -> None:
        """allow_methods default should be ['*'] to satisfy 'all HTTP methods allowed'."""
        settings = CORSSettings(origins=["https://app.example.com"])

        assert settings.allow_methods == ["*"]

    def test_allow_headers_defaults_to_wildcard(self) -> None:
        """All request headers should be allowed by default."""
        settings = CORSSettings(origins=["https://app.example.com"])

        assert settings.allow_headers == ["*"]


class TestCORSWildcardOriginValidation:
    """Tests for wildcard origin restriction.

    Spec requirement: wildcard ('*') origins MUST NOT be used when
    credentials are allowed (explicit allowlist only).
    """

    def test_wildcard_origin_rejected_when_credentials_allowed(self) -> None:
        """ValidationError raised when origins=['*'] and allow_credentials=True."""
        with pytest.raises(ValidationError) as exc_info:
            CORSSettings(
                origins=["*"],
                allow_credentials=True,
            )

        error_str = str(exc_info.value)
        # Error message should mention the constraint
        assert "wildcard" in error_str.lower()
        assert "credentials" in error_str.lower()

    def test_wildcard_among_other_origins_rejected_when_credentials_allowed(
        self,
    ) -> None:
        """ValidationError raised when '*' is mixed with real origins and credentials on."""
        with pytest.raises(ValidationError):
            CORSSettings(
                origins=["https://app.example.com", "*"],
                allow_credentials=True,
            )

    def test_wildcard_origin_allowed_when_credentials_disabled(self) -> None:
        """Wildcard origin is valid when credentials are not required."""
        settings = CORSSettings(
            origins=["*"],
            allow_credentials=False,
        )

        assert settings.is_enabled is True
        assert "*" in settings.origins

    def test_explicit_origins_with_credentials_allowed(self) -> None:
        """Explicit origin list with credentials enabled is valid."""
        settings = CORSSettings(
            origins=["https://app.example.com"],
            allow_credentials=True,
        )

        assert settings.is_enabled is True
        assert settings.allow_credentials is True


class TestCORSSettingsFromEnv:
    """Tests for environment variable configuration."""

    def test_origins_parsed_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Origins should be parseable from a comma-separated environment variable."""
        monkeypatch.setenv(
            "KARTOGRAPH_CORS_ORIGINS",
            '["https://app.example.com","https://admin.example.com"]',
        )

        settings = CORSSettings()

        assert "https://app.example.com" in settings.origins
        assert "https://admin.example.com" in settings.origins
        assert settings.is_enabled is True

    def test_empty_origins_env_disables_cors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty origins from env should disable CORS."""
        monkeypatch.setenv("KARTOGRAPH_CORS_ORIGINS", "[]")

        settings = CORSSettings()

        assert settings.is_enabled is False
