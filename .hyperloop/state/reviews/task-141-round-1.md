---
task_id: task-141
round: 1
role: verifier
verdict: fail
---
## Review of task-141 — HTTP-level integration tests for query_graph successful response shape

Branch: `hyperloop/task-141`
Task commit: `9ec34d100 test(query): add HTTP-level integration tests for query_graph successful response shape`

---

## Check Results

### 1. Backend Unit Tests — PASS
```
cd src/api && uv run pytest tests/unit -v
2990 passed, 52 warnings in 90.31s
```

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format --check) — PASS
568 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero errors in 568 source files.

### 5. Architecture Boundary Tests — PASS
`tests/unit/test_architecture.py` — 40 passed.

### 6. Frontend Tests — FAIL
```
Test Files  5 failed | 48 passed (53)
Tests       16 failed | 2477 passed (2493)
```

**Root cause:** The `check-no-test-regressions.sh` confirmed these failures are
**pre-existing on origin/alpha** and were NOT introduced by task-141's commit.

The mismatch originates from a conflict between three merged commits on origin/alpha:
- task-142 (`0035863e4`): changed test files to expect `__all__` as the KG scope sentinel
- task-143 (`3915b6dba`): changed source code back to use `''` (empty string)
- task-144 (`1309cd4af`): further aligned source to use `''` sentinel

The tests still assert `__all__` while the code uses `''`. This means `check-frontend-tests-pass.sh` fails even though task-141 introduced no regressions.

**Failing test names (16 total, 5 files):**

In `app/tests/query-kg-selector.test.ts`:
- `selectedKgId is initialised to the __all__ sentinel` — expects `ref('__all__')`, code has `ref('')`
- `the selector includes an "All knowledge graphs" unscoped option` — expects `value="__all__"`, code has `value=""`
- `the selector shows a Scoped badge when a KG is selected` — expects `selectedKgId !== '__all__'`, code has `v-if="selectedKgId"`
- `gates selectedKgId using __all__ sentinel check before passing to queryGraph` — expects `=== '__all__'`, code has `|| undefined`

In `app/tests/query.test.ts` (4 failures), `app/tests/query-history.test.ts` (3 failures),
`app/tests/task-125-spec-alignment.test.ts` (4 failures), `app/tests/task-129-spec-alignment.test.ts` (1 failure):
— all the same `__all__` vs `''` mismatch.

**Required fix (in src/dev-ui/app/tests/):**

These 5 test files must be updated to expect `''` (empty string) as the sentinel,
matching the current source in `src/dev-ui/app/pages/query/index.vue`:

| File | Lines to update |
|------|-----------------|
| `query-kg-selector.test.ts` | `value="__all__"` → `value=""`, `ref('__all__')` → `ref('')`, `!== '__all__'` → `selectedKgId`, `=== '__all__'` → `!selectedKgId` |
| `query.test.ts` | same sentinel changes |
| `query-history.test.ts` | same sentinel changes |
| `task-125-spec-alignment.test.ts` | same sentinel changes |
| `task-129-spec-alignment.test.ts` | same sentinel change |

The source code in `query/index.vue` is correct per spec (uses `''` + `|| undefined` gate).
The tests were incorrectly updated in task-142 and need to be reverted to expect `''`.

### 7. Process Check — FAIL
`check-commit-msg-hook-has-guard.sh` FAILS:

```
FAIL: commit-msg hook not found at
  /home/jsell/code/kartograph/.git/worktrees/task-141/hooks/commit-msg
```

The commit-msg hook was not installed before the task-141 commit was made.
The commit trailer block itself is correctly formatted (Spec-Ref, Task-Ref, and
Co-Authored-By are contiguous with no blank lines), so this did not cause a
trailer parse failure. Nevertheless, the check fails and the process requires
the hook to be installed.

**Required fix:**
```bash
bash .hyperloop/checks/install-git-commit-msg-hook.sh
bash .hyperloop/checks/check-all-commits-have-task-ref.sh
```

---

## Code Quality Assessment — PASS

The integration test file `test_query_mcp_http_success.py` is well-written:

- ✓ No `print()` or `logger.*` calls
- ✓ No `MagicMock`/`AsyncMock`/`patch` — uses real ASGI app with in-process transport
- ✓ Correct class-scoped fixtures with `loop_scope="class"` to handle the
  non-restartable `StreamableHTTPSessionManager` lifespan constraint
- ✓ Pre/post cleanup in `provisioned_success_graph` fixture
- ✓ Direct DB insertion pattern for API key (no Keycloak dependency)
- ✓ Explicit, non-tautological assertions with failure messages
- ✓ Covers both the data-present and empty-result paths
- ✓ Spec-Ref and Task-Ref trailers present and contiguous

---

## Summary

The task-141 implementation (backend integration tests) is of good quality and
introduces no regressions. However, two blocking check failures prevent passing:

1. **Frontend test suite fails (16 tests)** — pre-existing `__all__` vs `''`
   sentinel mismatch in 5 test files, originating from the task-142 commit.
   Fix: update the 5 test files to use `''` instead of `__all__`.

2. **Missing commit-msg hook** — install the hook and verify trailers.