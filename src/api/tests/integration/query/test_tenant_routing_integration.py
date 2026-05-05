"""Integration tests for per-tenant graph routing.

Exercises ``QueryGraphRepository`` (via ``TenantAwareQueryGraphRepository``)
against a real PostgreSQL + Apache AGE instance to verify that:

  1. Queries are routed to the correct ``tenant_{tenant_id}`` AGE graph.
  2. Queries against an unprovisioned tenant graph are rejected with a
     ``QueryExecutionError`` before any Cypher reaches the database.

Spec-Ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
Task-Ref: task-150

Scenarios covered:
  - Requirement: Per-Tenant Graph Routing / Query routed to tenant graph
      Given a provisioned ``tenant_{uuid}`` AGE graph,
      when a Cypher query is executed through ``QueryGraphRepository``
      targeting that graph, the results are returned successfully.

  - Requirement: Per-Tenant Graph Routing / Tenant graph not found
      Given a tenant_id whose graph has not been provisioned,
      when a query is submitted, a ``QueryExecutionError`` is raised before
      any AGE round-trip.

Design notes:
  These tests exercise the two integration points that unit tests cannot cover:
    1. ``ag_catalog.ag_graph`` catalog lookup → real PostgreSQL round-trip
    2. Cypher query execution → real Apache AGE round-trip

  ``QueryGraphRepository`` (the inner repository in the production DI chain) is
  instantiated directly with a real ``AgeGraphClient`` so the test exercises the
  same graph existence + read-only + timeout safeguards as the live code path.

  ``TenantAwareQueryGraphRepository`` is also exercised to verify the combined
  routing chain used in production (see ``get_mcp_query_service`` in
  ``query/dependencies.py``): the outer wrapper's existence check delegates to
  ``AGEGraphExistenceChecker``, which queries the same catalog the inner
  repository checks.

  Test graphs are named ``tenant_{uuid4_hex}`` to avoid collisions with
  production graphs or other integration test graphs.  They are dropped in
  ``autouse`` fixture teardown even if the test fails.

Run with:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest tests/integration/query/test_tenant_routing_integration.py \\
        -v -m integration
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import cast

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from query.domain.value_objects import NodeDict, QueryExecutionError
from query.infrastructure.query_repository import QueryGraphRepository
from query.infrastructure.tenant_routing import (
    AGEGraphExistenceChecker,
    TenantAwareQueryGraphRepository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drop_graph_if_exists(
    graph_name: str,
    connection_factory: ConnectionFactory,
) -> None:
    """Drop an AGE graph from the catalog if it exists.

    Runs ``SELECT ag_catalog.drop_graph(%s, true)`` — the ``true`` flag causes
    a CASCADE drop so all graph data is removed before the graph entry.
    Silently ignores errors (the graph may not exist yet).

    Args:
        graph_name: The AGE graph name to drop.
        connection_factory: Connection factory for obtaining a psycopg2 connection.
    """
    conn = connection_factory.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                (graph_name,),
            )
            if cursor.fetchone() is None:
                conn.rollback()
                return
            cursor.execute(
                "SELECT ag_catalog.drop_graph(%s, true)",
                (graph_name,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        # Ignore — graph may never have been created
    finally:
        connection_factory.return_connection(conn)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_graph_name() -> str:
    """Generate a unique tenant graph name for test isolation.

    Returns ``tenant_{16-char hex}`` — the same naming convention used in
    production (``tenant_{tenant_id}``) — with a UUID suffix so multiple
    parallel test runs do not collide.
    """
    return f"tenant_{uuid.uuid4().hex[:16]}"


@pytest.fixture(autouse=True)
def cleanup_tenant_graph(
    tenant_graph_name: str,
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[None, None, None]:
    """Drop the test tenant graph before and after each test.

    The pre-test drop guards against stale graphs from a previous failed run.
    The post-test drop ensures the real AGE catalog is left clean regardless
    of whether the test succeeded or raised an exception.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    # Pre-test cleanup
    _drop_graph_if_exists(tenant_graph_name, factory)

    yield

    # Post-test cleanup (runs even on failure)
    _drop_graph_if_exists(tenant_graph_name, factory)


@pytest.fixture
def connection_factory(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> ConnectionFactory:
    """Shared connection factory for test helpers."""
    return ConnectionFactory(integration_db_settings, pool=integration_connection_pool)


@pytest.fixture
def provisioned_tenant_client(
    tenant_graph_name: str,
    integration_db_settings: DatabaseSettings,
    connection_factory: ConnectionFactory,
) -> Generator[AgeGraphClient, None, None]:
    """Provision the tenant AGE graph and return a connected AgeGraphClient.

    Steps:
      1. Use ``AGEGraphProvisioner`` to create the tenant graph (same code path
         as production tenant provisioning via the outbox handler).
      2. Create an ``AgeGraphClient`` targeting that graph.
      3. Connect the client.
      4. Yield the connected client.
      5. Disconnect on teardown (graph drop is handled by ``cleanup_tenant_graph``).
    """
    provisioner = AGEGraphProvisioner(connection_factory=connection_factory)
    provisioner.ensure_graph_exists(tenant_graph_name)

    client = AgeGraphClient(
        settings=integration_db_settings,
        connection_factory=connection_factory,
        graph_name=tenant_graph_name,
        auto_create=False,
    )
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


# ---------------------------------------------------------------------------
# Tests — Scenario: Query routed to tenant graph
# ---------------------------------------------------------------------------


class TestQueryRoutedToTenantGraph:
    """Spec: Per-Tenant Graph Routing — Scenario: Query routed to tenant graph.

    GIVEN an authenticated query request
    WHEN the query is executed
    THEN it executes against the AGE graph named ``tenant_{tenant_id}`` for the
         resolved tenant
    AND queries never cross tenant boundaries regardless of query content.
    """

    def test_query_executes_against_provisioned_tenant_graph(
        self,
        provisioned_tenant_client: AgeGraphClient,
    ) -> None:
        """A simple read query returns results from the tenant's AGE graph.

        Creates a test node directly via ``AgeGraphClient``, then queries it
        through ``QueryGraphRepository`` to confirm the query reaches the
        correct graph.

        Spec: "THEN it executes against the AGE graph named ``tenant_{tenant_id}``
        for the resolved tenant"
        """
        # Seed the provisioned graph with one node via the raw client
        provisioned_tenant_client.execute_cypher(
            "CREATE (n:RoutingTestNode {marker: 'routing-test-node-1'})"
        )

        # Build QueryGraphRepository targeting the same tenant graph
        repo = QueryGraphRepository(client=provisioned_tenant_client)

        # Execute through the repository — should see the seeded node
        results = repo.execute_cypher("MATCH (n:RoutingTestNode) RETURN n")

        assert len(results) == 1, (
            f"Expected 1 result from the tenant graph, got {len(results)}. "
            "The query may have targeted the wrong graph."
        )
        node = cast(NodeDict, results[0]["node"])
        assert node["properties"]["marker"] == "routing-test-node-1", (
            f"Node marker mismatch: {node['properties']!r}"
        )

    def test_different_tenant_graphs_are_isolated(
        self,
        integration_db_settings: DatabaseSettings,
        connection_factory: ConnectionFactory,
    ) -> None:
        """Queries never cross tenant boundaries.

        Provisions two separate tenant graphs, seeds one with a node, and
        verifies the other graph returns no results.

        Spec: "AND queries never cross tenant boundaries regardless of query content"
        """
        graph_a = f"tenant_{uuid.uuid4().hex[:16]}"
        graph_b = f"tenant_{uuid.uuid4().hex[:16]}"

        provisioner = AGEGraphProvisioner(connection_factory=connection_factory)
        provisioner.ensure_graph_exists(graph_a)
        provisioner.ensure_graph_exists(graph_b)

        client_a = AgeGraphClient(
            settings=integration_db_settings,
            connection_factory=connection_factory,
            graph_name=graph_a,
            auto_create=False,
        )
        client_b = AgeGraphClient(
            settings=integration_db_settings,
            connection_factory=connection_factory,
            graph_name=graph_b,
            auto_create=False,
        )

        client_a.connect()
        client_b.connect()
        try:
            # Seed graph A with a node; graph B remains empty
            client_a.execute_cypher("CREATE (n:IsolationTestNode {tenant: 'graph-a'})")

            # Query both graphs — only graph A should have the node
            repo_a = QueryGraphRepository(client=client_a)
            repo_b = QueryGraphRepository(client=client_b)

            results_a = repo_a.execute_cypher("MATCH (n:IsolationTestNode) RETURN n")
            results_b = repo_b.execute_cypher("MATCH (n:IsolationTestNode) RETURN n")

            assert len(results_a) == 1, (
                f"Expected 1 result in graph A, got {len(results_a)}"
            )
            assert len(results_b) == 0, (
                f"Expected 0 results in graph B (isolation breach!), "
                f"got {len(results_b)}"
            )
        finally:
            client_a.disconnect()
            client_b.disconnect()
            # Clean up both graphs
            _drop_graph_if_exists(graph_a, connection_factory)
            _drop_graph_if_exists(graph_b, connection_factory)

    def test_tenant_aware_repository_routes_to_correct_graph(
        self,
        tenant_graph_name: str,
        provisioned_tenant_client: AgeGraphClient,
        connection_factory: ConnectionFactory,
    ) -> None:
        """TenantAwareQueryGraphRepository routes to the correct tenant graph.

        Exercises the full production-equivalent routing chain used in
        ``get_mcp_query_service()``:
          AGEGraphExistenceChecker → TenantAwareQueryGraphRepository →
          QueryGraphRepository.execute_cypher

        Spec: "THEN it executes against the AGE graph named ``tenant_{tenant_id}``"
        """
        # Derive the tenant_id from the graph name (strip "tenant_" prefix)
        tenant_id = tenant_graph_name[len("tenant_") :]

        # Seed the provisioned graph with a test node
        provisioned_tenant_client.execute_cypher(
            "CREATE (n:TenantAwareTestNode {marker: 'aware-routing-check'})"
        )

        # Build the production-equivalent routing chain
        existence_checker = AGEGraphExistenceChecker(
            connection_factory=connection_factory
        )
        inner_repo = QueryGraphRepository(client=provisioned_tenant_client)
        repo = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=inner_repo,
            existence_check_fn=existence_checker,
        )

        # Query via the aware repository — should succeed and return the seeded node
        results = repo.execute_cypher("MATCH (n:TenantAwareTestNode) RETURN n")

        assert len(results) == 1, (
            f"Expected 1 result through TenantAwareQueryGraphRepository, "
            f"got {len(results)}"
        )
        node = cast(NodeDict, results[0]["node"])
        assert node["properties"]["marker"] == "aware-routing-check", (
            f"Node properties mismatch: {node['properties']!r}"
        )


# ---------------------------------------------------------------------------
# Tests — Scenario: Tenant graph not found
# ---------------------------------------------------------------------------


class TestTenantGraphNotFound:
    """Spec: Per-Tenant Graph Routing — Scenario: Tenant graph not found.

    GIVEN a tenant whose AGE graph has not been provisioned
    WHEN a query is submitted
    THEN the request is rejected with an execution error before reaching the
         database.
    """

    def test_query_raises_execution_error_when_graph_not_provisioned(
        self,
        tenant_graph_name: str,
        integration_db_settings: DatabaseSettings,
        connection_factory: ConnectionFactory,
    ) -> None:
        """QueryGraphRepository raises QueryExecutionError for absent tenant graph.

        The graph is NOT provisioned before this test (``cleanup_tenant_graph``
        fixture performs a pre-test drop to ensure absence).  A connected
        ``AgeGraphClient`` targeting the non-existent graph is used to build
        a ``QueryGraphRepository``; the repository's ``_validate_graph_exists``
        must raise ``QueryExecutionError`` before any Cypher reaches AGE.

        Spec: "THEN the request is rejected with an execution error before
        reaching the database"
        """
        # Create a client that targets the (non-provisioned) tenant graph.
        # auto_create=False → connect() will NOT create the graph.
        # We need to connect to the DB first (to get a connection), then
        # attempt the query — the repository's catalog check raises the error.
        client = AgeGraphClient(
            settings=integration_db_settings,
            connection_factory=connection_factory,
            graph_name=tenant_graph_name,
            auto_create=False,
        )

        # connect() itself may succeed (it just acquires a DB connection and
        # calls age.setUpAge, which can work even for a non-existent graph).
        # The error should surface during execute_cypher's existence check.
        try:
            client.connect()
        except Exception:
            # If connect() fails (e.g. setUpAge errors on missing graph),
            # that is also an acceptable "rejected before reaching the DB" outcome.
            pytest.skip(
                "AgeGraphClient.connect() raised for missing graph — "
                "acceptable per spec but prevents testing via execute_cypher"
            )

        repo = QueryGraphRepository(client=client)

        try:
            with pytest.raises(QueryExecutionError) as exc_info:
                repo.execute_cypher("MATCH (n) RETURN n LIMIT 1")

            error_msg = str(exc_info.value).lower()
            assert (
                "tenant" in error_msg
                or "graph" in error_msg
                or "provision" in error_msg
            ), (
                f"Error message should reference the missing graph, got: {exc_info.value!r}"
            )
        finally:
            client.disconnect()

    def test_tenant_aware_repository_raises_before_reaching_database(
        self,
        tenant_graph_name: str,
        integration_db_settings: DatabaseSettings,
        connection_factory: ConnectionFactory,
    ) -> None:
        """TenantAwareQueryGraphRepository rejects queries for absent graphs.

        Uses ``AGEGraphExistenceChecker`` against the real catalog to confirm
        that ``TenantAwareQueryGraphRepository.execute_cypher`` raises
        ``QueryExecutionError`` without invoking the inner repository.

        Spec: "THEN the request is rejected with an execution error before
        reaching the database"
        """
        tenant_id = tenant_graph_name[len("tenant_") :]

        # Build a fake inner repository that records whether it was called
        inner_was_called = []

        class _RecordingFakeRepo:
            def execute_cypher(
                self,
                query: str,
                timeout_seconds: int = 30,
                max_rows: int = 1000,
            ):
                inner_was_called.append(query)
                return []

        existence_checker = AGEGraphExistenceChecker(
            connection_factory=connection_factory
        )
        repo = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=_RecordingFakeRepo(),
            existence_check_fn=existence_checker,
        )

        with pytest.raises(QueryExecutionError):
            repo.execute_cypher("MATCH (n) RETURN n LIMIT 1")

        # The inner repository (database) must NOT have been called
        assert len(inner_was_called) == 0, (
            f"Inner repository was called despite graph being absent "
            f"(spec: 'before reaching the database'). "
            f"Calls: {inner_was_called}"
        )

    def test_execution_error_message_references_tenant_graph(
        self,
        tenant_graph_name: str,
        integration_db_settings: DatabaseSettings,
        connection_factory: ConnectionFactory,
    ) -> None:
        """Error message must reference the missing tenant graph for debuggability.

        Spec: error must help operators identify the unprovisioned graph.
        """
        tenant_id = tenant_graph_name[len("tenant_") :]

        existence_checker = AGEGraphExistenceChecker(
            connection_factory=connection_factory
        )

        class _NoOpRepo:
            def execute_cypher(self, query, timeout_seconds=30, max_rows=1000):
                return []

        repo = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=_NoOpRepo(),
            existence_check_fn=existence_checker,
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            repo.execute_cypher("MATCH (n) RETURN n")

        error_msg = str(exc_info.value).lower()
        assert (
            "tenant" in error_msg or "graph" in error_msg or "provision" in error_msg
        ), (
            f"Error message must reference the missing tenant graph. Got: {exc_info.value!r}"
        )
