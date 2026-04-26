---
task_id: task-017
round: 21
role: verifier
verdict: fail
---
## Summary

The task-017 outbox implementation is **complete and correct** — all 6 SHALL
requirements and 11 scenarios are covered, unit/lint/format/type/arch tests all
pass. However, the branch carries multiple check failures caused by orchestrator
worker commits operating on this branch that must be resolved before merge.

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2421) | PASS | No failures |
| ruff check | PASS | Zero violations |
| ruff format | PASS | 481 files formatted |
| mypy | PASS | Zero errors |
| test_architecture.py (40) | PASS | All DDD boundary tests pass |
| check-branch-rebased-on-alpha | PASS | 1 commit behind (within 5 limit) |
| check-no-state-file-commits | **FAIL** | 39 state files committed on branch |
| check-no-source-regressions | **FAIL** | 2 source files deleted |
| check-no-test-regressions | **FAIL** | 3 test files deleted, many modified |
| check-cascade-delete-cleanup | **FAIL** | KG service missing credential cleanup |
| check-graceful-shutdown-cancel | FAIL* | False positive — .cancel() in docstring only |
| check-git-state-exclude | FAIL* | Local config only — not a code issue |
| check-run-backend-suite | **FAIL** | Aggregates failures above |

*False positive / local-only — not blocking implementation merge.

---

## Blocking Failures

### FAIL 1 — State files committed on branch (check-no-state-file-commits)

39 `.hyperloop/state/` files are present in branch commit history (added by
intake and review workers). Affected examples:
- `.hyperloop/state/intake/2026-04-26-index-and-nfr-specs-run*.md` (18 files)
- `.hyperloop/state/reviews/task-{001,007,008,010,014,017,018,020}-round-*.md`
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019,039}.md`

Root cause: intake commit `13ba0b7a` and subsequent process commits added state
files to this branch's history.

**Fix:** Cherry-pick delivery commits onto a fresh branch from alpha:
```
git log --oneline $(git merge-base HEAD alpha)..HEAD -- ':!.hyperloop/state'
git checkout alpha && git checkout -b hyperloop/task-017-clean
git cherry-pick <delivery-sha> [...]
```

### FAIL 2 — Source regressions (check-no-source-regressions)

Two source files exist on alpha but are deleted on this branch via intake commit
`13ba0b7a chore(intake): record Run 6 review of index and NFR specs`:
- `src/api/management/dependencies/encryption_keys.py`
- `src/api/management/presentation/auth_bridge.py`

**Fix:** Restore from alpha before or during cherry-pick remediation:
```
git checkout alpha -- src/api/management/dependencies/encryption_keys.py
git checkout alpha -- src/api/management/presentation/auth_bridge.py
```

### FAIL 3 — Test regressions (check-no-test-regressions)

Three test files exist on alpha but are deleted on this branch (same intake
commit `13ba0b7a`):
- `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py` (286 lines)
- `src/api/tests/unit/iam/presentation/test_tenant_routes.py` (587 lines)
- `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py` (760 lines)

Additionally, many other test files show net line removals due to modifications by
the same intake commit — those likely revert legitimate changes.

**Fix:** Resolved by cherry-pick remediation from FAIL 1.

### FAIL 4 — Cascade-delete credential cleanup (check-cascade-delete-cleanup)

`src/api/management/application/services/knowledge_graph_service.py` (line 405)
calls `await self._ds_repo.delete(ds)` without first calling `secret_store.delete()`
to clean up encrypted credentials in Vault. This orphans credential blobs.

This check was already flagged in the previous verifier round. It is not introduced
by task-017 but must be fixed on this branch because the check now runs against it.

**Fix per check output:**
1. Inject `ISecretStoreRepository` into `__init__`
2. Before `repo.delete(ds)`, for each ds with `credentials_path`, call:
   `await self._secret_store.delete(path=ds.credentials_path, tenant_id=<tenant_id>)`
3. Update DI factory to wire `ISecretStoreRepository`
4. Add unit test asserting `mock_secret_store.delete` is called per credential-bearing child

---

## Non-Blocking Notes

### check-graceful-shutdown-cancel — False positive
The check flags `worker.py` because it finds both `def stop` and `.cancel()` in
the same file. However, `.cancel()` appears **only in a docstring comment** at
line 130: `"no task.cancel(), so an in-progress"`. The actual `stop()` method
uses `_running = False` + `_shutdown_event.set()` + `await task` — fully correct.
The check script uses a simple grep without context awareness.

### check-git-state-exclude — Local configuration only
`.git/info/exclude` is missing the `.hyperloop/state/` exclusion for this worktree.
Fix locally: `echo '.hyperloop/state/' >> "$(git rev-parse --git-dir)/info/exclude"`
This does not block the implementation.

---

## Implementation Quality (All PASS)

The task-017 code changes themselves are clean:
- `shared_kernel/outbox/exceptions.py` — new `UnknownEventTypeError` with proper
  domain structure (`event_type`, `registered_types` attributes)
- `infrastructure/outbox/composite.py` — raises `UnknownEventTypeError` instead of
  `ValueError` for unknown event types
- `infrastructure/outbox/worker.py` — catches `UnknownEventTypeError` before generic
  `Exception` and immediately moves entry to DLQ (no retry)
- New test classes: `TestOutboxWorkerRetryBehavior`, `TestOutboxWorkerTransactionAtomicity`,
  `TestOutboxWorkerConcurrentSafety`, `TestOutboxWorkerIdempotency`
- `tests/unit/shared_kernel/outbox/test_exceptions.py` — TDD tests written first
- Spec-Ref and Task-Ref trailers present on all implementation commits
- Zero logger.* or print() calls in outbox code (domain probes used exclusively)
- No MagicMock/AsyncMock on domain aggregates

---

## Required Actions Before Re-Review

1. Cherry-pick delivery commits onto fresh branch from current alpha (removes
   state file contamination AND restores accidentally deleted source/test files)
2. Fix cascade-delete credential cleanup in `knowledge_graph_service.py`
3. Re-run `check-no-state-file-commits.sh` → must PASS
4. Re-run `check-no-source-regressions.sh` → must PASS
5. Re-run `check-no-test-regressions.sh` → must PASS
6. Re-run `check-cascade-delete-cleanup.sh` → must PASS
7. Re-run `check-run-backend-suite.sh` → must PASS
8. Re-submit for review