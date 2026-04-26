---
task_id: task-017
round: 19
role: verifier
verdict: fail
---
## Summary

INHERITED-VIOLATION FAIL. Task-017's outbox implementation is complete and
correct for all 6 SHALL requirements and 11 scenarios. The sole blocker is a
pre-existing cascade-delete test coverage gap in `test_tenant_service.py::TestDeleteTenant`
that was not introduced by task-017 but is now enforced by a new gate
(`check-cascade-delete-empty-collection-mocks.sh`) added to alpha by
`chore(process): enforce non-empty collection tests in cascade-delete classes`.

Per verifier overlay: "Attribution to another task does not excuse a failing
check. A fully-rebased branch that inherits a pre-existing violation owns
that violation."

---

## Backend Suite Output (alpha: 8759f1436eb54b0e77ad6d24ab36f0c3e892b11a)

```
========================================================
 Backend check suite — 2026-04-26T06:21:59-0400
 alpha: 8759f1436eb54b0e77ad6d24ab36f0c3e892b11a
========================================================

PASSED (14):
  ✓ check-no-check-script-deletions.sh
  ✓ check-process-overlays-intact.sh
  ✓ check-branch-has-commits.sh
  ✓ check-branch-rebased-on-alpha.sh     OK: Branch is 1 commit(s) behind 'alpha' — within acceptable range.
  ✓ check-no-state-file-commits.sh       PASS: No .hyperloop/state/ files committed on this branch.
  ✓ check-no-source-regressions.sh
  ✓ check-no-test-regressions.sh
  ✓ check-empty-test-stubs.sh
  ✓ check-domain-aggregate-mocks.sh
  ✓ check-no-direct-logger-usage.sh
  ✓ check-no-coming-soon-stubs.sh
  ✓ check-weak-test-assertions.sh
  ✓ check-di-wiring-updated.sh
  ✓ check-pytest-env-skip-if-set.sh

FAILED (1):
  ✗ check-cascade-delete-empty-collection-mocks.sh

RESULT: FAIL — resolve all failing checks before submitting.
```

---

## Failing Check Detail

### check-cascade-delete-empty-collection-mocks.sh — FAIL

**File:** `src/api/tests/unit/iam/application/test_tenant_service.py`
**Class:** `TestDeleteTenant`
**Issue:** `mock_group_repo.list_by_tenant` is only ever mocked with
`return_value=[]` (empty list) at all 8 occurrence sites. The cascade-delete
for-loop body (group.mark_for_deletion → group_repo.delete) is never entered
by any test.

**Originating commit:** `11db83fa feat(api.iam): auto tenant root workspace creation (#210)`
(pre-existing on alpha; task-017 did not modify `test_tenant_service.py` —
confirmed via `git diff alpha..HEAD -- src/api/tests/unit/iam/application/test_tenant_service.py`
returning 0 lines).

**Affected lines:**
```
line 1283:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1329:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1401:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1484:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1547:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1604:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1644:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
line 1713:  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
```

**Required fix:** Add one new test inside `TestDeleteTenant` that:

1. Builds a real `Group` domain object (use an existing factory helper or
   `Group(...)` constructor — no `MagicMock`)
2. Mocks `mock_group_repo.list_by_tenant = AsyncMock(return_value=[real_group])`
3. Calls the tenant service delete method
4. Asserts `mock_group_repo.delete.assert_called_once_with(real_group)`

Commit as `test(iam): add non-empty cascade-delete coverage for TestDeleteTenant`
with `Spec-Ref` and `Task-Ref: task-017` trailers.

---

## Unit Tests — PASS

```
2420 passed, 45 warnings in 58.94s
```

---

## Linting / Formatting / Type Checking — PASS

- `ruff check .` — All checks passed
- `ruff format --check .` — 481 files already formatted
- `mypy . --ignore-missing-imports` — Success: no issues found in 481 source files

---

## Architecture Boundary Tests — PASS

```
40 passed in 0.24s   (tests/unit/test_architecture.py)
```

All outbox boundary tests pass:
- `test_outbox_does_not_import_iam_internals` ✓
- `test_outbox_does_not_import_graph_internals` ✓
- `test_outbox_does_not_import_query_internals` ✓
- `test_outbox_does_not_import_management_internals` ✓
- `test_outbox_does_not_import_ingestion_internals` ✓
- `test_outbox_does_not_import_extraction_internals` ✓
- `test_outbox_may_import_shared_kernel` ✓

---

## Commit Trailers — PASS

All 4 implementation commits carry both `Spec-Ref` and `Task-Ref` trailers:

- `feat(shared-kernel): add UnknownEventTypeError for permanent outbox failures`
  Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc...  Task-Ref: task-017
- `fix(task-017): resolve backend suite check failures after alpha rebase`
  Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc...  Task-Ref: task-017
- `chore(task-017): record worker result — pass after branch hygiene remediation`
  Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc...  Task-Ref: task-017
- `chore(task-017): record verifier verdict — fail (integration test infrastructure)`
  Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc...  Task-Ref: task-017

---

## Spec Coverage — ALL COVERED

All 6 SHALL requirements and 11 scenarios are implemented correctly.
No re-implementation required. Fix only the cascade-delete test gap.

### Transactional Event Storage ✓
- `OutboxRepository.append()` uses `session.add()` only; caller owns transaction.
- Atomicity confirmed by unit + integration tests.

### Event Processing ✓
- Normal: handler dispatched, `processed_at` set on success.
- Transient failure: `retry_count` incremented, `last_error` recorded.
- Permanent failure: `failed_at` set, dead-letter state, no further retries.

### Idempotent Event Handlers ✓
- SpiceDB handler uses TOUCH (upsert) semantics.
- `fetch_unprocessed` filters `processed_at IS NULL AND failed_at IS NULL`.
- Two distinct idempotency tests: (a) filtering test, (b) double-invocation test.

### Concurrent Worker Safety ✓
- `fetch_unprocessed()` uses `FOR UPDATE SKIP LOCKED`.
- Compile-time test asserts `SKIP LOCKED` in generated SQL.

### Dual Delivery Mechanism ✓
- NOTIFY: `PostgresNotifyEventSource` via asyncpg-listen, sub-second latency.
- Polling fallback: `_poll_loop()` every 30s, catches missed entries.

### Event Fan-Out ✓
- `CompositeEventHandler` dispatches to all registered handlers per type.
- Unknown event type → `UnknownEventTypeError` → immediate DLQ, no retry.

---

## Required Action Before Re-Review

1. Add one non-empty cascade-delete test to `TestDeleteTenant` (see fix detail above).
2. Confirm `check-cascade-delete-empty-collection-mocks.sh` exits 0.
3. Run `bash .hyperloop/checks/check-run-backend-suite.sh` — must show `RESULT: ALL PASS`.
4. Resubmit.

No other changes are needed. The outbox implementation is complete and correct.