---
id: task-080
title: "UI component library — add AlertDialog (shadcn/vue)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): add AlertDialog shadcn/vue component"
pr_description: |
  ## What & Why

  `task-079` (Knowledge Graphs UI — add inline edit and delete) requires an
  `AlertDialog` component for the KG delete confirmation, but this component
  does not exist in the UI component library. The component library currently
  includes `alert` (notification banner) but **not** `alert-dialog` (modal
  confirmation dialog with destructive action).

  The shadcn/vue `AlertDialog` is the standard primitive for destructive
  confirmation flows — it is semantically distinct from `Dialog` in that it
  communicates to users that they are about to perform an irreversible action.
  It is used throughout the spec:

  - **task-079**: KG delete-with-confirmation dialog
  - Potentially future tasks requiring destructive action confirmation gates

  This PR adds the full shadcn/vue `AlertDialog` component set, following the
  identical pattern used by every other component in
  `src/dev-ui/app/components/ui/`:

  - `AlertDialog.vue` — root composable wrapper
  - `AlertDialogTrigger.vue`
  - `AlertDialogPortal.vue`
  - `AlertDialogOverlay.vue`
  - `AlertDialogContent.vue` — styled content container with ring focus
  - `AlertDialogHeader.vue`
  - `AlertDialogFooter.vue`
  - `AlertDialogTitle.vue`
  - `AlertDialogDescription.vue`
  - `AlertDialogAction.vue` — primary (potentially destructive) button
  - `AlertDialogCancel.vue` — cancel button
  - `index.ts` — barrel re-export

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed
  end-to-end** from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN a user performs any create, read, update, or **delete** operation via the UI
  > WHEN the operation is submitted
  > THEN the corresponding backend API call succeeds (2xx response)

  The `AlertDialog` component is the correct UI primitive for the delete
  confirmation flow added by `task-079`. Without it, `task-079` cannot be
  implemented as specified.

  ## Key Design Decisions

  - **Reka UI / shadcn/vue primitives**: `AlertDialogContent` is built on
    Reka's `DialogContent` (same as the existing `Dialog` component), so it
    inherits the focus-trap and ARIA attributes automatically.
  - **Design language compliance**: Uses `rounded-md` for buttons, `rounded-xl`
    for the content panel, `shadow-sm` elevation, and the `ring-[3px]` focus ring
    — matching the spec's Design Language requirement exactly.
  - **Destructive action styling**: `AlertDialogAction` accepts a `class` prop so
    callers can apply `bg-destructive text-destructive-foreground` (as task-079
    requires) without hard-coding it in the component.
  - **Follows established pattern exactly**: All file names, export names, and
    `index.ts` barrel patterns mirror the existing `dialog/` component set.

  ## Files Affected

  ```
  src/dev-ui/app/components/ui/alert-dialog/
    AlertDialog.vue
    AlertDialogTrigger.vue
    AlertDialogPortal.vue
    AlertDialogOverlay.vue
    AlertDialogContent.vue
    AlertDialogHeader.vue
    AlertDialogFooter.vue
    AlertDialogTitle.vue
    AlertDialogDescription.vue
    AlertDialogAction.vue
    AlertDialogCancel.vue
    index.ts
  src/dev-ui/app/tests/alert-dialog.test.ts  (structural tests)
  ```

  ## How to Verify

  1. `cd src/dev-ui && npm run test` — all tests pass (including the new
     structural test that verifies `index.ts` exports all named components).
  2. Import and use `AlertDialog` from `@/components/ui/alert-dialog` in any
     page — no runtime errors.
  3. Confirm `task-079` can now import `AlertDialogContent`, `AlertDialogAction`,
     etc. without compilation errors.

  ## TDD Cycle

  1. Write structural tests verifying `index.ts` exports all expected names — RED.
  2. Create all component files following the shadcn/vue pattern — GREEN.
  3. Run `cd src/dev-ui && npm run test` — all pass.
  4. Commit atomically, referencing this task.

  ## Caveats / Follow-up

  - This task has no runtime behaviour of its own — it is pure UI infrastructure.
  - `task-079` lists `task-080` as a dependency; it must be merged first.
---

## Spec Coverage

**Requirement: Backend API Alignment** from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN a user performs any create, read, update, or **delete** operation via the UI
> WHEN the operation is submitted
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

## Gap

### `AlertDialog` shadcn/vue component is absent from the component library

`task-079` specifies the following delete confirmation:

```vue
<AlertDialog v-model:open="deleteDialogOpen">
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete "{{ deletingKgName }}"?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently delete the knowledge graph and all of its data sources.
        This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel :disabled="deleting">Cancel</AlertDialogCancel>
      <AlertDialogAction
        class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        :disabled="deleting"
        @click.prevent="handleDelete"
      >
        <Loader2 v-if="deleting" class="mr-2 size-4 animate-spin" />
        {{ deleting ? 'Deleting...' : 'Delete' }}
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**Current component library:**

```
src/dev-ui/app/components/ui/
  alert/          ← notification banner (Alert, AlertTitle, AlertDescription)
  button/
  card/
  dialog/         ← general-purpose modal Dialog
  sheet/
  ... (21 component families, none is alert-dialog)
```

`AlertDialog` is semantically distinct from `Dialog` — it is the standard
shadcn primitive for irreversible destructive confirmation flows. Attempting
to import `@/components/ui/alert-dialog` will throw a module-not-found error.

## Scope

### TDD — write structural tests first

Create `src/dev-ui/app/tests/alert-dialog.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('AlertDialog component library — index.ts exports', () => {
  const indexContent = readFileSync(
    resolve(__dirname, '../components/ui/alert-dialog/index.ts'),
    'utf-8',
  )

  const expectedExports = [
    'AlertDialog',
    'AlertDialogTrigger',
    'AlertDialogPortal',
    'AlertDialogOverlay',
    'AlertDialogContent',
    'AlertDialogHeader',
    'AlertDialogFooter',
    'AlertDialogTitle',
    'AlertDialogDescription',
    'AlertDialogAction',
    'AlertDialogCancel',
  ]

  for (const name of expectedExports) {
    it(`exports ${name}`, () => {
      expect(indexContent).toContain(name)
    })
  }
})

describe('AlertDialog — design language compliance', () => {
  const contentFile = readFileSync(
    resolve(__dirname, '../components/ui/alert-dialog/AlertDialogContent.vue'),
    'utf-8',
  )

  it('uses rounded-xl for the content panel', () => {
    expect(contentFile).toMatch(/rounded-xl/)
  })

  it('applies shadow-sm elevation (flat UI)', () => {
    expect(contentFile).toMatch(/shadow-sm/)
  })
})
```

### Implementation

Create `src/dev-ui/app/components/ui/alert-dialog/` with these files, following
the identical patterns used by `src/dev-ui/app/components/ui/dialog/`:

```
AlertDialog.vue          ← <script setup> re-exports DialogRoot from reka-ui
AlertDialogTrigger.vue   ← wraps DialogTrigger
AlertDialogPortal.vue    ← wraps DialogPortal
AlertDialogOverlay.vue   ← uses same overlay classes as DialogOverlay
AlertDialogContent.vue   ← styled panel (rounded-xl, shadow-sm, focus ring)
AlertDialogHeader.vue    ← flex-col gap layout
AlertDialogFooter.vue    ← flex-col-reverse sm:flex-row sm:justify-end
AlertDialogTitle.vue     ← text-lg font-semibold
AlertDialogDescription.vue ← text-sm text-muted-foreground
AlertDialogAction.vue    ← Button wrapper (variant forwarded via class prop)
AlertDialogCancel.vue    ← Button variant="outline" wrapper
index.ts                 ← re-exports all of the above
```

The Reka UI (formerly Radix Vue) `AlertDialog` primitives are the same as
`Dialog` primitives — AlertDialog IS a Dialog underneath. Use
`import { DialogRoot as AlertDialogRoot, ... } from 'reka-ui'` and alias
to the AlertDialog naming convention.

## Acceptance Criteria

- `import { AlertDialog, AlertDialogContent, AlertDialogAction, AlertDialogCancel, ... } from '@/components/ui/alert-dialog'` resolves without errors.
- `AlertDialogContent` uses `rounded-xl` and `shadow-sm`.
- `AlertDialogAction` and `AlertDialogCancel` accept `class` and `disabled` props.
- `v-model:open` works identically to `Dialog`.
- All structural tests in `alert-dialog.test.ts` pass.
- `cd src/dev-ui && npm run test` — no regressions.
