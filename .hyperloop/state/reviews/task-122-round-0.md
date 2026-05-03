---
task_id: task-122
round: 0
role: verifier
verdict: fail
---
## Review Summary for task-122 (branch: hyperloop/task-122)

**Branch:** hyperloop/task-122
**Commits:** 1 commit ahead of alpha (`d20373779`)
**Diff:** 119 lines added to `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`

---

## Checklist Results

### 1. Unit Tests — PASS
- Backend: 2931 tests pass (`uv run pytest tests/unit`)
- Frontend: 1775 tests pass (`vitest run` in `src/dev-ui`)
- Architecture: 40 boundary tests pass (`test_architecture.py`)

### 2. Linting — PASS
- `ruff check .` reports zero violations.

### 3. Formatting — PASS
- `ruff format --check .` reports 561 files already formatted.

### 4. Type Checking — PASS
- `mypy` reports zero errors in 561 source files.
- `vue-tsc` reports no type errors.

### 5. Architecture Boundary Tests — PASS
- All 40 `pytest-archon` tests pass.

### 6. Integration Tests — N/A
- This branch adds frontend tests only; no infrastructure changes.

### 7. Code Review — **FAIL**

Two tests in the new `describe('Sync Monitoring - trigger shows progress immediately after trigger', ...)` block are **non-falsifiable (tautological)** — they cannot detect regressions in production code because they test their own inline logic rather than any real implementation.

#### Finding 1: Tautological test at line 424
```typescript
it('polling starts after trigger when new run is active', async () => {
  let pollingStarted = false
  let hasActiveSyncs = false

  async function triggerSyncAndStartPolling() {
    hasActiveSyncs = true          // hardcoded — never conditional on any mock/API
    if (hasActiveSyncs) {          // always true, branch always taken
      startPolling()
    }
  }
  await triggerSyncAndStartPolling()
  expect(pollingStarted).toBe(true) // trivially passes regardless of production code
})
```

**Problem:** `hasActiveSyncs` is set to `true` unconditionally inside the test function itself — the `if (hasActiveSyncs)` branch is therefore always taken. No matter how the real polling/composable code is written or broken, this test always passes.

**Fix:** Connect this to a real mock boundary. E.g., inject `isActiveSync` as a function that reads from a mock `dataSources` array, call `loadDataSources()` as a `vi.fn()` that sets state, and verify `startPolling` is called only when the returned data contains an active run.

#### Finding 2: Tautological test at line 445
```typescript
it('polling does NOT start when trigger fails (no active run)', () => {
  let pollingStarted = false
  let triggerFailed = true

  if (!triggerFailed) {   // always false — startPolling() can never execute
    startPolling()
  }
  expect(pollingStarted).toBe(false)  // trivially passes
})
```

**Problem:** `triggerFailed` is hardcoded to `true` and the only path that would call `startPolling()` is guarded by `!triggerFailed` (always `false`). `pollingStarted` is guaranteed to remain `false` regardless of any production code.

**Fix:** Use a `vi.fn()` that throws on the API call, assert that the catch block is entered (e.g., via a mock error toast), and verify `startPolling` was not called.

---

## Commit Trailers — PASS
- `Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da` ✓
- `Task-Ref: task-122` ✓

## No Secrets / No Logger Usage / No DDD Violations — PASS

---

## Notes (Non-blocking)

- The `check-partial-error-assertions.sh` script reported 2 OR-chained assertions in `tests/unit/query/test_mcp_query_service.py` (lines 209 and 298). These are pre-existing on `alpha` — **not introduced by this branch** — but the implementing team should note this as technical debt.

- The four remaining tests in the new `describe` block (tests 1, 4, 5, 6) are acceptable: they use `vi.fn()` mocks properly and exercise real conditional paths (e.g., the error toast test actually throws from the inline `apiFetch` and catches it).

---

## Action Required

Fix tests 2 and 3 so they are falsifiable: replace the hardcoded boolean assignments with mock functions or conditional logic that is actually driven by the test inputs (not set unconditionally inside the test function body). The tests must be able to fail if the production polling code is wrong.