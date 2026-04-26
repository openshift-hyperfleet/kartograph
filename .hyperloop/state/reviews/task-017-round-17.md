---
task_id: task-017
round: 17
role: implementer
verdict: fail
---
## Summary

The task-017 implementation is complete and correct for all 6 SHALL requirements.
All unit tests, linting, formatting, type checking, and architecture boundary
tests pass. The 13-check backend suite (check-run-backend-suite.sh) passes
entirely. However, integration tests fail due to a pre-existing infrastructure
configuration issue in `pyproject.toml` that hardcodes `SPICEDB_ENDPOINT` without
`skip_if_set = true`, preventing isolated instance connectivity.

---

## Check Results

### 1. Unit Tests — PASS
2420 unit tests pass. Zero failures, zero errors.
```
cd src/api && uv run pytest tests/unit -v
2420 passed, 45 warnings in 55.08s
```

### 2. Linting (ruff check) — PASS
```
cd src/api && uv run ruff check .
All checks passed!
```

### 3. Formatting (ruff format) — PASS
```
cd src/api && uv run ruff format --check .
481 files already formatted
```

### 4. Type Checking (mypy) — PASS
```
cd src/api && uv run mypy . --config-file pyproject.toml --ignore-missing-imports
Success: no issues found in 481 source files
```

### 5. Architecture Boundary Tests — PASS
```
cd src/api && uv run pytest tests/unit/test_architecture.py -v
40 passed in 0.22s
```

### 6. Integration Tests — FAIL (pre-existing infrastructure issue)

5 integration tests in `test_outbox_consistency.py` fail because
`pyproject.toml::tool.pytest_env` hardcodes `SPICEDB_ENDPOINT = "localhost:50051"`
**without `skip_if_set = true`**. This overrides the instance env var (`localhost:59051`),
causing all SpiceDB gRPC connections to attempt the wrong port and fail with:

```
SSL_ERROR_SSL: error:1000007d:SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED:
self signed certificate
```

Failing tests:
- `TestOutboxEventCreation::test_remove_member_appends_member_removed_event`
- `TestOutboxWorkerProcessing::test_worker_processes_group_created_and_writes_to_spicedb`
- `TestOutboxWorkerProcessing::test_worker_processes_member_added_and_writes_to_spicedb`
- `TestOutboxWorkerNotifyProcessing::test_worker_processes_via_notify_not_polling`
- `TestIdempotentEventHandlers::test_handler_invoked_twice_produces_same_spicedb_state`

**Root cause:** `src/api/pyproject.toml` (not modified by task-017, pre-existing on alpha):
```toml
[tool.pytest_env]
SPICEDB_ENDPOINT = "localhost:50051"   # ← missing skip_if_set = true
SPICEDB_PRESHARED_KEY = { value = "changeme", skip_if_set = true }   # ← correct
```

**Fix required (in pyproject.toml):**
```toml
SPICEDB_ENDPOINT = { value = "localhost:50051", skip_if_set = true }
```

**Attribution:** This is a pre-existing issue on alpha — `test_outbox_consistency.py`
and `pyproject.toml` were both unmodified by task-017 (`git diff alpha...HEAD`
shows zero changes to either file). The SpiceDB connectivity failure affects ALL
integration tests that write to SpiceDB when running in isolated instances, not
just the outbox tests.

### 7. Backend Suite (check-run-backend-suite.sh) — PASS (all 13 checks)
```
PASSED (13):
  ✓ check-no-check-script-deletions.sh
  ✓ check-process-overlays-intact.sh
  ✓ check-branch-has-commits.sh
  ✓ check-branch-rebased-on-alpha.sh      OK: 3 commits behind (within 5-commit limit)
  ✓ check-no-state-file-commits.sh        PASS: No .hyperloop/state/ files committed
  ✓ check-no-source-regressions.sh
  ✓ check-no-test-regressions.sh
  ✓ check-empty-test-stubs.sh
  ✓ check-domain-aggregate-mocks.sh
  ✓ check-no-direct-logger-usage.sh
  ✓ check-no-coming-soon-stubs.sh
  ✓ check-weak-test-assertions.sh
  ✓ check-di-wiring-updated.sh
RESULT: ALL PASS — safe to submit.
```

### 8. Commit Trailers — PASS
All 4 commits carry both `Spec-Ref` and `Task-Ref` trailers:
- `5ee65d48 feat(shared-kernel): add UnknownEventTypeError for permanent outbox failures`
- `4a3af567 fix(task-017): resolve backend suite check failures after alpha rebase`
- `955c3181 fix(management): replace bare MagicMock() with MagicMock(spec=DataSource) in KG service test`
- `cad2879c chore(task-017): record worker result — pass after branch hygiene remediation`

### 9. Code Review — PASS
- No direct `logger.*` or `print()` usage in outbox code; all observability via domain probes.
- No bare `MagicMock()` on domain aggregates.
- DDD boundaries respected: outbox infrastructure imports from shared_kernel only.
- Conventional commit messages used throughout.
- No hardcoded secrets or environment-specific values in implementation code.

---

## Non-Blocking Observations (from individual check runs)

These checks fail when run individually but are **not part of the backend suite gate**
and are **pre-existing on alpha** (not introduced by task-017):

- `check-graceful-shutdown-cancel.sh` — False positive: `.cancel()` appears only in
  a docstring comment in `worker.py` line 130 ("no task.cancel()..."). Actual stop()
  implementation uses `_running=False` + `_shutdown_event.set()` + natural `await task`.
- `check-pages-have-tests.sh` — `src/dev-ui/app/pages/auth/callback.vue` has no tests.
  Not touched by task-017.
- `check-partial-error-assertions.sh` — OR-chained assertions in `test_query_mcp.py`,
  `test_mutation_service.py`, `test_cors_settings.py`, `test_settings.py`. Not touched
  by task-017.
- `check-property-merge-semantics.sh` — `graph/infrastructure/age_bulk_loading/queries.py`
  uses direct property assignment. Not touched by task-017.
- `check-auth-status-codes.sh` — Review-required 403 assertions in integration tests.
  Not touched by task-017.

---

## Spec Coverage

All 6 SHALL requirements are implemented correctly:

- **Transactional Event Storage**: `OutboxRepository.append()` uses `session.add()`
  only, never calls `commit()`. The caller owns the transaction boundary.
- **Event Processing**: Worker dispatches to handlers, marks success, increments retry
  on transient failure, sets `failed_at` on permanent failure (dead letter).
- **Idempotent Event Handlers**: SpiceDB handler uses TOUCH semantics. `fetch_unprocessed`
  filters `processed_at IS NULL AND failed_at IS NULL`.
- **Concurrent Worker Safety**: `fetch_unprocessed()` uses `.with_for_update(skip_locked=True)`.
- **Dual Delivery Mechanism**: `PostgresNotifyEventSource` (real-time NOTIFY) +
  `_poll_loop()` (30s polling fallback).
- **Event Fan-Out**: `CompositeEventHandler` fans out to all registered handlers.
  `UnknownEventTypeError` immediately DLQs without retrying.

---

## Required Action Before Re-Review

1. In `src/api/pyproject.toml`, change:
   ```toml
   SPICEDB_ENDPOINT = "localhost:50051"
   ```
   to:
   ```toml
   SPICEDB_ENDPOINT = { value = "localhost:50051", skip_if_set = true }
   ```
2. Re-run integration tests with `make instance-up` and verify all 10 outbox
   consistency tests pass.
3. Re-submit for review.

Note: This fix should be applied on alpha as well (it is a systemic issue affecting
all SpiceDB integration tests in isolated instances, not just task-017).