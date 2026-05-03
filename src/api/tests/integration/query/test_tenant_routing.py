"""Integration tests for per-tenant graph routing in the Querying bounded context.

Spec: specs/query/query-execution.spec.md
Requirement: Per-Tenant Graph Routing

Scenarios covered:
  1. Query routed to tenant graph (cross-tenant isolation) — each tenant's
     QueryGraphRepository sees only its own AGE graph; data in one tenant's
     graph is invisible to another tenant's repository.

  2. Tenant graph not found raises QueryExecutionError before DB — when a
     tenant's AGE graph has not been provisioned, the system raises
     QueryExecutionError from TenantAwareQueryGraphRepository (backed by
     AGEGraphExistenceChecker querying ag_catalog.ag_graph) without issuing
     any Cypher to the database.

Run with:
    pytest -m integration tests/integration/query/test_tenant_routing.py
    # or via make:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest tests/integration/query/test_tenant_routing.py -v -m integration

Requires: Running PostgreSQL with AGE extension.
"""

from __future__ import annotations

import uuid
from typing import Generator

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from query.domain.value_objects import QueryExecutionError
from query.infrastructure.query_repository import QueryGraphRepository
from query.infrastructure.tenant_routing import (
    AGEGraphExistenceChecker,
    TenantAwareQueryGraphRepository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant_graph_name(unique_suffix: str) -> str:
    """Build a deterministic tenant graph name for tests."""
    return f"tenant_{unique_suffix}"


def _drop_graph_if_exists(
    pool: ConnectionPool,
    graph_name: str,
) -> None:
    """Drop an AGE graph, ignoring if it has already been removed."""
    conn = pool.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                (graph_name,),
            )
            if cursor.fetchone() is not None:
                cursor.execute(
                    "SELECT ag_catalog.drop_graph(%s, true)",
                    (graph_name,),
                )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        pool.return_connection(conn)


def _create_connected_tenant_client(
    settings: DatabaseSettings,
    pool: ConnectionPool,
    graph_name: str,
) -> AgeGraphClient:
    """Create and connect an AgeGraphClient targeting a specific tenant graph.

    Uses auto_create=True so the AGE graph is provisioned if absent.
    """
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(
        settings,
        connection_factory=factory,
        graph_name=graph_name,
        auto_create=True,
    )
    client.connect()
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_a_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provision tenant A's AGE graph and yield a connected client.

    Drops the graph during teardown to keep the database clean.
    """
    graph_name = _make_tenant_graph_name(f"a_{uuid.uuid4().hex[:8]}")
    client = _create_connected_tenant_client(
        integration_db_settings,
        integration_connection_pool,
        graph_name,
    )
    yield client
    client.disconnect()
    _drop_graph_if_exists(integration_connection_pool, graph_name)


@pytest.fixture
def tenant_b_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provision tenant B's AGE graph and yield a connected client.

    Drops the graph during teardown to keep the database clean.
    """
    graph_name = _make_tenant_graph_name(f"b_{uuid.uuid4().hex[:8]}")
    client = _create_connected_tenant_client(
        integration_db_settings,
        integration_connection_pool,
        graph_name,
    )
    yield client
    client.disconnect()
    _drop_graph_if_exists(integration_connection_pool, graph_name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPerTenantGraphRouting:
    """Integration tests for the Per-Tenant Graph Routing requirement.

    Spec: specs/query/query-execution.spec.md — Requirement: Per-Tenant Graph Routing
    """

    def test_query_executes_in_tenant_graph(
        self,
        tenant_a_client: AgeGraphClient,
        tenant_b_client: AgeGraphClient,
    ) -> None:
        """
        Spec Scenario: Query routed to tenant graph

        GIVEN two provisioned tenant graphs each belonging to a different tenant
        WHEN data is written only to tenant A's graph
        AND each tenant's QueryGraphRepository executes the same Cypher query
        THEN tenant A's repository returns its own data
        AND tenant B's repository returns nothing (empty graph)
        AND queries never cross tenant boundaries regardless of query content.

        The per-tenant isolation is enforced by the AGE ``cypher('graph_name', …)``
        call: each QueryGraphRepository uses the client's ``graph_name`` so rows
        can never leak across tenant boundaries.
        """
        # Seed tenant A's graph with a distinguishable node.
        tenant_a_client.execute_cypher("CREATE (n:Person {name: 'Alice', tenant: 'A'})")

        # Construct one repository per tenant — each targets its own graph.
        repo_a = QueryGraphRepository(client=tenant_a_client)
        repo_b = QueryGraphRepository(client=tenant_b_client)

        # --- Tenant A query ---
        results_a = repo_a.execute_cypher(
            "MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}"
        )

        assert len(results_a) == 1, (
            f"Expected exactly 1 Person in tenant A graph '{tenant_a_client.graph_name}', "
            f"got {len(results_a)}"
        )
        assert results_a[0]["name"] == "Alice"
        assert results_a[0]["tenant"] == "A"

        # --- Tenant B query (cross-tenant isolation) ---
        # Tenant B's graph is empty — Alice must NOT appear here.
        results_b = repo_b.execute_cypher(
            "MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}"
        )

        assert len(results_b) == 0, (
            f"Cross-tenant isolation violated: tenant B's graph "
            f"'{tenant_b_client.graph_name}' returned {len(results_b)} row(s) "
            "that should only exist in tenant A's graph. "
            f"Rows: {results_b}"
        )

    def test_tenant_graph_not_found_raises_before_db(
        self,
        integration_db_settings: DatabaseSettings,
        integration_connection_pool: ConnectionPool,
        graph_client: AgeGraphClient,
    ) -> None:
        """
        Spec Scenario: Tenant graph not found

        GIVEN a tenant whose AGE graph has NOT been provisioned
        WHEN a query is submitted via TenantAwareQueryGraphRepository
        THEN QueryExecutionError is raised before any Cypher reaches the database.
        AND the error message identifies the missing graph by name.

        Implementation details verified:
        - AGEGraphExistenceChecker queries ag_catalog.ag_graph (real DB round-trip)
          and correctly returns False for a graph that does not exist.
        - TenantAwareQueryGraphRepository raises QueryExecutionError immediately,
          never delegating to the inner QueryGraphRepository.

        The inner repository (``graph_client`` / QueryGraphRepository targeting the
        shared test_graph) would succeed if called, so if the outer layer
        incorrectly delegates, the query would return results instead of raising —
        making the test self-verifying.
        """
        # Use a random suffix to guarantee the graph has never been provisioned.
        ghost_tenant_id = f"ghost_{uuid.uuid4().hex[:8]}"
        expected_graph_name = _make_tenant_graph_name(ghost_tenant_id)

        # Production components wired to the real database:
        factory = ConnectionFactory(
            integration_db_settings, pool=integration_connection_pool
        )
        existence_checker = AGEGraphExistenceChecker(factory)

        # Inner repository: the existing graph_client targets test_graph (which
        # DOES exist). If TenantAwareQueryGraphRepository incorrectly skips the
        # existence check and calls the inner repo, the query would succeed and
        # no exception would be raised — failing the assertion below.
        inner_repo = QueryGraphRepository(client=graph_client)

        tenant_repo = TenantAwareQueryGraphRepository(
            tenant_id=ghost_tenant_id,
            inner_repository=inner_repo,
            existence_check_fn=existence_checker,
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            tenant_repo.execute_cypher("MATCH (n) RETURN n")

        error_message = str(exc_info.value)
        assert expected_graph_name in error_message, (
            f"Expected QueryExecutionError message to name the missing graph "
            f"'{expected_graph_name}', but got: {error_message!r}"
        )
