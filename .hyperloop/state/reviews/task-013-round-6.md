---
task_id: task-013
round: 6
role: verifier
verdict: fail
---
## Task-013 Verification — specs/ingestion/sync-lifecycle.spec.md

Review date: 2026-04-27
Branch: hyperloop/task-013
Reviewer: verifier agent (round 2)

---

## Check Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Unit tests (2530 total) | **PASS** | 2530 passed, 0 failed, 45 warnings |
| 2 | `ruff check` | **PASS** | Zero violations |
| 3 | `ruff format --check` | **PASS** | 531 files already formatted |
| 4 | `mypy` type checking | **PASS** | Zero errors across 531 source files |
| 5 | Architecture boundary tests | **PASS** | 40 passed |
| 6 | `check-no-direct-logger-usage` | **PASS** | No direct logger/print usage |
| 7 | `check-implementation-commits-exist` | **PASS** | 12 implementation commits |
| 8 | `check-empty-test-stubs` | **PASS** | No empty stubs |
| 9 | `check-domain-aggregate-mocks` | **PASS** | No bare MagicMock/AsyncMock on aggregates |
| 10 | `check-event-handlers-registered` | **PASS** | All 11 handlers registered in main.py |
| 11 | `check-domain-events-have-consumers` | **PASS** | All 33 domain events have consumers |
| 12 | `check-no-future-placeholder-comments` | **PASS** | No TODO placeholders |
| 13 | `check-no-coming-soon-stubs` | **PASS** | No stub markers |
| 14 | `check-weak-test-assertions` | **PASS** | No weak assertions |
| 15 | `check-no-test-regressions` | **PASS** | No deleted test files |
| 16 | `check-no-route-handler-removals` | **PASS** | No route handlers removed |
| 17 | `check-no-domain-exception-deletions` | **PASS** | No domain exceptions removed |
| 18 | Commit trailers (Spec-Ref, Task-Ref) | **PASS** | All 12 impl commits carry both trailers |
| 19 | `check-branch-rebased-on-alpha` | **PASS** | 4 commits behind — within acceptable range |
| 20 | `check-no-state-file-commits` | **PASS** | Zero .hyperloop/state/ files on branch |
| 21 | `check-no-source-regressions` | **FAIL** | See FAIL 1 below |
| 22 | `check-cascade-delete-cleanup` | **FAIL** | See FAIL 2 below |
| 23 | `check-worker-result-not-committed` | **FAIL** | See FAIL 3 below |
| 24 | Missing check scripts | **FAIL** | See FAIL 4 below |

---

## Blocking Failures

### FAIL 1 — Missing `Removes:` trailers (`check-no-source-regressions.sh`)

Two symbols removed without `Removes:` trailers in their commit messages:

- `[src/api/management/domain/events/data_source.py] -class DataSourceSyncRequested:`
- `[src/api/management/infrastructure/outbox/translator.py] -def _translate_data_source_sync_requested`

**Analysis:** Both removals ARE spec-mandated. The spec defines `SyncStarted` (not
`DataSourceSyncRequested`) as the entry event for the lifecycle state machine. Commit
`d3108eb1` ("feat(management/domain): replace DataSourceSyncRequested with SyncStarted event")
correctly replaces the event, and `e07c326d` updates the translator. The removals
are intentional and correctly implemented.

**However**, the `check-no-source-regressions.sh` script requires `Removes: <ClassName>`
trailers in the commit messages to signal spec-mandated removals to future verifiers.
These trailers are currently absent.

**Required fix:** Amend commits `d3108eb1` and `e07c326d` to add:
```
Removes: DataSourceSyncRequested
```
and
```
Removes: _translate_data_source_sync_requested
```
respectively. Force-push the cleaned branch after amending.

---

### FAIL 2 — Cascade delete credential cleanup (`check-cascade-delete-cleanup.sh`)

`src/api/management/application/services/knowledge_graph_service.py` deletes
DataSource records (line 416) without calling `secret_store.delete(...)` first
to remove the associated encrypted credentials from Vault.

```
[knowledge_graph_service.py] HEURISTIC 2 — DataSource cascade delete without secret cleanup
```

**Analysis:** This is a **pre-existing issue not introduced by task-013**. The task
branch's merge-base (`0e307113`) already lacked the credential cleanup. The task
itself makes zero changes to `knowledge_graph_service.py`.

Inspection of the alpha branch working tree reveals an **uncommitted fix** is pending:
the alpha working copy has the `secret_store.delete(...)` call added (lines 410–414),
but this change has not been committed to alpha yet.

**Required fix (two steps):**
1. The orchestrator/alpha maintainer must commit the pending `knowledge_graph_service.py`
   fix to alpha.
2. Once committed, rebase this task branch on the updated alpha:
   ```bash
   git rebase alpha
   bash .hyperloop/checks/check-cascade-delete-cleanup.sh   # must PASS
   ```

---

### FAIL 3 — `worker-result.yaml` in branch history (`check-worker-result-not-committed.sh`)

Commit `cc2c80d4` ("chore(hyperloop): record task-013 worker result as pass (recovery)")
modified `.hyperloop/worker-result.yaml` on the task branch. The check prohibits this
file from appearing in task branch commits.

**Analysis:** This file was committed by the previous (crashed) verifier's recovery
run as part of the branch rebuild. It violates the "worker-result must not be committed
to task branches" rule added in check `988aabf6`.

**Required fix:** After completing FAILs 1 and 2 above, rebuild the branch by
cherry-picking only the source delivery commits without carrying `worker-result.yaml`:

```bash
git checkout alpha
git checkout -b hyperloop/task-013-clean

# Cherry-pick 12 delivery commits (strip worker-result.yaml after each):
for SHA in d3108eb1 e07c326d aae70038 f0701edb 7609b0cc f87d57f2 \
           c17e2211 344f2e20 85a869d5 419e8c13 f1ef0e9d 5e6cc850; do
  git cherry-pick "$SHA"
  git restore --staged --worktree -- '.hyperloop/worker-result.yaml' 2>/dev/null || true
  git commit --amend --no-edit
done

bash .hyperloop/checks/check-worker-result-not-committed.sh  # must PASS
```

Note: When amending `d3108eb1` and `e07c326d`, also add the `Removes:` trailers
from FAIL 1.

---

### FAIL 4 — Missing check scripts referenced by `check-run-backend-suite.sh`

Three scripts listed in the suite do not exist:
- `check-new-checks-pass-on-head.sh`
- `check-no-foreign-task-commits.sh`
- `check-cascade-delete-empty-collection-mocks.sh`

**Analysis:** These are process/orchestrator infrastructure gaps, not implementer
failures. The scripts are referenced in the suite but have not been created. This
should be addressed by the orchestrator process, not the implementer.

---

## Implementation Quality (informational — all positive)

The actual code delivered for task-013 is well-executed and meets spec requirements:

- **TDD followed**: unit tests written first; all 12 spec scenarios covered by tests
- **Domain events**: `SyncStarted`, `JobPackageProduced`, `IngestionFailed`,
  `MutationLogProduced`, `ExtractionFailed`, `MutationsApplied`,
  `MutationApplicationFailed` — all present and wired correctly
- **State machine**: `SyncLifecycleHandler` correctly transitions through
  `ingesting → ai_extracting → applying → completed/failed`; terminal states are
  idempotent; missing sync run IDs handled gracefully (no-op)
- **Scheduler**: INTERVAL and CRON schedules both implemented with `croniter`
- **Staleness detection**: `is_node_stale()` pure domain function cleanly implemented
  in `graph/domain/value_objects.py`
- **No direct logger usage**: domain probes used throughout all new code
- **Architecture boundaries**: all 40 archon tests pass; new bounded contexts
  (Ingestion, Extraction) correctly layered
- **Ingestion pipeline**: extract → package → publish event flow correctly
  orchestrated; failure path emits `IngestionFailed`

The implementation would pass on a clean branch. Fix FAILs 1–3 and re-submit.

---

## Summary of Required Actions

| Priority | Action | Owner |
|---|---|---|
| 1 | Commit pending alpha fix for `knowledge_graph_service.py` credential cleanup | Orchestrator/alpha |
| 2 | Add `Removes:` trailers to commits `d3108eb1` and `e07c326d` | Implementer |
| 3 | Rebuild clean branch (cherry-pick without worker-result.yaml) | Implementer |
| 4 | Create missing check scripts | Orchestrator/process |