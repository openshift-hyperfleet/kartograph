"""Tenant AGE graph provisioning handler for the outbox pattern.

When a TenantCreated event is processed from the outbox, this handler
provisions a dedicated Apache AGE graph named `tenant_{tenant_id}`.

The provisioning uses create-if-not-exists semantics, making the handler
safe for idempotent replay (as required by the outbox pattern).

Spec: specs/iam/tenants.spec.md
Scenario: Tenant graph provisioning
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from infrastructure.database.connection import ConnectionFactory


@runtime_checkable
class GraphProvisioner(Protocol):
    """Protocol for provisioning AGE graph databases.

    Implementations must be idempotent: calling ensure_graph_exists
    with a name that already exists must be a no-op.
    """

    def ensure_graph_exists(self, graph_name: str) -> None:
        """Create an AGE graph if it does not already exist.

        Args:
            graph_name: The name of the graph to provision.

        Raises:
            Exception: If the graph cannot be created and does not already exist.
        """
        ...


class AGEGraphProvisioner:
    """Creates AGE graphs using a psycopg2 connection.

    Uses create-if-not-exists semantics by checking ag_catalog.ag_graph
    before calling create_graph. When catalog metadata exists but the graph
    is not queryable (common after a partial Postgres restore), the graph is
    dropped and recreated. This is idempotent and safe for replay.
    """

    _GRAPH_OID_MISSING = "does not exist"

    def __init__(self, connection_factory: "ConnectionFactory") -> None:
        """Initialize the provisioner with a connection factory.

        Args:
            connection_factory: Factory for obtaining psycopg2 connections.
        """
        self._connection_factory = connection_factory

    @staticmethod
    def _prepare_age_session(cursor) -> None:
        cursor.execute("LOAD 'age'")
        cursor.execute('SET search_path = ag_catalog, "$user", public')

    def _graph_is_queryable(self, cursor, graph_name: str) -> bool:
        """Return True when cypher queries can run against the named graph."""
        self._prepare_age_session(cursor)
        try:
            cursor.execute(
                "SELECT * FROM cypher(%s, $$ RETURN 1 $$) AS (result agtype)",
                (graph_name,),
            )
            cursor.fetchone()
            return True
        except Exception as exc:
            message = str(exc).lower()
            if self._GRAPH_OID_MISSING in message or "graph" in message:
                return False
            raise

    @staticmethod
    def _drop_graph(cursor, graph_name: str) -> None:
        cursor.execute(
            "SELECT ag_catalog.drop_graph(%s, true)",
            (graph_name,),
        )

    @staticmethod
    def _create_graph(cursor, graph_name: str) -> None:
        cursor.execute(
            "SELECT ag_catalog.create_graph(%s)",
            (graph_name,),
        )

    def ensure_graph_exists(self, graph_name: str) -> None:
        """Create the AGE graph if it does not already exist.

        Uses a transaction-level advisory lock to make the existence check
        and graph creation atomic, preventing race conditions under concurrent
        duplicate event deliveries (e.g. outbox replay).

        When catalog metadata exists but the graph OID is missing or corrupt
        (``graph with oid N does not exist``), the stale graph is dropped and
        recreated so workload reads/writes can proceed.

        The connection is always committed or rolled back on every code path,
        including the no-op/exists path, to avoid leaking open transactions
        back to the connection pool.

        Args:
            graph_name: Name of the AGE graph (e.g., "tenant_01ARZ3NDEK...")

        Raises:
            Exception: If graph creation fails for a reason other than
                the graph already existing.
        """
        conn = self._connection_factory.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                    (graph_name,),
                )

                cursor.execute(
                    "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                    (graph_name,),
                )
                catalog_exists = cursor.fetchone() is not None

                if catalog_exists and self._graph_is_queryable(cursor, graph_name):
                    conn.rollback()
                    return

                if catalog_exists:
                    self._prepare_age_session(cursor)
                    self._drop_graph(cursor, graph_name)

                self._create_graph(cursor, graph_name)

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            self._connection_factory.return_connection(conn)


def ensure_tenant_graph_operational(
    connection_factory: "ConnectionFactory",
    tenant_id: str,
) -> str:
    """Ensure ``tenant_{tenant_id}`` exists and accepts Cypher queries."""
    graph_name = f"tenant_{tenant_id}"
    AGEGraphProvisioner(connection_factory).ensure_graph_exists(graph_name)
    return graph_name


class TenantAGEGraphHandler:
    """Outbox event handler that provisions an AGE graph per tenant.

    Handles TenantCreated events from the transactional outbox.
    For each new tenant, ensures a dedicated AGE graph named
    `tenant_{tenant_id}` is created (create-if-not-exists, idempotent).

    This handler is safe for replay: if the graph already exists,
    the provisioner performs a no-op, so retrying after a partial
    failure does not cause errors.

    Architecture note:
        Lives in graph.infrastructure because it belongs to the graph
        persistence concern. It implements shared_kernel.outbox.ports.EventHandler
        so the outbox worker's CompositeEventHandler can dispatch to it.
        It must not import from iam.* — it works with the raw event payload dict.
    """

    def __init__(self, graph_provisioner: GraphProvisioner) -> None:
        """Initialize the handler with a graph provisioner.

        Args:
            graph_provisioner: Strategy for creating AGE graphs.
        """
        self._graph_provisioner = graph_provisioner

    def supported_event_types(self) -> frozenset[str]:
        """Return the event types this handler processes.

        Returns:
            Frozenset containing only "TenantCreated".
        """
        return frozenset({"TenantCreated"})

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        """Provision an AGE graph for the newly created tenant.

        Extracts the tenant_id from the payload, computes the graph name
        as `tenant_{tenant_id}`, and delegates to the provisioner.

        The provisioner's synchronous call is run in the default thread
        executor so it does not block the event loop (psycopg2 is sync).

        Args:
            event_type: Must be "TenantCreated".
            payload: Serialized event dict containing at minimum "tenant_id".

        Raises:
            KeyError: If the payload is missing "tenant_id".
            Exception: Propagated from the provisioner on failure.
                The outbox worker will retry or move to DLQ.
        """
        tenant_id = payload["tenant_id"]
        graph_name = f"tenant_{tenant_id}"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._graph_provisioner.ensure_graph_exists, graph_name
        )
