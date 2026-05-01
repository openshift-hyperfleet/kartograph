---
id: task-062
title: Audit workspace guidance — first-time tenant entry with no personal workspace
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: not-started
phase: null
deps:
  - task-014
  - task-046
round: 0
branch: null
pr: null
pr_title: "feat(ui): add workspace guidance prompt for first-time tenant entry with no workspaces"
pr_description: |
  ## What & Why

  Implements the **Tenant and Workspace Context — Workspace guidance** scenario from
  `specs/ui/experience.spec.md`. Without this prompt, a new user entering a tenant with
  no workspaces lands on a blank page or the wrong empty state — they have no path
  forward. This is logically prior to the KG creation prompt (task-046): a user with
  no workspace cannot have KGs.

  ## Spec Requirements Satisfied

  - **Scenario: Workspace guidance** — When a user enters a tenant for the first time and
    no personal workspace exists, the UI suggests creating one or joining an existing team
    workspace. The KG creation prompt (task-046) must NOT appear when workspace guidance
    is active; the two prompts are mutually exclusive and ordered correctly.

  ## Key Design Decisions

  - `WorkspaceGuidance.vue` is a dedicated component mounted from `pages/index.vue`
    under `v-if="!hasWorkspace"`. The KG creation prompt is gated under
    `v-else-if="knowledgeGraphs.length === 0"`.
  - "Join a Team Workspace" lists workspaces in the tenant the user is not yet a member of.
    If invitation-based, it shows a message to contact a workspace admin.
  - The component uses shadcn/vue primitives (Button, Card) and OKLCH amber as the
    primary action color, consistent with the Kartograph design language.

  ## Files Affected

  - `src/dev-ui/app/pages/index.vue` — home page v-if / v-else-if orchestration
  - `src/dev-ui/app/components/workspaces/WorkspaceGuidance.vue` — guidance component
  - `src/dev-ui/app/tests/workspace-guidance.test.ts` — 7 spec scenario tests (created)

  ## How to Verify

  1. Log in as a user with no workspaces in the current tenant.
  2. Home page shows "Get started with your first workspace" guidance, not the KG prompt.
  3. Click "Create Workspace" → dialog opens; create workspace → guidance disappears.
  4. Log in as a user who already has a workspace → guidance prompt absent.
  5. `cd src/dev-ui && pnpm test` passes (all 7 workspace-guidance tests).

  ## Caveats

  Depends on task-014 (workspace pages + `listWorkspaces()` composable) and task-046
  (home page KG redirect / new-user prompt) completing first so the home page structure
  is stable before this task adds its `v-if` guard layer.
---

## Spec Coverage

**Requirement: Tenant and Workspace Context — Scenario: Workspace guidance** from
`specs/ui/experience.spec.md`:

> GIVEN a user entering a tenant for the first time
> WHEN no personal workspace exists
> THEN the UI suggests creating one or joining an existing team workspace

## Gap

task-014 (complete) implemented the IAM management pages including workspace CRUD.
task-046 (not-started) addresses the "no knowledge graphs" new-user landing. Neither
task nor any subsequent audit explicitly covers the **workspace guidance** scenario,
which is a distinct, earlier touchpoint in the user journey.

The workspace guidance applies when:
- The user has navigated to (or been assigned to) a tenant
- `GET /iam/workspaces` returns an empty list **or** a list with no workspace where
  the user is an owner/member with a personal workspace role
- The UI should surface a contextual prompt — not a blank page — directing the user
  to either create their first workspace or join an existing team workspace

No task currently owns this scenario. It was not explicitly referenced in task-014's
acceptance criteria and has no subsequent audit task.

## Relationship to Adjacent Tasks

- **task-046** handles the "no knowledge graphs" landing. The workspace guidance
  scenario is logically prior: a user with no workspace has no KGs by definition.
  The two prompts must not conflict (workspace guidance appears before the KG creation
  prompt in the user journey).
- **task-058** audits the tenant selector and tenant-switch data refresh. That task
  does not verify what the UI shows when the tenant has no workspaces.

## Scope

### Audit step (read before writing)

Read `src/dev-ui/app/pages/index.vue` (the home page / landing page) and
`src/dev-ui/app/pages/workspaces/index.vue`. For each file, determine whether:

1. The component loads the workspace list on mount (or tenant change).
2. When the workspace list is empty, a workspace guidance prompt is shown rather
   than a blank state or the KG creation prompt.
3. The guidance prompt offers two actions:
   - **Create workspace** — opens the workspace creation dialog or navigates to
     a workspace creation flow.
   - **Join existing** — shows the list of available team workspaces in the tenant
     (workspaces the user is not yet a member of) and allows the user to request
     or accept membership.

Record PASS / FAIL per check.

### Changes required if any check FAILs

#### 1. `src/dev-ui/app/tests/workspace-guidance.test.ts`

Create this test file and write tests **before** touching implementation (TDD):

1. **Guidance shown when workspace list is empty:**
   ```typescript
   it('shows workspace guidance when the user has no workspaces', async () => {
     mockListWorkspaces.mockResolvedValueOnce([])
     const wrapper = await mountHomePage()
     expect(wrapper.find('[data-testid="workspace-guidance"]').exists()).toBe(true)
   })
   ```

2. **Create workspace action is present:**
   ```typescript
   it('workspace guidance contains a create-workspace button', async () => {
     mockListWorkspaces.mockResolvedValueOnce([])
     const wrapper = await mountHomePage()
     expect(wrapper.find('[data-testid="btn-create-workspace"]').exists()).toBe(true)
   })
   ```

3. **Join existing workspace action is present:**
   ```typescript
   it('workspace guidance contains a join-workspace action', async () => {
     mockListWorkspaces.mockResolvedValueOnce([])
     const wrapper = await mountHomePage()
     expect(wrapper.find('[data-testid="btn-join-workspace"]').exists()).toBe(true)
   })
   ```

4. **Guidance is NOT shown when the user already has workspaces:**
   ```typescript
   it('does not show workspace guidance when workspaces exist', async () => {
     mockListWorkspaces.mockResolvedValueOnce([{ id: 'ws-1', name: 'My Workspace' }])
     const wrapper = await mountHomePage()
     expect(wrapper.find('[data-testid="workspace-guidance"]').exists()).toBe(false)
   })
   ```

5. **KG creation prompt does not appear when workspace guidance is active:**
   ```typescript
   it('does not show KG creation prompt when no workspace exists', async () => {
     mockListWorkspaces.mockResolvedValueOnce([])
     const wrapper = await mountHomePage()
     // The "no KGs" task-046 prompt must not appear before workspace is set up
     expect(wrapper.find('[data-testid="new-user-kg-prompt"]').exists()).toBe(false)
   })
   ```

6. **Create workspace dialog opens on button click:**
   ```typescript
   it('clicking create workspace opens the workspace creation dialog', async () => {
     mockListWorkspaces.mockResolvedValueOnce([])
     const wrapper = await mountHomePage()
     await wrapper.find('[data-testid="btn-create-workspace"]').trigger('click')
     expect(wrapper.find('[data-testid="dialog-create-workspace"]').exists()).toBe(true)
   })
   ```

7. **After workspace creation, guidance disappears:**
   ```typescript
   it('hides workspace guidance after a workspace is successfully created', async () => {
     mockListWorkspaces
       .mockResolvedValueOnce([])         // initial load — no workspaces
       .mockResolvedValueOnce([{ id: 'ws-new', name: 'New WS' }]) // after create
     const wrapper = await mountHomePage()
     // simulate successful workspace creation
     await wrapper.vm.handleWorkspaceCreated({ id: 'ws-new', name: 'New WS' })
     expect(wrapper.find('[data-testid="workspace-guidance"]').exists()).toBe(false)
   })
   ```

#### 2. Implementation — home page / workspace guidance component

If the workspace guidance prompt is absent or incorrect, implement it:

**Location:** `src/dev-ui/app/pages/index.vue` (or a dedicated
`src/dev-ui/app/components/workspaces/WorkspaceGuidance.vue` component mounted
from the home page).

**Logic:**

```typescript
const workspaces = ref<Workspace[]>([])
const { currentTenantId } = useTenant()

watch(currentTenantId, async (tenantId) => {
  if (!tenantId) return
  workspaces.value = await listWorkspaces()
}, { immediate: true })

const hasWorkspace = computed(() => workspaces.value.length > 0)
```

**Template (workspace guidance section):**

```html
<WorkspaceGuidance
  v-if="!hasWorkspace"
  data-testid="workspace-guidance"
  @create="handleCreateWorkspace"
  @join="handleJoinWorkspace"
/>

<!-- task-046 new-user KG prompt must be gated behind hasWorkspace -->
<NewUserKgPrompt
  v-else-if="knowledgeGraphs.length === 0"
  data-testid="new-user-kg-prompt"
/>
```

The `WorkspaceGuidance` component should:
- Display a clear heading ("Get started with your first workspace").
- Offer a primary "Create Workspace" button that opens the workspace creation
  dialog (reuse the existing dialog from `pages/workspaces/index.vue` if available).
- Offer a secondary "Join a Team Workspace" action that lists workspaces in the
  tenant the user is not yet a member of, allowing them to request membership
  (or if invite-based: show a message to contact a workspace admin).
- Use the Kartograph design language: shadcn/vue components, OKLCH color tokens,
  amber primary action, Lucide icons.

#### 3. Verify ordering with task-046

Read `src/dev-ui/app/pages/index.vue` (after task-046 is implemented) and confirm:
- The `v-if="!hasWorkspace"` guard on `WorkspaceGuidance` is evaluated **before**
  the `v-else-if` for the KG creation prompt.
- The two states are mutually exclusive (no path shows both prompts simultaneously).

## Acceptance Criteria

- When a user belongs to a tenant with no workspaces, the home page shows a workspace
  guidance prompt with "Create Workspace" and "Join a Team Workspace" actions.
- The workspace guidance prompt does NOT appear when the user already has at least
  one workspace.
- The "no KG" creation prompt (task-046) is suppressed when workspace guidance is
  active (the user must create a workspace first).
- Creating a workspace from the guidance prompt hides the guidance and transitions
  the user toward creating their first knowledge graph.
- All 7 tests in `src/dev-ui/app/tests/workspace-guidance.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test`

## UI Location

- `src/dev-ui/app/pages/index.vue` — home/landing page orchestration
- `src/dev-ui/app/components/workspaces/WorkspaceGuidance.vue` — guidance component
- `src/dev-ui/app/tests/workspace-guidance.test.ts` — spec scenario tests

## Dependencies

- **task-014** must be complete: the workspace pages and `listWorkspaces()` composable
  must exist before this audit/implementation can run.
- **task-046** must be complete or in progress: the home landing logic (KG-based
  redirect) must exist so that this task can ensure the workspace guidance is correctly
  gated before the KG creation prompt.

## TDD Cycle

1. Read `pages/index.vue` — determine PASS/FAIL for each workspace guidance check.
2. Create `tests/workspace-guidance.test.ts` — write all 7 tests (they will fail if
   guidance is not implemented).
3. Create `components/workspaces/WorkspaceGuidance.vue` and wire it into
   `pages/index.vue` with the correct `v-if` / `v-else-if` ordering.
4. Run `cd src/dev-ui && pnpm test` — all tests pass.
5. Commit atomically per conventional commit conventions.
