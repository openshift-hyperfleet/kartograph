---
task_id: task-017
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — Outbox (outbox.spec.md)

Reviewed branch: `hyperloop/task-017`
Spec file: `specs/shared-kernel/outbox.spec.md`

---

## Requirement Status

### REQ-1: Transactional Event Storage — **COVERED**

**Scenario: Successful write**
- Implementation: `OutboxRepository.append()` calls `session.add()` only; never calls `session.commit()`. The repository docstring explicitly states "The calling service owns the transaction boundary."
- Unit test: `test_repository_append_does_not_commit` (verifies `commit` not called, `add` called once)
- Integration test: `TestAtomicityGuarantees.test_outbox_entry_created_in_same_transaction_as_group` (verifies both group row and outbox row exist after commit)

**Scenario: Transaction rollback**
- Implementation: Repository never commits; rollback by the caller's context manager discards pending `session.add()` entries.
- Unit test: `test_failed_service_call_leaves_no_outbox_entries` (asserts `commit` never called, demonstrating rollback discards the pending add)
- Integration test: `TestAtomicityGuarantees.test_rollback_removes_both_group_and_outbox_entry` (forces actual rollback, verifies neither group nor outbox row persisted)

---

### REQ-2: Event Processing — **COVERED**

**Scenario: Normal processing**
- Implementation: `OutboxWorker._process_entries()` → `handler.handle()` → `_mark_processed()` sets `processed_at`
- Unit tests: `test_processes_unprocessed_entries`, `test_marks_entry_as_processed`, `test_calls_event_processed_on_success`
- Integration tests: `test_worker_processes_group_created_and_writes_to_spicedb`, `test_worker_processes_member_added_and_writes_to_spicedb` (verifies `processed_at` set AND SpiceDB relationship written)

**Scenario: Transient failure**
- Implementation: `except Exception` in `_process_entries()` → `_handle_processing_failure()` → `_increment_retry()` updates `retry_count` and `last_error`
- Unit tests: `test_transient_failure_increments_retry_count` (verifies `event_processing_failed` probe called, `event_moved_to_dlq` not called), `test_calls_event_processing_failed_on_error` (verifies error message in probe call), `test_transient_failure_does_not_dlq_immediately`

**Scenario: Permanent failure (dead letter)**
- Implementation: `_handle_processing_failure()` → when `new_retry_count >= max_retries` → `_move_to_dlq()` sets `failed_at` timestamp; `failed_at IS NULL` filter in `_process_batch()` ensures DLQ entries are skipped
- Unit tests: `test_max_retries_moves_entry_to_dlq` (verifies `event_moved_to_dlq` called, `event_processing_failed` not called), `test_failed_entries_excluded_from_fetch` (verifies `failed_at IS NULL` in compiled SQL)

---

### REQ-3: Idempotent Event Handlers — **PARTIAL → FAIL**

**Scenario: Duplicate delivery**

The spec requires:
> GIVEN an outbox entry that was partially processed before a transient failure
> WHEN the worker retries the same entry
> THEN reprocessing produces the same final state as a single successful processing
> AND no duplicate side effects are created (e.g., duplicate SpiceDB relationships)

**What is implemented:**
- `_process_single()` and `_process_batch()` both use `processed_at IS NULL AND failed_at IS NULL` filters, preventing re-delivery of **already-successfully-processed** entries.
- `SpiceDBEventHandler.handle()` issues `write_relationship` / `delete_relationship` calls; SpiceDB's underlying API is an upsert, so duplicate writes are harmless.
- The `EventHandler` protocol docstring explicitly states: "Implementations should be idempotent — the outbox worker may retry events on failure, so handlers must tolerate duplicate delivery."

**What is tested:**
- `test_already_processed_entry_excluded_from_fetch` — verifies that `processed_at IS NULL` is present in the compiled query (prevents re-delivery of *already successfully processed* entries).
- `test_failed_entries_excluded_from_fetch` — verifies `failed_at IS NULL` (DLQ exclusion).

**Gap — no test covers the actual duplicate-delivery scenario:**

The spec scenario describes a **partial failure** case: the handler was invoked, may have written some SpiceDB relationships, then raised an exception. The entry is NOT marked processed. On retry, the handler is invoked again with the same payload. The spec requires that the final state matches a single successful run, with no duplicate relationships.

No test exercises this path:
1. No unit test calls the same handler twice with the same event and verifies idempotent final state.
2. No integration test creates a condition where a handler partially executes, then the worker retries the same entry, and SpiceDB is checked for duplicate/missing relationships.

The filtering tests cover "already processed → not re-delivered," which is a different sub-case (no failure; handler ran to completion). The scenario in the spec is "partial failure → retry must be safe."

**What is needed to fix this gap:**
Add an integration test in `test_outbox_consistency.py` or a new file that:
1. Creates an outbox entry.
2. Calls the SpiceDB handler (or worker) — it writes a relationship to SpiceDB.
3. Marks the outbox entry as NOT processed (simulating partial failure before `_mark_processed`).
4. Calls the worker/handler again with the same entry.
5. Asserts SpiceDB has exactly the expected relationships (not duplicated), and `processed_at` is now set.

Alternatively, a unit test using a fake SpiceDB client that records calls could verify that the second invocation does not produce different side effects than the first.

---

### REQ-4: Concurrent Worker Safety — **COVERED**

**Scenario: Concurrent workers**
- Implementation: `OutboxRepository.fetch_unprocessed()` uses `.with_for_update(skip_locked=True)`; `OutboxWorker._process_batch()` also uses the same clause inline in its own query.
- Unit test: `test_fetch_unprocessed_uses_for_update_skip_locked` — compiles the query with the PostgreSQL dialect and asserts `"SKIP LOCKED"` appears in the rendered SQL.

---

### REQ-5: Dual Delivery Mechanism — **COVERED**

**Scenario: Real-time notification**
- Implementation:
  - Migration `d32ecc44581a` creates a trigger `notify_outbox_insert()` that fires `AFTER INSERT ON outbox` and issues `pg_notify('outbox_events', NEW.id::text)`.
  - `PostgresNotifyEventSource.start()` listens on the `outbox_events` channel via `asyncpg-listen` and invokes the callback with the parsed UUID.
  - `OutboxWorker.start()` wires the event source to `self._process_single` for sub-second processing.
- Unit tests: `test_notify_triggers_callback_with_uuid`, `test_callback_receives_correct_uuid_type`
- Integration test: `test_worker_processes_via_notify_not_polling` — uses `poll_interval_seconds=999` to disable polling, inserts a group, waits 500 ms, and verifies `processed_at` is set and SpiceDB relationship exists (sub-second confirmation).

**Scenario: Polling fallback**
- Implementation: `OutboxWorker._poll_loop()` runs every `poll_interval_seconds` (default 30 s) and calls `_process_batch()`.
- Integration test: `test_worker_processes_group_created_and_writes_to_spicedb` calls `_process_batch()` directly — this is the same code path the poll loop executes, and the full end-to-end result (SpiceDB write + `processed_at` set) is verified.
- Note: No test explicitly simulates "NOTIFY missed → polling subsequently catches it" as a combined flow, but the polling mechanism itself is exercised end-to-end.

---

### REQ-6: Event Fan-Out — **COVERED**

**Scenario: Multiple handlers registered**
- Implementation: `CompositeEventHandler.register()` appends to `_handlers_by_type[event_type]`; `handle()` iterates all handlers for the type.
- Unit test: `test_handle_fans_out_to_multiple_handlers` — registers two handlers for `"SharedEvent"`, calls `handle()`, asserts both are awaited.

**Scenario: Unknown event type**
- Implementation: `CompositeEventHandler.handle()` raises `UnknownEventTypeError` (not `ValueError`); `OutboxWorker._process_entries()` catches `UnknownEventTypeError` *before* the generic `except Exception` clause and calls `_move_to_dlq()` immediately (bypassing `_handle_processing_failure` and all retry logic).
- Unit tests:
  - `test_handle_raises_for_unknown_event_type` — verifies `UnknownEventTypeError` raised with correct fields.
  - `test_unknown_event_type_error_is_not_value_error` — verifies it is NOT a `ValueError`.
  - `test_unknown_event_type_immediately_moves_to_dlq` — verifies worker calls `event_moved_to_dlq` and NOT `event_processing_failed`, even with `max_retries=5`.
  - `test_unknown_event_type_dlq_even_at_zero_retries` — retry_count=0 still goes straight to DLQ.
  - `test_retry_not_called_for_unknown_event_type` — patches `_increment_retry` and asserts it is never called.

---

## Summary Table

| Requirement | Status | Notes |
|---|---|---|
| Transactional Event Storage — Successful write | COVERED | Unit + integration |
| Transactional Event Storage — Transaction rollback | COVERED | Unit + integration |
| Event Processing — Normal processing | COVERED | Unit + integration |
| Event Processing — Transient failure | COVERED | Unit tests |
| Event Processing — Permanent failure (DLQ) | COVERED | Unit tests |
| Idempotent Event Handlers — Duplicate delivery | PARTIAL | Filtering tested; actual duplicate-invocation idempotency not tested |
| Concurrent Worker Safety — Concurrent workers | COVERED | SKIP LOCKED in compiled SQL |
| Dual Delivery — Real-time notification | COVERED | Unit + integration |
| Dual Delivery — Polling fallback | COVERED | Polling mechanism exercised end-to-end |
| Event Fan-Out — Multiple handlers | COVERED | Unit test |
| Event Fan-Out — Unknown event type | COVERED | Multiple unit tests |

## Verdict: FAIL

One SHALL requirement lacks complete test coverage:

**REQ-3 (Idempotent Event Handlers) — Duplicate delivery scenario:**
The implementation correctly relies on SpiceDB's upsert semantics and the `processed_at IS NULL` filter, but no test exercises the specific scenario described: a handler that partially executes (some side effects written), raises an exception, and is then retried — with the final state asserted to be identical to a single successful run. This gap must be closed with an explicit integration test before this spec requirement can be considered COVERED.