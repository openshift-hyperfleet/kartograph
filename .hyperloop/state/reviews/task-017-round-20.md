---
task_id: task-017
round: 20
role: verifier
verdict: fail
---
## Summary

The task-017 outbox implementation is spec-complete and the unit test suite
passes (2421 tests). However, the backend check suite reports 4 failures when
run correctly from the project root, blocking merge.

The previous verifier's `verdict: pass` was a false positive: the backend suite
was invoked from `.hyperloop/checks/` instead of the project root. All relative
pathspec-based checks (`'src/'`, `'.hyperloop/state/'`, etc.) silently matched
nothing from that subdirectory, producing spurious PASSes. Running
`bash .hyperloop/checks/check-run-backend-suite.sh` from the **project root**
(`/home/jsell/code/kartograph/worktrees/workers/task-017`) reveals 4 real
failures.

---

## Check Results (run from project root)

| Check | Result |
|---|---|
| check-no-check-script-deletions.sh | ✓ PASS |
| check-process-overlays-intact.sh | ✓ PASS |
| check-branch-has-commits.sh | ✓ PASS |
| check-branch-rebased-on-alpha.sh | ✓ PASS (2 commits behind — within threshold) |
| **check-no-state-file-commits.sh** | **✗ FAIL** |
| **check-no-source-regressions.sh** | **✗ FAIL** |
| **check-no-test-regressions.sh** | **✗ FAIL** |
| check-empty-test-stubs.sh | ✓ PASS |
| check-domain-aggregate-mocks.sh | ✓ PASS |
| check-no-direct-logger-usage.sh | ✓ PASS |
| check-no-coming-soon-stubs.sh | ✓ PASS |
| check-weak-test-assertions.sh | ✓ PASS |
| check-di-wiring-updated.sh | ✓ PASS |
| check-pytest-env-skip-if-set.sh | ✓ PASS |
| check-cascade-delete-empty-collection-mocks.sh | ✓ PASS |
| **check-new-checks-pass-on-head.sh** | **✗ FAIL** |

---

## Failure Details

### FAIL 1 — check-no-state-file-commits.sh (39 state files committed)

`git diff --name-only MERGE_BASE HEAD -- '.hyperloop/state/'` from the project
root shows 39 state files committed on this branch, including:

- `.hyperloop/state/intake/2026-04-26-index-and-nfr-specs-run4.md` through
  `-run19.md` (16 intake files)
- `.hyperloop/state/reviews/task-001-round-0.md`, `task-007-round-{0,1}.md`,
  `task-008-round-1.md`, `task-010-round-0.md`, `task-014-round-{0,1}.md`,
  `task-017-round-1.md`, `task-018-round-0.md`, `task-020-round-0.md`
  (9 review files)
- `.hyperloop/state/tasks/task-{002,004,005,006,009,011,012,013,015,019,039}.md`
  (11 task files)

**Root cause:** Orchestrator intake/review workers ran on this branch and
committed state files. These were NOT introduced by the task-017 implementer.

**Fix:** Strip `.hyperloop/state/` additions from branch history (cherry-pick
delivery commits onto a clean branch, or interactive rebase to drop state-file
modifications). Also add `.hyperloop/state/` to `.git/info/exclude` to prevent
recurrence.

---

### FAIL 2 — check-no-source-regressions.sh (2 source files deleted)

Deleted between merge-base (`3f324d21`) and HEAD:

- `src/api/management/dependencies/encryption_keys.py` (29 lines, no spec mandate)
- `src/api/management/presentation/auth_bridge.py` (14 lines, no spec mandate)

**Root cause:** Both files were deleted by commit `13ba0b7a` (`chore(intake):
record Run 6 review of index and NFR specs — no tasks created`), an orchestrator
intake commit. The outbox spec (`specs/shared-kernel/outbox.spec.md`) does not
mandate removal of either file.

**Side-effect:** `knowledge_graph_service.py` lost its secret_store injection
(present on alpha, absent on this branch). This causes `check-cascade-delete-
cleanup.sh` to fail (DataSource cascade delete calls `_ds_repo.delete()` without
`secret_store.delete()` for credential cleanup).

**Fix:** Restore both deleted files:

```bash
git checkout alpha -- src/api/management/dependencies/encryption_keys.py
git checkout alpha -- src/api/management/presentation/auth_bridge.py
```

Also restore the `secret_store` injection in `knowledge_graph_service.py` (diff
against alpha to identify the removed parameters and calls).

---

### FAIL 3 — check-no-test-regressions.sh (3 test files deleted)

Deleted between merge-base and HEAD:

- `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py` (233 lines)
- `src/api/tests/unit/iam/presentation/test_tenant_routes.py` (467 lines)
- `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`
  (607 lines)

**Root cause:** All three were deleted by the same orchestrator intake commit
`13ba0b7a` as the source files above.

**Fix:** Restore all three:

```bash
git checkout alpha -- src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py
git checkout alpha -- src/api/tests/unit/iam/presentation/test_tenant_routes.py
git checkout alpha -- src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py
```

---

### FAIL 4 — check-new-checks-pass-on-head.sh

Two newly-added check scripts fail on HEAD:

- `check-cascade-delete-cleanup.sh` — `knowledge_graph_service.py` calls
  `_ds_repo.delete()` without `secret_store.delete()` (see FAIL 2 above;
  resolving FAIL 2 will fix this).
- `check-git-state-exclude.sh` — `.git/info/exclude` does not contain
  `.hyperloop/state/`.

**Fix for git-state-exclude:**

```bash
echo '.hyperloop/state/' >> "$(git rev-parse --git-dir)/info/exclude"
```

---

## Implementation Quality (Non-blocking — spec coverage is correct)

The task-017 outbox implementation itself is complete and correct:

- **Unit tests:** 2421 passed, 0 failed, 45 warnings — no regressions
- **Linting:** `ruff check .` — zero violations
- **Formatting:** `ruff format --check .` — all 481 files formatted
- **Type checking:** `mypy` — zero errors across 481 source files
- **Architecture boundaries:** `test_architecture.py` — 40/40 PASS
- **Spec coverage:** All 6 SHALL requirements and 11 scenarios implemented:
  - Transactional Event Storage (successful write, rollback) ✓
  - Event Processing (normal, transient failure, dead letter) ✓
  - Idempotent Event Handlers (duplicate delivery) ✓
  - Concurrent Worker Safety (FOR UPDATE SKIP LOCKED) ✓
  - Dual Delivery Mechanism (NOTIFY + polling fallback) ✓
  - Event Fan-Out (multiple handlers, unknown event type → DLQ) ✓
- **Domain probes:** No direct `logger.*` or `print()` calls in outbox code
- **Commit trailers:** `feat(shared-kernel)` and `fix(task-017)` commits
  carry `Spec-Ref: specs/shared-kernel/outbox.spec.md@...` and
  `Task-Ref: task-017`

---

## Required Actions Before Re-Review

1. Strip `.hyperloop/state/` files from branch commit history
2. Add `.hyperloop/state/` to `.git/info/exclude`
3. Restore deleted source files from alpha:
   - `src/api/management/dependencies/encryption_keys.py`
   - `src/api/management/presentation/auth_bridge.py`
4. Restore `secret_store` injection to `knowledge_graph_service.py`
5. Restore deleted test files from alpha:
   - `tests/unit/iam/domain/test_workspace_role_hierarchy.py`
   - `tests/unit/iam/presentation/test_tenant_routes.py`
   - `tests/unit/management/presentation/test_knowledge_graph_routes.py`
6. Run `bash .hyperloop/checks/check-run-backend-suite.sh` from the **project
   root** (not from `.hyperloop/checks/`) — must report ALL PASS
7. Re-submit for review

Note: all failures were introduced by orchestrator workers running on this
branch, not by the task-017 implementer. The delivery commits are clean.