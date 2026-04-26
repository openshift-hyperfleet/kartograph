---
task_id: task-017
round: 14
role: spec-reviewer
verdict: fail
---
## Task-017 Outbox Pattern — Spec Alignment Review

Date: 2026-04-26
Branch: hyperloop/task-017

---

## Summary

The outbox implementation is **complete and correct** — all 6 SHALL requirements
and all 11 scenarios are implemented and tested. The FAIL verdict is issued solely
because two branch-hygiene CI gate checks are currently failing, which block merge.

---

## Spec Requirements Coverage

### Requirement: Transactional Event Storage — COVERED

**Scenario: Successful write** — COVERED
- Code: `infrastructure/outbox/repository.py::OutboxRepository.append()` calls
  `session.add()` only; never calls `session.commit()`. The calling service owns
  the transaction boundary (documented in class docstring).
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_repository_append_does_not_commit`
  asserts `mock_session.commit.assert_not_called()` and `session.add.assert_called_once()`.
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_outbox_entry_created_in_same_transaction_as_group`
  verifies group + outbox entry both exist after transaction commits.

**Scenario: Transaction rollback** — COVERED
- Code: Same shared-session design — no independent commit means rollback discards
  both aggregate and outbox entries atomically.
- Unit test: `test_worker.py::TestOutboxWorkerTransactionAtomicity::test_failed_service_call_leaves_no_outbox_entries`
- Integration test: `test_outbox_consistency.py::TestAtomicityGuarantees::test_rollback_removes_both_group_and_outbox_entry`
  forces an exception inside `async_session.begin()` and asserts neither group
  nor outbox entry persists.

### Requirement: Event Processing — COVERED

**Scenario: Normal processing** — COVERED
- Code: `worker.py::OutboxWorker._process_entries()` dispatches to handler then
  calls `_mark_processed()` which sets `processed_at=datetime.now(UTC)`.
- Unit tests: `test_worker.py::TestOutboxWorkerProcessBatch::test_processes_unprocessed_entries`,
  `test_marks_entry_as_processed`, `test_calls_event_processed_on_success`.
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerProcessing::test_worker_processes_group_created_and_writes_to_spicedb`
  confirms `processed_at is not None` and SpiceDB relationship exists.

**Scenario: Transient failure** — COVERED
- Code: `worker.py::_handle_processing_failure()` increments `retry_count` and
  records `last_error` when `new_retry_count < max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_transient_failure_increments_retry_count`
  asserts `probe.event_processing_failed` called, `probe.event_moved_to_dlq` not called.

**Scenario: Permanent failure (dead letter)** — COVERED
- Code: `worker.py::_handle_processing_failure()` calls `_move_to_dlq()` which
  sets `failed_at=datetime.now(UTC)` when `new_retry_count >= max_retries`.
- Unit test: `test_worker.py::TestOutboxWorkerRetryBehavior::test_max_retries_moves_entry_to_dlq`
  asserts `probe.event_moved_to_dlq` called, `probe.event_processing_failed` not called.

### Requirement: Idempotent Event Handlers — COVERED

**Scenario: Duplicate delivery** — COVERED
- Code: SpiceDB handler uses `write_relationship` with TOUCH semantics (upsert).
  `repository.py::fetch_unprocessed` filters on `processed_at IS NULL AND failed_at IS NULL`.
- Unit test: `test_worker.py::TestOutboxWorkerIdempotency::test_already_processed_entry_excluded_from_fetch`
  verifies `processed_at IS NULL` in compiled query.
- Integration test: `test_outbox_consistency.py::TestIdempotentEventHandlers::test_handler_invoked_twice_produces_same_spicedb_state`
  calls handler twice on same payload without `mark_processed`; asserts final
  SpiceDB state is identical (no duplicate relationships).

### Requirement: Concurrent Worker Safety — COVERED

**Scenario: Concurrent workers** — COVERED
- Code: Both `repository.py::fetch_unprocessed()` and `worker.py::_process_batch()`
  use `.with_for_update(skip_locked=True)`.
- Unit test: `test_worker.py::TestOutboxWorkerConcurrentSafety::test_fetch_unprocessed_uses_for_update_skip_locked`
  compiles the query against the PostgreSQL dialect and asserts `"SKIP LOCKED"` appears.

### Requirement: Dual Delivery Mechanism — COVERED

**Scenario: Real-time notification** — COVERED
- Code: `event_sources/postgres_notify.py::PostgresNotifyEventSource` listens on
  `outbox_events` channel via `asyncpg-listen`; invokes `_process_single` callback
  with UUID from the notification payload.
- Unit tests: `test_postgres_notify_event_source.py` — 23+ tests covering notification
  receipt, UUID parsing, invalid payloads, stop/start lifecycle.
- Integration test: `test_outbox_consistency.py::TestOutboxWorkerNotifyProcessing::test_worker_processes_via_notify_not_polling`
  sets `poll_interval_seconds=999`; asserts `processed_at` is set within 500 ms.

**Scenario: Polling fallback** — COVERED
- Code: `worker.py::_poll_loop()` runs every `poll_interval_seconds` (default 30 s)
  using `asyncio.wait_for(_shutdown_event.wait(), timeout=poll_interval)` for
  clean early exit on shutdown without aborting in-progress batches.
- Unit test: `test_worker.py::TestOutboxWorkerLifecycle::test_in_progress_batch_completes_before_shutdown`
  verifies the poll loop runs and a batch completes before `stop()` returns.

### Requirement: Event Fan-Out — COVERED

**Scenario: Multiple handlers registered** — COVERED
- Code: `composite.py::CompositeEventHandler.handle()` dispatches to all handlers
  in `_handlers_by_type[event_type]` in registration order.
- Unit test: `test_composite.py::TestCompositeEventHandler::test_handle_fans_out_to_multiple_handlers`
  registers two handlers for `SharedEvent`; asserts both are invoked.

**Scenario: Unknown event type** — COVERED
- Code: `composite.py` raises `UnknownEventTypeError` when no handler is registered.
  `worker.py::_process_entries()` catches `UnknownEventTypeError` before the generic
  `Exception` handler and immediately calls `_move_to_dlq()` without incrementing
  retry count.
- Unit tests:
  - `test_composite.py::test_handle_raises_for_unknown_event_type`
  - `test_worker.py::TestOutboxWorkerRetryBehavior::test_unknown_event_type_immediately_moves_to_dlq`
  - `test_worker.py::test_retry_not_called_for_unknown_event_type`

---

## Branch Hygiene Failures (Blocking Merge)

Both checks were run live and both fail at the time of this review.

### FAIL 1 — Branch is 6 commits behind alpha (threshold: 5)

```
check-branch-rebased-on-alpha.sh exits 1
STALE BRANCH: This branch is 6 commit(s) behind 'alpha'.
```

Lagging commits (none related to outbox implementation):
- `13ba0b7a chore(intake): record Run 6 review of index and NFR specs`
- `3f324d21 feat(management): implement Management REST API for Data Sources`
- `33e9632d feat(iam): enforce last-admin and no-children-delete protection`
- `f4500909 feat(iam): fix AGEGraphProvisioner`
- `3ac824e6 feat(iam): add integration test — group member removal`
- `5f9beb47 feat(management): implement Management REST API for Knowledge Graphs`

**Fix:** `git rebase alpha`

### FAIL 2 — State files committed on branch

```
check-no-state-file-commits.sh exits 1
FAIL: The following .hyperloop/state/ files are present in branch commits:
  .hyperloop/state/intake/2026-04-25-seventh-run.md
  .hyperloop/state/intake/2026-04-25-eighth-run.md
  .hyperloop/state/intake/2026-04-25-ninth-run.md
  .hyperloop/state/intake/2026-04-26-tenants-nfr-index-repeat.md
  .hyperloop/state/tasks/task-038.md
```

These were added by intake workers operating on this branch rather than alpha.
They must be stripped from branch commit history.

**Fix:** Identify the delivery commits (those that do NOT touch `.hyperloop/state/`),
create a clean branch from current alpha, and cherry-pick only the delivery commits:

```bash
# Step 1 — list delivery SHAs (commits not touching state files)
git log --oneline $(git merge-base HEAD alpha)..HEAD -- ':!.hyperloop/state'

# Step 2 — create clean branch and cherry-pick
git checkout alpha
git checkout -b hyperloop/task-017-clean
git cherry-pick <delivery-sha-1> [<delivery-sha-2> ...]

# Step 3 — verify both checks pass
bash .hyperloop/checks/check-no-state-file-commits.sh
bash .hyperloop/checks/check-branch-rebased-on-alpha.sh
```

---

## Required Actions Before Re-Review

1. Rebase onto or cherry-pick onto current alpha (resolve FAIL 1)
2. Strip `.hyperloop/state/` file additions from branch commit history (resolve FAIL 2)
3. Confirm `check-branch-rebased-on-alpha.sh` → PASS
4. Confirm `check-no-state-file-commits.sh` → PASS
5. Re-submit for review

---

## Notes (Non-Blocking)

**check-graceful-shutdown-cancel — False positive:** The check flags `worker.py`
because the file contains both `def stop` and `.cancel()`. The `.cancel()` string
appears only in a docstring (line 130). The actual `stop()` implementation uses
`_running = False` + `_shutdown_event.set()` + natural `await task` — no
`task.cancel()` in production code.

**check-empty-test-stubs — Pre-existing:** `tests/integration/test_api_key_auth.py:691`
has an empty stub. `git diff alpha...HEAD` confirms this file was NOT modified by
task-017 — the stub exists on alpha already.

**check-no-direct-logger-usage — Pre-existing, different context:**
`query/presentation/mcp.py` uses `print()`. This is in the Querying bounded context,
not in the outbox implementation. All outbox code uses domain probes exclusively.