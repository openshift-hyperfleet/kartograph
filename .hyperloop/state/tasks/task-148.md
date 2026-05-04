---
id: task-148
title: "Update query console KG selector tests from __all__ to empty-string sentinel"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(ui): update query console KG selector tests from __all__ to empty-string sentinel"
pr_description: |
  ## What and Why

  The query console's KG selector in `pages/query/index.vue` was previously
  changed (as part of the task-147 goal) to use `''` (empty string) as the
  sentinel for the "all knowledge graphs" unscoped state instead of `'__all__'`.

  **The implementation in `pages/query/index.vue` is correct:**
  - `const selectedKgId = ref('')` — empty string initialises to unscoped
  - `v-if="selectedKgId"` — truthy check gates the "Scoped" badge
  - `<SelectItem value="">All knowledge graphs</SelectItem>` — empty value
  - `selectedKgId.value || undefined` — falsy gate converts `''` → `undefined`
    before passing to the MCP `knowledge_graph_id` parameter

  **The problem:** 5 test files with 16 tests still assert `'__all__'`
  patterns from the old implementation and are failing:

  | File | Failing tests |
  |------|--------------|
  | `tests/query-kg-selector.test.ts` | 4 |
  | `tests/query-history.test.ts` | 3 |
  | `tests/query.test.ts` | 4 |
  | `tests/task-125-spec-alignment.test.ts` | 4 |
  | `tests/task-129-spec-alignment.test.ts` | 1 |

  **Total: 16 failing tests**

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`

  - **Requirement: Query Console — Scenario: Knowledge graph context**
    "THEN the user can optionally select a specific knowledge graph to scope queries"
    "AND when unscoped, queries span all knowledge graphs the user can access in the tenant"

  The `''` sentinel correctly satisfies both conditions:
  - Selecting a KG sets `selectedKgId` to a real ID → passed to `knowledge_graph_id`
  - Leaving unscoped keeps `selectedKgId = ''` → `'' || undefined` → `knowledge_graph_id`
    is omitted from the request → queries span all KGs in the tenant

  ## Key Design Decisions

  The `''` (empty string) sentinel is the correct approach because:
  1. Empty string is falsy in JavaScript, enabling the simple `|| undefined` gate
  2. Consistent with the mutations console and other selectors in the codebase
  3. No Reka UI incompatibility — the concern about Reka UI reserving `value=""`
     was a red herring; `value=""` works correctly in SelectItem for this use case

  The `'__all__'` sentinel was removed from the implementation and must now be
  removed from the tests too. All test assertions about `'__all__'` should be
  updated to assert the equivalent `''` patterns.

  ## What Files Are Affected

  **No implementation changes** — `pages/query/index.vue` is already correct.

  **Test files to update (5 files, 16 assertions):**

  ### `tests/query-kg-selector.test.ts`
  4 failing assertions referencing `__all__`:
  - Line ~50: `expect(queryVue).toMatch(/<SelectItem[^>]*value="__all__"/)` →
    assert `value=""` instead
  - Line ~57: `expect(queryVue).toContain("selectedKgId = ref('__all__')")` →
    assert `"selectedKgId = ref('')"` instead
  - Line ~62: `expect(queryVue).toContain("selectedKgId !== '__all__'")` →
    assert `v-if="selectedKgId"` or `'v-if="selectedKgId"'` instead
  - Line ~186: `expect(queryVue).toContain("selectedKgId.value === '__all__'")` →
    assert `"selectedKgId.value || undefined"` instead

  ### `tests/query-history.test.ts`
  3 failing assertions in the "KG scope selector — structural verification" section.
  Update `'__all__'` patterns to match the `''` sentinel approach.

  ### `tests/query.test.ts`
  4 failing assertions:
  - Line ~56: `expect(src).toContain("selectedKgId.value === '__all__'")` →
    assert `"selectedKgId.value || undefined"` instead
  - Remaining assertions about `__all__` → update to `''` equivalents

  ### `tests/task-125-spec-alignment.test.ts`
  4 failing assertions about `__all__` patterns. Update to `''` equivalents.

  ### `tests/task-129-spec-alignment.test.ts`
  1 failing assertion about `selectedKgId.value === '__all__'`. Update to
  assert `selectedKgId.value || undefined`.

  ## How to Verify

  ```bash
  cd src/dev-ui
  pnpm test -- query
  pnpm test -- task-125
  pnpm test -- task-129
  ```

  All 16 previously failing tests must pass. Run the full suite:
  ```bash
  pnpm test
  ```
  Expect 0 failing tests (currently 16 failing).

  ## Caveats

  - Some test descriptions (e.g. "selectedKgId is initialised to the __all__
    sentinel") should have their description text updated to remove the `__all__`
    reference, but the key change is the code assertion itself.
  - task-147 (which originally motivated this change) claimed "no test changes
    are needed." That claim was incorrect — the tests DO need updating, as this
    task demonstrates. task-147 itself is now superseded by this task and the
    prior implementation change.
  - The `query-history.test.ts` file may have a "KG scope selector — structural
    verification" section appended at the end by a prior task; verify the line
    numbers and update only those assertions.
---
