---
task_id: task-017
round: 11
role: verifier
verdict: fail
---
# Task-017 Outbox Pattern — Verifier Result

Date: 2026-04-26
Branch: hyperloop/task-017

---

## Summary

The task-017 outbox implementation is **complete and correct**. All 6 SHALL
requirements and 11 scenarios are covered by passing tests. However, two
hard-gate check scripts are FAILING due to branch hygiene regressions — the
same classes of blockers identified in the prior round. Alpha has moved forward
by 27 commits since the previous verifier issued PASS, re-introducing both
failures.

---

## Check Results

### FAIL — check-branch-rebased-on-alpha
Branch is **27 commits behind local alpha** (merge-base at `48a74d7d`).
The 27 lagging commits are all orchestrator housekeeping
(`chore(process)`, `chore(intake)`), but the check is a hard gate.

```
Resolution: git rebase alpha
```

Note: The branch is 0 commits behind `origin/alpha` — the local `alpha`
branch has moved ahead of the remote. This is a local-alpha-vs-remote-alpha
divergence that the check script detects.

### FAIL — check-no-state-file-commits
**23 `.hyperloop/state/` files** are committed on this branch relative to
local alpha's merge base. Offending files include:

- `.hyperloop/state/intake/2026-04-25-eighth-run.md`
- `.hyperloop/state/intake/2026-04-25-ninth-run.md`
- `.hyperloop/state/tasks/task-038.md`
- `.hyperloop/state/reviews/task-{001,007,008,010,014,017,018,020}-round-*.md`
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019}.md`

These were added by intake/process workers operating on this branch
(commits `a53a00b8`, `49aeb182`, `55062388`, and earlier orchestrator commits).
The previous verifier's PASS verdict appears to have been premature, or alpha
moved forward and re-introduced state-file divergence after the fix.

### PASS — Unit Tests
`uv run pytest tests/unit -q`: **2497 passed, 47 warnings, 0 failures**

### PASS — Linting
`uv run ruff check .`: All checks passed.

### PASS — Formatting
`uv run ruff format --check .`: 486 files already formatted.

### PASS — Type Checking
`uv run mypy . --config-file pyproject.toml --ignore-missing-imports`:
Success — no issues found in 486 source files.

### PASS — Architecture Boundary Tests
`uv run pytest tests/unit/test_architecture.py -v`: 40 passed.
All outbox boundary tests pass (does not import IAM/Graph/Query/Management
internals; shared_kernel import allowed).

### PASS — check-branch-has-commits
53 commits ahead of alpha.

### PASS — check-cross-task-deferral
No cross-task deferral comments found.

### PASS — check-domain-aggregate-mocks
No bare MagicMock/AsyncMock on domain aggregate variables.

### PASS — check-fake-success-notifications
All success notifications co-located with real API calls.

### PASS — check-no-coming-soon-stubs / check-no-future-placeholder-comments
No stub markers or placeholder comments.

### PASS — check-no-source-regressions / check-no-test-regressions
No test file deletions or truncations.

### PASS — check-process-overlays-intact
Process overlay infrastructure intact.

### PASS — check-weak-test-assertions
No weak categorical assertions.

### PASS — Commit Trailers
Implementation commit `03132862` has both required trailers:
- `Spec-Ref: specs/shared-kernel/outbox.spec.md@86d0f4fc5118312577593defb88be1d5005b72cf`
- `Task-Ref: task-017`

---

## Pre-existing Failures (NOT regressions from task-017)

### check-graceful-shutdown-cancel — False positive
`worker.py` line 130 contains `.cancel()` only inside a docstring comment.
Production `stop()` uses `_running = False` + `_shutdown_event.set()` +
natural `await task` — no `task.cancel()` in executable code.
Confirmed via: `grep -n ".cancel()" src/api/infrastructure/outbox/worker.py`

### check-empty-test-stubs — Pre-existing on alpha
`tests/integration/test_api_key_auth.py:691` stub exists on alpha.
`git diff origin/alpha...HEAD` confirms this file was NOT modified by task-017.

### check-no-direct-logger-usage — Pre-existing, different bounded context
`query/presentation/mcp.py:197` uses `print()`. Not modified by task-017.
All outbox code (infrastructure/outbox, shared_kernel/outbox) uses domain
probes exclusively — no direct logger.* or print() calls in task-017 files.

### check-auth-status-codes — Pre-existing, different files
Flagged files (`test_group_authorization.py`, `test_workspace_authorization.py`,
`test_api_key_auth.py`) were NOT modified by task-017.

### check-no-check-script-deletions — Pre-existing
Missing `--exclude-dir=.venv` in 5 scripts. This pre-dates task-017;
same failure exists on alpha.

---

## Implementation Quality Assessment

All 6 outbox spec requirements are correctly implemented:

- **Transactional Event Storage**: `OutboxRepository.append()` calls `session.add()`
  only; caller owns the transaction boundary. Verified via unit test
  `test_repository_append_does_not_commit`.
- **Event Processing**: Normal processing marks `processed_at`; transient failure
  increments `retry_count` and records `last_error`; permanent failure sets `failed_at`.
- **Idempotent Event Handlers**: SpiceDB handler uses TOUCH semantics (upsert).
  `fetch_unprocessed` filters `processed_at IS NULL AND failed_at IS NULL`.
- **Concurrent Worker Safety**: `fetch_unprocessed()` uses `FOR UPDATE SKIP LOCKED`.
  Confirmed by checking compiled SQL in unit test.
- **Dual Delivery Mechanism**: `PostgresNotifyEventSource` for real-time (sub-second);
  `_poll_loop()` provides polling fallback (default 30s interval).
- **Event Fan-Out**: `CompositeEventHandler` dispatches to all registered handlers.
  `UnknownEventTypeError` immediately DLQs without incrementing retry count.

---

## Required Actions Before Re-Review

1. Rebase on local alpha: `git rebase alpha` — resolves `check-branch-rebased-on-alpha`
2. Strip `.hyperloop/state/` modifications from commit history:
   ```
   git rebase -i alpha
   # On any offending commit: git reset HEAD -- .hyperloop/state/
   # Then: git commit --amend --no-edit
   ```
   Or after rebase, if state files appear in working tree, verify they are
   not staged and are covered by `.gitignore`.
3. Re-run `check-branch-rebased-on-alpha.sh` → must exit 0
4. Re-run `check-no-state-file-commits.sh` → must exit 0
5. Re-submit for verification