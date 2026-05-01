---
id: task-061
title: Mutations Console — submission flow (floating progress indicator, failure handling)
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: not-started
phase: null
deps:
  - task-060
round: 0
branch: null
pr: null
pr_title: "feat(ui): add Mutations Console floating progress indicator persisted across navigation"
pr_description: |
  ## What & Why

  Implements the Submission and Submission failure scenarios of the **Mutations Console**
  requirement from `specs/ui/experience.spec.md`. The key architectural challenge is that
  the floating indicator must persist when the user navigates away from `/graph/mutations`
  — this requires app-level (global) state, not page-level state.

  ## Spec Requirements Satisfied

  - **Scenario: Submission** — Clicking Apply Mutations (or `Ctrl/Cmd+Enter`) submits
    mutations to the API; a floating indicator appears bottom-right showing status
    (submitting / success / failed), operation count, and elapsed time. The indicator
    persists on navigation, can be minimized to a compact pill, and dismissed after
    completion.
  - **Scenario: Submission failure** — The floating indicator shows the error message;
    if any operations were applied before failure, that count is displayed.

  ## Key Design Decisions

  - A Pinia store (`useMutationSubmission` composable backed by `provide`/`inject`)
    holds submission state at the app root, ensuring cross-page persistence.
  - `MutationProgress.vue` is mounted in `layouts/default.vue` so it renders on every
    route.
  - The minimized pill links back to `/graph/mutations` so the user can return from
    wherever they navigated.
  - Timer uses `setInterval` locally within the component to avoid polluting the store
    with a live-updating timestamp.

  ## Files Affected

  - `src/dev-ui/app/composables/useMutationSubmission.ts` — global submission state
  - `src/dev-ui/app/components/graph/MutationProgress.vue` — floating indicator
  - `src/dev-ui/app/layouts/default.vue` — mounts the indicator globally
  - `src/dev-ui/app/pages/graph/mutations.vue` — wires submit button to the composable
  - `src/dev-ui/app/tests/mutations-submission.test.ts` — 10 spec scenario tests (created)

  ## How to Verify

  1. Enter mutations in the editor, click Apply Mutations → indicator appears bottom-right.
  2. Navigate to `/query` while submission is in progress → indicator still visible.
  3. On success → indicator shows green check + operation count.
  4. On failure → indicator shows red error message and ops-applied-before-failure count.
  5. Minimize → compact pill; expand → full card.
  6. Dismiss → indicator hidden.
  7. `cd src/dev-ui && pnpm test` passes.

  ## Caveats

  Depends on task-060 (core editor) landing first, as the `submitMutations()` function
  and editor state must exist before the global indicator can be wired to them.
---

## Spec Coverage

**Requirement: Mutations Console** — 2 of 8 scenarios from `specs/ui/experience.spec.md`:

### Scenario: Submission
> GIVEN valid mutations in the editor
> WHEN the user clicks Apply Mutations (or presses Ctrl/Cmd+Enter)
> THEN the mutations are submitted to the API and a floating progress indicator appears
>   in the bottom-right corner
> AND the indicator shows status (submitting / success / failed), operation count, and
>   elapsed time
> AND the indicator persists when the user navigates away from the mutations console
> AND the indicator can be minimized to a compact pill or dismissed after completion

### Scenario: Submission failure
> GIVEN a failed mutation submission
> THEN the floating indicator shows the error message
> AND the number of operations applied before failure is displayed if any were processed

## Scope and Architectural Note

The submission flow is architecturally distinct from the core editor features (task-060)
because the floating progress indicator **persists across navigation**. This requires
global (app-level) state, not page-level state.

The indicator must:
- Appear in the bottom-right corner of the viewport regardless of which page the user
  is currently on.
- Continue showing elapsed time and status after the user navigates away from
  `/graph/mutations`.
- Be minimizable to a compact pill (icon + status) and dismissible after completion.

## Changes Required

### 1. Global progress store (`src/dev-ui/app/stores/mutationProgress.ts`)

Create a Pinia store (or Vue `provide`/`inject` at app root) that holds the in-flight
mutation submission state:

```typescript
interface MutationProgressState {
  status: 'idle' | 'submitting' | 'success' | 'failed'
  operationCount: number
  appliedCount: number   // ops applied before failure (partial success)
  errorMessage: string | null
  startedAt: Date | null
  completedAt: Date | null
  minimized: boolean
}
```

### 2. `src/dev-ui/app/components/mutations/FloatingProgressIndicator.vue`

Implement the floating indicator component:

- **Positioning:** Fixed to the viewport bottom-right (`fixed bottom-4 right-4 z-50`).
- **Full view (not minimized):** Shows a card with:
  - Status label (Submitting / Success / Failed) with appropriate color (amber for
    submitting, green for success, red for failed)
  - Operation count (e.g., "42 operations")
  - Elapsed time counter (live ticker while `submitting`; frozen on completion)
  - Error message (red, scroll-clipped) when status is `failed`
  - Partial success note ("12 operations applied before failure") when
    `appliedCount > 0` and `status === 'failed'`
  - "Minimize" button (visible while `submitting` or after completion)
  - "Dismiss" button (visible only when `status !== 'submitting'`)
- **Minimized pill:** Icon + status label only; expand on click.
- **Hidden:** When `status === 'idle'`.

### 3. Mount indicator in `src/dev-ui/app/layouts/default.vue`

Add `<FloatingProgressIndicator />` to the root layout so it renders on every page:

```html
<!-- layouts/default.vue -->
<template>
  <div>
    <!-- existing layout -->
    <FloatingProgressIndicator />
  </div>
</template>
```

### 4. Submission logic in `src/dev-ui/app/pages/graph/mutations.vue`

Wire the "Apply Mutations" button and Ctrl/Cmd+Enter handler to the global store:

```typescript
async function submitMutations() {
  const progress = useMutationProgress()
  progress.start(operations.length)

  try {
    const result = await apiFetch('/graph/mutations', {
      method: 'POST',
      body: { mutations: operations },
    })
    progress.succeed(result.applied_count ?? operations.length)
  } catch (err) {
    progress.fail(err.message, err.applied_count ?? 0)
  }
}
```

The backend endpoint for applying mutations is `POST /graph/mutations` (bulk apply).
Verify the actual route against the backend API spec before wiring.

### 5. `src/dev-ui/app/tests/mutations-submission.test.ts`

Create this test file and write tests **before** implementing (TDD):

1. **Indicator appears on submission:**
   Assert that clicking "Apply Mutations" causes the `FloatingProgressIndicator` to
   render with status "submitting".

2. **Indicator shows operation count:**
   Assert that the indicator displays the correct operation count from the submitted
   JSONL.

3. **Elapsed time is shown:**
   Assert that an elapsed time element is present while status is "submitting".

4. **Indicator persists across navigation:**
   Assert that after submission starts, navigating to a different route (e.g. `/query`)
   does not remove the indicator from the DOM.

5. **Indicator shows success state:**
   Assert that after the API call resolves successfully, the indicator changes to
   "success" status.

6. **Indicator can be minimized:**
   Assert that clicking "Minimize" collapses the indicator to the pill view.

7. **Indicator can be dismissed after completion:**
   Assert that clicking "Dismiss" (after success or failure) removes the indicator
   (sets status back to "idle").

8. **Failure: error message shown:**
   Assert that when the API call rejects, the indicator shows the error message.

9. **Failure: partial success count:**
   Assert that when `appliedCount > 0` and status is "failed", the indicator shows
   "N operations applied before failure".

10. **Failure: dismiss still works:**
    Assert that "Dismiss" is available and removes the indicator after failure.

**Pinia test setup:**

```typescript
import { setActivePinia, createPinia } from 'pinia'

beforeEach(() => {
  setActivePinia(createPinia())
})
```

## Acceptance Criteria

- Clicking "Apply Mutations" triggers `POST /graph/mutations` and shows the floating
  indicator in "submitting" state in the bottom-right corner.
- The indicator displays: status, operation count, elapsed time.
- The indicator remains visible after navigating away from `/graph/mutations`.
- The indicator minimizes to a pill and expands on click.
- The indicator can be dismissed (status → idle, indicator hidden) after success or failure.
- On failure: the indicator shows the error message and the number of ops applied before
  failure (if any).
- All tests in `src/dev-ui/app/tests/mutations-submission.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test`

## UI Location

- `src/dev-ui/app/stores/mutationProgress.ts` — Pinia store
- `src/dev-ui/app/components/mutations/FloatingProgressIndicator.vue` — indicator component
- `src/dev-ui/app/layouts/default.vue` — mount point (global visibility)
- `src/dev-ui/app/pages/graph/mutations.vue` — submission wiring
- `src/dev-ui/app/tests/mutations-submission.test.ts` — submission scenario tests

## Dependencies

- **task-060** must be complete: the Mutations Console editor and `submitMutations()`
  function must exist before the global progress indicator can be wired to them.

## TDD Cycle

1. Create `tests/mutations-submission.test.ts` — write all 10 tests (they will fail).
2. Create `stores/mutationProgress.ts` Pinia store.
3. Implement `FloatingProgressIndicator.vue`.
4. Mount indicator in `layouts/default.vue`.
5. Wire `submitMutations()` in `mutations.vue` to the store.
6. Run `cd src/dev-ui && pnpm test` — all tests pass.
7. Commit atomically per conventional commit conventions.
