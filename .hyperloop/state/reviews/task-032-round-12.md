---
task_id: task-032
round: 12
role: implementer
verdict: fail
---
# Verification Result — task-032 (Groups) — Round 18

## Rebase
Branch was 16 commits behind alpha (PR comment: "not mergeable — conflicts with alpha").
Rebased successfully. Merge conflicts were cosmetic only (grep flag formatting,
docstring wording, pytest.skip message text); resolved by keeping alpha's version.
Branch is now within acceptable range (1 commit behind alpha).

## Standard Checks

| Check | Result |
|-------|--------|
| Unit tests (2401) | PASS — 53 s, zero failures |
| ruff check | PASS — zero violations |
| ruff format | PASS — 479 files formatted |
| mypy | PASS — zero errors in 479 source files |
| Architecture boundaries | PASS — all 40 tests pass |

## Backend Check Suite

| Check | Result |
|-------|--------|
| check-no-check-script-deletions | PASS |
| check-process-overlays-intact | PASS |
| check-branch-has-commits | PASS |
| check-branch-rebased-on-alpha | PASS |
| check-no-state-file-commits | PASS |
| check-no-source-regressions | PASS |
| check-no-test-regressions | PASS |
| check-empty-test-stubs | PASS |
| check-domain-aggregate-mocks | PASS |
| check-no-direct-logger-usage | PASS |
| check-no-coming-soon-stubs | PASS |
| check-weak-test-assertions | PASS |
| check-di-wiring-updated | PASS |
| check-pytest-env-skip-if-set | PASS |
| **check-cascade-delete-empty-collection-mocks** | **FAIL** |

## Failing Check

**check-cascade-delete-empty-collection-mocks — FAIL**

File: `src/api/tests/unit/iam/application/test_tenant_service.py`
Class: `TestDeleteTenant`

Every test in this class mocks `mock_group_repo.list_by_tenant` with
`return_value=[]` (lines 1283, 1329, 1401, 1484, 1547, 1604, 1644, 1713, 1772).
The cascade-delete loop in `TenantService.delete_tenant()` (around line 655) that
calls `self._group_repository.delete(group)` for each group is never entered.
The SHALL requirement that groups are removed when a tenant is deleted has no
unit test coverage of the inner loop body.

## Required Fix (Actionable)

Add one test to `TestDeleteTenant` that exercises the cascade with a real Group
aggregate:

```python
@pytest.mark.asyncio
async def test_deletes_groups_on_tenant_deletion(
    self,
    tenant_service,
    mock_tenant_repo,
    mock_workspace_repo,
    mock_group_repo,
    mock_api_key_repo,
    mock_authz,
):
    """Cascade delete: all groups belonging to the tenant are deleted."""
    tenant_id = TenantId.generate()
    admin_id = UserId.from_string("admin-456")
    tenant = Tenant(id=tenant_id, name="Acme Corp")
    group = Group.create(
        name="Engineering",
        tenant_id=tenant_id,
        creator_id=admin_id,
    )

    mock_authz.check_permission = AsyncMock(return_value=True)
    mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
    mock_tenant_repo.delete = AsyncMock(return_value=True)
    mock_workspace_repo.list_by_tenant = AsyncMock(return_value=[])
    mock_group_repo.list_by_tenant = AsyncMock(return_value=[group])
    mock_group_repo.delete = AsyncMock()
    mock_api_key_repo.list = AsyncMock(return_value=[])
    mock_authz.read_relationships = AsyncMock(return_value=[])

    result = await tenant_service.delete_tenant(
        tenant_id, requesting_user_id=admin_id
    )

    assert result is True
    mock_group_repo.delete.assert_called_once_with(group)
```

Use `Group.create(...)` (real aggregate, not a MagicMock) so the loop body
actually executes. If `delete_tenant` calls `group.mark_for_deletion()` before
persisting, add an assertion for that too — check `tenant_service.py` lines
~600-660 for the exact call sequence.

## Spec Coverage

Prior rounds verified all 10 spec requirements are implemented. This verdict
is FAIL solely on the cascade-delete test gap discovered by the newly-enforced
check script; spec coverage itself is complete.