---
task_id: task-017
round: 27
role: verifier
verdict: fail
---
# Task-017 Outbox Pattern — Verification Review (Round 5)

Date: 2026-04-27
Branch: hyperloop/task-017
Spec: specs/shared-kernel/outbox.spec.md
Reviewer: code-reviewer agent (Round 5)

---

## Summary

The implementation is substantively complete and correct. All 6 spec requirements
with all 11 scenarios are fully covered, all 2484 unit tests pass, and the code
quality checks (linting, formatting, type-checking, architecture boundaries) are
clean. The FAIL verdict is issued solely due to two infrastructure-level check
failures that are not resolvable by the task implementer:

1. **check-alpha-local-vs-remote.sh** (NEW in this round): false positive — local
   alpha is 63 commits ahead of origin/alpha (expected orchestrator behavior), but
   the branch IS correctly rebased on local alpha (confirmed by
   check-branch-rebased-on-alpha.sh: 0 commits behind). The check exits 1 based
   solely on the local/remote divergence, not on whether the branch itself is current.

2. **check-worker-result-not-committed.sh**: systemic Protocol contradiction —
   the verifier Protocol mandates committing this file, but the check forbids it.
   Prior verification rounds committed the file per Protocol, permanently
   contaminating the branch history. No verifier can satisfy both constraints.

---

## Check Results

### 1. Unit Tests — PASS
2484 tests passed in 86.33s. Zero failures, zero errors.

### 2. Linting (ruff check) — PASS
All checks passed. Zero violations.

### 3. Formatting (ruff format --check) — PASS
497 files already formatted. Zero violations.

### 4. Type Checking (mypy) — PASS
Success: no issues found in 497 source files.

### 5. Architecture Boundary Tests — PASS
40 tests passed. All DDD layer rules enforced.
TestOutboxInfrastructureBoundaries: 7 tests confirm outbox does not import
bounded-context internals (IAM, Graph, Querying, Management, Ingestion, Extraction).
Outbox correctly isolated to shared_kernel only.

### 6. check-run-backend-suite.sh — FAIL (2 of 25 checks)

After rebasing on alpha (branch was 3 commits behind at start of this round):

#### Passing checks (23):
  ✓ check-no-check-script-deletions.sh
  ✓ check-process-overlays-intact.sh
  ✓ check-new-checks-pass-on-head.sh
  ✓ check-branch-has-commits.sh
  ✓ check-branch-rebased-on-alpha.sh  (0 commits behind local alpha after rebase)
  ✓ check-no-state-file-commits.sh
  ✓ check-no-foreign-task-commits.sh
  ✓ check-no-source-regressions.sh
  ✓ check-no-route-handler-removals.sh
  ✓ check-no-test-regressions.sh
  ✓ check-empty-test-stubs.sh
  ✓ check-domain-aggregate-mocks.sh
  ✓ check-no-direct-logger-usage.sh
  ✓ check-no-coming-soon-stubs.sh
  ✓ check-weak-test-assertions.sh
  ✓ check-di-wiring-updated.sh
  ✓ check-event-handlers-registered.sh
  ✓ check-domain-events-have-consumers.sh
  ✓ check-pytest-env-skip-if-set.sh
  ✓ check-cascade-delete-cleanup.sh
  ✓ check-cascade-delete-empty-collection-mocks.sh
  ✓ check-unused-fixtures.sh
  ✓ check-no-future-placeholder-comments.sh

#### Failing checks (2):

**FAIL: check-alpha-local-vs-remote.sh** (NEW — added to suite via alpha commit a71a4900)

Local alpha is 63 commits ahead of origin/alpha. The check exits 1 whenever local
alpha is >5 commits ahead of origin/alpha, regardless of whether the task branch
is already rebased on local alpha. This is expected orchestrator behavior (local
alpha advances independently of remote pushes). The branch IS correctly rebased
on local alpha — check-branch-rebased-on-alpha.sh confirms 0 commits behind.
This is a false positive in the check logic; it fires even after a successful
`git rebase alpha`.

Fix (orchestrator level): Either push local alpha to origin/alpha more frequently
so the divergence stays under 5 commits, or update check-alpha-local-vs-remote.sh
to exit 0 when the branch itself is current with local alpha.

**FAIL: check-worker-result-not-committed.sh**

`.hyperloop/worker-result.yaml` is committed in branch history. Prior review
commits (from rounds 1–4) modified this file in commits:
  - eb66ecc0 chore(review): spec-alignment verdict PASS for task-017 outbox pattern
  - 5adaca93 chore(task-017): rebase on alpha and update worker result
  - b94f29b0 chore(review): task-017 verification round 3 — FAIL
  - 93e16c3f chore(review): task-017 verification round 4 — FAIL

Each verifier committed the file per the Protocol ("commit this file along with
your other changes"). The check prohibits this. The Protocol and the check are
contradictory; no verifier can satisfy both simultaneously.

Fix (orchestrator level): Strip `.hyperloop/worker-result.yaml` from the branch
commit history. This requires non-interactive history rewriting (e.g.,
`git filter-branch --index-filter 'git rm --cached --ignore-unmatch .hyperloop/worker-result.yaml' -- alpha..HEAD`)
and cannot be done with `git rebase -i` (interactive mode is disabled for agents).

### 7. Code Review — PASS

**Domain Probe Compliance:** Zero `logger.*` or `print()` calls in any modified
outbox or management files. Domain probes used throughout.

**Fake vs Mock:** `DataSource` and `Group` aggregates instantiated as real domain
objects via `_make_ds()` / `Group.create()` factory helpers in tests. No bare
`MagicMock(spec=DataSource)` for domain aggregates.

**DDD Layer Rules:** `UnknownEventTypeError` placed in
`shared_kernel/outbox/exceptions.py` (correct layer). `infrastructure/outbox/composite.py`
imports only from `shared_kernel`. No bounded-context leakage.

**Conventional Commits:** Implementation commit (`e24cb701`) carries both
`Spec-Ref` and `Task-Ref` trailers. Bodies explain the "why" clearly.

**No hardcoded secrets or env-specific values.**

---

## Spec Requirements Coverage

All 6 SHALL requirements and all 11 scenarios are fully covered.

### Transactional Event Storage — COVERED
- `OutboxRepository.append()` uses `session.add()` only; caller owns transaction
- Unit: `TestOutboxWorkerTransactionAtomicity` (2 tests)
- Integration: `test_outbox_entry_created_in_same_transaction_as_group`

### Event Processing — COVERED
- Normal processing → `_mark_processed()`; transient failure → `_increment_retry()`;
  permanent failure → `_move_to_dlq()`
- Unit: `TestOutboxWorkerRetryBehavior` (6 tests)
- Integration: `test_worker_processes_group_created_and_writes_to_spicedb`

### Idempotent Event Handlers — COVERED
- SpiceDB handler: TOUCH/upsert semantics; `fetch_unprocessed` filters `processed_at IS NULL`
- Unit: `TestOutboxWorkerIdempotency` (2 tests)
- Integration: `test_handler_invoked_twice_produces_same_spicedb_state`

### Concurrent Worker Safety — COVERED
- `fetch_unprocessed()` uses `.with_for_update(skip_locked=True)`
- Unit: `TestOutboxWorkerConcurrentSafety` — compiles query with PostgreSQL dialect
  and asserts `SKIP LOCKED` present

### Dual Delivery Mechanism — COVERED
- `PostgresNotifyEventSource` for sub-second delivery; `_poll_loop()` for 30s fallback
- Unit: 30+ tests in `test_postgres_notify_event_source.py`
- Integration: `test_worker_processes_via_notify_not_polling` (poll_interval=999s)

### Event Fan-Out — COVERED
- `CompositeEventHandler.handle()` fans out to all registered handlers
- `UnknownEventTypeError` in `shared_kernel/outbox/exceptions.py` triggers
  immediate DLQ bypass in `worker.py`
- Unit: `TestCompositeEventHandler`, `TestUnknownEventTypeError` (6 new tests)
  `test_unknown_event_type_immediately_moves_to_dlq`,
  `test_retry_not_called_for_unknown_event_type`

---

## Notes (Non-Blocking)

- **check-graceful-shutdown-cancel:** False positive. `worker.py` mentions `.cancel()`
  only in a docstring. Production code uses `_shutdown_event.set()` + natural `await`.

- **check-alpha-local-vs-remote.sh false positive:** This check was newly added to the
  suite via alpha commit `a71a4900`. The check design fires on local/remote alpha
  divergence unconditionally. Since local alpha is orchestrator-managed and advances
  independently, this check will fire on EVERY task branch and every verification
  round until origin/alpha is brought current. This is an orchestrator-level issue,
  not a task-017 regression.

---

## Required Actions (Orchestrator Level — Not Resolvable by Task Implementer)

1. **Resolve check-worker-result-not-committed.sh contradiction:**
   Either strip `.hyperloop/worker-result.yaml` from branch history via
   non-interactive filter-branch, OR update the verifier Protocol to write
   the verdict to a path that is not flagged by this check.

2. **Resolve check-alpha-local-vs-remote.sh false positive:**
   Either push local alpha to origin more frequently (keep divergence ≤5 commits),
   OR update the check to exit 0 when the task branch itself is current with local alpha.

Until both resolutions are applied, this check will fail in every subsequent
verification round, even though the task-017 implementation is complete and correct.