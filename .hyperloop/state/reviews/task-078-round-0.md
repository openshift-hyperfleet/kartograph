---
task_id: task-078
round: 0
role: verifier
verdict: fail
---
## Summary

Task-078 adds `GET /management/data-sources` (flat list endpoint with `latest_sync_run` embedded), frontend sync-log viewer tests, and the `get_latest_for_data_source` method on `IDataSourceSyncRunRepository`. The implementation is correct and well-structured, but one newly introduced type-checking failure blocks acceptance.

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| Unit Tests (backend, 2705) | PASS | All pass |
| Ruff linting | PASS | Zero violations |
| Ruff formatting | PASS | All files formatted |
| Mypy type checking | **FAIL** | 7 errors (see below) |
| Architecture boundary tests | PASS | 40 tests pass |
| Frontend tests (1278) | PASS | All pass |
| check-no-direct-logger-usage | PASS | |
| check-all-commits-have-task-ref | PASS | Task-Ref and Spec-Ref present |
| check-no-repo-port-mocks | FAIL (pre-existing) | Also fails on alpha; not introduced by this PR |
| check-cascade-delete-rollback-test | FAIL (pre-existing) | Also fails on alpha; not introduced by this PR |

---

## Failing Check: Mypy Type Errors (NEWLY INTRODUCED)

**File:** `tests/unit/management/application/test_sync_scheduler.py`

**Root cause:** The implementation correctly adds `get_latest_for_data_source` to `IDataSourceSyncRunRepository` in `management/ports/repositories.py`. However, the `_FakeSyncRunRepository` class used in `test_sync_scheduler.py` was **not updated** to implement this new protocol method. Mypy reports 7 `[arg-type]` errors because `_FakeSyncRunRepository` no longer satisfies the `IDataSourceSyncRunRepository` protocol.

**Error sample:**
```
tests/unit/management/application/test_sync_scheduler.py:134: error: Argument
"sync_run_repository" to "SyncSchedulerService" has incompatible type
"_FakeSyncRunRepository"; expected "IDataSourceSyncRunRepository"  [arg-type]
  note: "_FakeSyncRunRepository" is missing following "IDataSourceSyncRunRepository"
  protocol member: get_latest_for_data_source
```

**Fix:** Add `get_latest_for_data_source` to `_FakeSyncRunRepository` in `tests/unit/management/application/test_sync_scheduler.py`:

```python
async def get_latest_for_data_source(
    self, data_source_id: str
) -> DataSourceSyncRun | None:
    runs = [r for r in self._runs if r.data_source_id == data_source_id]
    return max(runs, key=lambda r: r.created_at) if runs else None
```

Or, if `_FakeSyncRunRepository` stores runs in a dict/list that doesn't have easy lookup by data_source_id, a `return None` stub is sufficient to make mypy happy and the scheduler tests don't exercise this method.

---

## Code Review Notes (non-blocking)

1. **Presentation layer imports Application layer type** (`models.py` line 153 imports `DataSourceWithLatestRun` from `data_source_service.py`). This is a minor DDD layer concern — the dataclass lives in the application layer and is imported by the presentation layer. Acceptable for now, but ideally `DataSourceWithLatestRun` would live in a shared DTO module or the presentation layer would re-map from domain objects directly without depending on an application-layer dataclass.

2. **Broad exception handler in route** (`routes.py` lines 283–287): The `except Exception` in `list_all_data_sources` swallows all errors. Consider logging (via probe) before re-raising, or at minimum distinguishing authorization errors from infrastructure errors. As written, authorization failures and database errors both return 500.

3. **N+1 query pattern in `list_all_for_user`**: The method iterates KGs, then per-KG fetches data sources, then per-DS fetches the latest run. For large tenants this is O(KG × DS) queries. This is noted in the commit message as acceptable for the sidebar use case, which is reasonable given current scale. Worth a future optimization with a single JOIN query.

4. **The frontend `sync-logs.test.ts` tests are pure logic tests** (no component instantiation), which is correct for a state machine. The test file is well-structured and covers edge cases thoroughly.

---

## Required Fix Before Re-submission

1. Update `_FakeSyncRunRepository` in `tests/unit/management/application/test_sync_scheduler.py` to implement `get_latest_for_data_source`, then verify `uv run mypy . --config-file pyproject.toml --ignore-missing-imports` reports zero errors.