---
task_id: task-017
round: 25
role: spec-reviewer
verdict: fail
---
# Task-017 Spec Alignment Review — Round N

Date: 2026-04-27
Spec: specs/shared-kernel/outbox.spec.md
Branch: hyperloop/task-017

---

## Summary

Two blockers prevent a PASS verdict:

1. **Branch staleness** — `check-branch-rebased-on-alpha.sh` reports the branch
   is **10 commits behind alpha** (threshold is ≤5). This causes
   `check-run-backend-suite.sh` to halt immediately, preventing confirmation
   of the full CI gate suite.

2. **Idempotency scenario — missing test** — The prior review (Findings section)
   cited `TestIdempotentEventHandlers::test_handler_invoked_twice_produces_same_spicedb_state`
   as covering the "Duplicate delivery" scenario. **This test does not exist** in the
   codebase. No equivalent end-to-end test covers the specific scenario of the outbox
   worker retrying an entry and producing the same SpiceDB state without duplicate
   relationships.

All other spec requirements are fully COVERED — implementation and tests are
present and the full unit suite (2484 tests, 0 failures) passes.

---

## Requirement Coverage

### Requirement: Transactional Event Storage — COVERED

**Scenario: Successful write** — COVERED
- Code: `infrastructure/outbox/repository.py::OutboxRepository.append()` — calls
  `session.add()` only, never `session.commit()`; transaction boundary owned by caller.
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_repository_append_does_not_commit`
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_outbox_entry_created_in_same_transaction_as_group`

**Scenario: Transaction rollback** — COVERED
- Same design — no independent commit means rollback discards both aggregate and outbox entries.
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_failed_service_call_leaves_no_outbox_entries`
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_rollback_removes_both_group_and_outbox_entry`

---

### Requirement: Event Processing — COVERED

**Scenario: Normal processing** — COVERED
- Code: `worker.py::_process_entries()` dispatches to handler, then calls
  `_mark_processed()` setting `processed_at=datetime.now(UTC)`.
- Unit tests: `test_worker.py::TestOutboxWorkerProcessBatch::test_processes_unprocessed_entries`,
  `test_marks_entry_as_processed`, `test_calls_event_processed_on_success`
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerProcessing::test_worker_processes_group_created_and_writes_to_spicedb`

**Scenario: Transient failure** — COVERED
- Code: `worker.py::_handle_processing_failure()` increments `retry_count` and
  records `last_error` when `new_retry_count < max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_transient_failure_increments_retry_count`

**Scenario: Permanent failure (dead letter)** — COVERED
- Code: `worker.py::_handle_processing_failure()` calls `_move_to_dlq()` which
  sets `failed_at=datetime.now(UTC)` when `new_retry_count >= max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_max_retries_moves_entry_to_dlq`

---

### Requirement: Idempotent Event Handlers — PARTIAL

**Scenario: Duplicate delivery** — PARTIAL

- **Implementation**: PRESENT. `SpiceDBEventHandler` calls `authz.write_relationship()`,
  which is backed by SpiceDB `OPERATION_TOUCH` (upsert). Writing the same relationship
  twice is a no-op. `fetch_unprocessed()` excludes entries with `processed_at IS NOT NULL`
  and `failed_at IS NOT NULL`, limiting retry exposure.

- **Tests covering the mechanism**:
  - `test_write_relationship_is_idempotent` in `tests/unit/shared_kernel/authorization/test_in_memory_provider.py` — verifies the authorization layer fake deduplicates: writing the same relationship twice leaves exactly one entry.
  - `test_already_processed_entry_excluded_from_fetch` in `test_worker.py` — verifies already-processed entries are excluded.

- **Missing test**: The prior review cited `TestIdempotentEventHandlers::test_handler_invoked_twice_produces_same_spicedb_state` in `test_outbox_consistency.py`. **This test does not exist.** There is no test that exercises the scenario end-to-end:
  > GIVEN the SpiceDB handler is invoked twice for the same outbox payload
  > WHEN the second call happens (simulating a retry after partial failure)
  > THEN the SpiceDB/authz state is identical to a single invocation (no duplicate relationships)

  **Fix**: Add a unit or integration test that calls the SpiceDB handler (or the worker's
  `_process_entries`) twice with the same entry payload and asserts the authorization
  provider state contains exactly the expected relationships (no duplicates). The
  `InMemoryAuthorizationProvider` fake already supports this via its `read_relationships`
  method.

---

### Requirement: Concurrent Worker Safety — COVERED

**Scenario: Concurrent workers** — COVERED
- Code: `repository.py::fetch_unprocessed()` uses `.with_for_update(skip_locked=True)`.
- Unit test: `test_worker.py::TestOutboxWorkerConcurrentSafety::test_fetch_unprocessed_uses_for_update_skip_locked`
  — compiles the query against the PostgreSQL dialect and asserts `"SKIP LOCKED"` is present.

---

### Requirement: Dual Delivery Mechanism — COVERED

**Scenario: Real-time notification** — COVERED
- Code: `event_sources/postgres_notify.py::PostgresNotifyEventSource` listens on
  `outbox_events` channel via asyncpg-listen.
- Unit tests: `test_postgres_notify_event_source.py` (30+ tests)
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerNotifyProcessing::test_worker_processes_via_notify_not_polling`
  — poll_interval_seconds=999; confirms entry processed within 500 ms via NOTIFY only.

**Scenario: Polling fallback** — COVERED
- Code: `worker.py::_poll_loop()` runs every `poll_interval_seconds` (default 30s).
- Unit test: `test_worker.py::TestOutboxWorkerLifecycle::test_in_progress_batch_completes_before_shutdown`

---

### Requirement: Event Fan-Out — COVERED

**Scenario: Multiple handlers registered** — COVERED
- Code: `composite.py::CompositeEventHandler.handle()` dispatches to all handlers in
  `_handlers_by_type[event_type]`.
- Unit test: `test_composite.py::test_handle_fans_out_to_multiple_handlers`

**Scenario: Unknown event type** — COVERED
- Code: `composite.py` raises `UnknownEventTypeError`; `worker.py` catches it before
  the generic handler and immediately calls `_move_to_dlq()`.
- Unit tests: `test_composite.py::test_handle_raises_for_unknown_event_type`,
  `test_worker.py::TestOutboxWorkerRetryBehavior::test_unknown_event_type_immediately_moves_to_dlq`,
  `test_worker.py::test_retry_not_called_for_unknown_event_type`

---

## Branch Hygiene Failures (Blocking)

### FAIL 1 — Branch not rebased on alpha (10 commits behind)

`check-branch-rebased-on-alpha.sh` exits 1. The 10 lagging commits are all
orchestrator housekeeping (`chore(intake)` NFR/index records, `chore(process)`
overlay updates) — none touch source or test files. However, the threshold is ≤5
and this branch is at 10.

`check-run-backend-suite.sh` halts on this condition and does not run the remaining
21 CI gate checks.

**Fix:** `git rebase alpha` from the branch root. No conflicts expected (all diverging
commits are in `.hyperloop/` paths not touched by task-017 source commits).

### FAIL 2 — Idempotency scenario test missing (see above)

The prior verifier passed the branch when it was within the rebase threshold.
Since the branch drifted further, the suite can no longer be confirmed. Additionally,
an independent review of the test files reveals the idempotency scenario integration
test cited in the prior review findings does not exist.

---

## Non-Blocking Notes

### check-graceful-shutdown-cancel — Confirmed false positive
The check flags `worker.py` because both `def stop` and the string `task.cancel()`
appear in the file. The `.cancel()` string appears **only in a docstring comment**
(line 130: "no task.cancel(), so an in-progress..."). The actual `stop()` implementation
correctly uses `_running = False` + `_shutdown_event.set()` + natural `await task` —
no `task.cancel()` calls in production code. Not a violation. This check is not in
the canonical 21-check CI suite.

---

## Required Actions Before Re-Review

1. `git rebase alpha` — incorporate lagging housekeeping commits; re-run
   `check-branch-rebased-on-alpha.sh` → must PASS.
2. Add a test for the duplicate delivery idempotency scenario — invoking the
   outbox handler (or `_process_entries`) twice for the same payload and asserting
   no duplicate SpiceDB relationships exist.
3. Re-run full backend suite (`check-run-backend-suite.sh`) — all 21 checks must PASS.
4. Re-submit for review.