"""Unit tests for TenantAGEGraphHandler (TDD).

Tests verify that when a TenantCreated event is processed via the outbox,
an AGE graph named `tenant_{tenant_id}` is provisioned using a
create-if-not-exists pattern (idempotent).

Spec: specs/iam/tenants.spec.md
Scenario: Tenant graph provisioning
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from graph.infrastructure.tenant_graph_handler import (
    AGEGraphProvisioner,
    TenantAGEGraphHandler,
)


class FakeGraphProvisioner:
    """In-memory fake for AGEGraphProvisioner that tracks calls.

    Avoids mocking so test failures are more descriptive.
    """

    def __init__(self) -> None:
        self.provisioned_graphs: list[str] = []
        self.should_raise: Exception | None = None

    def ensure_graph_exists(self, graph_name: str) -> None:
        """Record the graph provisioning call."""
        if self.should_raise is not None:
            raise self.should_raise
        self.provisioned_graphs.append(graph_name)


class TestTenantAGEGraphHandlerSupportedEventTypes:
    """Tests for supported event types declaration."""

    def test_supports_tenant_created_event(self) -> None:
        """Handler must support the TenantCreated event type."""
        handler = TenantAGEGraphHandler(FakeGraphProvisioner())
        assert "TenantCreated" in handler.supported_event_types()

    def test_does_not_support_other_events(self) -> None:
        """Handler should only support TenantCreated, not other IAM events."""
        handler = TenantAGEGraphHandler(FakeGraphProvisioner())
        supported = handler.supported_event_types()
        assert "TenantDeleted" not in supported
        assert "TenantMemberAdded" not in supported
        assert "WorkspaceCreated" not in supported
        assert "GroupCreated" not in supported


class TestTenantAGEGraphHandlerGraphProvisioning:
    """Tests for graph provisioning on TenantCreated events."""

    @pytest.mark.asyncio
    async def test_provisions_age_graph_on_tenant_created(self) -> None:
        """Handler provisions an AGE graph when TenantCreated is handled."""
        provisioner = FakeGraphProvisioner()
        handler = TenantAGEGraphHandler(provisioner)

        tenant_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": "Acme Corp",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        await handler.handle("TenantCreated", payload)

        assert provisioner.provisioned_graphs == [f"tenant_{tenant_id}"]

    @pytest.mark.asyncio
    async def test_graph_name_format_is_tenant_underscore_id(self) -> None:
        """Graph name must be `tenant_{tenant_id}` (underscore separator)."""
        provisioner = FakeGraphProvisioner()
        handler = TenantAGEGraphHandler(provisioner)

        tenant_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": "Acme Corp",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        await handler.handle("TenantCreated", payload)

        expected_graph_name = f"tenant_{tenant_id}"
        assert provisioner.provisioned_graphs[0] == expected_graph_name

    @pytest.mark.asyncio
    async def test_graph_name_uses_hyphenated_ulid_intact(self) -> None:
        """Tenant ID is embedded in graph name exactly as-is."""
        provisioner = FakeGraphProvisioner()
        handler = TenantAGEGraphHandler(provisioner)

        tenant_id = "DIFFERENT-TENANT-ID-FORMAT"
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": "Other Tenant",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        await handler.handle("TenantCreated", payload)

        assert provisioner.provisioned_graphs == [f"tenant_{tenant_id}"]

    @pytest.mark.asyncio
    async def test_calls_provisioner_exactly_once_per_event(self) -> None:
        """Each TenantCreated event triggers exactly one provisioning call."""
        provisioner = FakeGraphProvisioner()
        handler = TenantAGEGraphHandler(provisioner)

        payload: dict[str, Any] = {
            "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "name": "Acme Corp",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        await handler.handle("TenantCreated", payload)

        assert len(provisioner.provisioned_graphs) == 1


class TestTenantAGEGraphHandlerIdempotency:
    """Tests for idempotency: re-processing TenantCreated is safe."""

    @pytest.mark.asyncio
    async def test_handler_is_idempotent_when_provisioner_is_idempotent(self) -> None:
        """Handler relies on provisioner's idempotency (create-if-not-exists).

        The handler itself calls the provisioner; it is the provisioner's
        responsibility to be idempotent. The handler should pass through
        any errors from the provisioner to signal non-transient failures.
        """
        provisioner = FakeGraphProvisioner()
        handler = TenantAGEGraphHandler(provisioner)

        payload: dict[str, Any] = {
            "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "name": "Acme Corp",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        # First call
        await handler.handle("TenantCreated", payload)
        # Second call (replay) - should not raise
        await handler.handle("TenantCreated", payload)

        # Both calls reach the provisioner; provisioner decides idempotency
        assert len(provisioner.provisioned_graphs) == 2

    @pytest.mark.asyncio
    async def test_provisioner_exception_propagates_to_allow_retry(self) -> None:
        """Exceptions from the provisioner bubble up so the outbox worker retries."""
        provisioner = FakeGraphProvisioner()
        provisioner.should_raise = RuntimeError("AGE not available")
        handler = TenantAGEGraphHandler(provisioner)

        payload: dict[str, Any] = {
            "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "name": "Acme Corp",
            "occurred_at": "2026-04-22T12:00:00+00:00",
        }

        with pytest.raises(RuntimeError, match="AGE not available"):
            await handler.handle("TenantCreated", payload)


class TestAGEGraphProvisionerIdempotency:
    """Tests for AGEGraphProvisioner create-if-not-exists behavior.

    These tests use a mock psycopg2 cursor to simulate the database
    without a real AGE connection.
    """

    def _make_provisioner(
        self,
    ) -> tuple[AGEGraphProvisioner, MagicMock, MagicMock, MagicMock]:
        """Create a provisioner with a mocked connection factory.

        Returns:
            (provisioner, mock_connection_factory, mock_conn, mock_cursor)
        """
        mock_connection_factory = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Simulate context manager for `with conn.cursor() as cursor:`
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_connection_factory.get_connection.return_value = mock_conn

        provisioner = AGEGraphProvisioner(mock_connection_factory)
        return provisioner, mock_connection_factory, mock_conn, mock_cursor

    def test_creates_graph_when_not_exists(self) -> None:
        """Provisioner calls create_graph when graph does not exist."""
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )

        # Simulate: graph does NOT exist (SELECT returns None)
        mock_cursor.fetchone.return_value = None

        provisioner.ensure_graph_exists("tenant_abc123")

        # Verify it tried to check for existence
        check_calls = [
            c
            for c in mock_cursor.execute.call_args_list
            if "ag_catalog.ag_graph" in str(c)
        ]
        assert len(check_calls) >= 1

        # Verify it called create_graph
        create_calls = [
            c for c in mock_cursor.execute.call_args_list if "create_graph" in str(c)
        ]
        assert len(create_calls) >= 1

        # Verify connection was committed
        mock_conn.commit.assert_called()

    def test_skips_create_when_graph_already_exists(self) -> None:
        """Provisioner does NOT call create_graph if graph already exists."""
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )

        # Simulate: graph ALREADY EXISTS (SELECT returns a row)
        mock_cursor.fetchone.return_value = (1,)

        provisioner.ensure_graph_exists("tenant_abc123")

        # Verify no create_graph call was made
        create_calls = [
            c for c in mock_cursor.execute.call_args_list if "create_graph" in str(c)
        ]
        assert len(create_calls) == 0

    def test_returns_connection_to_factory_on_success(self) -> None:
        """Connection is always returned to factory after provisioning."""
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )
        mock_cursor.fetchone.return_value = None  # graph does not exist

        provisioner.ensure_graph_exists("tenant_xyz")

        mock_connection_factory.return_connection.assert_called_once_with(mock_conn)

    def test_returns_connection_to_factory_on_error(self) -> None:
        """Connection is returned even if an exception occurs."""
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )
        mock_cursor.fetchone.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError):
            provisioner.ensure_graph_exists("tenant_xyz")

        # Despite the error, connection must be returned
        mock_connection_factory.return_connection.assert_called_once_with(mock_conn)

    def test_rollback_or_commit_called_on_no_op_path(self) -> None:
        """Spec: DB connection must commit or rollback even on no-op path.

        When the graph already exists, the connection must be committed or
        rolled back before returning to the pool to avoid leaking open
        transactions.

        Spec: specs/iam/tenants.spec.md - Requirement: Tenant graph provisioning
        'the database connection MUST be properly committed or rolled back on
        all code paths (including the no-op/exists path)'
        """
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )

        # Simulate: graph ALREADY EXISTS — no-op path
        mock_cursor.fetchone.return_value = (1,)

        provisioner.ensure_graph_exists("tenant_abc123")

        # Either commit or rollback MUST be called on the no-op path
        assert mock_conn.commit.called or mock_conn.rollback.called, (
            "Connection must commit or rollback on no-op path to avoid leaking "
            "open transactions back to the connection pool"
        )

    def test_advisory_lock_acquired_for_atomicity(self) -> None:
        """Spec: existence check and creation must be performed atomically.

        An advisory lock must be acquired before the existence check to prevent
        race conditions under concurrent duplicate event deliveries.

        Spec: specs/iam/tenants.spec.md - Requirement: Tenant graph provisioning
        'the existence check and graph creation MUST be performed atomically
        (e.g. via CREATE GRAPH IF NOT EXISTS or an advisory lock)'
        """
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )
        mock_cursor.fetchone.return_value = None  # graph does not exist

        provisioner.ensure_graph_exists("tenant_abc123")

        # Verify that an advisory lock was acquired
        all_calls = mock_cursor.execute.call_args_list
        lock_calls = [
            i
            for i, c in enumerate(all_calls)
            if "advisory" in str(c).lower() or "pg_advisory" in str(c).lower()
        ]
        assert len(lock_calls) >= 1, (
            "Advisory lock must be acquired to make existence check + creation atomic"
        )

        # The advisory lock must be acquired BEFORE the existence check
        existence_check_calls = [
            i for i, c in enumerate(all_calls) if "ag_catalog.ag_graph" in str(c)
        ]
        assert lock_calls[0] < existence_check_calls[0], (
            "Advisory lock must be acquired before the existence check"
        )

    def test_rolls_back_on_create_failure(self) -> None:
        """Connection is rolled back when create_graph fails, then re-raises.

        With the advisory lock, the call sequence is:
        1. advisory lock (no-op)
        2. existence check (returns None - graph not found)
        3. create_graph (fails)
        """
        provisioner, mock_connection_factory, mock_conn, mock_cursor = (
            self._make_provisioner()
        )

        # Graph does not exist, but create_graph fails.
        # With advisory lock, there are now 3 execute calls:
        # 1. advisory lock, 2. existence check, 3. create_graph (raises)
        call_count = [0]

        def execute_side_effect(sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: advisory lock — no-op
                pass
            elif call_count[0] == 2:
                # Second call: existence check — no-op (fetchone returns None)
                pass
            elif call_count[0] == 3:
                # Third call: create_graph fails
                raise RuntimeError("Cannot create graph")

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchone.return_value = None

        with pytest.raises(RuntimeError, match="Cannot create graph"):
            provisioner.ensure_graph_exists("tenant_abc")

        mock_conn.rollback.assert_called()
