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
    before calling create_graph. This is idempotent and safe for replay.
    """

    def __init__(self, connection_factory: "ConnectionFactory") -> None:
        """Initialize the provisioner with a connection factory.

        Args:
            connection_factory: Factory for obtaining psycopg2 connections.
        """
        self._connection_factory = connection_factory

    def ensure_graph_exists(self, graph_name: str) -> None:
        """Create the AGE graph if it does not already exist.

        Uses a transaction-level advisory lock to make the existence check
        and graph creation atomic, preventing race conditions under concurrent
        duplicate event deliveries (e.g. outbox replay).

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
                # Acquire a transaction-level advisory lock keyed by graph name.
                # This makes the check + create atomic: concurrent callers block
                # here until the first caller's transaction commits or rolls back.
                # The lock is released automatically when the transaction ends.
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                    (graph_name,),
                )

                # Check if graph exists in the AGE catalog
                cursor.execute(
                    "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                    (graph_name,),
                )
                if cursor.fetchone() is not None:
                    # Graph already exists — idempotent no-op.
                    # Rollback to release advisory lock and cleanly end the
                    # transaction; avoids leaking an open transaction to the pool.
                    conn.rollback()
                    return

                # Attempt to create the graph
                cursor.execute(
                    "SELECT ag_catalog.create_graph(%s)",
                    (graph_name,),
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            self._connection_factory.return_connection(conn)


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
