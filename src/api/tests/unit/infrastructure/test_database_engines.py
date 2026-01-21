"""Unit tests for database engine creation.

Tests the creation and configuration of async SQLAlchemy engines for read/write operations.
"""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from infrastructure.database.engines import (
    build_async_url,
    create_read_engine,
    create_write_engine,
)
from infrastructure.settings import DatabaseSettings


@pytest.fixture
def mock_db_settings() -> DatabaseSettings:
    """Create mock database settings for testing."""
    return DatabaseSettings(
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password=SecretStr("test_password"),
        pool_min_connections=2,
        pool_max_connections=10,
    )


def test_build_async_url(mock_db_settings):
    """Test async database URL construction."""
    url = build_async_url(mock_db_settings)

    assert url == (
        "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db?ssl=prefer"
    )


def test_build_async_url_with_special_characters():
    """Test URL construction with special characters in password."""
    settings = DatabaseSettings(
        host="db.example.com",
        port=5432,
        database="mydb",
        username="user@domain",
        password=SecretStr("p@ssw0rd!#$"),
    )

    url = build_async_url(settings)

    # Credentials should be percent-encoded per RFC 3986
    # @ -> %40, ! -> %21, # -> %23, $ -> %24
    assert "user%40domain" in url  # username encoded
    assert "p%40ssw0rd%21%23%24" in url  # password encoded
    # Raw special characters should NOT be in the URL
    assert "user@domain" not in url
    assert "p@ssw0rd!#$" not in url


def test_create_write_engine(mock_db_settings):
    """Test write engine creation with proper configuration."""
    engine = create_write_engine(mock_db_settings)

    assert isinstance(engine, AsyncEngine)
    assert engine.pool.size() == mock_db_settings.pool_max_connections
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "test_db"

    # Cleanup
    engine.sync_engine.dispose()


def test_create_read_engine(mock_db_settings):
    """Test read engine creation with proper configuration."""
    engine = create_read_engine(mock_db_settings)

    assert isinstance(engine, AsyncEngine)
    assert engine.pool.size() == mock_db_settings.pool_max_connections
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "test_db"

    # Cleanup
    engine.sync_engine.dispose()


def test_engines_use_separate_pools(mock_db_settings):
    """Test that read and write engines have separate connection pools."""
    write_engine = create_write_engine(mock_db_settings)
    read_engine = create_read_engine(mock_db_settings)

    # Engines should be different instances
    assert write_engine is not read_engine

    # Should have separate pools
    assert write_engine.pool is not read_engine.pool

    # Cleanup
    write_engine.sync_engine.dispose()
    read_engine.sync_engine.dispose()


def test_engine_pool_configuration(mock_db_settings):
    """Test that engine pools are configured correctly."""
    engine = create_write_engine(mock_db_settings)

    # Pool should respect max connections
    assert engine.pool.size() == 10

    # Configuration verified via engine creation parameters
    # (max_overflow=0 behavior is tested via integration tests)

    # Cleanup
    engine.sync_engine.dispose()
