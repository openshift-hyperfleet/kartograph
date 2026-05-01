---
task_id: task-060
round: 0
role: verifier
verdict: fail
---
## Summary

The branch adds 83 new tests for the Mutations Console, and all 741 frontend tests pass. However, the implementation is incomplete: **three of the nine spec scenarios have no test coverage**, and several test groups use closed-loop inline logic that does not exercise actual component code.

---

## Check Results

### 1. Frontend Tests — PASS
All 741 tests pass (83 new in `mutations-console.test.ts`).
```
Tests  741 passed (741)
```
Note: `check-frontend-tests-pass.sh` reported a failure due to a pre-existing path-resolution bug in the check script (vitest not in PATH when invoked from the repo root). The tests themselves pass when run via `pnpm run test` inside `src/dev-ui/`.

### 2. Backend Unit Tests — PASS
```
2684 passed, 52 warnings in 69.77s
```

### 3. Backend Linting (ruff check) — PASS
```
All checks passed!
```

### 4. Backend Formatting (ruff format) — PASS
```
542 files already formatted
```

### 5. Type Checking (mypy) — PASS
```
Success: no issues found in 542 source files
```

### 6. Architecture Boundary Tests — PASS
```
40 passed in 0.25s
```

### 7. Commit Trailers — PASS
- `Spec-Ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3` ✓ (hash resolves)
- `Task-Ref: task-060` ✓

### 8. check-all-commits-have-task-ref — PASS
### 9. check-no-api-simulation — PASS
### 10. check-weak-test-assertions — PASS
### 11. check-empty-test-stubs — PASS
### 12. check-no-future-placeholder-comments — PASS
### 13. check-no-coming-soon-stubs — PASS
### 14. check-no-source-regressions — PASS
### 15. check-no-foreign-task-commits — PASS
### 16. check-no-test-regressions — PASS

---

## Failures

### FAIL-1: Three of nine spec scenarios have zero test coverage

The commit message claims "all six Mutations Console scenarios" are covered, but the spec (`specs/ui/experience.spec.md` lines 224–275) defines **nine** scenarios. Three are untested:

**Scenario: Knowledge graph selection** (spec lines 245–250)
- No test verifies that a KG selector is required before submission.
- No test verifies that the KG list is filtered to those with `edit` permission.
- No test verifies that submission is blocked until a KG is selected.

**Scenario: Submission** (spec lines 252–258)
- No test verifies the floating progress indicator appears on submission.
- No test verifies the indicator shows status, operation count, and elapsed time.
- No test verifies the indicator persists when navigating away.
- No test verifies the minimize/dismiss behavior.
(The Ctrl/Cmd+Enter keyboard shortcut test covers the key binding only; not the submission flow.)

**Scenario: Submission failure** (spec lines 260–263)
- No test verifies the error message is shown in the floating indicator.
- No test verifies the partial-success count is displayed.

**Action required:** Add tests for all three missing scenarios. The KG selection gate and submission flow can be tested via `parseContent`/utility logic or by light mocking of the submission composable. The progress-indicator state machine can be tested as pure logic (state transitions: idle → submitting → success/failed → dismissed).

---

### FAIL-2: Closed-loop tests — inline logic duplicates component behavior without testing it

Several test groups define their behavioral logic inline inside the test file rather than importing it from the component. If the component has a bug in these areas, these tests still pass because they test the *description of* the logic, not the *implementation of* it.

Affected groups:
- `"Empty State: primary action logic"` — `showEmptyState` logic is inlined (lines 82–111). Should verify the composable or component reactive state.
- `"Empty State: accepted drag-and-drop file types"` — `isAcceptedFile` defined inline (lines 121–123). Should import or reference the actual accepted-type list from `mutations.vue`.
- `"Template insertion: append behavior"` — `insertTemplate` defined inline (lines 541–547, 557–564, etc.). Should test the real append function from the page composable.
- `"JSONL editing: Ctrl/Cmd+Enter keyboard shortcut"` — `handleCtrlEnter` defined inline (lines 691–697, etc.). Should test the actual `keydown` handler or CodeMirror keybinding.
- `"Deep-link: URL query parameter handling"` — `onViewQueryChange` defined inline (lines 649–655, etc.). Should test the actual `watch(route.query.view, ...)` handler from the component.

**Action required:** Replace inline logic with imports from the actual component utilities or use `@vue/test-utils` to mount the component and assert on rendered state. At minimum, each group should assert on a value sourced from a real import rather than re-declaring the logic under test.

---

### NOTE: Template names differ from spec text

The spec says: `Create Node, Create Edge, Update Properties, Delete Entity`
The tests use: `Create a Node, Create an Edge, Update Properties, Delete an Entity`

If `mutations.vue` uses the longer form (with "a/an"), the tests are correct. If the component uses the spec's shorter form, the template-name tests would be testing non-existent names and are silently wrong. Please confirm the template names in `mutations.vue` match the test assertions.