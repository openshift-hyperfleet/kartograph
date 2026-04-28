---
task_id: task-005
round: 0
role: verifier
verdict: fail
---
## Verifier Verdict — task-005 (specs/graph/schema.spec.md)

Worker: verifier
Date: 2026-04-28

---

## Summary

The implementation itself is correct and well-structured: the `GET /graph/schema/ontology`
endpoint was added cleanly, all spec scenarios are covered by tests, and the code follows
project conventions. However, **two automated checks fail** that must be resolved before merge.

---

## Check Results

### 1. Unit Tests — PASS
2485 tests passed, 0 failures, 0 errors.

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format) — PASS
All 495 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero errors across 495 source files.

### 5. Architecture Boundary Tests — PASS
40/40 passed. No bounded-context import violations.

### 6. Integration Tests — NOT RUN
Task only adds a route and route-level tests. No new infrastructure layer touched;
integration suite not required.

### 7. Code Review

#### FAIL — check-worker-result-not-committed.sh
Commit `1a4951e9f` (`feat(graph): add GET /graph/schema/ontology endpoint`) includes
a **deletion** of `.hyperloop/worker-result.yaml`. The check prohibits this file from
appearing in any task-branch commit — including as an addition, modification, or deletion.

**Fix (do not use `git rm` and a new commit — that still leaves a deletion in history):**
```
git rebase -i $(git merge-base HEAD alpha)
# mark 1a4951e9f as 'edit'
# when the rebase pauses:
git restore --staged --worktree -- .hyperloop/worker-result.yaml
git rebase --continue
```
Then verify: `bash .hyperloop/checks/check-worker-result-not-committed.sh`

#### FAIL — check-no-test-regressions.sh
The branch is 3 commits behind the current alpha HEAD. Those 3 alpha commits added
test classes to `tests/unit/graph/presentation/test_routes.py` and introduced two new
test files that are absent on this branch:

Missing test classes (present on alpha, absent from branch):
- `TestKnowledgeGraphScopedMutationsRoute`
- `TestKGMutationsErrorStatusCodes`
- `TestTenantGraphRouting`
- `TestServerErrorProbeEmission`
- `FakeAuthorizationProvider` / `FakeGraphServiceProbe` (helper classes)

Missing test files (present on alpha, deleted from branch):
- `tests/unit/graph/infrastructure/test_age_query_builder_update_merge.py`
- `tests/unit/graph/infrastructure/test_mutation_applier_sort.py`

Other files with fewer net lines than alpha HEAD (8 files flagged).

**Fix:** Rebase the task branch onto the current alpha HEAD. The rebase will incorporate
the newer alpha tests; confirm they still pass before pushing.
```
git rebase alpha
uv run pytest tests/unit -v
```

#### PASS — Task-Ref and Spec-Ref trailers
Both commits carry correct `Task-Ref: task-005` and `Spec-Ref:` trailers.

#### PASS — No direct logger/print usage
All observability flows through domain probes as required.

#### PASS — No foreign task commits
Only task-005 commits on the branch.

#### PASS — No empty test stubs, no future-placeholder comments

#### NOTE — check-partial-error-assertions.sh (pre-existing, not introduced by this task)
The check flags OR-chained assertions in three test files, but `git diff alpha HEAD`
confirms none of these files were modified by this task. The failures are pre-existing
on alpha and should not block this task — but the implementer should not introduce
additional OR-chained assertions.

---

## What Needs Fixing

1. **Rebase onto latest alpha** — picks up the missing test classes and files, resolves
   the test-regression check.
2. **Scrub worker-result.yaml from commit history** — rewrite `1a4951e9f` via interactive
   rebase to remove the file deletion from the commit.

The implementation logic (route handler, response model, service wiring) is correct and
requires no functional changes.