---
id: task-087
title: "Mutations Console — knowledge graph selector (blocks submission until KG chosen)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-059
  - task-060
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph selector to Mutations Console — gates submission until KG chosen"
pr_description: |
  ## What & Why

  The **Mutations Console** requirement in `specs/ui/experience.spec.md` has nine scenarios.
  Tasks task-060 and task-061 cover eight of them but both omit **Scenario: Knowledge graph
  selection**, which is the gate that ties a set of mutations to a specific target graph
  before the user can submit.

  The missing scenario reads:

  > **Scenario: Knowledge graph selection**
  > - GIVEN the mutations console
  > - THEN a knowledge graph selector is displayed before the user can submit
  > - AND the selector lists all knowledge graphs the user has `edit` permission on within
  >   the current workspace
  > - AND no submission is possible until a knowledge graph is selected
  > - AND the selected knowledge graph is used as the target for the mutation submission

  Without this selector, the Mutations Console has no way to know which graph to write
  mutations into. The submission API call (`POST /graph/mutations` or equivalent) requires
  a target knowledge graph ID. task-061 (floating progress indicator) assumes the KG is
  already selected; this task provides that selector.

  ## Spec Requirements Satisfied

  - **Requirement: Mutations Console — Scenario: Knowledge graph selection** from
    `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`

  ## What This PR Does

  ### 1. API composable — list KGs with `edit` permission

  The selector must filter to knowledge graphs the user has `edit` permission on.
  The management API provides a `permission` query parameter for filtering:

  ```typescript
  // composables/api/useManagementApi.ts (or useKnowledgeGraphApi.ts)
  async function listEditableKnowledgeGraphs(workspaceId?: string): Promise<KnowledgeGraph[]> {
    const params = new URLSearchParams({ permission: 'edit' })
    if (workspaceId) params.set('workspace_id', workspaceId)
    return apiFetch(`/management/knowledge-graphs?${params}`)
  }
  ```

  If the backend does not yet support permission filtering on the list endpoint, fetch
  all KGs and filter client-side using the known list (acceptable MVP; note caveat below).

  ### 2. `KnowledgeGraphSelector.vue` component

  A select / combobox that:
  - Loads the list of editable KGs on mount.
  - Shows a loading state while fetching.
  - Renders each KG as `{name} ({id truncated})`.
  - Emits `update:modelValue` with the selected KG ID.
  - Shows an empty state ("No knowledge graphs available — create one first") if the
    list is empty.

  ```html
  <!-- components/mutations/KnowledgeGraphSelector.vue -->
  <template>
    <Select v-model="selected" :disabled="isLoading || kgs.length === 0">
      <SelectTrigger>
        <SelectValue placeholder="Select a knowledge graph…" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem v-for="kg in kgs" :key="kg.id" :value="kg.id">
          {{ kg.name }}
        </SelectItem>
      </SelectContent>
    </Select>
  </template>
  ```

  Use shadcn/vue `Select` (Reka UI) to stay consistent with the design language.

  ### 3. Integration into `pages/graph/mutations.vue`

  - Render `<KnowledgeGraphSelector v-model="selectedKgId" />` prominently above the
    editor and below the page title.
  - Disable the "Apply Mutations" button and the `Ctrl/Cmd+Enter` submission shortcut
    when `selectedKgId` is null / empty.
  - Pass `selectedKgId` to the submission call so the backend targets the correct graph.

  ```typescript
  const selectedKgId = ref<string | null>(null)
  const canSubmit = computed(() => selectedKgId.value !== null && hasMutations.value)

  async function submitMutations() {
    if (!canSubmit.value) return
    // Pass selectedKgId.value to API call
    await apiFetch(`/graph/${selectedKgId.value}/mutations`, {
      method: 'POST',
      body: { mutations: operations.value },
    })
  }
  ```

  Verify the actual submission endpoint path against the backend API spec before wiring.

  ### 4. Tests — `src/dev-ui/app/tests/mutations-kg-selector.test.ts`

  Write all tests before implementation (TDD):

  1. **Selector is rendered on the mutations console page:**
     Assert that `KnowledgeGraphSelector` (or the Select element with the right placeholder)
     is present in the mounted Mutations Console page.

  2. **Selector lists editable KGs:**
     Mock `listEditableKnowledgeGraphs` to return `[{id: 'kg-1', name: 'My Graph'}]`.
     Assert that the selector contains an option for "My Graph".

  3. **Submit button is disabled with no KG selected:**
     Assert that the "Apply Mutations" button has `disabled` attribute when `selectedKgId`
     is null (even if the editor has content).

  4. **Submit button is enabled after KG selection:**
     Assert that selecting a KG from the dropdown and providing editor content enables the
     "Apply Mutations" button.

  5. **Submission targets selected KG:**
     After selecting `kg-1` and clicking "Apply Mutations", assert that `apiFetch` was
     called with a URL containing `kg-1`.

  6. **Empty state shown when no editable KGs exist:**
     Mock `listEditableKnowledgeGraphs` to return `[]`.
     Assert that the selector shows an empty state message and the submit button is disabled.

  7. **Ctrl/Cmd+Enter blocked without KG selected:**
     Assert that pressing `Ctrl+Enter` inside the editor does NOT trigger submission when
     `selectedKgId` is null.

  ## Files Affected

  - `src/dev-ui/app/components/mutations/KnowledgeGraphSelector.vue` — new component
  - `src/dev-ui/app/pages/graph/mutations.vue` — mount selector, wire `canSubmit`,
    pass `selectedKgId` to submission call
  - `src/dev-ui/app/composables/api/useManagementApi.ts` (or equivalent) — add
    `listEditableKnowledgeGraphs()` function
  - `src/dev-ui/app/tests/mutations-kg-selector.test.ts` — spec scenario tests

  ## How to Verify

  1. Navigate to `/graph/mutations`.
  2. Confirm a knowledge graph selector is visible and lists KGs with edit permission.
  3. Confirm the "Apply Mutations" button and `Ctrl+Enter` are inert until a KG is
     selected.
  4. Select a KG → button becomes active.
  5. Submit → the API call includes the selected KG's ID in the endpoint or body.
  6. `cd src/dev-ui && pnpm test` — all tests in `mutations-kg-selector.test.ts` pass;
     no regressions.

  ## Design Decisions

  - **Placement:** The selector appears above the editor area, below the page heading,
    and always visible (not inside the editor panel). This makes it clear the KG choice
    is a prerequisite for all mutations on the page, not just the current editor session.
  - **Permission filter:** `edit` permission (the spec says `edit`, not `view`). If the
    backend's list endpoint doesn't support `?permission=edit`, filter client-side.
  - **Component reuse:** The selector uses the same shadcn/vue `Select` component used
    elsewhere in the UI for consistency with the design language.
  - **Relationship to task-061:** task-061 wires the submission API call; this task
    ensures `selectedKgId` is available and the submission button is gated. Ideally
    task-087 lands before task-061 so the submission flow can read the KG ID directly.
    If task-061 lands first, update `submitMutations()` in that PR to accept `selectedKgId`.

  ## Caveats

  - The spec says "within the current workspace." If the management API doesn't filter
    by workspace on the KG list, the selector shows all KGs with edit permission across
    all workspaces in the tenant. This is acceptable as an MVP; a `?workspace_id=` filter
    can be added once the current-workspace context is surfaced in the UI composable.
  - The spec counts this as ONE of the nine Mutations Console scenarios. task-060 and
    task-061 together claimed "8 of 8" — this was a miscounting error; the actual total
    is nine.
---

## Spec Coverage

**Requirement: Mutations Console — Scenario: Knowledge graph selection** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN the mutations console
> THEN a knowledge graph selector is displayed before the user can submit
> AND the selector lists all knowledge graphs the user has `edit` permission on within
>   the current workspace
> AND no submission is possible until a knowledge graph is selected
> AND the selected knowledge graph is used as the target for the mutation submission

## Why This Was Missed

task-060's spec coverage section says "6 of 8 Mutations Console scenarios" and
task-061 says "2 of 8." Together they add to 8, but the spec has **9** scenarios.
The Knowledge graph selection scenario is the ninth — it falls between the core
editor features (task-060) and the submission flow (task-061), making it easy to
overlook.

## Current State

No component, composable function, or test covers this scenario. The mutations console
page (`src/dev-ui/app/pages/graph/mutations.vue`) has no knowledge graph selector.
The "Apply Mutations" button (when it exists after task-060) does not gate on KG
selection.

## Acceptance Criteria

- A knowledge graph selector is visible on the Mutations Console page at all times.
- The selector fetches KGs with `edit` permission from the management API.
- The "Apply Mutations" button and the `Ctrl/Cmd+Enter` shortcut are disabled when no
  KG is selected.
- Selecting a KG enables the submit button (assuming editor content is present).
- The API submission call includes the selected KG's ID.
- An empty state is shown in the selector when no KGs with edit permission exist.
- All tests in `src/dev-ui/app/tests/mutations-kg-selector.test.ts` pass.
- `cd src/dev-ui && pnpm test` passes with no regressions.

## UI Location

- `src/dev-ui/app/components/mutations/KnowledgeGraphSelector.vue` — selector component
- `src/dev-ui/app/pages/graph/mutations.vue` — integration point
- `src/dev-ui/app/composables/api/useManagementApi.ts` — API composable

## Dependencies

- **task-059** must be complete: the Mutations Console must appear in the sidebar
  before this selector is integrated into the page.
- **task-060** must be complete: the core editor page structure must exist before the
  KG selector can be added to it.

## TDD Cycle

1. Create `src/dev-ui/app/tests/mutations-kg-selector.test.ts` — write all 7 tests
   listed above. They will fail (RED).
2. Create `KnowledgeGraphSelector.vue` component.
3. Add `listEditableKnowledgeGraphs()` to the management API composable.
4. Mount the selector in `mutations.vue` and wire `canSubmit`.
5. Run `cd src/dev-ui && pnpm test` — all tests pass (GREEN).
6. Commit atomically.
