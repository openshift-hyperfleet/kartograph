---
task_id: task-045
round: 15
role: verifier
verdict: fail
---
## Verification Summary

Branch: hyperloop/task-045 (8 commits ahead of alpha @ baab78e8)
Primary deliverable: Query Console KG scope selector (Req: Query Console — Scenario: Knowledge graph context)

---

## Check Results

| Check | Result | Notes |
|-------|--------|-------|
| check-run-backend-suite.sh | PASS | All 28 sub-checks pass |
| Unit tests (2695) | PASS | `uv run pytest tests/unit -v` |
| Architecture boundary tests (40) | PASS | `test_architecture.py` |
| ruff linting | PASS | Zero violations |
| ruff format | PASS | All files formatted |
| mypy type checking | PASS | Zero errors (545 source files) |
| Frontend tests (765) | PASS | 24 test files pass |
| check-branch-rebases-cleanly.sh | PASS | No conflicts |
| check-branch-rebased-on-alpha.sh | PASS | 0 commits behind |
| check-all-commits-have-task-ref.sh | PASS | All 7 task commits have Task-Ref: task-045 |
| check-no-foreign-task-commits.sh | PASS | No foreign task refs |
| check-no-api-simulation.sh | PASS | No setTimeout-sleep simulation |
| check-no-direct-logger-usage.sh | PASS | No logger.*/print() in production code |
| check-selector-forwarding.sh | PASS | selectedKgId forwarded to executeQuery() |
| check-pages-have-tests.sh | PASS | 13/13 pages have test coverage |
| **check-frontend-scenario-labels.sh (Data Source Connection)** | **FAIL** | See Finding 1 |
| **check-frontend-scenario-labels.sh (Ontology Design)** | **FAIL** | See Finding 2 |
| **Inline component logic copies** | **FAIL** | See Finding 3 |

---

## Findings

### Finding 1 (BLOCKING): Missing scenario labels — Data Source Connection requirement

Running `check-frontend-scenario-labels.sh` against the Data Source Connection requirement returns exit code 1:

```
MISSING : Adapter type selection
MISSING : Connection configuration
COVERED : Credential handling
```

The spec defines three scenarios under `### Requirement: Data Source Connection`. The commits on this branch claim to cover data source wizard logic in `data-sources.test.ts`, but neither "Adapter type selection" nor "Connection configuration" appear as describe()/it() labels (or anywhere) in any test file. The tests that logically cover this behavior are labelled "Step Navigation" and "Form Validation", not the spec scenario names.

**Fix required:** Add describe() or it() blocks whose labels include the exact scenario names:
- `'Adapter type selection'` (select adapter type first; form adapts to show adapter-specific fields)
- `'Connection configuration'` (provide repo URL, access token; defaults inferred)

Or, if these scenarios are out of scope for task-045, file formal blockers at `.hyperloop/blockers/` — do NOT omit silently.

---

### Finding 2 (BLOCKING): Missing scenario label — Ontology Design requirement

Running `check-frontend-scenario-labels.sh` against the Ontology Design requirement returns exit code 1:

```
COVERED : Intent description
COVERED : Agent-proposed ontology
COVERED : Ontology review and approval
COVERED : Individual type editing
MISSING : Ontology change after initial extraction
```

The test at `knowledge-graphs.test.ts:293` covers the THEN clause (warn + confirm before applying changes) but is labelled `'Ontology Edit - Post-Extraction Confirmation Gate'` rather than `'Ontology change after initial extraction'`. The check script performs a case-insensitive substring search and finds no match.

**Fix required:** Rename the describe block or add a comment/label containing the exact text `'Ontology change after initial extraction'` so the check script can attribute coverage to this scenario.

---

### Finding 3 (BLOCKING): Inline component logic copies — PARTIAL coverage

Per the verifier overlay: *"A frontend test group that defines its own inline copy of component logic is PARTIAL, not COVERED."*

Three test files introduced in this branch define inline state machines and wrapper functions that mirror production component logic instead of importing it:

**`src/dev-ui/app/tests/data-sources.test.ts`** (lines ~1–980):
- Defines `nextStep()`, form-validation logic, `makeWizardState()`, `connToken` check functions inline
- These shadow the real functions in `pages/data-sources/index.vue` without importing from it

**`src/dev-ui/app/tests/sync-logs.test.ts`** (lines ~1–356):
- Defines `makeLogState()` with `fetchRunLogs()`, `viewLogs()`, `closeLogs()` inline
- Does not import from the real page component

**`src/dev-ui/app/tests/backend-api-alignment.test.ts`** (lines ~1–569):
- Each test defines an inline wrapper (e.g. `async function listGroups()`) that calls a `vi.fn()` spy, then asserts the spy was called with expected arguments
- These tests are tautological: the wrapper IS the subject under test; a regression in the real `useIamApi.ts` would NOT be caught

**Fix required:**

For data-sources.test.ts and sync-logs.test.ts: Import real composables or mount the page with `@vue/test-utils`. Where a pure function (like `buildQueryGraphArgs` in `useQueryApi.ts`) is exported, import it directly (this pattern is already correctly used in `knowledge-graphs.test.ts` lines 2 and 595–622).

For backend-api-alignment.test.ts: Import the real functions from `useIamApi.ts` and assert on those. Alternatively, mount the relevant page with mocked `useFetch`/`$fetch` and assert the URL each call was made with.

---

## Primary Task Deliverable Assessment

The primary deliverable — the Query Console KG scope selector (Requirement: Query Console — Scenario: Knowledge graph context) — IS correctly implemented and tested:

- `pages/query/index.vue` has `selectedKgId`, `knowledgeGraphs`, `kgScopeLabel`, and passes `selectedKgId.value || undefined` to `queryGraph()`
- `knowledge-graphs.test.ts` imports the real `buildQueryGraphArgs` from `useQueryApi.ts` (not an inline copy) and verifies the exact MCP arg behavior
- `check-selector-forwarding.sh` passes — `selectedKgId.value` appears inside the `executeQuery()` async body

The backend ontology proposal endpoint (POST `/management/ontology-proposals`) and ontology field on CreateDataSourceRequest are correctly implemented with real unit tests that exercise the actual Pydantic models and route handlers.

---

## Required Actions Before Resubmission

1. Add exact spec scenario label strings for "Adapter type selection", "Connection configuration", and "Ontology change after initial extraction" in the respective test files (or file formal blockers).
2. Replace inline logic copies in `data-sources.test.ts`, `sync-logs.test.ts`, and `backend-api-alignment.test.ts` with real imports from production modules (or `@vue/test-utils` mounts).
3. Re-run `bash .hyperloop/checks/check-frontend-scenario-labels.sh` for all three failing requirements and confirm exit 0 before resubmitting.