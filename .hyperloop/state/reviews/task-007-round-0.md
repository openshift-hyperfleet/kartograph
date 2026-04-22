---
task_id: task-007
round: 0
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — Task 007: Bulk Loading

Spec reviewed: `specs/graph/bulk-loading.spec.md`
Branch: `hyperloop/task-007`

---

## Requirement: Operation Partitioning
**Status: COVERED**

The system SHALL partition mutation operations by type and enforce referential integrity ordering.

### Scenario: Mixed operation batch
**Implementation:** `strategy.py:apply_batch` (lines 70–143) partitions into
`delete_edges`, `delete_nodes`, `create_nodes`, `create_edges`, and `update_ops`,
executing them in exactly that order.

**Tests:**
- `test_age_bulk_loading_strategy_partitioning.py`:
  - `TestOperationPartitioning.test_full_ordering_delete_create_update` — verifies
    full DELETEs → CREATEs → UPDATEs ordering.
  - `TestDeleteOrderingEdgesBeforeNodes.test_delete_edges_before_delete_nodes` — verifies
    edge DELETEs run before node DELETEs.
  - `TestCreateOrderingNodesBeforeEdges.test_create_nodes_before_create_edges` — verifies
    node CREATEs run before edge CREATEs.

---

## Requirement: Label and Index Pre-Creation
**Status: COVERED**

The system SHALL create graph labels and performance indexes before bulk-inserting data.

### Scenario: New label in batch
**Implementation:** `strategy.py:_pre_create_labels_and_indexes` (called at lines 293–302 of
`_execute_creates`) fetches existing labels, creates any new ones via `create_label`, then
calls `create_label_indexes` on each new label — all before `execute_label_upsert` writes
rows. The indexing strategy creates 3 indexes for nodes and 5 for edges.

**Tests:**
- `test_age_indexing_strategy.py`:
  - `TestCreateLabelIndexesForNodes` — verifies BTREE(id), GIN(properties),
    BTREE(properties.id) created (3 total).
  - `TestCreateLabelIndexesForEdges` — verifies 5 indexes including start_id/end_id.
  - `TestSkipsExistingIndexes` — verifies no recreation of existing indexes.
- Integration `TestBulkLoadingIndexCreation.test_node_label_creation_creates_indexes`
  and `test_edge_label_creation_creates_indexes` — verifies ≥3/≥5 indexes in live
  PostgreSQL after bulk loading.

---

## Requirement: Staging-Based Ingestion
**Status: COVERED**

The system SHALL use temporary staging tables and PostgreSQL COPY for efficient data loading.

### Scenario: Node bulk create
**Implementation:**
- `staging.py:create_node_staging_table` — `CREATE TEMP TABLE … ON COMMIT DROP`.
- `staging.py:copy_nodes_to_staging` — uses `cursor.copy_from()` (PostgreSQL COPY protocol).
- `queries.py:execute_label_upsert` / `_build_insert_*_query` — uses direct SQL INSERT
  (not Cypher). The staging table is dropped automatically on `conn.commit()`.

**Tests:**
- `test_staging_table_manager.py`:
  - `TestNodeStagingTableCreation.test_node_staging_table_uses_on_commit_drop`
  - `TestNodeStagingTableCreation.test_node_staging_table_is_temp`
- Integration `TestBulkLoadingIdempotency.test_repeated_batch_is_idempotent` confirms
  nodes are materialized via direct SQL.

### Scenario: Edge bulk create with ID resolution
**Implementation:**
- Nodes are always created before edges (`apply_batch` lines 119–137).
- `staging.py:create_graphid_lookup_table` builds a flat TEMP table from
  `_ag_label_vertex` — which includes nodes inserted earlier in the same transaction
  (PostgreSQL read-your-own-writes visibility).
- `staging.py:resolve_edge_graphids` uses two separate UPDATE statements (not a
  cartesian join) to resolve start_graphid and end_graphid.
- Edges are inserted via direct SQL with resolved graphids.

**Tests:**
- `test_staging_table_manager.py`:
  - `TestGraphidLookupTableCreation.test_lookup_table_queries_ag_label_vertex` —
    verifies the lookup queries `_ag_label_vertex` so same-batch nodes are included.
  - `TestGraphidLookupTableCreation.test_lookup_table_uses_on_commit_drop`
  - `TestGraphidLookupTableCreation.test_lookup_table_creates_index_on_logical_id`
- Integration `TestEdgeLabelPreCreation.test_creates_edge_label_tables_on_empty_database`
  — creates nodes and edges in the same batch, verifying same-batch node ID resolution.
- Integration `TestCartesianJoinFix.test_edge_resolution_with_many_nodes_succeeds`

---

## Requirement: Duplicate and Orphan Detection
**Status: COVERED**

### Scenario: Duplicate IDs in batch
**Implementation:** `staging.py:check_for_duplicate_ids` groups by ID, detects COUNT > 1,
calls `probe.duplicate_ids_detected`, and raises `ValueError`.

**Tests:**
- `test_staging_table_manager.py`: `TestDuplicateIdDetection` (5 tests).
- Integration `TestBulkLoadingDuplicateDetection.test_duplicate_node_ids_in_same_batch_raises_error`
  and `test_duplicate_edge_ids_in_same_batch_raises_error`.

### Scenario: Orphaned edges
**Implementation:** `staging.py:check_for_orphaned_edges` detects edges with NULL
start_graphid or end_graphid after resolution, calls `probe.orphaned_edges_detected`,
and raises `ValueError` with the missing node IDs listed.

**Tests:**
- `test_staging_table_manager.py`: `TestOrphanedEdgeDetection` (7 tests including
  detection of NULL start, NULL end, multiple orphans, and probe call verification).
- Integration `TestOrphanedEdgeDetection` (3 tests including `test_edge_to_nonexistent_node_raises_error`,
  `test_edge_from_nonexistent_node_raises_error`, and
  `test_multiple_orphaned_edges_lists_all_in_error`).

---

## Requirement: Concurrency Safety
**Status: PARTIAL — FAILS spec contract**

### Scenario: Concurrent batches
**Status: COVERED**

**Implementation:** `queries.py:acquire_advisory_lock` calls
`pg_advisory_xact_lock(%s)` (transaction-scoped, blocking). Locks are acquired in
`apply_batch` before any data operations.

**Tests:**
- `TestAdvisoryLockOrdering.test_advisory_locks_acquired_for_create_nodes`
- `TestAdvisoryLockOrdering.test_advisory_locks_acquired_for_create_edges`
- `TestAdvisoryLockOrdering.test_each_unique_label_locked_exactly_once`
- `TestAdvisoryLockOrdering.test_no_locks_acquired_for_delete_only_batch`
- Integration `TestStableAdvisoryLocks.test_compute_stable_hash_is_deterministic`

### Scenario: Deterministic lock ordering
**Status: PARTIAL**

**Implementation (sorted ordering — COVERED):**
`strategy.py` line 106: `for label in sorted(all_labels):` — labels are sorted
alphabetically before any `acquire_advisory_lock` call. This is correct.

**Tests for sorted ordering (COVERED):**
- `TestAdvisoryLockOrdering.test_labels_acquired_in_alphabetical_order`
- `TestAdvisoryLockOrdering.test_labels_sorted_before_first_lock`
- `TestAdvisoryLockOrdering.test_lock_order_is_deterministic_regardless_of_operation_input_order`

**Gap — "if any lock acquisition fails, all previously acquired locks are released before retry":**

The spec THEN block states:
> AND if any lock acquisition fails, all previously acquired locks are released before retry

Two distinct problems:

1. **No retry logic.** When `acquire_advisory_lock` raises (e.g., PostgreSQL raises
   a deadlock error), `apply_batch` catches it at line 157, calls `rollback()`, and
   returns `MutationResult(success=False, ...)`. There is no retry loop. The spec's
   "before retry" language implies the caller is expected to retry; the implementation
   provides no retry mechanism, and `rollback()` is performed only at the
   bulk-operation level, not explicitly in response to a lock failure.

2. **No test for this failure path.** There is no unit test or integration test that
   exercises lock acquisition failure (e.g., mocking `acquire_advisory_lock` to raise
   on the second call and verifying that: (a) the first lock is released, and (b) the
   error result enables the caller to retry). The existing tests only verify normal
   lock ordering and that locks are acquired — they never exercise the failure path.

**What is needed to fix this:**

*Implementation:* Add retry logic (e.g., a bounded retry loop with backoff) wrapping
the advisory lock acquisition block. On failure, the transaction is rolled back
(releasing all `pg_advisory_xact_lock`-held locks), and the batch is retried.

*Test (minimum):* A unit test that patches `AgeQueryBuilder.acquire_advisory_lock`
to raise on the Nth call, then verifies that `apply_batch` either retries and
succeeds, or returns a clear failure result after exhausting retries — and that no
lock is left unreleased.

---

## Summary Table

| Requirement | Scenario | Status |
|---|---|---|
| Operation Partitioning | Mixed operation batch (DELETEs→CREATEs→UPDATEs, edges before nodes) | COVERED |
| Label and Index Pre-Creation | New label created + indexed before insertion | COVERED |
| Staging-Based Ingestion | Node bulk create (TEMP + COPY + direct SQL + ON COMMIT DROP) | COVERED |
| Staging-Based Ingestion | Edge bulk create with ID resolution (lookup from _ag_label_vertex) | COVERED |
| Duplicate and Orphan Detection | Duplicate IDs detected and reported | COVERED |
| Duplicate and Orphan Detection | Orphaned edges detected and reported | COVERED |
| Concurrency Safety | Concurrent batches (advisory locks acquired) | COVERED |
| Concurrency Safety | Deterministic lock ordering (alphabetical) | PARTIAL |

---

## Verdict: FAIL

One scenario's THEN conditions are not fully satisfied:

- **Concurrency Safety / Deterministic lock ordering** — The alphabetical sort IS
  implemented and tested. However, the spec THEN condition "if any lock acquisition
  fails, all previously acquired locks are released **before retry**" has no
  implementation of retry logic and no test exercising the failure path. This
  constitutes a missing test for a spec THEN condition and a missing implementation
  of the retry behavior.

All other SHALL requirements are implemented and tested.