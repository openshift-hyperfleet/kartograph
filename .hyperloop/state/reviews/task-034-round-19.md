---
task_id: task-034
round: 19
role: verifier
verdict: fail
---
# Spec Alignment Review: task-034 Credentials

## Review Date
2026-04-27

## Summary

The **implementation quality** for the Credentials spec is sound: all five SHALL
requirements are implemented, all 2405 unit tests pass, linting/formatting/type-
checking are clean, and architecture boundaries are respected. However, two check
scripts produce genuine FAIL results that must be resolved before the branch can
be merged:

1. **`check-run-backend-suite.sh` — FAIL**: The branch is **42 commits behind
   `alpha`**. The suite halts immediately and declares all subsequent checks
   unreliable. This is a blocking process failure.

2. **`check-cascade-delete-empty-collection-mocks.sh` — FAIL**: The check finds
   that every occurrence of `mock_group_repo.list_by_tenant` inside
   `TestDeleteTenant` (`test_tenant_service.py`) uses `return_value=[]`. The
   cascade-delete loop body is never entered in any test, so the inner
   `group_repo.delete()` call is never exercised. Although this is a pre-existing
   condition unrelated to this credential task, the check runs against the live
   branch and fails.

---

## Per-Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2405) | **PASS** | 0 failures, 45 warnings |
| `ruff check` | **PASS** | Zero violations |
| `ruff format --check` | **PASS** | 479 files formatted |
| `mypy` | **PASS** | Zero errors in 479 source files |
| `test_architecture.py` (40 tests) | **PASS** | No boundary leaks |
| `check-cascade-delete-cleanup.sh` | **PASS** | All DS-delete paths call secret_store.delete |
| `check-no-direct-logger-usage.sh` | **PASS** | Domain probes used throughout |
| `check-domain-aggregate-mocks.sh` | **PASS** | 0 bare MagicMock violations |
| `check-cross-task-deferral.sh` | **PASS** | No cross-task deferral comments |
| `check-run-backend-suite.sh` | **FAIL** | Branch 42 commits behind alpha — suite halted |
| `check-cascade-delete-empty-collection-mocks.sh` | **FAIL** | TestDeleteTenant always mocks group_repo as empty list |
| `check-no-state-file-commits.sh` | unreliable | Stale merge-base makes this a false positive; state files exist on current alpha |
| `check-no-test-regressions.sh` | unreliable | Stale merge-base — deleted test files confirmed absent from current alpha |

---

## Spec Requirement Coverage (Informational)

All spec requirements are correctly implemented — this is not the source of the
FAIL verdict.

### Credential Encryption — COVERED
- `FernetSecretStore.store()` encrypts with `MultiFernet`; composite PK
  `(path, tenant_id)` in DB; `session.merge()` for upsert.
- `FernetSecretStore.retrieve()` decrypts and returns the original dict.
- `KeyError("Credentials not found")` raised when no record found.
- Full unit and integration test coverage.

### Tenant Isolation — COVERED
- WHERE clause filters on both `path` AND `tenant_id`; composite PK enforces
  DB-level isolation.
- Unit + integration tenant-isolation tests confirmed.

### Key Rotation — COVERED
- `MultiFernet` accepts ordered key list; first key encrypts, all tried on
  decrypt. `TestMultiFernetRotation::test_decrypt_with_rotated_keys` passes.

### Credential Lifecycle — COVERED
- `DataSourceService.delete()` calls `secret_store.delete()` before removing the
  DS row. Unit test asserts correct call.
- **KG cascade (previously FAIL — now resolved):** `KnowledgeGraphService.delete()`
  iterates child data sources and calls `secret_store.delete()` for each DS with
  a `credentials_path`, before removing the DB row. Two focused unit tests cover
  this: `test_delete_removes_credentials_for_data_sources_with_credentials_path`
  and `test_delete_skips_credential_cleanup_when_no_secret_store`.

---

## Actionable Findings

### Finding 1 — BLOCKING: Rebase the branch on current alpha

```bash
git rebase alpha
```

The branch is 42 commits stale. `check-run-backend-suite.sh` halts all
subsequent checks until the branch is current. After rebase, re-run the full
check suite.

### Finding 2 — BLOCKING: Fix TestDeleteTenant cascade-delete loop coverage

**File:** `src/api/tests/unit/iam/application/test_tenant_service.py`
**Class:** `TestDeleteTenant`

Every test in this class mocks `mock_group_repo.list_by_tenant` with
`return_value=[]`. The for-loop that calls `group_repo.delete()` is never
entered, so the cascade behavior is untested.

**Fix:** Add at least one test that mocks `list_by_tenant` with a non-empty
list of real domain aggregates and asserts that `group_repo.delete` is called
for each:

```python
async def test_delete_tenant_cascades_groups(self, ...):
    group = Group(...)  # real domain object, not MagicMock
    mock_group_repo.list_by_tenant = AsyncMock(return_value=[group])
    await tenant_service.delete(tenant_id=..., user_id=...)
    mock_group_repo.delete.assert_called_once_with(group)
```

**Note:** This is a pre-existing issue, not introduced by task-034, but the
check runs against the live branch and must pass before the verdict can be PASS.

---

## Commit Trailers

Implementation commits carry correct trailers:
```
Spec-Ref: specs/management/credentials.spec.md
Task-Ref: task-034
```

Spec-Ref: specs/management/credentials.spec.md
Task-Ref: task-034