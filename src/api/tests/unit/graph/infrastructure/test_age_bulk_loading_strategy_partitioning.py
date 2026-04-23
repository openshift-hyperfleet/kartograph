"""Unit tests for AgeBulkLoadingStrategy operation partitioning and concurrency safety.

Tests for bulk-loading.spec.md:

Requirement: Operation Partitioning
  - Scenario: Mixed operation batch
    DELETEs execute first (edges before nodes)
    CREATEs execute next (nodes before edges)
    UPDATEs execute last

Requirement: Concurrency Safety
  - Scenario: Concurrent batches (advisory locks acquired)
  - Scenario: Deterministic lock ordering (sorted alphabetical)
    Labels MUST be sorted into a canonical order before acquisition
    Locks acquired strictly in that order to prevent deadlocks
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.age_bulk_loading.strategy import AgeBulkLoadingStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_op(
    op_type: MutationOperationType,
    entity_type: EntityType,
    entity_id: str = "node:abc123def4560001",
    label: str | None = None,
    start_id: str | None = None,
    end_id: str | None = None,
) -> MutationOperation:
    """Helper to build a MutationOperation without triggering Pydantic validation."""
    return MutationOperation.model_construct(
        op=op_type,
        type=entity_type,
        id=entity_id,
        label=label,
        start_id=start_id,
        end_id=end_id,
        set_properties={"data_source_id": "ds1", "source_path": "/a", "slug": "x"},
        remove_properties=None,
    )


def _make_create_node(
    label: str = "person", entity_id: str = "node:abc123def4560001"
) -> MutationOperation:
    return _make_op(
        MutationOperationType.CREATE, EntityType.NODE, entity_id=entity_id, label=label
    )


def _make_create_edge(
    label: str = "knows",
    entity_id: str = "edge:abc123def4560002",
    start_id: str = "node:abc123def4560001",
    end_id: str = "node:abc123def4560003",
) -> MutationOperation:
    return _make_op(
        MutationOperationType.CREATE,
        EntityType.EDGE,
        entity_id=entity_id,
        label=label,
        start_id=start_id,
        end_id=end_id,
    )


def _make_delete_node(entity_id: str = "node:abc123def4560001") -> MutationOperation:
    return _make_op(MutationOperationType.DELETE, EntityType.NODE, entity_id=entity_id)


def _make_delete_edge(entity_id: str = "edge:abc123def4560002") -> MutationOperation:
    return _make_op(MutationOperationType.DELETE, EntityType.EDGE, entity_id=entity_id)


def _make_update(
    entity_type: EntityType = EntityType.NODE,
    entity_id: str = "node:abc123def4560001",
) -> MutationOperation:
    return _make_op(MutationOperationType.UPDATE, entity_type, entity_id=entity_id)


@pytest.fixture
def strategy() -> AgeBulkLoadingStrategy:
    return AgeBulkLoadingStrategy()


@pytest.fixture
def mock_probe() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_client() -> MagicMock:
    """Build a mock GraphClientProtocol client with a cursor context manager."""
    client = MagicMock()
    mock_cursor = MagicMock()
    conn = client.raw_connection
    conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Requirement: Operation Partitioning
# Scenario: Mixed operation batch
# ---------------------------------------------------------------------------


class TestOperationPartitioning:
    """DELETEs first → CREATEs → UPDATEs last (spec: Operation Partitioning)."""

    def _apply_batch_with_call_tracking(
        self,
        strategy: AgeBulkLoadingStrategy,
        operations: list[MutationOperation],
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> list[str]:
        """Run apply_batch patching internal methods to track call order."""
        call_order: list[str] = []

        def record(name: str):
            def side_effect(*args, **kwargs):
                call_order.append(name)
                return 0

            return side_effect

        with (
            patch.object(
                strategy, "_execute_deletes", side_effect=record("delete")
            ) as _del,
            patch.object(
                strategy, "_execute_creates", side_effect=record("create")
            ) as _cre,
            patch.object(
                strategy, "_execute_updates", side_effect=record("update")
            ) as _upd,
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        return call_order

    def test_deletes_execute_before_creates(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """DELETE operations MUST execute before CREATE operations."""
        operations = [
            _make_create_node(),
            _make_delete_node(entity_id="node:abc123def4560009"),
        ]
        call_order = self._apply_batch_with_call_tracking(
            strategy, operations, mock_client, mock_probe
        )

        # Both types must appear in the call order
        assert "delete" in call_order, "DELETE was never executed"
        assert "create" in call_order, "CREATE was never executed"
        assert call_order.index("delete") < call_order.index("create"), (
            "DELETE must execute before CREATE"
        )

    def test_creates_execute_before_updates(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """CREATE operations MUST execute before UPDATE operations."""
        operations = [
            _make_update(),
            _make_create_node(),
        ]
        call_order = self._apply_batch_with_call_tracking(
            strategy, operations, mock_client, mock_probe
        )

        assert "create" in call_order, "CREATE was never executed"
        assert "update" in call_order, "UPDATE was never executed"
        assert call_order.index("create") < call_order.index("update"), (
            "CREATE must execute before UPDATE"
        )

    def test_deletes_execute_before_updates(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """DELETE operations MUST execute before UPDATE operations."""
        operations = [
            _make_update(),
            _make_delete_node(entity_id="node:abc123def4560009"),
        ]
        call_order = self._apply_batch_with_call_tracking(
            strategy, operations, mock_client, mock_probe
        )

        assert "delete" in call_order, "DELETE was never executed"
        assert "update" in call_order, "UPDATE was never executed"
        assert call_order.index("delete") < call_order.index("update"), (
            "DELETE must execute before UPDATE"
        )

    def test_full_ordering_delete_create_update(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Mixed batch: DELETEs first, CREATEs next, UPDATEs last."""
        operations = [
            _make_update(),
            _make_create_node(),
            _make_delete_node(entity_id="node:abc123def4560009"),
        ]
        call_order = self._apply_batch_with_call_tracking(
            strategy, operations, mock_client, mock_probe
        )

        assert call_order.index("delete") < call_order.index("create"), (
            "DELETE must come before CREATE"
        )
        assert call_order.index("create") < call_order.index("update"), (
            "CREATE must come before UPDATE"
        )


class TestDeleteOrderingEdgesBeforeNodes:
    """Edge DELETEs MUST execute before node DELETEs (spec: referential integrity)."""

    def test_delete_edges_before_delete_nodes(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """When deleting both nodes and edges, edge deletes run first."""
        delete_order: list[str] = []

        def tracking_execute_deletes(
            cursor, operations, entity_type, probe, graph_name
        ):
            delete_order.append(entity_type.value)
            return 0

        operations = [
            _make_delete_node(entity_id="node:abc123def4560001"),
            _make_delete_edge(entity_id="edge:abc123def4560002"),
        ]

        with patch.object(
            strategy, "_execute_deletes", side_effect=tracking_execute_deletes
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        assert "edge" in delete_order, "Edge DELETE must occur"
        assert "node" in delete_order, "Node DELETE must occur"
        assert delete_order.index("edge") < delete_order.index("node"), (
            "Edge deletes must execute before node deletes"
        )


class TestCreateOrderingNodesBeforeEdges:
    """Node CREATEs MUST execute before edge CREATEs (spec: referential integrity)."""

    def test_create_nodes_before_create_edges(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """When creating both nodes and edges, node creates run first."""
        create_order: list[str] = []

        def tracking_execute_creates(
            cursor, operations, entity_type, graph_name, session_id, probe
        ):
            create_order.append(entity_type.value)
            return 0

        operations = [
            _make_create_edge(entity_id="edge:abc123def4560002"),
            _make_create_node(entity_id="node:abc123def4560001"),
        ]

        with patch.object(
            strategy, "_execute_creates", side_effect=tracking_execute_creates
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        assert "node" in create_order, "Node CREATE must occur"
        assert "edge" in create_order, "Edge CREATE must occur"
        assert create_order.index("node") < create_order.index("edge"), (
            "Node creates must execute before edge creates"
        )


# ---------------------------------------------------------------------------
# Requirement: Concurrency Safety
# Scenario: Deterministic lock ordering
# ---------------------------------------------------------------------------


class TestAdvisoryLockOrdering:
    """Advisory locks MUST be acquired in a deterministic (sorted) order.

    Spec: labels MUST be sorted into a canonical order (e.g., alphabetical)
    before acquisition. Locks are acquired strictly in that order to prevent
    deadlocks.
    """

    def _collect_locked_labels(
        self,
        strategy: AgeBulkLoadingStrategy,
        operations: list[MutationOperation],
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> list[str]:
        """Run apply_batch and capture the label order passed to acquire_advisory_lock."""
        locked_labels: list[str] = []

        def track_lock(cursor, graph_name, label):
            locked_labels.append(label)

        with (
            patch.object(
                strategy._queries, "acquire_advisory_lock", side_effect=track_lock
            ),
            patch.object(strategy, "_execute_deletes", return_value=0),
            patch.object(strategy, "_execute_creates", return_value=0),
            patch.object(strategy, "_execute_updates", return_value=0),
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        return locked_labels

    def test_labels_acquired_in_alphabetical_order(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Labels must be locked in alphabetical order to prevent deadlocks."""
        # Labels deliberately given in non-alphabetical order
        operations = [
            _make_create_node(label="zebra", entity_id="node:abc123def4560001"),
            _make_create_node(label="apple", entity_id="node:abc123def4560002"),
            _make_create_edge(label="mango", entity_id="edge:abc123def4560003"),
        ]

        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert locked_labels == sorted(locked_labels), (
            f"Advisory locks must be acquired in alphabetical order, "
            f"got: {locked_labels}"
        )

    def test_labels_sorted_before_first_lock(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """The FIRST lock acquired must be alphabetically first (e.g., 'apple' before 'zebra')."""
        operations = [
            _make_create_node(label="zebra", entity_id="node:abc123def4560001"),
            _make_create_node(label="apple", entity_id="node:abc123def4560002"),
        ]

        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert len(locked_labels) >= 2, "Both labels must be locked"
        assert locked_labels[0] == "apple", (
            f"First lock must be 'apple' (alphabetically first), got: {locked_labels[0]}"
        )
        assert locked_labels[1] == "zebra", (
            f"Second lock must be 'zebra' (alphabetically last), got: {locked_labels[1]}"
        )

    def test_lock_order_is_deterministic_regardless_of_operation_input_order(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Same labels given in different order must produce the same lock order."""
        labels = ["mango", "apple", "carrot", "banana"]

        operations_forward = [
            _make_create_node(label=lbl, entity_id=f"node:abc123def{i:08x}")
            for i, lbl in enumerate(labels)
        ]
        operations_reverse = [
            _make_create_node(label=lbl, entity_id=f"node:abc123def{i:08x}")
            for i, lbl in enumerate(reversed(labels))
        ]

        locked_forward = self._collect_locked_labels(
            strategy, operations_forward, mock_client, mock_probe
        )
        locked_reverse = self._collect_locked_labels(
            strategy, operations_reverse, mock_client, mock_probe
        )

        assert locked_forward == locked_reverse, (
            "Lock order must be identical regardless of operation input order"
        )

    def test_advisory_locks_acquired_for_create_nodes(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Labels from CREATE node operations must receive advisory locks."""
        operations = [
            _make_create_node(label="person", entity_id="node:abc123def4560001"),
        ]
        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert "person" in locked_labels, "CREATE node label must be locked"

    def test_advisory_locks_acquired_for_create_edges(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Labels from CREATE edge operations must receive advisory locks."""
        operations = [
            _make_create_edge(label="knows", entity_id="edge:abc123def4560002"),
        ]
        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert "knows" in locked_labels, "CREATE edge label must be locked"

    def test_each_unique_label_locked_exactly_once(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Each distinct label must be locked exactly once, not multiple times."""
        operations = [
            _make_create_node(label="person", entity_id="node:abc123def4560001"),
            _make_create_node(label="person", entity_id="node:abc123def4560002"),
            _make_create_node(label="person", entity_id="node:abc123def4560003"),
        ]
        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert locked_labels.count("person") == 1, (
            "Each label should be locked exactly once, not once per operation"
        )

    def test_no_locks_acquired_for_delete_only_batch(
        self,
        strategy: AgeBulkLoadingStrategy,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """DELETE operations do not require advisory locks (no data written)."""
        operations = [
            _make_delete_node(entity_id="node:abc123def4560001"),
            _make_delete_edge(entity_id="edge:abc123def4560002"),
        ]
        locked_labels = self._collect_locked_labels(
            strategy, operations, mock_client, mock_probe
        )

        assert locked_labels == [], (
            "DELETE-only batch should not acquire any advisory locks"
        )


# ---------------------------------------------------------------------------
# Requirement: Concurrency Safety
# Scenario: Deterministic lock ordering
# Sub-clause: if any lock acquisition fails, all previously acquired locks are
#             released before retry
# ---------------------------------------------------------------------------


class TestAdvisoryLockRetry:
    """Lock acquisition failure MUST trigger rollback and retry.

    Spec: AND if any lock acquisition fails, all previously acquired locks are
    released before retry (Concurrency Safety / Deterministic lock ordering).

    Since pg_advisory_xact_lock() is transaction-scoped, a rollback automatically
    releases every lock held by that transaction. The retry loop then re-acquires
    all locks in sorted order on the next attempt.
    """

    def test_retries_on_lock_acquisition_failure_and_succeeds(
        self,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """When lock acquisition fails on the first attempt, strategy retries and succeeds."""
        strategy = AgeBulkLoadingStrategy(max_retries=2)
        operations = [_make_create_node(label="person")]
        call_count = 0

        def flaky_lock(cursor: MagicMock, graph_name: str, label: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated lock acquisition failure")

        with (
            patch.object(
                strategy._queries, "acquire_advisory_lock", side_effect=flaky_lock
            ),
            patch.object(strategy, "_execute_deletes", return_value=0),
            patch.object(strategy, "_execute_creates", return_value=1),
            patch.object(strategy, "_execute_updates", return_value=0),
        ):
            result = strategy.apply_batch(
                mock_client, operations, mock_probe, "test_graph"
            )

        assert result.success is True, "Batch must succeed after a single retry"
        assert call_count == 2, (
            f"acquire_advisory_lock must be called twice (1 failure + 1 success), "
            f"got {call_count}"
        )

    def test_rollback_called_on_lock_failure_before_retry(
        self,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Rollback is called to release all held locks before each retry attempt."""
        strategy = AgeBulkLoadingStrategy(max_retries=2)
        operations = [_make_create_node(label="person")]
        call_count = 0

        def flaky_lock(cursor: MagicMock, graph_name: str, label: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated lock failure")

        with (
            patch.object(
                strategy._queries, "acquire_advisory_lock", side_effect=flaky_lock
            ),
            patch.object(strategy, "_execute_deletes", return_value=0),
            patch.object(strategy, "_execute_creates", return_value=1),
            patch.object(strategy, "_execute_updates", return_value=0),
        ):
            result = strategy.apply_batch(
                mock_client, operations, mock_probe, "test_graph"
            )

        # Rollback must be called exactly once (after the first failure)
        mock_client.raw_connection.rollback.assert_called_once()
        assert result.success is True, "Batch must ultimately succeed on retry"

    def test_returns_failure_after_all_retries_exhausted(
        self,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """After max retries, apply_batch returns MutationResult with success=False."""
        strategy = AgeBulkLoadingStrategy(max_retries=2)
        operations = [_make_create_node(label="person")]

        with patch.object(
            strategy._queries,
            "acquire_advisory_lock",
            side_effect=RuntimeError("persistent lock failure"),
        ):
            result = strategy.apply_batch(
                mock_client, operations, mock_probe, "test_graph"
            )

        assert result.success is False
        assert len(result.errors) > 0, "Errors list must be non-empty on failure"
        assert "persistent lock failure" in result.errors[0], (
            "Error message must propagate to the caller"
        )

    def test_retry_attempts_are_bounded_by_max_retries(
        self,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """Strategy does not retry indefinitely; total attempts == max_retries + 1."""
        max_retries = 2
        strategy = AgeBulkLoadingStrategy(max_retries=max_retries)
        operations = [_make_create_node(label="person")]
        lock_call_count = 0

        def always_fail(cursor: MagicMock, graph_name: str, label: str) -> None:
            nonlocal lock_call_count
            lock_call_count += 1
            raise RuntimeError("lock failure")

        with patch.object(
            strategy._queries, "acquire_advisory_lock", side_effect=always_fail
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        # Initial attempt + max_retries retries
        assert lock_call_count == max_retries + 1, (
            f"Expected {max_retries + 1} total attempts, got {lock_call_count}"
        )

    def test_second_lock_failure_triggers_rollback_of_all_held_locks(
        self,
        mock_client: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        """When the Nth lock fails, rollback releases ALL previously acquired locks.

        With sorted labels ['apple', 'zebra']: 'apple' is acquired first (succeeds),
        then 'zebra' fails. Rollback must be called so that the 'apple' advisory lock
        (held by the transaction) is released before retry.
        """
        strategy = AgeBulkLoadingStrategy(max_retries=2)
        # Two labels: sorted → ["apple", "zebra"]
        operations = [
            _make_create_node(label="apple", entity_id="node:abc123def4560001"),
            _make_create_node(label="zebra", entity_id="node:abc123def4560002"),
        ]
        call_count = 0

        def fail_on_second_lock(cursor: MagicMock, graph_name: str, label: str) -> None:
            nonlocal call_count
            call_count += 1
            # First attempt: "apple" (call 1) succeeds, "zebra" (call 2) fails
            if call_count == 2:
                raise RuntimeError("zebra lock failed")

        with (
            patch.object(
                strategy._queries,
                "acquire_advisory_lock",
                side_effect=fail_on_second_lock,
            ),
            patch.object(strategy, "_execute_deletes", return_value=0),
            patch.object(strategy, "_execute_creates", return_value=1),
            patch.object(strategy, "_execute_updates", return_value=0),
        ):
            strategy.apply_batch(mock_client, operations, mock_probe, "test_graph")

        # Rollback must be called to release the "apple" lock held before "zebra" failed
        mock_client.raw_connection.rollback.assert_called()
