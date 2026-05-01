---
id: task-046
title: Fix home page landing — KG-based redirect and new-user KG creation prompt
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps:
  - task-015
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Navigation Structure** — 2 scenarios from `specs/ui/experience.spec.md`:

1. **Default landing**
   > GIVEN a returning user with existing knowledge graphs
   > WHEN they open Kartograph
   > THEN they land on the Explore section (Query Console or home dashboard)

2. **New user landing**
   > GIVEN a user with no knowledge graphs
   > WHEN they open Kartograph
   > THEN they are guided toward the setup flow with a prompt to create their first knowledge graph

## Current State

**Scenario 1 — Default landing (mismatch):**
`src/dev-ui/app/pages/index.vue` redirects authenticated users to `/query` only when
`localStorage.getItem('kartograph:query-history')` is non-empty. This uses
*query history* as the trigger, not the existence of knowledge graphs. A user who created
KGs via the API but has not yet executed queries will not be redirected, violating the spec.

The test in `src/dev-ui/app/tests/index.test.ts` checks `kartograph:visited` — a key
that does not exist in the actual implementation. The tests are vestigial stubs and provide
no spec coverage for the redirect logic.

**Scenario 2 — New user landing (FAIL):**
The onboarding checklist shown to new users has 4 steps:
1. Create a tenant
2. Define a node type (links to `/graph/schema`)
3. Create an API key (links to `/api-keys`)
4. Connect via MCP (links to `/integrate/mcp`)

None of these steps guides the user toward creating their first knowledge graph. The
spec explicitly requires that a user with no knowledge graphs is prompted to create one.
No "Create Knowledge Graph" step, count check, or call-to-action is present in the
current checklist.

## Changes Required

### 1. `src/dev-ui/app/tests/index.test.ts`

Replace the vestigial stubs with spec-accurate tests **before** fixing the implementation:

1. **Default redirect — has KGs → redirects to /query:**
   Assert that when `apiFetch('/management/knowledge-graphs')` returns
   `{ knowledge_graphs: [{ id: 'kg-1', name: 'My Graph' }] }` and the tenant is set,
   `navigateTo('/query')` is called on mount (use a `vi.fn()` spy).

2. **Default redirect — no KGs → stays on home page:**
   Assert that when `apiFetch('/management/knowledge-graphs')` returns
   `{ knowledge_graphs: [] }`, no navigation occurs.

3. **Default redirect — API error → no redirect (graceful fallback):**
   Assert that when `apiFetch` throws, no navigation occurs and no error is surfaced
   to the user (the home page loads normally).

4. **Checklist — includes "Create a knowledge graph" step:**
   Assert that `checklistItems` contains a step whose `label` is
   `'Create a knowledge graph'` and whose `actionTo` is `'/knowledge-graphs'`.

5. **Checklist — KG step is `done: true` when KG count > 0:**
   Assert that with `kgCount.value = 2`, the KG checklist step's `done` computed
   field is `true`.

6. **Checklist — KG step is `done: false` when no KGs:**
   Assert that with `kgCount.value = 0`, the KG checklist step's `done` computed
   field is `false`.

7. **Workspace guidance — shown once per tenant when workspace count is 0:**
   Assert that `showWorkspaceGuidanceIfNeeded()` triggers a toast when
   `workspaceCount.value === 0` and the per-tenant localStorage guard has not been set.

8. **Workspace guidance — not shown again if already shown for this tenant:**
   Assert that `showWorkspaceGuidanceIfNeeded()` does NOT trigger a toast when
   the localStorage guard key for the current tenant is already set.

### 2. `src/dev-ui/app/pages/index.vue`

**Redirect logic:**
- On mount (after verifying `hasTenant.value`), call:
  ```typescript
  const { apiFetch } = useApiClient()
  const result = await apiFetch<{ knowledge_graphs: { id: string }[] }>(
    '/management/knowledge-graphs'
  )
  const kgCount = result.knowledge_graphs?.length ?? 0
  ```
  Wrap in `try/catch`; on error, set `kgCount = 0` and continue without redirecting.
- Replace the `kartograph:query-history` localStorage check:
  ```typescript
  // Old:
  const rawHistory = localStorage.getItem('kartograph:query-history')
  if (rawHistory) { ...redirect... }

  // New:
  if (kgCount > 0) {
    sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')
    await navigateTo('/query')
    return
  }
  ```
- Expose `kgCount` as a ref so the checklist computed can reference it.

**Onboarding checklist:**
- Add a new step as the second item (after "Create a tenant"):
  ```typescript
  {
    done: (kgCount.value ?? 0) > 0,
    label: 'Create a knowledge graph',
    description: 'Organise your data sources into a queryable knowledge graph.',
    actionTo: '/knowledge-graphs',
    actionLabel: 'Create Knowledge Graph',
  },
  ```
- Reuse the `kgCount` fetched during the redirect check — do **not** make a second
  network request. The total checklist length becomes 5 steps.

**KG count stat card:**
- The existing `statsCards` array already links to `/knowledge-graphs` via the
  `Workspaces` card. Consider adding a `Knowledge Graphs` stat card pointing to
  `/knowledge-graphs` to keep stats consistent with the checklist. This is optional
  but preferred for visual consistency.

## Dependencies

- **task-015** must be complete: the `/knowledge-graphs` page (with the creation dialog
  and workspace selector) must exist before the checklist action link is useful.

## TDD Cycle

1. Write/fix tests in `src/dev-ui/app/tests/index.test.ts` (they will fail initially
   against the current implementation).
2. Update `src/dev-ui/app/pages/index.vue` with KG-based redirect and the new
   "Create a knowledge graph" checklist step.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
4. Commit atomically per conventional commit conventions.
