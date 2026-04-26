---
task_id: task-017
round: 9
role: spec-reviewer
verdict: fail
---
# Task-017 Outbox Pattern — Spec Alignment Review

Date: 2026-04-25
Branch: hyperloop/task-017 (20 commits ahead of alpha, 17 commits behind)

---

## Spec Requirements Coverage

All 6 SHALL requirements and all 11 scenarios are COVERED — the implementation
itself is complete and correct. The FAIL verdict is issued solely for two branch
hygiene blockers that prevent safe merge.

---

### Requirement: Transactional Event Storage — COVERED

**Scenario: Successful write** — COVERED
- Code: `src/api/infrastructure/outbox/repository.py` — `OutboxRepository.append()`
  calls `session.add()` only; never calls `session.commit()`. The calling service owns
  the transaction boundary (documented in the class docstring).
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_repository_append_does_not_commit`
  — asserts `mock_session.commit.assert_not_called()` and `session.add.assert_called_once()`.
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_outbox_entry_created_in_same_transaction_as_group`
  — verifies group + outbox entry both exist after the transaction commits.

**Scenario: Transaction rollback** — COVERED
- Code: Same repository design — no independent commit means rollback discards both
  aggregate and outbox entries atomically.
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_failed_service_call_leaves_no_outbox_entries`
  — verifies `session.commit` is never called so rollback discards the add.
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_rollback_removes_both_group_and_outbox_entry`
  — forces an exception inside `async_session.begin()` and asserts neither group nor
  outbox entry persists.

---

### Requirement: Event Processing — COVERED

**Scenario: Normal processing** — COVERED
- Code: `worker.py::OutboxWorker._process_entries()` dispatches to handler, then
  calls `_mark_processed()` which sets `processed_at=datetime.now(UTC)`.
- Unit test: `test_worker.py::TestOutboxWorkerProcessBatch::test_processes_unprocessed_entries`
  + `test_marks_entry_as_processed` + `test_calls_event_processed_on_success`
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerProcessing::test_worker_processes_group_created_and_writes_to_spicedb`
  — confirms `processed_at is not None` and SpiceDB relationship exists.

**Scenario: Transient failure** — COVERED
- Code: `worker.py::_handle_processing_failure()` — increments `retry_count` and
  records `last_error` via `_increment_retry()` when `new_retry_count < max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_transient_failure_increments_retry_count`
  — asserts `probe.event_processing_failed` called, `probe.event_moved_to_dlq` not called.

**Scenario: Permanent failure (dead letter)** — COVERED
- Code: `worker.py::_handle_processing_failure()` — calls `_move_to_dlq()` which
  sets `failed_at=datetime.now(UTC)` when `new_retry_count >= max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_max_retries_moves_entry_to_dlq`
  — asserts `probe.event_moved_to_dlq` called, `probe.event_processing_failed` not called.

---

### Requirement: Idempotent Event Handlers — COVERED

**Scenario: Duplicate delivery** — COVERED
- Code: SpiceDB handler uses `write_relationship` which is an upsert (TOUCH semantics).
  Fetching also filters on `processed_at IS NULL` and `failed_at IS NULL`
  (`repository.py::fetch_unprocessed`).
- Unit test: `test_worker.py::TestOutboxWorkerIdempotency::test_already_processed_entry_excluded_from_fetch`
  — verifies `processed_at IS NULL` in compiled query.
- Integration test: `test_outbox_consistency.py::TestIdempotentEventHandlers::test_handler_invoked_twice_produces_same_spicedb_state`
  — invokes handler twice on the same payload without calling `mark_processed` between
  calls; asserts final SpiceDB state is identical (no duplicate relationships).

---

### Requirement: Concurrent Worker Safety — COVERED

**Scenario: Concurrent workers** — COVERED
- Code: `repository.py::fetch_unprocessed()` and `worker.py::_process_batch()` both
  use `.with_for_update(skip_locked=True)` — entries are row-locked and skipped by
  competing sessions.
- Unit test: `test_worker.py::TestOutboxWorkerConcurrentSafety::test_fetch_unprocessed_uses_for_update_skip_locked`
  — compiles the query against the PostgreSQL dialect and asserts `"SKIP LOCKED"` appears.

---

### Requirement: Dual Delivery Mechanism — COVERED

**Scenario: Real-time notification** — COVERED
- Code: `event_sources/postgres_notify.py::PostgresNotifyEventSource` listens on
  `outbox_events` channel via `asyncpg-listen`; invokes `_process_single` callback
  with UUID from the notification payload.
- Unit tests: `test_postgres_notify_event_source.py` — 30+ tests covering notification
  receipt, UUID parsing, invalid payloads, timeout handling, stop/start lifecycle.
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerNotifyProcessing::test_worker_processes_via_notify_not_polling`
  — sets `poll_interval_seconds=999` so only NOTIFY can process; asserts `processed_at`
  is set within 500 ms.

**Scenario: Polling fallback** — COVERED
- Code: `worker.py::_poll_loop()` runs every `poll_interval_seconds` (default 30s);
  uses `asyncio.wait_for(_shutdown_event.wait(), timeout=poll_interval)` to allow
  early exit on shutdown without skipping the current batch.
- Unit test: `test_worker.py::TestOutboxWorkerLifecycle::test_in_progress_batch_completes_before_shutdown`
  — verifies polling fallback loop runs and completes a batch before stop() returns.

---

### Requirement: Event Fan-Out — COVERED

**Scenario: Multiple handlers registered** — COVERED
- Code: `composite.py::CompositeEventHandler.handle()` dispatches to all handlers
  in `_handlers_by_type[event_type]` in registration order.
- Unit test: `test_composite.py::TestCompositeEventHandler::test_handle_fans_out_to_multiple_handlers`
  — registers two handlers for `SharedEvent`, calls `handle()`, asserts both handlers
  were invoked with the correct payload.

**Scenario: Unknown event type** — COVERED
- Code: `composite.py::CompositeEventHandler.handle()` raises `UnknownEventTypeError`
  when no handler is registered. `worker.py::_process_entries()` catches
  `UnknownEventTypeError` before the generic `Exception` handler and immediately calls
  `_move_to_dlq()` without incrementing retry count.
- Unit tests:
  - `test_composite.py::test_handle_raises_for_unknown_event_type` — asserts
    `UnknownEventTypeError` is raised with `.event_type` and `.registered_types`.
  - `test_worker.py::TestOutboxWorkerRetryBehavior::test_unknown_event_type_immediately_moves_to_dlq`
    — asserts `probe.event_moved_to_dlq` called at retry_count=0, `probe.event_processing_failed`
    not called.
  - `test_worker.py::test_retry_not_called_for_unknown_event_type` — patches
    `_increment_retry` and asserts it is never called.

---

## Branch Hygiene Failures (Blocking)

These failures are detected by CI gate checks. The spec requirements are all met,
but the branch cannot be merged until both issues are resolved.

### FAIL 1 — Branch not rebased on alpha

`check-branch-rebased-on-alpha.sh` reports the branch is 17 commits behind `alpha`.
All lagging commits are orchestrator housekeeping (`chore(intake)`, `chore(process)`).
No implementation conflicts are expected, but the check is a hard merge gate.

**Fix:** `git rebase alpha` from the branch root.

### FAIL 2 — State files committed on branch

`check-no-state-file-commits.sh` finds 23 `.hyperloop/state/` files that differ
from alpha on this branch. Affected paths include:

- `.hyperloop/state/intake/2026-04-25-{seventh,eighth,ninth}-run.md`
- `.hyperloop/state/reviews/task-{001,007,008,010,014,017,018,020}-round-*.md`
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019}.md`

These were added by intake and review workers operating on this branch, not by the
task-017 implementer. However, their presence in the branch's commit history
blocks merge.

**Fix:** After rebasing on alpha, verify whether the state file changes survive.
Strip any remaining `.hyperloop/state/` modifications via interactive rebase
(`git rebase -i alpha`, then `git reset HEAD -- .hyperloop/state/` on the
offending commits and re-commit without those paths).

---

## Notes (Non-Blocking)

### check-graceful-shutdown-cancel — False positive
The check flags `worker.py` because the file contains both `def stop` and `.cancel()`.
The `.cancel()` string appears **only in a docstring comment** (line 130 of
`worker.py`). The actual `stop()` implementation correctly uses `_running = False` +
`_shutdown_event.set()` + natural `await task` — no `task.cancel()` calls in
production code.

### check-empty-test-stubs — Pre-existing
`tests/integration/test_api_key_auth.py:691` contains an empty stub
(`test_create_api_key_requires_tenant_membership`). `git diff alpha...HEAD` confirms
this file was NOT modified by task-017 — the stub exists on alpha already. Not a
task-017 regression.

### check-no-direct-logger-usage — Pre-existing, different bounded context
`query/presentation/mcp.py:197` uses `print()`. This is in the Querying bounded
context, not in the outbox implementation. The outbox code itself (shared_kernel,
infrastructure/outbox) uses domain probes exclusively — no logger.* or print() calls.

---

## Required Actions Before Re-Review

1. `git rebase alpha` — incorporate the 17 lagging housekeeping commits
2. Strip `.hyperloop/state/` file additions from branch commit history
3. Re-run `check-branch-rebased-on-alpha.sh` → must PASS
4. Re-run `check-no-state-file-commits.sh` → must PASS
5. Re-submit for review