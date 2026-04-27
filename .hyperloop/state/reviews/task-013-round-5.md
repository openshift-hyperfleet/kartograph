---
task_id: task-013
round: 5
role: verifier
verdict: fail
---
## Task-013 Verification — specs/ingestion/sync-lifecycle.spec.md

Review date: 2026-04-27
Branch: hyperloop/task-013
Reviewer: verifier agent

---

## Check Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Unit tests (2629 total) | **PASS** | 2629 passed, 0 failed, 47 warnings |
| 2 | `ruff check` | **PASS** | Zero violations |
| 3 | `ruff format --check` | **PASS** | 536 files already formatted |
| 4 | `mypy` type checking | **PASS** | Zero errors across 536 source files |
| 5 | Architecture boundary tests | **PASS** | 40 passed |
| 6 | `check-no-direct-logger-usage` | **PASS** | No direct logger/print usage |
| 7 | `check-implementation-commits-exist` | **PASS** | 13 implementation commits |
| 8 | `check-empty-test-stubs` | **PASS** | No empty stubs |
| 9 | `check-domain-aggregate-mocks` | **PASS** | No bare MagicMock/AsyncMock on aggregates |
| 10 | `check-event-handlers-registered` | **PASS** | All 11 handlers registered in main.py |
| 11 | `check-domain-events-have-consumers` | **PASS** | All 33 domain events have consumers |
| 12 | `check-no-future-placeholder-comments` | **PASS** | No TODO placeholders |
| 13 | `check-no-coming-soon-stubs` | **PASS** | No stub markers |
| 14 | `check-weak-test-assertions` | **PASS** | No weak assertions |
| 15 | Commit trailers (Spec-Ref, Task-Ref) | **PASS** | All 12 task-013 impl commits carry correct trailers |
| 16 | `check-branch-rebased-on-alpha` | **FAIL** | Branch is 52 commits behind local alpha |
| 17 | `check-no-state-file-commits` | **FAIL** | 32 `.hyperloop/state/` files committed to branch |
| 18 | `check-run-backend-suite` | **FAIL** | Halted — branch is stale (depends on #16) |
| 19 | `check-no-source-regressions` | **FAIL** | See analysis below |

---

## Blocking Failures

### FAIL 1 — Branch 52 commits behind alpha (`check-branch-rebased-on-alpha.sh`)

The local `alpha` branch is at `cf22c380` (64 intake/process commits ahead of
`origin/alpha`). This branch diverged from `alpha` at merge-base `8f377074`,
which is now 52 commits behind. The branch cannot be merged cleanly.

**Required fix:** Rebase the delivery commits (see below) onto a fresh checkout
of current local alpha.

### FAIL 2 — `.hyperloop/state/` files committed to branch (`check-no-state-file-commits.sh`)

32 files under `.hyperloop/state/intake/` were added by commits on this branch.
These are orchestrator-managed and MUST NOT be in any task branch. Their presence
causes permanent merge conflicts.

**Required fix (cherry-pick approach — recommended for 12 delivery commits):**

```bash
# Step 1 — identify clean delivery SHAs (no .hyperloop/state/ changes):
git log --oneline $(git merge-base HEAD alpha)..HEAD -- ':!.hyperloop/state'
# Delivery SHAs (task-013 work, in chronological order):
#   82a54e2c  feat(management/domain): replace DataSourceSyncRequested with SyncStarted
#   dd9d65f7  feat(management/infra): add SyncLifecycleHandler
#   e79c5093  feat(ingestion): scaffold ingestion bounded context
#   11ae9db2  test: add unit tests for sync lifecycle and ingestion context
#   4b4d5997  feat(extraction,graph): add lifecycle event stubs and migration
#   b80ffbed  feat(graph): add staleness-based node lifecycle detection
#   dc213a3b  feat(graph): add GraphMutationEventHandler
#   80bef3ed  feat(extraction): add ExtractionEventHandler
#   c84050c7  feat(management): add SyncSchedulerService
#   ab015e14  feat(main): wire all handlers and scheduler
#   dcac5876  test(management): add CRON schedule evaluation unit tests
#   10893d42  feat(management): implement CRON schedule evaluation using croniter
#   (plus any chore/verify commits you want to carry forward)

# Step 2 — create a clean branch from current alpha:
git checkout alpha
git checkout -b hyperloop/task-013-clean

# Step 3 — cherry-pick delivery commits:
git cherry-pick 82a54e2c dd9d65f7 e79c5093 11ae9db2 4b4d5997 \
    b80ffbed dc213a3b 80bef3ed c84050c7 ab015e14 dcac5876 10893d42

# Step 4 — verify clean:
bash .hyperloop/checks/check-no-state-file-commits.sh
bash .hyperloop/checks/check-branch-rebased-on-alpha.sh
```

Note: The `0bb08b56` commit (task-032 IAM work) is already on `origin/alpha`
and should NOT be cherry-picked — it will arrive via alpha during the rebase.

### FAIL 3 — Source regressions flagged (`check-no-source-regressions.sh`)

The check flagged several removals. Analysis:

| Removed item | Verdict |
|---|---|
| `DataSourceSyncRequested` class | **Spec-mandated** — replaced by `SyncStarted` per spec requirement |
| `_translate_data_source_sync_requested` | **Spec-mandated** — follows event class rename |
| `request_sync(self, *, requested_by=None)` old signature | **Spec-mandated** — new signature adds required `sync_run_id` |
| `KnowledgeGraphListResponse` | **False positive** — class still exists at line 106 (moved in file) |
| `list_knowledge_graphs`, `get_knowledge_graph`, `create_knowledge_graph` | **False positive** — all three still exist (lines 191, 144, 93 in routes.py) |

The `check-no-source-regressions.sh` script produces false positives when
methods are refactored/reordered without the removal being semantically a
deletion. The true spec-mandated removals (DataSourceSyncRequested rename chain)
are covered by the spec's "SyncStarted" requirement.

**Action required before re-verify:** After rebuilding the branch (FAIL 1+2 fix),
confirm the rebuilt branch also passes this check — if `check-no-source-regressions.sh`
still FAILs post-rebuild, document each spec-mandated removal with an inline comment
or add a `Removes:` trailer to the relevant commit so the script can be updated.

---

## Implementation Quality (informational)

The actual code delivered for task-013 is well-executed:

- **TDD followed**: tests written first (all 12 spec scenarios covered)
- **Domain events**: `SyncStarted`, `JobPackageProduced`, `IngestionFailed`,
  `MutationLogProduced`, `ExtractionFailed`, `MutationsApplied`,
  `MutationApplicationFailed` — all present and wired
- **State machine**: `SyncLifecycleHandler` correctly transitions through
  `ingesting → ai_extracting → applying → completed/failed`
- **Scheduler**: INTERVAL and CRON schedules both implemented with `croniter`
- **Staleness detection**: `is_node_stale()` domain function cleanly implemented
- **No direct logger usage**: domain probes used throughout
- **Architecture boundaries**: all 40 archon tests pass

The implementation would pass on a clean branch. Fix the branch hygiene
(FAILs 1 and 2) then re-submit for verification.