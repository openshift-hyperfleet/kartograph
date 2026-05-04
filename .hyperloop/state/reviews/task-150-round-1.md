---
task_id: task-150
round: 1
role: verifier
verdict: fail
---
## Review Summary

Two blocking failures prevent this task from passing:

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| check-task-owns-branch-commits.sh | **FAIL** | Zero commits above origin/alpha for task-150 |
| Frontend tests (vitest) | **FAIL** | 16 failures — `__all__` sentinel vs `''` mismatch |
| Backend unit tests (pytest) | PASS | 2990 passed |
| Ruff linting | PASS | zero violations |
| Ruff formatting | PASS | all files formatted |
| mypy type checking | PASS | zero errors |
| Architecture boundary tests | PASS | 40 passed |
| check-all-commits-have-task-ref.sh | PASS | No branch-specific commits to check (all skipped as upstream PRs) |

---

## Failing Checks — Actionable Details

### FAIL 1: Zero implementation commits for task-150

`check-task-owns-branch-commits.sh` exits 1:

```
FAIL: Branch has ZERO commits above origin/alpha.

  Branch HEAD:   fcf5e4e86
  origin/alpha:  fcf5e4e8
```

The branch `hyperloop/task-150` HEAD equals `origin/alpha` HEAD. The only commit
visible above local `alpha` is `fcf5e4e86` ("fix(ui): use empty string sentinel…
(#617)"), which carries `Task-Ref: task-146` and is already merged into
`origin/alpha`. No task-150-specific work has been committed.

**How to fix:**
Start fresh from `origin/alpha`, implement the task, and commit with the correct
trailer:
```bash
git checkout -b hyperloop/task-150 origin/alpha
# ... implement the fix ...
git commit -m 'fix(ui): ...' -m '' -m 'Task-Ref: task-150'
```

---

### FAIL 2: 16 frontend tests failing

Running `npx vitest run` in `src/dev-ui/` shows 5 failed test files / 16 failed
tests. Every failure is a sentinel mismatch: the tests assert that the query
console uses `'__all__'` as the unscoped KG selector sentinel, but the
implementation uses `''` (empty string).

**Failing test files:**
- `app/tests/query-history.test.ts` (3 failures)
- `app/tests/query-kg-selector.test.ts` (3 failures)
- `app/tests/query.test.ts` (4 failures)
- `app/tests/task-125-spec-alignment.test.ts` (4 failures)
- `app/tests/task-129-spec-alignment.test.ts` (2 failures)

**Example failure:**
```
expect(queryVue).toContain("selectedKgId.value === '__all__'")
```
The source file now uses `selectedKgId.value || undefined` (with `''` initial
value) instead of the `=== '__all__'` sentinel check.

**How to fix:** The tests and implementation are out of sync. Per project TDD
rules, tests must not be changed to match a broken implementation. The
implementation (`query/index.vue`) must be reverted to use the `'__all__'`
sentinel (matching what the tests specify), OR the tests must be legitimately
updated as part of a task that redesigns the sentinel — with proper
`Task-Ref: task-150` commits and a full explanation.

The `check-frontend-tests-pass.sh` check enforces: "Never submit with failing
tests." This is a blocking requirement.