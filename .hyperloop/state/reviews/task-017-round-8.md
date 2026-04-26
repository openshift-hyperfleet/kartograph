---
task_id: task-017
round: 8
role: verifier
verdict: fail
---
## Task-017: Outbox Pattern — Verification Review

Branch: `hyperloop/task-017`
Date: 2026-04-25
Worker: verifier (recovery run)

---

## Summary

The task-017 implementation itself is correct and complete — all quality checks
pass and all 11 spec scenarios are covered. However, two pre-existing branch
hygiene failures prevent a PASS verdict and must be resolved before the branch
can be merged.

---

## Check Results

| Check | Result | Detail |
|---|---|---|
| Unit tests (2462) | **PASS** | 81 outbox-specific, 2462 total |
| Ruff check | **PASS** | Zero violations |
| Ruff format | **PASS** | 484 files formatted |
| Mypy | **PASS** | Zero errors across 484 source files |
| Architecture boundary tests (40) | **PASS** | All DDD layer rules enforced |
| check-branch-rebased-on-alpha | **FAIL** | Branch is 11 commits behind alpha |
| check-no-state-file-commits | **FAIL** | `.hyperloop/state/` files touched in commit `5f9beb47` |
| check-empty-test-stubs | NOTE | Pre-existing on alpha; not introduced by this branch |
| check-graceful-shutdown-cancel | NOTE | False positive — `.cancel()` appears only in a docstring, not in code |
| check-domain-aggregate-mocks | **PASS** | No violations |
| check-no-test-regressions | **PASS** | No test files deleted or truncated |
| check-no-source-regressions | **PASS** | No unspecified source regressions |
| check-no-coming-soon-stubs | **PASS** | No stub markers |
| check-no-future-placeholder-comments | **PASS** | No placeholder comments |
| check-weak-test-assertions | **PASS** | No weak categorical assertions |

---

## Failure Details

### FAIL 1: Branch Not Rebased on Alpha
`check-branch-rebased-on-alpha.sh` reports 11 commits behind alpha. All 11 are
orchestrator housekeeping commits (`chore(intake)`, `chore(process)`), none
implementation changes. However, the stale state is a merge blocker.

**Fix:** `git rebase alpha` — these are housekeeping-only commits so rebase
should be clean (no implementation conflicts expected).

### FAIL 2: State Files Committed on Branch
`check-no-state-file-commits.sh` reports that commit `5f9beb47`
(`feat(management): implement Management REST API for Knowledge Graphs (#471)`)
deleted 20 `.hyperloop/state/` files. This commit was already present in the
branch before the task-017 work was added; task-017 itself did not introduce
these changes. However, the violation is recorded against this branch's commit
history and blocks merging.

Affected files include:
- `.hyperloop/state/reviews/task-{001,007,007,008,010,014,014,017,018,020}-round-*.md`
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019}.md`

**Fix:** After rebasing on alpha, verify whether the state file deletions
survive the rebase. If they do, rewrite the commit history to drop the state
file changes (interactive rebase or `git commit --fixup` + autosquash). The
task-008 implementation changes (management REST API) must be preserved; only
the `.hyperloop/state/` deletions must be excised.

---

## Notes (Non-Blocking)

### check-empty-test-stubs (pre-existing)
`tests/integration/test_api_key_auth.py:691` has an empty stub
(`test_create_api_key_requires_tenant_membership`). `git diff alpha...HEAD`
confirms this file was NOT modified by this branch — the stub exists on alpha
already. Not a task-017 regression.

### check-graceful-shutdown-cancel (false positive)
The script flags `worker.py` because the file contains both `def stop` and
`.cancel()`. The `.cancel()` string appears only in a docstring comment (line 130:
`"4. Await all tasks naturally — no task.cancel(), so an in-progress"`).
The actual `stop()` implementation correctly uses `_running = False` +
`_shutdown_event.set()` + natural `await task` without any `task.cancel()` call.
The graceful shutdown implementation is correct.

---

## Task-017 Implementation Assessment

The outbox implementation is complete and correctly addresses all 11 spec scenarios:

- **Transactional Event Storage**: `OutboxRepository.append()` never calls
  `session.commit()` — the calling service owns the transaction boundary.
- **Event Processing (normal)**: Worker fetches entries, dispatches to handler,
  marks processed with timestamp.
- **Transient failure**: Retry count incremented, last error recorded.
- **Permanent failure (DLQ)**: `failed_at` set after `max_retries` exceeded.
- **Idempotent handlers**: SpiceDB uses TOUCH semantics (write) and filter-based
  delete, making double-processing safe.
- **Concurrent worker safety**: `FOR UPDATE SKIP LOCKED` prevents duplicate processing.
- **Dual delivery**: `PostgresNotifyEventSource` for real-time + `_poll_loop` fallback.
- **Event fan-out**: `CompositeEventHandler.register()` supports multiple handlers
  per event type.
- **Unknown event type**: `UnknownEventTypeError` immediately DLQs without retry —
  correctly caught before the generic `Exception` handler.

Code quality is excellent: no direct logger/print calls in business logic (DOO
probes used throughout), no MagicMock on domain aggregates, no hardcoded secrets,
conventional commits with Spec-Ref and Task-Ref trailers.

---

## Required Actions Before Re-Review

1. `git rebase alpha` to incorporate the 11 orchestrator housekeeping commits
2. After rebase, verify that `.hyperloop/state/` deletions from commit `5f9beb47`
   are gone. If they persist, strip them from that commit via interactive rebase
   (keep the management REST API code changes, remove the state file deletions).
3. Re-run `check-branch-rebased-on-alpha.sh` and `check-no-state-file-commits.sh`
   to confirm clean.