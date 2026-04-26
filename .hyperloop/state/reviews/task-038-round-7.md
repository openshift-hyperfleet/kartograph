---
task_id: task-038
round: 7
role: verifier
verdict: fail
---
## Worker Result — task-038 (specs/shared-kernel/tenant-context.spec.md)

Worker: reviewer
Date: 2026-04-26

---

### Summary

The task-038 implementation of Tenant Context (tenant_context.py,
mcp_api_key_auth.py and their unit tests) is present and complete — the
functional code was merged to alpha in prior iterations. However, the branch
carries a contaminating task-012 ingestion commit (`c6b4ab3a`) that was picked
up during a bad rebase against `origin/alpha`. That commit introduces multiple
regressions and causes **5 of the project check scripts to FAIL**. The verdict
is **FAIL** until the branch is cleaned.

---

### Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2465) | PASS | All pass, zero failures |
| ruff check | PASS | Zero violations |
| ruff format | PASS | 496 files formatted |
| mypy | PASS | Zero errors |
| Architecture boundary tests | PASS | 40/40 pass |
| check-branch-has-commits | PASS | 11 commits ahead |
| check-branch-rebased-on-alpha | PASS | 2 commits behind local alpha (within range) |
| check-no-direct-logger-usage | PASS | No logger.*/print() violations |
| check-domain-aggregate-mocks | PASS | No bare MagicMock on aggregates |
| check-weak-test-assertions | PASS | No weak categorical assertions |
| check-empty-test-stubs | PASS | No pass-only stubs |
| check-cross-task-deferral | PASS | No cross-task deferral comments |
| check-deferred-integration | PASS | dlt properly imported |
| check-no-coming-soon-stubs | PASS | None found |
| check-implementation-commits-exist | PASS | 4 implementation commits found |
| check-alpha-local-vs-remote | **FAIL** | Local alpha is 6 commits ahead of origin/alpha |
| check-cascade-delete-cleanup | **FAIL** | secret_store.delete removed from knowledge_graph_service.py |
| check-no-test-regressions | **FAIL** | 3 test files deleted; 16 others truncated |
| check-no-source-regressions | **FAIL** | 2 source files deleted; secret_store wiring removed |
| check-no-state-file-commits | **FAIL** | 41 .hyperloop/state/ files committed to this branch |

---

### Root Cause: Contaminating Ingestion Commit

Commit `c6b4ab3a` (`feat(ingestion): implement Ingestion context — Task-Ref: task-012`)
is present in this branch's history but is NOT on `alpha`. It was added during a
rebase against `origin/alpha` (not local `alpha`). This commit:

1. **Removed `ISecretStoreRepository` from `knowledge_graph_service.py`** — the
   secret store injection, constructor parameter, and the `secret_store.delete()`
   call in the cascade-delete loop were all stripped out. Deleting a KnowledgeGraph
   now orphans vault credential blobs permanently.

2. **Deleted 3 test files** vs. alpha:
   - `tests/unit/iam/domain/test_workspace_role_hierarchy.py` (233 lines)
   - `tests/unit/iam/presentation/test_tenant_routes.py` (467 lines)
   - `tests/unit/management/presentation/test_knowledge_graph_routes.py` (607 lines)

3. **Deleted 2 source files** vs. alpha:
   - `src/api/management/dependencies/encryption_keys.py`
   - `src/api/management/presentation/auth_bridge.py`

4. **Reduced test coverage** in 16 other test files (net line removal), including
   `test_knowledge_graph_service.py` (−169 lines) and `test_data_sources_routes.py`
   (−204 lines).

---

### State File Contamination

41 `.hyperloop/state/` files were committed to this task branch by orchestrator
processes running in the worktree. The check-no-state-file-commits.sh script
explicitly prohibits this; these files are managed exclusively on trunk/alpha.

---

### Required Fix: Cherry-Pick onto Clean Branch

The check script output provides exact instructions. The task-038 delivery
commits that should be preserved are:

```
01270e2f  test(query): add integration tests for MCP authentication endpoint
e4ff5f74  fix(test): add pytest.skip() call to empty 503 integration test stub
676ebadf  fix(task-038): correct worker-result.yaml
```

Step 1 — Identify clean delivery commits:
```
git log --oneline $(git merge-base HEAD alpha)..HEAD -- ':!.hyperloop/state'
```

Step 2 — Create fresh branch from local alpha and cherry-pick:
```
git checkout alpha
git checkout -b hyperloop/task-038-clean
git cherry-pick 01270e2f e4ff5f74
```

Step 3 — Update this worker-result.yaml and commit it on the clean branch.

Step 4 — Confirm checks pass, then force-push:
```
git push origin hyperloop/task-038-clean:hyperloop/task-038 --force-with-lease
```

---

### Spec Coverage (Implementation on Alpha — Unchanged)

All 13 SHALL scenarios from the spec are implemented and tested. The
implementation on `alpha` is correct; the regression was introduced only by the
contaminating task-012 commit on this branch.

Spec-Ref: specs/shared-kernel/tenant-context.spec.md
Task-Ref: task-038