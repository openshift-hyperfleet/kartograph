---
task_id: task-013
round: 3
role: verifier
verdict: fail
---
## Task-013 Verification — specs/ingestion/sync-lifecycle.spec.md

Branch has been cleaned and rebased onto current alpha (13bb83a6, run 51).
All foreign-task commits and state-file commits are gone. Core checks (1–5) pass.
One real check script failure blocks the PASS verdict.

---

## Check Results

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Unit tests (2524) | **PASS** | All green |
| 2 | Ruff linting | **PASS** | Zero violations |
| 3 | Ruff formatting | **PASS** | 531 files already formatted |
| 4 | mypy type checking | **PASS** | No issues in 531 source files |
| 5 | Architecture boundary tests (40) | **PASS** | All green |
| — | check-branch-rebased-on-alpha.sh | **PASS** | 0 commits behind alpha |
| — | check-no-state-file-commits.sh | **PASS** | Zero state files on branch |
| — | check-no-direct-logger-usage.sh | **PASS** | Zero violations |
| — | check-domain-aggregate-mocks.sh | **PASS** | Zero violations |
| — | check-no-coming-soon-stubs.sh | **PASS** | Zero markers |
| — | check-empty-test-stubs.sh | **PASS** | Zero stubs |
| — | check-weak-test-assertions.sh | **PASS** | Zero violations |
| — | check-no-source-regressions.sh | **FAIL*** | False positive — see note |
| — | check-no-future-placeholder-comments.sh | **FAIL** | Real issue — see note |
| — | Commit trailers (Spec-Ref / Task-Ref) | **PASS** | Present on all 10 delivery commits |

---

## Failure Details

### FAIL 1 — check-no-future-placeholder-comments.sh (REAL — blocks PASS)

```
src/api/management/application/services/sync_scheduler.py:137:
    # TODO: Implement CRON schedule evaluation using a cron library
    # (e.g., python-croniter). CRON schedules require parsing the
    # expression and finding the most recent fire time relative to
    # last_sync_at. For now, CRON schedules are not evaluated.
    pass
```

**Why this fails:** The spec explicitly requires CRON support in the "Scheduled trigger"
scenario:

> GIVEN a data source with a **CRON** or INTERVAL schedule
> WHEN the schedule fires
> THEN a sync is initiated as if manually triggered

CRON is not optional. The implementation only handles INTERVAL schedules.
The TODO comment is not an acceptable substitute for either an implementation
or a formal blocker. No `.hyperloop/blockers/` file exists.

**Required fix (choose one):**

**Option A — Implement CRON evaluation:**
Add `croniter` (or `cronsim`) to `pyproject.toml`. Implement
`_is_cron_due(cron_expr, last_sync_at, now)` in `SyncSchedulerService`.
Remove the TODO comment. Add unit tests covering the CRON evaluation path.

**Option B — Formal blocker + clean code:**
1. Remove the TODO comment and the bare `pass` (CRON branch can simply be
   omitted until the blocker is resolved; `MANUAL` and `INTERVAL` are the only
   supported types).
2. Create `.hyperloop/blockers/task-013-blocker.md` documenting that CRON
   schedule evaluation is deferred pending library selection, and raise it with
   the orchestrator.

---

### FAIL* 2 — check-no-source-regressions.sh (FALSE POSITIVE — not blocking)

The check flags:
- `DataSourceSyncRequested` class removed from `management/domain/events/data_source.py`
- `request_sync()` method removed from `management/domain/aggregates/data_source.py`
- `_translate_data_source_sync_requested` removed from `management/infrastructure/outbox/translator.py`

These removals are **explicitly spec-mandated**. The spec requires `SyncStarted`
(not `DataSourceSyncRequested`) as the entry event. All 10 delivery commits carry
`Spec-Ref: specs/ingestion/sync-lifecycle.spec.md` trailers. The check script
cannot interpret spec context so it always flags this pattern. This is a known
false positive for this task and does not block the verdict.

---

## Spec Scenario Coverage

| Requirement | Scenario | Status |
|---|---|---|
| Sync Orchestration | Successful sync | COVERED |
| Sync Orchestration | Extraction failure | COVERED |
| Lifecycle State Machine | State transitions (all 7) | COVERED |
| Lifecycle State Machine | Terminal states | COVERED |
| Event-Driven Side Effects | Status updates | COVERED |
| Event-Driven Side Effects | Extraction trigger | COVERED |
| Event-Driven Side Effects | Mutation trigger | COVERED |
| Sync Initiation | Manual trigger | COVERED |
| Sync Initiation | Scheduled trigger — INTERVAL | COVERED |
| Sync Initiation | Scheduled trigger — CRON | **NOT COVERED** |
| Staleness-Based Node Lifecycle | Stale node detection | COVERED |
| Staleness-Based Node Lifecycle | Active node | COVERED |

---

## Implementation Quality (separate from the blocking failure)

The 10 task-013 delivery commits are otherwise correct:
- DOO probes used correctly; no bare `logger.*` or `print()` calls.
- No MagicMock/AsyncMock on domain aggregates; proper fakes used throughout.
- Architecture boundaries clean (40/40 pytest-archon tests green).
- DB migration correctly expands CHECK constraint to the full 6-state set.
- `SyncLifecycleHandler` implements all 7 state transitions with terminal-state
  idempotency and graceful no-op for missing sync runs.
- Ingestion bounded context is complete and well-tested.

---

## Branch State After This Review

Branch `hyperloop/task-013` is now rebased onto alpha HEAD (run 51).
All prior contamination (state files, foreign-task commits) has been removed.
The only remaining work is fixing the CRON placeholder per the options above.