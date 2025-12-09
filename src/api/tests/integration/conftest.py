"""Integration test fixtures for database tests.

These fixtures require a running PostgreSQL instance with AGE extension.
Use docker-compose for testing.
"""

from collections.abc import Generator
import os

import pytest
from pydantic import SecretStr

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.settings import DatabaseSettings


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires database)",
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


@pytest.fixture
def graph_client(
    integration_db_settings: DatabaseSettings,
) -> Generator[AgeGraphClient, None, None]:
    """Provide a connected graph client for integration tests.

    Automatically connects and disconnects around each test.
    """
    client = AgeGraphClient(integration_db_settings)
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
