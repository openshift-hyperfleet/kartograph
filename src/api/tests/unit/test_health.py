"""Unit tests for health check endpoints.

Covers spec/nfr/health-checks.spec.md requirements:
- Basic health check (GET /health)
- Database health check (GET /health/db) with correct HTTP status codes
- Startup ordering validated via Kubernetes deployment configuration
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app() -> FastAPI:
    """Create a minimal test app with health routes."""
    from health_routes import router

    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


# ─── Requirement: Basic Health Check ─────────────────────────────────────────


class TestBasicHealthEndpoint:
    """Tests for GET /health — basic liveness probe.

    Scenario: Application is running
    - GIVEN the application has started
    - WHEN GET /health is called
    - THEN a 200 response is returned with {"status": "ok"}
    """

    def test_health_returns_200(self) -> None:
        """GET /health returns HTTP 200."""
        client = TestClient(_make_app())
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_body(self) -> None:
        """GET /health response body is exactly {"status": "ok"}."""
        client = TestClient(_make_app())
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ─── Requirement: Database Health Check ──────────────────────────────────────


class TestDatabaseHealthEndpointReachable:
    """Tests for GET /health/db when database is reachable.

    Scenario: Database is reachable
    - GIVEN the application is running and the database is available
    - WHEN GET /health/db is called
    - THEN a 200 response is returned confirming database connectivity
    """

    def _connected_client(self) -> MagicMock:
        """Return a fake AgeGraphClient that reports a healthy connection."""
        fake = MagicMock()
        fake.verify_connection.return_value = True
        fake.graph_name = "test_graph"
        return fake

    def test_health_db_returns_200_when_connected(self) -> None:
        """GET /health/db returns HTTP 200 when database is reachable."""
        fake_client = self._connected_client()

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        assert response.status_code == 200

    def test_health_db_confirms_connectivity_in_body(self) -> None:
        """GET /health/db response body confirms database is connected."""
        fake_client = self._connected_client()

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        body = response.json()
        assert body["status"] == "ok"
        assert body["connected"] is True

    def test_health_db_includes_graph_name_in_body(self) -> None:
        """GET /health/db response body includes the graph name."""
        fake_client = self._connected_client()

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        assert response.json()["graph_name"] == "test_graph"


class TestDatabaseHealthEndpointUnreachable:
    """Tests for GET /health/db when database is unreachable.

    Scenario: Database is unreachable
    - GIVEN the application is running but the database is unavailable
    - WHEN GET /health/db is called
    - THEN a 503 Service Unavailable response is returned
    - AND the response body contains an error message
    """

    def test_health_db_returns_503_when_pool_creation_fails(self) -> None:
        """GET /health/db returns 503 when pool cannot be created (DB is down)."""
        from infrastructure.database.exceptions import DatabaseConnectionError

        with patch(
            "health_routes.get_age_connection_pool",
            side_effect=DatabaseConnectionError("Connection refused"),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        assert response.status_code == 503

    def test_health_db_error_body_contains_message_when_pool_fails(self) -> None:
        """GET /health/db 503 response body contains an error message."""
        from infrastructure.database.exceptions import DatabaseConnectionError

        with patch(
            "health_routes.get_age_connection_pool",
            side_effect=DatabaseConnectionError("Connection refused"),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        body = response.json()
        assert "detail" in body
        assert len(body["detail"]) > 0

    def test_health_db_returns_503_when_connect_fails(self) -> None:
        """GET /health/db returns 503 when client.connect() fails."""
        from infrastructure.database.exceptions import DatabaseConnectionError

        fake_client = MagicMock()
        fake_client.connect.side_effect = DatabaseConnectionError("Cannot connect")

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        assert response.status_code == 503

    def test_health_db_returns_503_when_verify_connection_returns_false(self) -> None:
        """GET /health/db returns 503 when verify_connection() reports unhealthy."""
        fake_client = MagicMock()
        fake_client.verify_connection.return_value = False
        fake_client.graph_name = "test_graph"

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        assert response.status_code == 503

    def test_health_db_error_body_contains_message_when_unhealthy(self) -> None:
        """GET /health/db 503 response body contains an error message when unhealthy."""
        fake_client = MagicMock()
        fake_client.verify_connection.return_value = False
        fake_client.graph_name = "test_graph"

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            client = TestClient(_make_app())
            response = client.get("/health/db")

        body = response.json()
        assert "detail" in body
        assert len(body["detail"]) > 0

    def test_health_db_disconnect_called_even_on_verify_failure(self) -> None:
        """client.disconnect() is always called after connect(), even on failure."""
        fake_client = MagicMock()
        fake_client.verify_connection.return_value = False

        with (
            patch("health_routes.get_age_connection_pool"),
            patch("health_routes.get_database_settings"),
            patch("health_routes.ConnectionFactory"),
            patch("health_routes.AgeGraphClient", return_value=fake_client),
        ):
            TestClient(_make_app()).get("/health/db")

        fake_client.disconnect.assert_called_once()


# ─── Requirement: Startup Ordering ───────────────────────────────────────────

# The Kubernetes API deployment uses init containers to enforce startup ordering:
# - wait-for-db-migrate:     waits for the database migration job to complete
# - wait-for-spicedb-schema: waits for the SpiceDB schema job to complete
# Both init containers run (sequentially) before the main API container starts,
# which satisfies "the application waits for ... before starting".

_DEPLOY_YAML = (
    Path(__file__).parents[4]
    / "deploy"
    / "apps"
    / "kartograph"
    / "base"
    / "api-deployment.yaml"
)


def _load_init_containers() -> list[dict]:
    """Parse and return the init containers from the API deployment spec."""
    with open(_DEPLOY_YAML) as fh:
        doc = yaml.safe_load(fh)
    return doc["spec"]["template"]["spec"].get("initContainers", [])


class TestStartupOrderingDbMigrations:
    """Scenario: Database migration dependency.

    - GIVEN the application is starting
    - WHEN database migrations have not yet completed
    - THEN the application waits for migration completion before starting

    Enforced via a Kubernetes init container that blocks the main container
    from starting until the migration Job has completed successfully.
    """

    def test_deployment_has_db_migrate_init_container(self) -> None:
        """API deployment must declare a 'wait-for-db-migrate' init container."""
        names = [c["name"] for c in _load_init_containers()]
        assert "wait-for-db-migrate" in names, (
            "Deployment must have 'wait-for-db-migrate' init container "
            "to block startup until database migrations complete."
        )

    def test_db_migrate_init_container_references_migration_job(self) -> None:
        """wait-for-db-migrate init container must reference the migration Job."""
        container = next(
            c for c in _load_init_containers() if c["name"] == "wait-for-db-migrate"
        )
        # The command must reference the job that runs alembic migrations.
        command_str = " ".join(str(part) for part in container["command"])
        assert "kartograph-db-migrate" in command_str, (
            "wait-for-db-migrate must wait on the 'kartograph-db-migrate' Job."
        )


class TestStartupOrderingSpiceDBSchema:
    """Scenario: Authorization schema dependency.

    - GIVEN the application is starting
    - WHEN the SpiceDB schema has not yet been loaded
    - THEN the application waits for schema initialization before starting

    Enforced via a Kubernetes init container that blocks the main container
    from starting until the SpiceDB schema Job has completed successfully.
    """

    def test_deployment_has_spicedb_schema_init_container(self) -> None:
        """API deployment must declare a 'wait-for-spicedb-schema' init container."""
        names = [c["name"] for c in _load_init_containers()]
        assert "wait-for-spicedb-schema" in names, (
            "Deployment must have 'wait-for-spicedb-schema' init container "
            "to block startup until SpiceDB schema is loaded."
        )

    def test_spicedb_schema_init_container_references_schema_job(self) -> None:
        """wait-for-spicedb-schema init container must reference the schema Job."""
        container = next(
            c for c in _load_init_containers() if c["name"] == "wait-for-spicedb-schema"
        )
        command_str = " ".join(str(part) for part in container["command"])
        assert "kartograph-spicedb-schema" in command_str, (
            "wait-for-spicedb-schema must wait on the 'kartograph-spicedb-schema' Job."
        )

    def test_db_migrate_runs_before_spicedb_schema(self) -> None:
        """DB migration init container must appear before SpiceDB schema init container.

        Kubernetes runs init containers sequentially in definition order,
        so position encodes dependency: migrations before schema loading.
        """
        containers = _load_init_containers()
        names = [c["name"] for c in containers]
        assert "wait-for-db-migrate" in names
        assert "wait-for-spicedb-schema" in names
        migrate_idx = names.index("wait-for-db-migrate")
        spicedb_idx = names.index("wait-for-spicedb-schema")
        assert migrate_idx < spicedb_idx, (
            "wait-for-db-migrate must precede wait-for-spicedb-schema "
            "in the init containers list."
        )
