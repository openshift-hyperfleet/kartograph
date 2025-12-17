"""Unit tests for infrastructure settings."""

import pytest
from pydantic import ValidationError

from infrastructure.settings import DatabaseSettings


class TestDatabaseSettingsPoolConfiguration:
    """Tests for connection pool configuration."""

    def test_default_pool_settings(self):
        """Should have sensible pool defaults."""
        settings = DatabaseSettings()
        assert settings.pool_min_connections >= 1
        assert settings.pool_max_connections >= settings.pool_min_connections
        assert settings.pool_max_connections <= 20
        assert settings.pool_enabled is True

    def test_pool_settings_from_fields(self):
        """Should accept pool settings via constructor."""
        settings = DatabaseSettings(
            pool_min_connections=5,
            pool_max_connections=15,
            pool_enabled=True,
        )
        assert settings.pool_min_connections == 5
        assert settings.pool_max_connections == 15
        assert settings.pool_enabled is True

    def test_pool_can_be_disabled(self):
        """Should allow disabling pool for tests."""
        settings = DatabaseSettings(pool_enabled=False)
        assert settings.pool_enabled is False

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
