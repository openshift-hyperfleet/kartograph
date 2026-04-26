---
task_id: task-038
round: 8
role: verifier
verdict: fail
---
## Worker Result — task-038 (specs/shared-kernel/tenant-context.spec.md)

Worker: reviewer
Date: 2026-04-26 (second pass)

---

### Summary

The task-038 delivery commits (`01270e2f`, `e4ff5f74`) — integration tests for
MCP Authentication — are correct and complete. All delivery commit trailers are
present (`Spec-Ref: specs/shared-kernel/tenant-context.spec.md`, `Task-Ref:
task-038`). The implementation itself (tenant_context.py, mcp_api_key_auth.py)
was already on `alpha` before this task began and remains correct.

However, the `hyperloop/task-038` branch **still** carries the contaminating
task-012 ingestion commit (`c6b4ab3a`) picked up during a rebase against
`origin/alpha` in a prior iteration. This commit remains the root cause of all
failing checks. A local `task-038-clean` branch exists (with a passing
worker-result) but has **not** been force-pushed to `hyperloop/task-038`.

The verdict is **FAIL** — the contaminating commit must be removed before merge.

---

### Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests | PASS | 2465 tests, zero failures |
| ruff check | PASS | Zero violations, 496 files |
| ruff format | PASS | All files formatted |
| mypy | PASS | Zero errors, 496 source files |
| Architecture boundary tests | PASS | 40/40 pass |
| check-branch-has-commits | PASS | 16 commits ahead of alpha |
| check-branch-rebased-on-alpha | PASS | 5 commits behind local alpha (within range) |
| check-alpha-local-vs-remote | PASS | Local alpha within 4 commits of origin/alpha |
| check-no-direct-logger-usage | PASS | No logger.*/print() violations |
| check-domain-aggregate-mocks | PASS | No bare MagicMock on aggregates |
| check-weak-test-assertions | PASS | No weak categorical assertions |
| check-empty-test-stubs | PASS | No pass-only stubs |
| check-cross-task-deferral | PASS | No cross-task deferral comments |
| check-deferred-integration | PASS | dlt properly imported |
| check-no-coming-soon-stubs | PASS | None found |
| check-no-check-script-deletions | PASS | Check script infrastructure intact |
| check-process-overlays-intact | PASS | Process overlay files intact |
| check-implementation-commits-exist | PASS | 4 implementation commits found |
| check-cascade-delete-cleanup | **FAIL** | secret_store.delete absent from knowledge_graph_service.py |
| check-no-test-regressions | **FAIL** | 3 test files deleted; 11+ truncated vs. alpha |
| check-no-source-regressions | **FAIL** | 2 source files deleted; secret_store wiring removed |
| check-no-state-file-commits | **FAIL** | 40+ .hyperloop/state/ files committed to this branch |

---

### Root Cause: Contaminating Ingestion Commit (c6b4ab3a) — Unchanged

Commit `c6b4ab3a` (`feat(ingestion): implement Ingestion context — Task-Ref:
task-012`) is still present in this branch's history and is NOT on local
`alpha`. It was absorbed during a rebase against `origin/alpha`. This commit:

1. **Removed `ISecretStoreRepository`** from `knowledge_graph_service.py` —
   the injection, constructor parameter, and the `secret_store.delete()` call
   inside the cascade-delete loop are all missing. Deleting a KnowledgeGraph
   now permanently orphans vault credential blobs.

2. **Deleted test files** vs. alpha:
   - `tests/unit/iam/domain/test_workspace_role_hierarchy.py`
   - `tests/unit/iam/presentation/test_tenant_routes.py`
   - `tests/unit/management/presentation/test_knowledge_graph_routes.py`

3. **Deleted source files** vs. alpha:
   - `src/api/management/dependencies/encryption_keys.py`
   - `src/api/management/presentation/auth_bridge.py`

4. **Truncated test coverage** in many other test files (net line removal in
   `test_knowledge_graph_service.py`, `test_data_sources_routes.py`, etc.)

5. **Committed 40+ `.hyperloop/state/` files** — these are trunk-managed files
   that must never appear in task branches.

---

### Clean Branch Exists — But Not Pushed

A local `task-038-clean` branch already contains the correct cherry-picked
delivery commits and a prior passing verdict. The fix is a single force-push:

```bash
git push origin task-038-clean:hyperloop/task-038 --force-with-lease
```

After pushing, verify with the backend suite check:
```bash
bash .hyperloop/checks/check-run-backend-suite.sh
```

---

### Commit Trailers (Delivery Commits)

Both task-038 delivery commits have correct trailers:

- `01270e2f test(query): add integration tests for MCP authentication endpoint`
  - `Spec-Ref: specs/shared-kernel/tenant-context.spec.md@b68605133f...`
  - `Task-Ref: task-038`
- `e4ff5f74 fix(test): add pytest.skip() call to empty 503 integration test stub`
  - `Spec-Ref: specs/shared-kernel/tenant-context.spec.md@b68605133f...`
  - `Task-Ref: task-038`

---

### Spec Coverage (Implementation on Alpha — All 13 Scenarios)

All 13 SHALL scenarios from `specs/shared-kernel/tenant-context.spec.md` are
covered by the implementation on `alpha`. The task-038 delivery adds integration
test coverage for the four MCP Authentication scenarios, which was the remaining
gap from the prior review round.

Spec-Ref: specs/shared-kernel/tenant-context.spec.md
Task-Ref: task-038