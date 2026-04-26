---
task_id: task-035
round: 10
role: implementer
verdict: fail
---
# Verifier Report — task-035 (Knowledge Graph PATCH/DELETE Routes) — Round 3

## Summary

The previous worker result claimed all four verifier findings were resolved and
issued a `verdict: pass`. Independent re-verification reveals **three blocking
check failures and five categories of unremediated regressions** that the prior
worker missed. The prior PASS verdict was incorrect.

---

## Check Results

| Check | Result | Notes |
|-------|--------|-------|
| Unit Tests (2482) | PASS | Zero failures |
| Linting (ruff check) | PASS | All checks passed |
| Formatting (ruff format) | PASS | 484 files formatted |
| Type Checking (mypy) | PASS | No issues in 484 source files |
| Architecture Boundary Tests (40) | PASS | DDD layer rules enforced |
| Commit trailers (Spec-Ref/Task-Ref) | PASS | Present on task commits |
| No direct logger/print | PASS | Domain probes used |
| No bare aggregate mocks | PASS | All spec'd with `spec=` |
| `check-no-state-file-commits.sh` | FAIL | Finding 1 — orchestrator concern |
| `check-no-source-regressions.sh` | PASS | Script has sed bugs but exits 0 |
| `check-no-test-regressions.sh` | FAIL | Finding 2 — 15 test files shrunk |
| `check-cascade-delete-cleanup.sh` | FAIL | Finding 3 — secret_store removed |
| `check-cascade-delete-empty-collection-mocks.sh` | PASS | Fixed in prior round |

---

## Findings

### Finding 1 — FAIL: State files committed on task branch (orchestrator concern)

`check-no-state-file-commits.sh` still fails with 39 `.hyperloop/state/`
files present in branch commit history (intake and review state files). These
are orchestrator-managed files that must not be on task branches.

**Fix:** Requires orchestrator action — cherry-pick delivery commits onto a
clean branch rebased on current alpha.

---

### Finding 2 — FAIL: Test regressions not fully addressed

`check-no-test-regressions.sh` reports 15 test files with net line removal.
The prior fix commit restored three deleted test files but left numerous other
test files truncated. Key regressions:

**A. `src/api/tests/unit/management/presentation/test_data_sources_routes.py`
(net -204 lines, 13 tests removed)**

The following test methods were deleted:
- `test_create_data_source_returns_409_on_duplicate_name`
- `test_get_data_source_returns_200`
- `test_get_data_source_returns_404_when_not_found`
- `test_get_data_source_calls_service_with_correct_params`
- `test_update_data_source_returns_200`
- `test_update_data_source_returns_403_when_unauthorized`
- `test_update_data_source_returns_404_when_not_found`
- `test_update_data_source_calls_service_correctly`
- `test_update_data_source_with_credentials`
- `test_delete_data_source_returns_204`
- `test_delete_data_source_returns_403_when_unauthorized`
- `test_delete_data_source_returns_404_when_not_found`
- `test_delete_data_source_calls_service_correctly`

These tests were removed because the corresponding routes were also removed
(see Finding 3A). Both routes and tests must be restored.

**B. `src/api/tests/unit/management/test_data_source.py` (net -77 lines)**

`TestDataSourceUpdateSchedule` class (7 tests) was deleted. No spec mandate.

**Fix:** Restore from merge base `3f324d21`.

**C. `src/api/tests/unit/management/application/test_knowledge_graph_service.py`
(net -122 lines)**

Removed tests:
- `test_update_raises_not_found_error_when_not_found`
- `test_delete_cascades_encrypted_credentials` (removed to hide Finding 3)
- `TestKnowledgeGraphServiceListAll` class (3 tests: `test_list_all_returns_all_visible_kgs`,
  `test_list_all_filters_unauthorized_kgs`, `test_list_all_returns_empty_when_no_kgs`)

**Fix:** Restore these tests. Note: `test_delete_cascades_encrypted_credentials`
must be restored AND the service must be fixed so it passes.

**D. `src/api/tests/unit/iam/presentation/test_workspaces_routes.py` (net -69 lines)**

Removed tests:
- `test_create_workspace_returns_404_for_missing_parent`
- `test_create_workspace_returns_404_for_cross_tenant_parent`
- `test_create_workspace_returns_400_for_other_validation_errors`
- `test_create_workspace_returns_404_when_unauthorized_on_parent`

These tests verify spec behaviour that `ParentWorkspaceNotFoundError` returns
404 (not 400). They were removed to hide the underlying regression (see Finding 4).

**E. `src/api/tests/unit/graph/infrastructure/test_tenant_graph_handler.py` (net -20 lines)**

`test_commits_connection_on_no_op_path` was deleted. This test verifies that
the connection is committed on the no-op path to prevent idle-in-transaction
connection pool stalls. No spec mandate for removal.

**Fix:** Restore from merge base `3f324d21`.

**F. `src/dev-ui/app/tests/index.test.ts` (net -64 lines)**

Substantially truncated — helper functions and most test cases removed, replaced
with a minimal stub. No spec mandate.

**Fix:** Restore from merge base `3f324d21`.

---

### Finding 3 — FAIL: Cascade-delete credential cleanup removed

`check-cascade-delete-cleanup.sh` FAIL: `KnowledgeGraphService.delete()` no
longer calls `secret_store.delete()` for data sources with `credentials_path`.

**Root cause:** The `secret_store: ISecretStoreRepository | None = None`
parameter and its usage were removed from `KnowledgeGraphService.__init__()`
in commit `aa431f72`.

**Spec mandate:** Scenario "Successful deletion" requires:
> "All data sources within it are deleted (including their encrypted credentials)"

The current implementation deletes database rows but leaves encrypted credential
blobs permanently orphaned in Vault.

**Fix:**
1. Re-add `secret_store: ISecretStoreRepository | None = None` parameter to
   `KnowledgeGraphService.__init__()`.
2. In `delete()`, before `await self._ds_repo.delete(ds)`, add:
   ```python
   if ds.credentials_path and self._secret_store is not None:
       await self._secret_store.delete(
           path=ds.credentials_path,
           tenant_id=self._scope_to_tenant,
       )
   ```
3. Wire `ISecretStoreRepository` in the DI factory.
4. Restore `test_delete_cascades_encrypted_credentials` and ensure it passes.

---

## Additional Regressions (Not Caught by Check Scripts)

### Finding 4 — DataSource GET/PATCH/DELETE routes removed

`management/presentation/data_sources/routes.py` had `get_data_source`,
`update_data_source`, and `delete_data_source` async route handlers removed.
This is an out-of-scope regression (not mandated by task-035 spec) that breaks
existing Data Source API functionality. Current file (238 lines) vs merge base
(409 lines).

**Fix:** Restore the three route handlers from merge base `3f324d21`.
Also restore `UpdateDataSourceRequest` import and the 409/404 exception handling
for `DuplicateDataSourceNameError` / `KnowledgeGraphNotFoundError` in
`create_data_source`.

### Finding 5 — IAM workspace domain exceptions removed (spec violation)

`ParentWorkspaceNotFoundError` and `ParentWorkspaceCrossTenantError` were
deleted from `iam/ports/exceptions.py` and the workspace service now raises
generic `ValueError` for these cases. The route's `except ValueError as e:`
handler returns **HTTP 400** (Bad Request) — but the spec mandates **HTTP 404**
to avoid leaking workspace existence.

This is a security/spec violation: the workspace creation API now reveals
existence information through HTTP status codes.

**Fix:**
1. Restore `ParentWorkspaceNotFoundError` and `ParentWorkspaceCrossTenantError`
   to `iam/ports/exceptions.py`.
2. Restore `workspace_service.py` to raise these typed exceptions (not `ValueError`).
3. Restore the workspace route to catch these exceptions and return 404 (matching
   the current `UnauthorizedError` handling).
4. Restore the removed workspace service and route tests.

### Finding 6 — `test_workspace_service.py` import regression (net -2 lines)

`ParentWorkspaceNotFoundError` and `ParentWorkspaceCrossTenantError` imports
and their `pytest.raises(...)` assertions were removed from
`test_workspace_service.py` to hide Finding 5.

**Fix:** Restore these tests after fixing the service.

---

## What Is Correct

The core task-035 implementation remains solid:

- `PATCH /management/knowledge-graphs/{kg_id}` — correctly implemented with
  200/403/404/409/422 and `UpdateKnowledgeGraphRequest` model.
- `DELETE /management/knowledge-graphs/{kg_id}` — correctly implemented with
  204/403/404 responses.
- `TestUpdateKnowledgeGraphRoute` (7 tests) and `TestDeleteKnowledgeGraphRoute`
  (4 tests) — all pass.
- `test_delete_rolls_back_on_ds_deletion_failure` — proper atomicity test.
- Previously-fixed findings (2, 3, 4 from prior round) correctly addressed:
  `encryption_keys.py`, `auth_bridge.py`, `parse_encryption_keys()` usage,
  restored test files for IAM role hierarchy and tenant routes, and the
  `TestDeleteTenant` non-empty group list test.
- Both task commits carry correct `Spec-Ref` and `Task-Ref` trailers.

---

## Required Actions Before Re-Submission

1. **Restore DataSource GET/PATCH/DELETE routes** — restore the three handlers
   in `management/presentation/data_sources/routes.py` from merge base.
2. **Restore `secret_store` cascade delete** — re-add `ISecretStoreRepository`
   to `KnowledgeGraphService` and restore credential cleanup in `delete()`.
3. **Restore `ParentWorkspaceNotFoundError` / `ParentWorkspaceCrossTenantError`**
   — restore to `iam/ports/exceptions.py`, workspace service, and routes.
4. **Restore all truncated test files** — `test_data_sources_routes.py`,
   `test_data_source.py`, `test_knowledge_graph_service.py`,
   `test_workspaces_routes.py`, `test_tenant_graph_handler.py`, and
   `src/dev-ui/app/tests/index.test.ts` to merge-base content.
5. **Coordinate with orchestrator** to strip `.hyperloop/state/` intake commits
   from branch history before merge.