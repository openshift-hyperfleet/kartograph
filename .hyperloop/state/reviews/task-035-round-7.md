---
task_id: task-035
round: 7
role: verifier
verdict: fail
---
# Verifier Report — task-035 (Knowledge Graph PATCH/DELETE Routes)

## Summary

The core task implementation is correct and complete: PATCH and DELETE HTTP routes
are in place, properly tested, and the atomicity rollback test exists. However,
the backend check suite reports 4 failures that constitute blocking regressions.

---

## Check Results

| Check | Result | Notes |
|-------|--------|-------|
| Unit Tests (2413) | PASS | Zero failures |
| Linting (ruff check) | PASS | All checks passed |
| Formatting (ruff format) | PASS | 479 files formatted |
| Type Checking (mypy) | PASS | No issues in 479 source files |
| Architecture Boundary Tests (40) | PASS | DDD layer rules enforced |
| Commit trailers (Spec-Ref/Task-Ref) | PASS | Present on both task commits |
| No direct logger/print | PASS | Domain probes used throughout |
| No bare aggregate mocks | PASS | All spec'd with `spec=` |
| check-no-state-file-commits.sh | FAIL | See Finding 1 |
| check-no-source-regressions.sh | FAIL | See Finding 2 |
| check-no-test-regressions.sh | FAIL | See Finding 3 |
| check-cascade-delete-empty-collection-mocks.sh | FAIL | See Finding 4 |

---

## Findings

### Finding 1 — FAIL: State files committed on task branch

`check-no-state-file-commits.sh` reports `.hyperloop/state/intake/` files in
branch commits. These are orchestrator-managed files that belong only on trunk.
All appear in `chore(intake)` commits, not in task implementation commits, but
the check catches them regardless and they violate the process contract.

**Fix:** The orchestrator must strip or rebase out the intake state commits from
this task branch before merging. The verifier cannot do this unilaterally.

---

### Finding 2 — FAIL: Source files deleted without spec mandate

`check-no-source-regressions.sh` reports two source files deleted (both removed
in commit `13ba0b7a chore(intake): record Run 6 review — no tasks created`):

1. **`src/api/management/dependencies/encryption_keys.py`**
   — Contained `parse_encryption_keys()`, a canonical Fernet key parser that
   stripped whitespace and removed empty segments. This module was in the
   merge base (`3f324d21`). Its deletion introduced a functional regression:
   `management/dependencies/data_source.py` now uses
   `settings.encryption_key.get_secret_value().split(",")` directly, which
   leaves whitespace in keys (`"key1, key2"` -> `["key1", " key2 "]`) and
   passes empty strings through (`"key1,,"` -> `["key1", "", ""]`). Both will
   cause `Fernet("...")` to raise at runtime.

   **Fix:** Restore `encryption_keys.py` from the merge base (`3f324d21`) and
   update `data_source.py` to call `parse_encryption_keys(...)`.

2. **`src/api/management/presentation/auth_bridge.py`**
   — Re-exported `CurrentUser` and `get_current_user` from IAM into the
   management presentation layer. This was in the merge base. Its deletion
   forced `routes.py` to import directly from `iam.dependencies.user` and
   `iam.application.value_objects`. This may violate the IAM isolation
   architecture rule (the auth_bridge existed precisely to be the single
   allowed cross-context import point).

   **Fix:** Restore `auth_bridge.py` from the merge base and update the
   routes import accordingly, OR confirm that `management.presentation.routes`
   is explicitly excluded from the IAM architecture test and document why
   the bridge is no longer needed.

---

### Finding 3 — FAIL: Test files deleted without spec mandate

`check-no-test-regressions.sh` reports three complete test files deleted (all
removed in commit `13ba0b7a`):

1. **`src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`**
   (760 lines, 35 tests) — This file was committed to alpha via PR #471 and
   was in the merge base. It covered all five endpoint classes (Create, Get,
   List-for-workspace, List-all, Update, Delete) including:
   - 401 Unauthenticated tests for every endpoint
   - 422 oversized-name validation tests for Create and Update
   The replacement file `test_knowledge_graphs_routes.py` covers only 17
   tests and is missing the 401 and 422 oversized-name scenarios.

   **Fix:** Restore `test_knowledge_graph_routes.py` from the merge base AND
   keep `test_knowledge_graphs_routes.py`. Both files covered different enough
   scenarios that both should co-exist, or the replacement must have at minimum
   the same test count and scenario coverage as the deleted file.

2. **`src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py`**
   (286 lines) — IAM workspace three-tier role hierarchy tests. Unrelated to
   this task's scope. No spec mandate for removal.

   **Fix:** Restore from merge base (`3f324d21`).

3. **`src/api/tests/unit/iam/presentation/test_tenant_routes.py`**
   (587 lines) — IAM tenant CRUD route tests. Unrelated to this task's scope.
   No spec mandate for removal.

   **Fix:** Restore from merge base (`3f324d21`).

---

### Finding 4 — FAIL: TestDeleteTenant always uses empty collection mocks

`check-cascade-delete-empty-collection-mocks.sh` reports that in
`tests/unit/iam/application/test_tenant_service.py`, the `TestDeleteTenant`
class mocks `mock_group_repo.list_by_tenant` with `return_value=[]` in all
8 test methods. The cascade-delete loop body (which calls `group_repo.delete()`)
is therefore never exercised.

This is a pre-existing gap but the check catches it and blocks submission.

**Fix:** Add at least one test in `TestDeleteTenant` that mocks
`mock_group_repo.list_by_tenant` with a non-empty list of real `Group` domain
objects and asserts that `mock_group_repo.delete` was called for each item:

    obj1 = Group(...)  # real domain object, not MagicMock
    mock_group_repo.list_by_tenant = AsyncMock(return_value=[obj1])
    # call service.delete(...)
    mock_group_repo.delete.assert_called_once_with(obj1)

---

## What Is Correct

The core task work (addressing the spec-reviewer's FAIL) is properly done:

- `PATCH /management/knowledge-graphs/{kg_id}` — correctly implemented with
  200/403/404/409/422 responses and `UpdateKnowledgeGraphRequest` model.
- `DELETE /management/knowledge-graphs/{kg_id}` — correctly implemented with
  204/403/404 responses and atomic cascade semantics.
- `TestUpdateKnowledgeGraphRoute` (7 tests) and `TestDeleteKnowledgeGraphRoute`
  (4 tests) in `test_knowledge_graphs_routes.py` — all pass.
- `test_delete_rolls_back_on_ds_deletion_failure` — a proper transactional
  atomicity test using `_RollbackSession` (not mocks). Verified at line 627 of
  `tests/unit/management/application/test_knowledge_graph_service.py`.
- Both task commits carry `Spec-Ref: specs/management/knowledge-graphs.spec.md`
  and `Task-Ref: task-035` trailers.

---

## Required Actions Before Re-Submission

1. Restore `management/dependencies/encryption_keys.py` from merge base
   (`3f324d21`) and fix `data_source.py` to use `parse_encryption_keys()`
   instead of raw `.split(",")`.
2. Restore `management/presentation/auth_bridge.py` from merge base and
   update the routes import to use it (or document the architecture exception).
3. Restore `tests/unit/management/presentation/test_knowledge_graph_routes.py`
   (760-line, 35-test file) from merge base.
4. Restore `tests/unit/iam/domain/test_workspace_role_hierarchy.py` from merge
   base.
5. Restore `tests/unit/iam/presentation/test_tenant_routes.py` from merge base.
6. Add at least one non-empty-list test to `TestDeleteTenant` for
   `mock_group_repo.list_by_tenant` exercising the cascade-delete loop body.
7. Coordinate with orchestrator to strip `.hyperloop/state/` intake commits
   from this task branch before merge.