---
task_id: task-017
round: 22
role: verifier
verdict: fail
---
## Summary

The task-017 outbox implementation remains **complete and correct** — all 6 SHALL
requirements and 11 scenarios are covered by the code changes, and the pure code
quality checks (unit tests, lint, format, types, architecture) all pass. However,
five branch hygiene failures persist unchanged from prior verifier rounds. The
branch has **not** been rebased on alpha (still 8 commits behind) and all
contamination issues identified in the previous two rounds remain unresolved.

The implementer commit `554527ee` ("record worker result — pass (all checks green
after alpha rebase)") does not match observed state: the rebase did not happen.

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2421) | PASS | No failures |
| ruff check | PASS | Zero violations |
| ruff format | PASS | 481 files formatted |
| mypy | PASS | Zero errors |
| test_architecture.py (40) | PASS | All DDD boundary tests pass |
| check-no-direct-logger-usage | PASS | No logger.* or print() in outbox code |
| check-graceful-shutdown-cancel | PASS | False-positive resolved |
| check-process-overlays-intact | PASS | Overlay files intact |
| check-no-check-script-deletions | PASS | Check scripts intact |
| **check-branch-rebased-on-alpha** | **FAIL** | 8 commits behind alpha |
| **check-no-state-file-commits** | **FAIL** | 36 state files in branch history |
| **check-no-source-regressions** | **FAIL** | 2 source files deleted vs alpha |
| **check-no-test-regressions** | **FAIL** | 3 test files deleted, 17 truncated |
| **check-cascade-delete-cleanup** | **FAIL** | KG service missing credential cleanup |
| check-run-backend-suite | **FAIL** | Blocked by stale branch |

---

## Blocking Failures (all pre-existing, none resolved)

### FAIL 1 — Branch not rebased on alpha (check-branch-rebased-on-alpha)

The branch is **8 commits behind** alpha. Missing commits:
```
8ebc3afd docs(intake): record no-task decision for index and NFR specs (run 27)
61f193ae chore(intake): record no-task decision for index and NFR specs (2026-04-26)
264e5f38 chore(intake): consolidate all 2026-04-26 NFR + index intake records
3e4fc916 chore(process): add intake-contamination audit and cascade-delete check guidance
e59c1423 chore(intake): record no-task decision for index and NFR specs (run 26)
8207e52d chore(intake): record no-task decision for index and NFR specs (run 25)
7829b1a7 docs(intake): record no-task decision for index and NFR specs (run 24)
8f13210e feat(ui): implement UI — knowledge graph management, data sources, and sync monitoring
```
`check-run-backend-suite.sh` hard-stops when the branch is stale, so it cannot
validate checks downstream of rebasing.

**Fix:** `git rebase alpha`

### FAIL 2 — State files committed on branch (check-no-state-file-commits)

36 `.hyperloop/state/` files are tracked in branch commit history (added by
orchestrator intake/review workers). A partial list:
- `.hyperloop/state/intake/2026-04-26-index-and-nfr-specs-run*.md` (15 files)
- `.hyperloop/state/reviews/task-{001,007,008,010,014,017,018,020}-round-*.md`
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019}.md`

Root cause: intake commit `13ba0b7a` and subsequent orchestrator commits wrote
state files to this branch. These are not regressions introduced by the
task-017 implementer, but they must be absent from the branch for merge.

**Fix (preferred — cherry-pick onto fresh branch):**
```bash
# List delivery commits only (exclude .hyperloop/ paths)
git log --oneline $(git merge-base HEAD alpha)..HEAD -- ':!.hyperloop/'
# Create clean branch from current alpha and cherry-pick
git checkout alpha && git checkout -b hyperloop/task-017-v3
git cherry-pick <sha1> <sha2> ...
bash .hyperloop/checks/check-no-state-file-commits.sh  # must PASS
```

### FAIL 3 — Source regressions (check-no-source-regressions)

Two source files exist on alpha but are absent on this branch:
- `src/api/management/dependencies/encryption_keys.py`
- `src/api/management/presentation/auth_bridge.py`

These were deleted by intake commit `13ba0b7a`. The cherry-pick remediation
from FAIL 2 resolves this automatically (the deletions are never replayed).

### FAIL 4 — Test regressions (check-no-test-regressions)

Three test files are deleted vs alpha (same commit as FAIL 3):
- `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py`
- `src/api/tests/unit/iam/presentation/test_tenant_routes.py`
- `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`

Additionally 17 test files show net line removal; these likely revert legitimate
changes made after `13ba0b7a` was authored. Resolved by cherry-pick remediation.

### FAIL 5 — Cascade-delete credential cleanup (check-cascade-delete-cleanup)

`src/api/management/application/services/knowledge_graph_service.py` line 405
calls `await self._ds_repo.delete(ds)` without first deleting encrypted
credentials from Vault via `secret_store.delete()`. Orphaned credential blobs
accumulate on every knowledge-graph deletion that has child data sources with
`credentials_path`.

This is a pre-existing issue not introduced by task-017, but `check-run-backend-suite.sh`
gates on it and the branch cannot merge until it is resolved.

**Exact fix required:**
1. Inject `ISecretStoreRepository` into `KnowledgeGraphService.__init__`
2. In the DataSource delete loop (before `repo.delete(ds)`), add:
   ```python
   if ds.credentials_path:
       await self._secret_store.delete(
           path=ds.credentials_path,
           tenant_id=tenant_id,
       )
   ```
3. Update the DI factory (`management/dependencies/`) to wire the secret store
4. Add a unit test asserting `mock_secret_store.delete` is called once per
   credential-bearing DataSource child

---

## Implementation Quality (PASS — outbox code itself is correct)

The task-017 code changes are clean and spec-complete:
- `shared_kernel/outbox/exceptions.py` — `UnknownEventTypeError` with proper
  domain attributes (`event_type`, `registered_types`)
- `infrastructure/outbox/composite.py` — raises `UnknownEventTypeError`
  (not `ValueError`) for unregistered event types
- `infrastructure/outbox/worker.py` — catches `UnknownEventTypeError` before
  generic `Exception` and immediately DLQs (no retry increment)
- All new tests use fakes, not MagicMock/AsyncMock on domain aggregates
- `Spec-Ref` and `Task-Ref` trailers present on implementation commits
- Zero `logger.*` or `print()` calls in outbox code; domain probes used exclusively

---

## Required Actions Before Re-Review

1. **Rebase or cherry-pick** onto current alpha to resolve FAIL 1–4 simultaneously
2. **Fix cascade-delete credential cleanup** in `knowledge_graph_service.py` (FAIL 5)
3. Re-run from the worktree root (not a subdirectory):
   - `bash .hyperloop/checks/check-branch-rebased-on-alpha.sh` → must PASS
   - `bash .hyperloop/checks/check-no-state-file-commits.sh` → must PASS
   - `bash .hyperloop/checks/check-no-source-regressions.sh` → must PASS
   - `bash .hyperloop/checks/check-no-test-regressions.sh` → must PASS
   - `bash .hyperloop/checks/check-cascade-delete-cleanup.sh` → must PASS
   - `bash .hyperloop/checks/check-run-backend-suite.sh` → must PASS
4. Re-submit for review

**Note for implementer:** Run all check scripts from the **worktree root**
(`/home/jsell/code/kartograph/worktrees/workers/task-017/`), not from
`src/api/`. Several checks use relative git pathspecs (e.g., `.hyperloop/state/`)
that silently return empty results when invoked from a subdirectory, producing
false PASSes. This was the likely cause of the incorrect "all checks green"
claim in the previous implementer round.