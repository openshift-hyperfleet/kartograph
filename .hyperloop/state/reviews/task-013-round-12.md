---
task_id: task-013
round: 12
role: verifier
verdict: fail
---
## Worker Verdict — task-013 (specs/ingestion/sync-lifecycle.spec.md)

Verifier: round-8 re-verification
Date: 2026-04-28

---

### Summary

Three checks are failing, all sharing a single root cause: the branch picked up 6
`process-improvement` commits in a prior rebase from a stale local `alpha`. Those
commits are now in local `alpha`, but their presence on this branch triggers both
the foreign-commit check and the staleness check. One of them (`5c0a0f1b8`) also
deleted `src/api/shared_kernel/outbox/exceptions.py` without a `Removes:` trailer,
causing the source-regression check to FAIL.

**All three failures are resolved by a single `git rebase alpha` (local ref).**

---

### Check Results

| # | Check | Result | Details |
|---|---|---|---|
| 1 | `uv run pytest tests/unit` | **PASS** | 2578 passed, 0 failed |
| 2 | `uv run ruff check .` | **PASS** | All checks passed |
| 3 | `uv run ruff format --check .` | **PASS** | 533 files already formatted |
| 4 | `uv run mypy . --ignore-missing-imports` | **PASS** | No issues found in 533 source files |
| 5 | `pytest tests/unit/test_architecture.py` | **PASS** | 40 passed |
| 6 | `check-worker-result-not-committed.sh` | **PASS** | Fixed from previous round |
| 7 | `check-no-foreign-task-commits.sh` | **FAIL** | See below |
| 8 | `check-branch-rebased-on-alpha.sh` | **FAIL** | See below |
| 9 | `check-no-source-regressions.sh` | **FAIL** | See below |
| 10 | `check-run-backend-suite.sh` | **FAIL** | Suite halted due to stale branch (#8) |
| 11 | All other checks (logger, domain events, event handlers, state files, etc.) | **PASS** | Passed |

---

### Failing Check 1: Foreign Task Commits

**Script:** `check-no-foreign-task-commits.sh`

Six commits on this branch carry `Task-Ref: process-improvement` instead of
`Task-Ref: task-013`:

```
FOREIGN: cfd0ff6435  Task-Ref=process-improvement
         chore(process): prohibit cherry-pick as a mechanism for picking up upstream commits
FOREIGN: cedf0fbab2  Task-Ref=process-improvement
         chore(process): add process-improvement agent overlay to prevent task-branch contamination
FOREIGN: 5c0a0f1b8d  Task-Ref=process-improvement
         chore(process): honor Removes: trailer and tighten pre-commit restore gate
FOREIGN: 0cd9f95464  Task-Ref=process-improvement
         chore(process): recreate check-alpha-local-vs-remote and teach MISSING-check remediation
FOREIGN: 35f470e433  Task-Ref=process-improvement
         chore(process): guard against overlay content regressions and worker-result deletion commits
FOREIGN: f770274eef  Task-Ref=process-improvement
         chore(process): enforce branch hygiene and close test-regression baseline gap
```

All 6 are now present in local `alpha`. A `git rebase alpha` will detect them as
empty patches and drop them automatically.

---

### Failing Check 2: Branch Stale vs Local Alpha

**Script:** `check-branch-rebased-on-alpha.sh`

The branch is 8 commits behind local `alpha` (merge-base `605405ecf`). Local `alpha`
has progressed to `42b8f9c60` with 8 additional commits. The check requires ≤5
commits of drift.

**Resolution:** `git rebase alpha`

---

### Failing Check 3: Source Regression — `exceptions.py` Deleted Without Trailer

**Script:** `check-no-source-regressions.sh`

`src/api/shared_kernel/outbox/exceptions.py` exists at the merge-base (`605405ecf`)
but is deleted by commit `5c0a0f1b8` (one of the foreign process-improvement commits)
with no `Removes:` trailer. There are no references to `UnknownEventTypeError`
anywhere in the codebase, so the deletion is functionally inert, but the check
correctly flags it as an undocumented removal.

After `git rebase alpha`, the new merge-base will be local `alpha`'s tip
(`42b8f9c60`), where `exceptions.py` is also absent. The diff will no longer show
the file as deleted on this branch, so the regression check will pass without any
additional action.

---

### Requirement Coverage (Implementation Correct — PASS)

The implementation itself is sound; all spec requirements are covered:

| Requirement | Status |
|---|---|
| Sync Orchestration | **COVERED** — `IngestionService.run()`, `IngestionEventHandler` |
| Lifecycle State Machine | **COVERED** — `SyncLifecycleHandler`, all 7 state transitions, terminal state guard |
| Event-Driven Side Effects | **COVERED** — `ExtractionEventHandler`, `GraphMutationEventHandler` |
| Sync Initiation | **COVERED** — manual trigger via API, scheduled via `SyncSchedulerService` |
| Staleness-Based Node Lifecycle | **COVERED** — `is_node_stale()` pure domain function |

---

### Action Required

**Single fix resolves all three failures:**

```bash
git rebase alpha
# Git will drop the 6 process-improvement commits as empty patches
# (they are already in local alpha)

# Verify all three previously-failing checks now pass:
bash .hyperloop/checks/check-no-foreign-task-commits.sh
bash .hyperloop/checks/check-branch-rebased-on-alpha.sh
bash .hyperloop/checks/check-no-source-regressions.sh

# Run full suite:
bash .hyperloop/checks/check-run-backend-suite.sh
```

Do NOT use `git rebase origin/alpha` — the check-alpha-local-vs-remote check
explicitly requires rebasing on local `alpha`, not the remote ref.