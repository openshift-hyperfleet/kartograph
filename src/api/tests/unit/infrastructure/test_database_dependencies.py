"""Tests for database dependency injection.

Tests the lifespan-initialized database engines and FastAPI dependency
providers for async database sessions against a real database.
"""

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from main import app


class TestDatabaseEngineLifecycle:
    """Tests for database engine initialization via lifespan."""

    def test_lifespan_initializes_engines(self):
        """Test that lifespan creates engines on app.state."""
        with TestClient(app):
            # Lifespan has run, engines should exist
            assert hasattr(app.state, "write_engine")
            assert hasattr(app.state, "read_engine")
            assert hasattr(app.state, "write_sessionmaker")
            assert hasattr(app.state, "read_sessionmaker")

            assert isinstance(app.state.write_engine, AsyncEngine)
            assert isinstance(app.state.read_engine, AsyncEngine)

            # Verify engines are configured correctly
            assert app.state.write_engine.url.drivername == "postgresql+asyncpg"
            assert app.state.read_engine.url.drivername == "postgresql+asyncpg"

    def test_write_and_read_engines_are_separate(self):
        """Test that write and read engines are different instances."""
        with TestClient(app):
            write_engine = app.state.write_engine
            read_engine = app.state.read_engine

            # Write and read engines should be different
            assert write_engine is not read_engine


class TestDatabaseHealthEndpoint:
    """Tests for database connectivity via health endpoint."""

    def test_health_endpoint_works(self):
        """Test that health endpoint responds when DB is available."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
