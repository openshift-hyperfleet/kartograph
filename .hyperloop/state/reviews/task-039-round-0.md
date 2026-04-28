---
task_id: task-039
round: 0
role: verifier
verdict: fail
---
## Verifier Verdict — task-039 (specs/iam/tenants.spec.md)

Worker: verifier
Date: 2026-04-28

---

## Summary

The branch contains a **foreign task commit** (`abb01f1d1`, Task-Ref: task-017)
that must be removed before this branch can be merged. The two genuine task-039
commits are correct and their implementation is sound.

---

## Check Results

### 1. Unit Tests — PASS
2495 tests passed, 0 failures, 0 errors (101s).

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format --check) — PASS
497 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero errors in 497 source files.

### 5. Architecture Boundary Tests — PASS
40/40 pytest-archon tests pass. All DDD layer boundaries enforced.

### 6. Backend Check Suite — FAIL

`check-run-backend-suite.sh` exits 1 with the following failures:

**FAIL — check-worker-result-not-committed.sh (BLOCKING)**

Commit `abb01f1d1` touches `.hyperloop/worker-result.yaml` (as a deletion).
The check requires that the file never appear in ANY branch commit — including
deletions. This is directly caused by the foreign commit below.

**FAIL — check-alpha-local-vs-remote.sh (MISSING, pre-existing infra gap)**

The script `check-alpha-local-vs-remote.sh` is referenced in the suite but does
not exist on alpha or this branch. The file was added and later removed from
alpha's history (`db09e7c16`). This is a pre-existing infrastructure gap, not
introduced by this branch.

**FAIL — check-no-foreign-task-commits.sh (MISSING)**

`check-no-foreign-task-commits.sh` was added to alpha in commit `03858dbb0` or
`70c0a5ed7` — both of which postdate this branch's merge-base (`199467157`).
The script is therefore absent from this branch. It is not a deletion; the branch
simply predates its addition to alpha.

Even without the script present, manual inspection confirms a foreign commit:
commit `abb01f1d1` carries `Task-Ref: task-017`, not `task-039`.

### 7. Other Check Failures (pre-existing, not introduced by this branch)

The following checks fail both on this branch AND at the merge-base (`199467157`).
They were not introduced by task-039:

- **check-pages-have-tests.sh**: `src/dev-ui/app/pages/auth/callback.vue` has no
  test file. Existed at merge-base; not touched by this branch.

- **check-partial-error-assertions.sh**: OR-chained assertions at
  `test_query_mcp.py:213`, `test_mutation_service.py:543`,
  `test_cors_settings.py:113`, `test_settings.py:40`. All pre-exist on alpha.

- **check-property-merge-semantics.sh**: Direct `SET properties =` assignment at
  `graph/infrastructure/age_bulk_loading/queries.py:184`. Pre-exists on alpha.
  `age_bulk_loading/queries.py` was last touched in
  `01c32189f refactor(api.graph): improve age bulk loader organization` and
  `9bc8851be feat(api.iam): aihcm 157 workspace member routes` — both before
  the merge-base.

---

## Foreign Commit — Root Cause

```
abb01f1d1  feat(shared-kernel): fix outbox worker to immediately dead-letter
           unknown event types (#491)
           Task-Ref: task-017
```

**Files touched by this commit:**
- `.hyperloop/worker-result.yaml` (deleted — protocol artifact that must not appear)
- `src/api/infrastructure/outbox/composite.py`
- `src/api/infrastructure/outbox/worker.py`
- `src/api/shared_kernel/outbox/exceptions.py`
- `src/api/tests/unit/infrastructure/outbox/test_composite.py`
- `src/api/tests/unit/infrastructure/outbox/test_worker.py`
- `src/api/tests/unit/management/application/test_knowledge_graph_service.py`
- `src/api/tests/unit/shared_kernel/outbox/test_exceptions.py`

**Why this is a hard block:**
1. The commit carries `Task-Ref: task-017` — a different task.
2. It introduces `shared_kernel/outbox/exceptions.py` (36 lines) which does NOT
   exist on alpha. Merging would introduce task-017 work to alpha without proper
   attribution.
3. It touched `test_knowledge_graph_service.py` — the same file the task-039
   work touches, making it impossible to isolate what each task added.
4. It causes `check-worker-result-not-committed.sh` to fail because it contains
   a `worker-result.yaml` deletion in the branch commit log.

---

## Required Fix

Drop the foreign commit via interactive rebase:

```bash
git rebase -i $(git merge-base HEAD alpha)
# In the editor, change 'drop' for:
#   abb01f1d1  feat(shared-kernel): fix outbox worker to immediately dead-letter ...
git push --force-with-lease origin hyperloop/task-039
```

After the drop, only 2 commits remain on the branch:
- `ec1f3d7ed` — fix(graph): enforce commit/rollback on all code paths and advisory lock atomicity in AGEGraphProvisioner
- `1f05be0e0` — test(iam): add missing spec coverage for tenant name validation and deletion ordering

Re-run `bash .hyperloop/checks/check-run-backend-suite.sh` after the rebase to
confirm the suite passes (the pre-existing failures noted above will still appear
but they are not regressions introduced by this branch).

---

## task-039 Code Quality (the two genuine commits)

These are reviewed independently and are correct:

**AGEGraphProvisioner (`tenant_graph_handler.py`)**
- Advisory lock via `pg_advisory_xact_lock(hashtext(%s)::bigint)` is acquired
  before the existence check — makes check+create atomic per spec.
- `conn.rollback()` called on the no-op (graph-already-exists) path — satisfies
  the spec requirement that "the database connection MUST be properly committed
  or rolled back on all code paths (including the no-op/exists path)".
- `conn.commit()` called on the creation path (unchanged from before).
- Exception path: `conn.rollback()` + `return_connection` in finally block (unchanged).

**Tests (`test_tenant_graph_handler.py`)**
- `test_rollback_or_commit_called_on_no_op_path`: verifies commit or rollback on the no-op path.
- `test_advisory_lock_acquired_for_atomicity`: verifies lock is acquired before
  existence check (checks call ordering in mock).
- Updated `test_rolls_back_on_create_failure`: correctly updated for the 3-call
  sequence (lock → existence check → create_graph).
All three correctly target the spec requirement.

**Tenant name validation tests (`test_tenant_bootstrap_routes.py`)**
- Empty name → 422, service never called. ✓
- 256-char name → 422, service never called. ✓
- 255-char name (boundary) → 200, service called. ✓

**Deletion ordering test (`test_tenant_service.py`)**
- Uses real `Workspace` aggregates (not mocks). ✓
- `deletion_order.index("Grandchild") < deletion_order.index("Child")` and
  `deletion_order.index("Child") < deletion_order.index("Root")`. ✓
- Provides workspaces in wrong order to confirm service sorts them. ✓

**KnowledgeGraphService credential cleanup (`test_knowledge_graph_service.py`)**
- Verifies `secret_store.delete` called exactly once for the DS with
  `credentials_path` and not for the DS without. ✓
- Note: this file is also touched by the foreign commit (`abb01f1d1`). After
  dropping the foreign commit, verify that the task-039 additions to this file
  are preserved intact.

**Commit trailers**: Both task-039 commits carry correct `Task-Ref: task-039`
and `Spec-Ref: specs/iam/tenants.spec.md@c40320f0de04dd5f9a901d024e2d8e94f502f3ed`.

**No direct logger/print usage**: confirmed clean.
**No MagicMock for domain aggregates**: real `Workspace` and `Tenant` instances used.
**No hardcoded secrets**: confirmed clean.