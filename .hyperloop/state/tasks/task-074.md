---
id: task-074
title: Mutations Console — workspace-scoped KG selector (workspace picker before KG picker)
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-065
round: 0
branch: null
pr: null
pr_title: "feat(ui): add workspace selector to Mutations Console — scope KG list to current workspace"
pr_description: |
  ## What & Why

  The **Mutations Console — Scenario: Knowledge graph selection** in `experience.spec.md`
  contains a precision requirement that task-065 does not address:

  > AND the selector lists all knowledge graphs the user has `edit` permission on
  > **within the current workspace**

  Task-065 populates the KG dropdown using `GET /management/knowledge-graphs?permission=edit`,
  which is a tenant-wide listing (all KGs the user can edit across every workspace in the
  tenant). This matches the **Query Console** scope ("span all knowledge graphs the user can
  access in the tenant") but does NOT match the Mutations Console spec, which explicitly
  constrains the listing to "within the current workspace."

  Without workspace scoping, a user with access to KGs in five different workspaces would
  see all five in the dropdown and could submit mutations to a KG in the wrong workspace
  — a potentially dangerous cross-context mutation.

  This task adds a workspace selector that appears **before** the KG dropdown in the Mutations
  Console and filters the KG list to only those belonging to the selected workspace.

  ## Spec Requirements Satisfied

  **Requirement: Mutations Console — Scenario: Knowledge graph selection**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN the mutations console
  > THEN a knowledge graph selector is displayed before the user can submit
  > AND the selector lists all knowledge graphs the user has `edit` permission on
  >   **within the current workspace**
  > AND no submission is possible until a knowledge graph is selected
  > AND the selected knowledge graph is used as the target for the mutation submission

  The "within the current workspace" clause is the specific constraint addressed here.

  ## Key Design Decisions

  - **Two-selector flow**: A workspace dropdown appears above the KG dropdown. Until a
    workspace is selected the KG list is empty and disabled. Once a workspace is selected
    the KG list is populated with `GET /management/knowledge-graphs?workspace_id={id}&permission=edit`.
    Selecting a workspace resets the KG selection (prevents stale cross-workspace selection).

  - **Workspace list source**: `GET /management/workspaces` — the same endpoint used by
    the Workspaces management page. The list is filtered to workspaces the user belongs to.
    The workspace list reloads on tenant switch (mirrors the KG list behaviour from task-065).

  - **API endpoint**: The management API for knowledge graphs is expected to accept a
    `workspace_id` query parameter. If the backend does not yet support this filter, the
    composable should be written with the query param in place and the task notes this as
    a backend dependency. The UI should NOT fall back to unfiltered results silently — it
    should show the workspace-filtered list (or an empty list if no KGs exist in that workspace).

  - **Submit gating**: Submission requires BOTH workspace AND KG to be selected.
    `canSubmitMutations` is updated to include `!!selectedWorkspaceId && !!selectedKgId`.
    The tooltip/toast for the disabled state distinguishes "select a workspace first" from
    "select a knowledge graph".

  - **UX label**: The workspace selector appears above the KG selector with label
    "Workspace" and placeholder "Select a workspace". The KG selector label changes to
    "Knowledge Graph" with placeholder "Select a knowledge graph" (no change). This matches
    the two-step Create Knowledge Graph flow (task-040).

  - **Tenant switch**: Both workspace and KG selections are cleared on tenant switch.

  - **Interaction principles**: Progressive disclosure — KG selector is rendered but
    disabled until a workspace is chosen, communicating the dependency without hiding elements.

  ## Files Affected

  - `src/dev-ui/app/pages/graph/mutations.vue` — add `selectedWorkspaceId` / `workspaces`
    state; add workspace `<Select>` above KG selector; gate KG list on workspace selection;
    update `canSubmitMutations` call and toast messages.
  - `src/dev-ui/app/composables/api/useIamApi.ts` — verify `listWorkspaces()` is usable
    here (it already exists for the layout); expose or import for the mutations page.
  - `src/dev-ui/app/utils/mutationConsole.ts` — update `canSubmitMutations` signature to
    require `selectedWorkspaceId: string` and gate on it alongside `selectedKnowledgeGraphId`.
  - `src/dev-ui/app/tests/mutations-workspace-selector.test.ts` — new TDD-first test file
    covering all scenario clauses.

  ## How to Verify

  1. Navigate to `/graph/mutations` with mutations content ready.
  2. Verify the Apply Mutations button is **disabled** with no workspace selected.
  3. Open the workspace dropdown — workspaces from the current tenant appear.
  4. Select a workspace — the KG dropdown becomes enabled and lists only KGs in that workspace.
  5. Select a KG — Apply Mutations becomes enabled.
  6. Submit — verify the API call uses the selected KG ID (network tab).
  7. Switch tenant — both workspace and KG selections are cleared.
  8. Select workspace A, then switch to workspace B — KG selection is cleared and the KG
     list reloads.
  9. Run `cd src/dev-ui && pnpm test` — all tests in `mutations-workspace-selector.test.ts`
     pass; no regressions in `mutations-console.test.ts` or `mutations-kg-selector.test.ts`.

  ## Caveats

  - Depends on task-065 landing first, as this task modifies the same KG selector state
    and `canSubmitMutations` utility that task-065 introduces.
  - If the backend management API does not yet support `?workspace_id=` filtering on
    `GET /management/knowledge-graphs`, the API composable should be written with the
    parameter in place (ready for when the backend adds it). A TODO comment should be left
    so the backend team knows this filter is expected.
  - The workspace list is the full list of workspaces accessible to the user in the tenant.
    If workspace-level permission checking is needed (e.g., only workspaces where the user
    has `edit` on at least one KG), that can be addressed in a follow-up task. For now,
    show all workspaces and let the KG list naturally be empty if none are accessible.

---

## Spec Coverage

**Requirement: Mutations Console — Scenario: Knowledge graph selection**
from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

The specific clause covered by this task (the others are covered by task-065):

> AND the selector lists all knowledge graphs the user has `edit` permission on
> **within the current workspace**

### Gap Verification

**task-065** (Mutations Console — knowledge graph selector and scoped API submission):

The task-065 design decision explicitly states:

> "Selector population: GET /management/knowledge-graphs — same endpoint used by the
> Query Console's KG scope selector (task-045). On tenant switch, the list reloads
> and the selection clears."

task-045 (Query Console KG scope) uses a **tenant-wide** listing: "when unscoped, queries
span all knowledge graphs the user can access in the **tenant**." The Query Console spec
deliberately uses tenant scope. The Mutations Console spec uses **workspace** scope.

task-065 treats both the same, violating the Mutations Console spec's "within the current
workspace" constraint.

**Code verification (`src/dev-ui/app/pages/graph/mutations.vue`):**

```typescript
// Line ~129-134 (task-065 implementation)
const result = await apiFetch<{ knowledge_graphs: KnowledgeGraphItem[] }>(
  '/management/knowledge-graphs',
  { query: { permission: 'edit' } },   // ← no workspace_id filter
)
```

This API call returns KGs across ALL workspaces in the tenant — not "within the current
workspace" as the spec requires. There is no `selectedWorkspaceId` state or workspace
`<Select>` component in `mutations.vue`.

### TDD Tests to Write First

Create `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Pure logic: canSubmitMutations with workspace gate ────────────────────────
//
// Spec: "no submission is possible until a knowledge graph is selected"
// This task extends the gate to also require a workspace selection.

import { canSubmitMutations } from '../utils/mutationConsole'

describe('canSubmitMutations — workspace gate', () => {
  const base = {
    content: '{"op": "CREATE"}',
    isLargeFile: false,
    submitting: false,
    preparing: false,
  }

  it('returns false when workspace is empty (no workspace selected)', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: '',
      selectedKnowledgeGraphId: 'kg-123',
    })).toBe(false)
  })

  it('returns false when KG is empty even with workspace selected', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: '',
    })).toBe(false)
  })

  it('returns true when both workspace and KG are selected with valid content', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: 'kg-123',
    })).toBe(true)
  })

  it('returns false when submitting is true (even with selections)', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: 'kg-123',
      submitting: true,
    })).toBe(false)
  })
})

// ── Structural: verify implementation in mutations.vue ────────────────────────

describe('Mutations Console — workspace selector structural checks', () => {
  const mutVue = readFileSync(
    resolve(__dirname, '../pages/graph/mutations.vue'),
    'utf-8',
  )

  it('declares selectedWorkspaceId state', () => {
    // Workspace selection state must exist
    expect(mutVue).toMatch(/selectedWorkspaceId/)
  })

  it('renders a workspace <Select> before the KG selector', () => {
    // Spec: "a knowledge graph selector is displayed … within the current workspace"
    // Implies a workspace is selected first; the selector must render in the template
    expect(mutVue).toMatch(/Select.*[Ww]orkspace|[Ww]orkspace.*Select/)
  })

  it('passes workspace_id to the knowledge-graphs API call', () => {
    // Spec: "within the current workspace" — must filter the KG list by workspace
    expect(mutVue).toMatch(/workspace_id|workspaceId/)
  })

  it('resets KG selection when workspace changes', () => {
    // Switching workspace must clear the stale KG selection
    expect(mutVue).toMatch(/selectedKnowledgeGraphId.*=.*''|selectedKnowledgeGraphId\.value.*=.*''/)
  })
})
```

### Implementation Steps

1. **Write tests** in `mutations-workspace-selector.test.ts` (RED).
2. **Update `canSubmitMutations`** in `src/dev-ui/app/utils/mutationConsole.ts`:
   - Add `selectedWorkspaceId: string` to the options parameter.
   - Gate on `!!selectedWorkspaceId` in addition to existing conditions.
3. **Update `mutations.vue`**:
   - Add `workspaces` and `selectedWorkspaceId` refs.
   - Add `loadWorkspaces()` calling `listWorkspaces()` (from `useIamApi`).
   - Watch `hasTenant` to load/clear workspaces (and clear `selectedWorkspaceId`).
   - Add workspace `<Select>` above the KG `<Select>` with label "Workspace".
   - Update `loadKnowledgeGraphs()` to pass `workspace_id: selectedWorkspaceId.value` in query params.
   - Watch `selectedWorkspaceId` to clear `selectedKnowledgeGraphId.value = ''` and reload KGs.
   - Update `canSubmitMutations` calls to include `selectedWorkspaceId`.
   - Update toast message: distinguish "select a workspace first" from "select a knowledge graph".
4. **Run tests** (GREEN for pure-logic tests; structural tests pass once implementation done).
5. **Commit atomically** with `feat(ui): add workspace selector to Mutations Console`.

## Acceptance Criteria

- A workspace dropdown appears above the KG dropdown in the Mutations Console.
- The workspace list is populated by `GET /management/workspaces` on page load and on tenant switch.
- Until a workspace is selected: KG dropdown is disabled; Apply Mutations is disabled.
- Selecting a workspace enables the KG dropdown and loads KGs filtered to that workspace.
- Switching workspace clears the KG selection and reloads the KG list.
- Submit is only possible when BOTH workspace and KG are selected (and content is valid).
- The API call for KGs includes `workspace_id` (or equivalent) as a query parameter.
- All tests in `mutations-workspace-selector.test.ts` pass.
- No regressions in `mutations-console.test.ts` or `mutations-kg-selector.test.ts`.
- `cd src/dev-ui && pnpm test` exits 0.
