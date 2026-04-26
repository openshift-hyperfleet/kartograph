---
task_id: task-038
round: 0
role: verifier
verdict: fail
---
## Verification Summary for task-038

**Task:** Add integration tests for MCP authentication endpoint
**Branch:** `hyperloop/task-038`
**Verifier ran checks from:** `/home/jsell/code/kartograph/worktrees/workers/task-038/src/api`

---

## Check Results

### 1. Unit Tests — PASS
```
2478 passed, 47 warnings in 61.98s
```
All 2,478 unit tests pass with zero failures or errors.

### 2. Linting (ruff check) — PASS
```
All checks passed!
```

### 3. Formatting (ruff format) — PASS
```
485 files already formatted
```

### 4. Type Checking (mypy) — PASS
```
Success: no issues found in 485 source files
```

### 5. Architecture Boundary Tests — PASS
```
40 passed in 0.23s
```
All pytest-archon DDD boundary tests pass.

### 6. Integration Tests — NOT RUN
Integration tests require a running dev instance (`make instance-up`). Not run for this review as the branch has disqualifying check failures that must be resolved first.

### 7. Code Review — MIXED

**Commit trailers (Spec-Ref, Task-Ref):** PRESENT
The delivery commit `f633f241` has both required trailers:
```
Spec-Ref: specs/shared-kernel/tenant-context.spec.md@b68605133f2258e79280a70c9d0638f97cb7f539
Task-Ref: task-038
```

**Spec scenario coverage:** COMPLETE
`tests/integration/test_mcp_authentication.py` covers all four MCP Authentication scenarios:
1. API key authentication — tenant resolved from key scope, no X-Tenant-ID needed ✓
2. Bearer token fallback — JWT + X-Tenant-ID accepted when no API key ✓
3. Authentication failure — 401 returned for missing/invalid credentials ✓
4. Service unavailability — 503 documented + skipped with clear unit-test cross-reference ✓

**DOO compliance:** BORDERLINE
`check-no-direct-logger-usage.sh` flags `src/api/query/presentation/mcp.py:197`. Inspection shows the `print()` is inside a docstring `Examples:` block (not executable code). This file was not modified by task-038. However, the flag is legitimate because the same violation exists in alpha and the stale branch has not picked up alpha's process fixes (commits `44101233` and `eee15b4a`).

**No MagicMock/AsyncMock on domain aggregates:** PASS
No fake-success notifications or coming-soon stubs detected.

---

## Failing Process Checks

### CRITICAL FAIL: Branch is 24 commits behind alpha

```
check-branch-rebased-on-alpha.sh output:
STALE BRANCH: This branch is 24 commit(s) behind 'alpha'.

Commits on 'alpha' not yet incorporated into this branch:
eee15b4a chore(process): prohibit literal anti-pattern code in test docstrings
44101233 fix(process): exclude test dirs from property-merge check; fix arg-less scripts
f36fc292 chore(process): handle "Agent future missing or failed" via verdict discovery
b6860513 feat(tasks): add task-038 for MCP tenant context authentication
6551edb8 chore(process): require proof of rebase execution, reject repeated stale verdicts
...
```

The branch must be rebased onto current alpha before submission.
**Fix:** `git rebase alpha` from within the task-038 worktree, then confirm with `bash .hyperloop/checks/check-branch-rebased-on-alpha.sh` showing `OK:`.

### CRITICAL FAIL: State file contamination — 24 `.hyperloop/state/` files committed on this branch

```
check-no-state-file-commits.sh output:
FAIL: The following .hyperloop/state/ files are present in branch commits:

  .hyperloop/state/intake/2026-04-25-eighth-run.md
  .hyperloop/state/intake/2026-04-25-ninth-run.md
  .hyperloop/state/intake/2026-04-25-seventh-run.md
  .hyperloop/state/reviews/task-001-round-0.md
  .hyperloop/state/reviews/task-007-round-0.md
  .hyperloop/state/reviews/task-007-round-1.md
  .hyperloop/state/reviews/task-008-round-1.md
  .hyperloop/state/reviews/task-010-round-0.md
  .hyperloop/state/reviews/task-014-round-0.md
  .hyperloop/state/reviews/task-014-round-1.md
  .hyperloop/state/reviews/task-017-round-1.md
  .hyperloop/state/reviews/task-018-round-0.md
  .hyperloop/state/reviews/task-020-round-0.md
  .hyperloop/state/tasks/task-002.md
  .hyperloop/state/tasks/task-004.md
  .hyperloop/state/tasks/task-005.md
  .hyperloop/state/tasks/task-006.md
  .hyperloop/state/tasks/task-009.md
  .hyperloop/state/tasks/task-011.md
  .hyperloop/state/tasks/task-012.md
  .hyperloop/state/tasks/task-013.md
  .hyperloop/state/tasks/task-015.md
  .hyperloop/state/tasks/task-019.md
  .hyperloop/state/tasks/task-038.md
```

Orchestrator-managed state files must never be committed to a task branch. Their presence causes permanent merge conflicts during rebase. This is the highest-severity process violation — it makes the branch effectively un-rebatable without history rewriting.

**Fix:** The cleanest resolution is to:
1. Identify the task's actual delivery commits (only `f633f241` — `tests/integration/test_mcp_authentication.py`).
2. Cherry-pick that commit onto a fresh branch from current alpha:
   ```
   git checkout alpha
   git checkout -b hyperloop/task-038-v2
   git cherry-pick f633f241
   ```
3. Confirm `check-no-state-file-commits.sh` and `check-branch-rebased-on-alpha.sh` both pass.

### FAIL: Direct print() call (pre-existing, but not fixed)

`check-no-direct-logger-usage.sh` flags:
```
/src/api/query/presentation/mcp.py:197:  print(source["content"])  # Full AsciiDoc content starting from title
```
This `print()` is in a docstring `Examples:` block, not in executable logic, and was not introduced by task-038. However, it exists on this branch and the check fails. After rebasing, verify whether alpha's updated check scripts (`44101233`) exclude docstring examples — if not, this violation must be resolved.

---

## What the Implementation Got Right

The integration test file itself is well-constructed:
- All four spec scenarios are covered with appropriately scoped test classes
- The 503 scenario is legitimately skipped with a clear cross-reference to the unit test that covers it (`test_returns_503_when_validator_raises`)
- Tests use `asgi_lifespan` + `httpx.AsyncClient` — correct integration test pattern
- The `WWW-Authenticate` header assertion is included per the spec
- No `MagicMock`/`AsyncMock` on domain collaborators
- The `tenant_auth_headers` fixture correctly exercises the Bearer token fallback path

The quality of the test content is not the problem. The problem is purely process: the branch was never rebased and accumulated state file contamination.