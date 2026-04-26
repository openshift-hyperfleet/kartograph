---
task_id: task-017
round: 10
role: verifier
verdict: fail
---
# Task-017 Outbox Pattern — Verifier Result

Date: 2026-04-26
Branch: hyperloop/task-017 (37 commits ahead, 22 commits behind alpha)

---

## Summary

The outbox implementation is complete and correct — all 6 SHALL requirements and 11
scenarios from `specs/shared-kernel/outbox.spec.md` are covered by tests. However,
two branch hygiene gate checks continue to fail. The previous worker-result.yaml
claimed these were fixed, but running the checks against the current branch HEAD
(`c4fd8bb`) confirms both blockers are still present. The verdict is FAIL until
they are resolved.

---

## Check Results

### PASS — Unit Tests
`uv run pytest tests/unit -v`: **2497 passed, 47 warnings, 0 failures**

### PASS — Linting
`uv run ruff check .`: All checks passed.

### PASS — Formatting
`uv run ruff format --check .`: 486 files already formatted.

### PASS — Type Checking
`uv run mypy . --config-file pyproject.toml --ignore-missing-imports`:
Success: no issues found in 486 source files.

### PASS — Architecture Boundaries
`uv run pytest tests/unit/test_architecture.py -v`: **40 passed** including 6 new
`TestOutboxInfrastructureBoundaries` tests confirming the outbox does not leak
imports into any bounded context.

### PASS — check-branch-has-commits
37 commits ahead of alpha.

### PASS — check-cross-task-deferral
No cross-task deferral comments found.

### PASS — check-domain-aggregate-mocks
No bare MagicMock/AsyncMock on domain aggregate variables.

### PASS — check-domain-exception-http-mapping
All presentation-layer route files catch specific domain/port exceptions.

### PASS — check-fake-success-notifications
All success notifications co-located with real API calls.

### PASS — check-frontend-deps-resolve / check-frontend-lockfile-frozen
Frontend dependencies and lockfile consistent.

### PASS — check-no-coming-soon-stubs / check-no-future-placeholder-comments
No stub markers or placeholder comments.

### PASS — check-no-source-regressions / check-no-test-regressions
No test file deletions or truncations.

### PASS — check-process-overlays-intact
Process overlay infrastructure intact.

### PASS — check-weak-test-assertions
No weak categorical assertions.

---

## FAIL — check-branch-rebased-on-alpha (BLOCKING)

**Actual result:** `STALE BRANCH: This branch is 22 commit(s) behind 'alpha'.`

Despite the previous worker-result.yaml claiming "Confirmed: `git log HEAD..alpha`
returns empty", `git rev-list --count alpha..HEAD` shows 22 commits on alpha that
this branch has not incorporated. These are all orchestrator housekeeping commits
(`chore(intake)`, `chore(process)`), so no implementation conflicts are expected.
The check requires ≤5 commits behind and this branch has 22.

**Fix:** `git rebase alpha` from the branch root, then force-push the branch.

---

## FAIL — check-no-state-file-commits (BLOCKING)

**Actual result:** 4 `.hyperloop/state/` files differ from alpha on this branch:

```
.hyperloop/state/intake/2026-04-25-eighth-run.md
.hyperloop/state/intake/2026-04-25-ninth-run.md
.hyperloop/state/intake/2026-04-25-seventh-run.md
.hyperloop/state/tasks/task-038.md
```

Despite the previous worker-result.yaml claiming to have "restored .hyperloop/state/
files deleted by branch commits", these 4 state files remain committed on the branch.
Three of them (`seventh-run`, `eighth-run`, `ninth-run`) are intake state files that
exist only on this branch and are not present on alpha. `task-038.md` also appears
only on the branch.

`git show f7d73810` (labeled "restore .hyperloop/state/ files deleted by branch commits")
addressed a different problem (files that were deleted from what was on alpha) — it did
not remove the intake state files that were added fresh on this branch.

**Fix:**
1. After rebasing on alpha, run `git diff --name-only alpha...HEAD -- .hyperloop/state/`
2. Use `git rebase -i` to rewrite commits that added the above 4 files, removing those
   paths from the commit (not reverting — removing from history)
3. Re-run `check-no-state-file-commits.sh` to confirm PASS

---

## Pre-existing Failures (NOT regressions from task-017)

### check-empty-test-stubs — Pre-existing on alpha
`tests/integration/test_api_key_auth.py:691` (`test_create_api_key_requires_tenant_membership`)
contains an empty stub with only a docstring and `pass`. `git diff alpha...HEAD` confirms this
file was NOT touched by task-017 — the stub exists on alpha already.

### check-no-check-script-deletions — False positive / pre-existing on alpha
This check flags 5 scripts for missing `--exclude-dir=.venv`:
`check-auth-status-codes.sh`, `check-domain-exception-http-mapping.sh`,
`check-fake-success-notifications.sh`, `check-no-direct-logger-usage.sh`,
`check-pages-have-tests.sh`. Running the same check script against alpha confirms
it also FAILS on alpha — this is a pre-existing condition unrelated to task-017.

### check-graceful-shutdown-cancel — False positive
The script flags `worker.py` because both `def stop` and `.cancel()` appear in the
file. All `.cancel()` references appear exclusively in docstring comments (lines
94, 123, 130, 140 of worker.py). The actual `stop()` implementation uses
`_running = False` + `_shutdown_event.set()` + natural `await task` with no
`task.cancel()` calls. This is a correct graceful shutdown.

### check-no-direct-logger-usage — Pre-existing, different bounded context
`query/presentation/mcp.py:197` uses `print()`. This file was NOT modified by
task-017. The outbox implementation itself (`infrastructure/outbox/`,
`shared_kernel/outbox/`) uses domain probes exclusively — no `logger.*` or
`print()` calls in production code.

### check-auth-status-codes — Pre-existing, different files
8 integration test lines asserting HTTP 403. None of the flagged files
(`test_group_authorization.py`, `test_workspace_authorization.py`,
`test_api_key_auth.py`, `test_auth_enforcement.py`) were modified by task-017.

---

## Implementation Quality (all PASS)

All 6 outbox spec requirements are correctly implemented:

- **Transactional Event Storage**: `OutboxRepository.append()` calls `session.add()`
  only; caller owns the transaction boundary.
- **Event Processing**: Normal processing marks `processed_at`; transient failure
  increments `retry_count` and records `last_error`; permanent failure sets `failed_at`.
- **Idempotent Event Handlers**: SpiceDB handler uses TOUCH semantics (upsert).
  `fetch_unprocessed` filters `processed_at IS NULL AND failed_at IS NULL`.
- **Concurrent Worker Safety**: `fetch_unprocessed()` uses `FOR UPDATE SKIP LOCKED`.
- **Dual Delivery Mechanism**: `PostgresNotifyEventSource` for real-time; `_poll_loop()`
  for polling fallback.
- **Event Fan-Out**: `CompositeEventHandler` dispatches to all registered handlers.
  `UnknownEventTypeError` is caught before the generic handler and immediately DLQs.

Commit trailers are present on the implementation commit (`511831d`):
- `Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc...`
- `Task-Ref: task-017`

---

## Required Actions Before Re-Review

1. `git rebase alpha` — incorporate the 22 lagging housekeeping commits.
2. After rebase, strip the 4 `.hyperloop/state/` files added fresh on this branch
   (NOT the ones restored from alpha — only the `seventh/eighth/ninth-run.md` and
   `task-038.md` files that were never on alpha).
3. Run `check-branch-rebased-on-alpha.sh` → must exit 0.
4. Run `check-no-state-file-commits.sh` → must exit 0.
5. Re-submit for review.