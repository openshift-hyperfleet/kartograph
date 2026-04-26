---
task_id: task-019
round: 5
role: verifier
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (re-verification)

This review rebased the branch on alpha (resolving 3 merge conflicts) then ran the
full backend check suite.

### Check Results

| Check | Result | Detail |
|-------|--------|--------|
| 1. Unit Tests | PASS | 2404 passed, 0 failures |
| 2. Linting (ruff check) | PASS | All checks passed |
| 3. Formatting (ruff format --check) | PASS | 483 files already formatted |
| 4. Type Checking (mypy) | PASS | No issues found in 479 source files |
| 5. Architecture Boundary Tests | PASS | 40 passed |
| 6. check-domain-aggregate-mocks.sh | PASS | 0 violations (prior fix confirmed effective) |
| 7. check-cascade-delete-empty-collection-mocks.sh | FAIL | Pre-existing violation, see below |

---

## Failing Check: Cascade-Delete Empty Collection Mocks

`check-cascade-delete-empty-collection-mocks.sh` fails on a **pre-existing violation**
in `tests/unit/iam/application/test_tenant_service.py::TestDeleteTenant`. This file
was **not touched by task-019** (diff against alpha is empty for this file).

The check was added to alpha in commit `17861145` (process improvement) after
this task was already in flight, but the corresponding fix to `test_tenant_service.py`
was not included. Alpha itself fails this check. However, since the check is now
part of the mandatory backend suite (`check-run-backend-suite.sh`), this branch
cannot be verified as PASS until the violation is resolved.

**Violation details:**

```
Class 'TestDeleteTenant': 'mock_group_repo.list_by_tenant' is only ever
mocked with return_value=[] (empty list). The cascade-delete loop
body is never entered — the inner delete() is never tested.

Affected lines in test_tenant_service.py:
  1283, 1329, 1401, 1484, 1547, 1604, 1644, 1713
```

---

## Required Fix (Narrow and Self-Contained)

Add **one new test** to `TestDeleteTenant` in
`src/api/tests/unit/iam/application/test_tenant_service.py` that mocks
`mock_group_repo.list_by_tenant` with a non-empty return value and asserts
`mock_group_repo.delete` is called for each group.

The simplest acceptable fix:

```python
@pytest.mark.asyncio
async def test_delete_cascades_groups(self, service, mock_group_repo, ...):
    """delete() calls group_repo.delete() for each group in the tenant."""
    from iam.domain.models import Group  # use real Group or a _make_group() factory
    group = _make_group(tenant_id=tenant_id)  # real object, not MagicMock
    mock_group_repo.list_by_tenant = AsyncMock(return_value=[group])
    # ... set up other mocks ...
    await service.delete(tenant_id=tenant_id, ...)
    mock_group_repo.delete.assert_called_once_with(group)
```

---

## Implementation Quality (Unaffected by the Failing Check)

The credential implementation itself is correct and complete:

- **Credential Encryption**: `FernetSecretStore.store/retrieve` — PASS
- **Tenant Isolation**: Composite PK `(path, tenant_id)` — PASS
- **Key Rotation**: `MultiFernet` with fallback keys — PASS
- **Credential Lifecycle / data source deletion**: `DataSourceService.delete()` — PASS
- **Credential Lifecycle / knowledge graph cascade**: `KnowledgeGraphService.delete()`
  injects `ISecretStoreRepository` and calls `secret_store.delete()` for each DS
  with a `credentials_path` — PASS
- **Domain aggregate mocks**: All replaced with real `_make_ds()` factory — PASS

Commit trailers are present on all task-019 implementation commits:
- `3ed67df2` (feat) — Spec-Ref + Task-Ref ✓
- `07dd3715` (test) — Spec-Ref + Task-Ref ✓
- `5e5e4b35` (fix) — Task-Ref ✓

---

## Action Required

1. Fix `tests/unit/iam/application/test_tenant_service.py::TestDeleteTenant`:
   add at least one test that exercises `mock_group_repo.list_by_tenant` with a
   non-empty list and asserts inner `delete()` was called for each item.
2. Run `bash .hyperloop/checks/check-run-backend-suite.sh` — must exit 0.
3. Commit the fix with a conventional commit message and Task-Ref trailer.