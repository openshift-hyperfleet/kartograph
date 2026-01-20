"""Integration test fixtures for database and authentication tests.

These fixtures require running services:
- PostgreSQL instance with AGE extension
- Keycloak for authentication tests

Use docker-compose for testing.

IMPORTANT: Environment variables must be set at the top of this file,
before ANY imports that might trigger settings caching.
"""

# Step 1: Set environment variables FIRST, before any other imports
import os

# Step 2: Now safe to import other modules
from collections.abc import Generator

import httpx
import pytest
from pydantic import SecretStr

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings

os.environ.setdefault("SPICEDB_ENDPOINT", "localhost:50051")
os.environ.setdefault("SPICEDB_PRESHARED_KEY", "changeme")
os.environ.setdefault("SPICEDB_USE_TLS", "true")

# Configure SpiceDB client to use the self-signed certificate
_cert_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "certs", "spicedb-cert.pem"
)
if os.path.exists(_cert_path):
    os.environ.setdefault("SPICEDB_CERT_PATH", os.path.abspath(_cert_path))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires database)",
    )
    config.addinivalue_line(
        "markers",
        "keycloak: mark test as requiring Keycloak authentication server",
    )


@pytest.fixture(scope="session")
def integration_db_settings() -> DatabaseSettings:
    """Database settings for integration tests.

    Override with environment variables:
        KARTOGRAPH_DB_HOST, KARTOGRAPH_DB_PORT, etc.
    """
    return DatabaseSettings(
        host=os.getenv("KARTOGRAPH_DB_HOST", "localhost"),
        port=int(os.getenv("KARTOGRAPH_DB_PORT", "5432")),
        database=os.getenv("KARTOGRAPH_DB_DATABASE", "kartograph"),
        username=os.getenv("KARTOGRAPH_DB_USERNAME", "kartograph"),
        password=SecretStr(
            os.getenv("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password")
        ),
        graph_name=os.getenv("KARTOGRAPH_DB_GRAPH_NAME", "test_graph"),
    )


@pytest.fixture(scope="session")
def integration_connection_pool(
    integration_db_settings: DatabaseSettings,
) -> Generator[ConnectionPool, None, None]:
    """Session-scoped connection pool for integration tests."""
    pool = ConnectionPool(integration_db_settings)
    yield pool
    pool.close_all()


@pytest.fixture
def graph_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provide a connected graph client for integration tests.

    Automatically connects and disconnects around each test.
    Uses connection pool to match production behavior.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    client = AgeGraphClient(integration_db_settings, connection_factory=factory)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture
def clean_graph(graph_client: AgeGraphClient):
    """Ensure a clean graph state before and after each test.

    Deletes all nodes and relationships in the test graph.
    """
    # Clean before test
    try:
        graph_client.execute_cypher("MATCH (n) DETACH DELETE n")
    except Exception:
        pass  # Graph might be empty or not exist

    yield graph_client

    # Clean after test
    try:
        graph_client.execute_cypher("MATCH (n) DETACH DELETE n")
    except Exception:
        pass


# =============================================================================
# Keycloak / OIDC Authentication Fixtures
# =============================================================================

# Set OIDC defaults for tests (can be overridden by env vars)
os.environ.setdefault(
    "KARTOGRAPH_OIDC_ISSUER_URL", "http://localhost:8080/realms/kartograph"
)
os.environ.setdefault("KARTOGRAPH_OIDC_CLIENT_ID", "kartograph-api")
os.environ.setdefault("KARTOGRAPH_OIDC_CLIENT_SECRET", "kartograph-api-secret")


@pytest.fixture(scope="session")
def oidc_settings():
    """OIDC settings for integration tests.

    Uses OIDCSettings from infrastructure, which reads from environment.
    Default issuer is localhost:8080 for host-based testing.

    For containerized tests, set KARTOGRAPH_OIDC_ISSUER_URL to use
    Docker service names (e.g., http://keycloak:8080/realms/kartograph).
    """
    from infrastructure.settings import get_oidc_settings

    # Clear the lru_cache to pick up test env vars
    get_oidc_settings.cache_clear()
    return get_oidc_settings()


@pytest.fixture
def keycloak_token_url(oidc_settings) -> str:
    """Keycloak token endpoint URL derived from OIDC settings."""
    return f"{oidc_settings.issuer_url}/protocol/openid-connect/token"


@pytest.fixture
def oidc_client_credentials(oidc_settings) -> dict[str, str]:
    """OIDC client credentials from settings."""
    return {
        "client_id": oidc_settings.client_id,
        "client_secret": oidc_settings.client_secret.get_secret_value(),
    }


@pytest.fixture
def get_test_token(keycloak_token_url: str, oidc_client_credentials: dict[str, str]):
    """Factory fixture to get access tokens for test users.

    Uses OAuth2 password grant (deprecated but acceptable for integration tests).
    Requires Keycloak to be running.

    Usage:
        def test_something(get_test_token):
            token = get_test_token("alice", "password")
            headers = {"Authorization": f"Bearer {token}"}
    """

    def _get_token(username: str, password: str) -> str:
        with httpx.Client() as client:
            response = client.post(
                keycloak_token_url,
                data={
                    "grant_type": "password",
                    "client_id": oidc_client_credentials["client_id"],
                    "client_secret": oidc_client_credentials["client_secret"],
                    "username": username,
                    "password": password,
                    "scope": "openid profile email",
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    return _get_token


@pytest.fixture
def alice_token(get_test_token) -> str:
    """Get access token for alice user."""
    return get_test_token("alice", "password")


@pytest.fixture
def bob_token(get_test_token) -> str:
    """Get access token for bob user."""
    return get_test_token("bob", "password")


@pytest.fixture
def auth_headers(alice_token: str) -> dict[str, str]:
    """Default auth headers using alice's token."""
    return {"Authorization": f"Bearer {alice_token}"}
