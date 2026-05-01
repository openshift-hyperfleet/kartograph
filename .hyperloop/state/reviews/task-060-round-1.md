---
task_id: task-060
round: 1
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — Mutations Console (specs/ui/experience.spec.md)

## Prior Finding Resolution

### FAIL-1 (Prior): Zero test coverage for three scenarios
STATUS: RESOLVED — tests now exist for all three previously uncovered scenarios:
- "Knowledge graph selection" — test group at mutations-console.test.ts:672-734
- "Submission" — test group at mutations-console.test.ts:747-843
- "Submission failure" — test group at mutations-console.test.ts:854-924

### FAIL-2 (Prior): Closed-loop tests
STATUS: PARTIALLY RESOLVED — critical-path tests (submission gate, KG selection, submission failure, deep-link navigation changes) now import and call real functions from `~/utils/mutationConsole`. However, three test groups still contain inline logic that does not call the component/utility under test:

- **mutations-console.test.ts:54-82** ("Empty state: quick-start templates"): Defines a local `quickStartTemplates` array inline and asserts against it. The actual `quickStartTemplates` array in `mutations.vue` is never imported or called. These tests can never fail if the component removes or renames a template. CLOSED-LOOP.
- **mutations-console.test.ts:576-590** ("Deep-link" first three cases): Uses `'editor' === 'editor'`, `undefined === 'editor'`, and `'other' === 'editor'` as assertions — literal comparisons, not calls to `getEditorVisibilityForViewChange()`. The remaining six tests in that group do call the real function. The first three are CLOSED-LOOP.
- **mutations-console.test.ts:498-518** ("Large-file mode threshold" tests 2-4): Uses `largeContent.length > FIVE_MB` inline. This tests JavaScript's string length comparison, not the actual `readFile()` conditional in mutations.vue. CLOSED-LOOP.

---

## New Findings

### FAIL-3 (New, Critical): API endpoint mismatch — KG ID never sent to backend

Spec (line 255): "the mutations are submitted to the API scoped to the selected knowledge graph"

- Backend endpoint: `POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations` (routes.py:78)
- Frontend call in `useGraphApi.ts:47`: `POST /graph/mutations` — no `knowledge_graph_id` in path or body
- `useMutationSubmission.ts:42` calls `applyMutations(jsonlContent, { signal })` — no KG ID parameter
- `mutations.vue:332` calls `submission.submit(body, opCount)` and at line 350 `submission.submit(jsonlBody, ...)` — selected KG ID (`selectedKnowledgeGraphId.value`) is checked by `canSubmitMutations` but never forwarded to the API call

The selected knowledge graph is gated in the UI but silently dropped before the HTTP request. The API will respond 404 because `/graph/mutations` does not exist as a backend route (the route requires the KG ID path segment).

No test catches this because no test mocks or exercises the actual `applyMutations` HTTP call with a knowledge graph ID.

### FAIL-4 (New): KG selector does not filter by `edit` permission

Spec (line 248): "the selector lists all knowledge graphs the user has `edit` permission on within the current workspace"

- `loadKnowledgeGraphs()` in mutations.vue:115-129 calls `/management/knowledge-graphs`
- That management endpoint filters by VIEW permission (management/presentation/knowledge_graphs/routes.py:40 — "filtered by VIEW permission via SpiceDB")
- No additional client-side edit-permission filter is applied
- Result: the selector shows all KGs the user can view, not only those they can edit
- No test covers this filtering requirement

### FAIL-5 (New): No test for "indicator persists when user navigates away"

Spec (line 257): "the indicator persists when the user navigates away from the mutations console"

- Implementation uses `useState` (useMutationSubmission.ts:30) which persists across Nuxt route changes — this is the correct approach
- `MutationProgress.vue` is present as a global component (shown in template), so it renders outside the mutations page
- However, no test asserts that the state survives a navigation event (e.g., after calling submit and changing route, the indicator is still visible)
- The closest test (mutations-console.test.ts:783-792) only checks that status `!= 'idle'` makes isVisible true — it does not test cross-navigation persistence

---

## Per-Scenario Status

| Scenario | Spec Lines | Implementation | Test Coverage |
|---|---|---|---|
| Empty state | 225-227 | COVERED — two primary actions + four templates in mutations.vue | PARTIAL — template names tests are closed-loop (inline array) |
| JSONL editing | 228-233 | COVERED — CodeMirror with linting/autocomplete/Ctrl+Enter | COVERED — linter, keyboard, parsing tests call real functions |
| Live preview | 234-237 | COVERED — MutationPreview.vue + syncParseResult | COVERED — breakdown by op type, validation warnings tested |
| File upload | 238-244 | COVERED — large-file mode at 5MB, file extension validation | PARTIAL — threshold tests 2-4 are closed-loop |
| Knowledge graph selection | 245-250 | PARTIAL — selector present, but (a) uses view-not-edit endpoint, (b) KG ID not sent to API | PARTIAL — submission gate logic tested via canSubmitMutations; edit-permission filter untested; API routing untested |
| Submission | 251-258 | PARTIAL — floating indicator present with status/count/elapsed; but KG-scoped API call broken (FAIL-3) | PARTIAL — state machine tested; cross-navigation persistence not tested |
| Submission failure | 259-261 | COVERED — indicator shows error, partial operations_applied count | COVERED — state shape tested directly against MutationSubmissionState types |
| Template insertion | 262-265 | COVERED — insertTemplate() appends via getMergedEditorContent | COVERED — append behavior tested via real function |
| Deep-link | 266-269 | COVERED — view=editor and template params handled in onMounted | PARTIAL — first three cases are closed-loop inline assertions |

---

## Failures Required to Fix

1. **FAIL-3 (Critical)**: `useGraphApi.applyMutations()` must accept a `knowledgeGraphId` parameter and call `POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations`. `useMutationSubmission.submit()` must accept and forward the KG ID. `mutations.vue` must pass `selectedKnowledgeGraphId.value` through the call chain. A test must verify the correct URL is called with the KG ID in the path.

2. **FAIL-4**: KG selector must filter to KGs with `edit` permission. Either call a different endpoint that returns edit-scoped KGs, or add a permission parameter. A test must assert that only edit-capable KGs appear.

3. **FAIL-2 (Remaining closed-loop tests)**:
   - `mutations-console.test.ts:54-82`: Import `quickStartTemplates` from `mutations.vue` (or extract to a testable utility) and assert against the real array, or mount the component.
   - `mutations-console.test.ts:576-590`: Replace inline boolean comparisons with calls to `getEditorVisibilityForViewChange()`.
   - `mutations-console.test.ts:498-518`: Extract a `isLargeFileContent(text)` utility or call `isAcceptedMutationFile` with size context, and test that instead.

4. **FAIL-5**: Add a test that sets submission state to 'submitting', simulates a route change, and asserts `isVisible` remains true (or that state persists across navigation via `useState`).