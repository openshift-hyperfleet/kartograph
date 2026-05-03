---
id: task-131
title: "Mutations Console — test floating progress indicator persists across route navigation"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-129]
round: 0
branch: null
pr: null
pr_title: "test(ui): add navigation-persistence test for mutations floating progress indicator"
pr_description: |
  ## What and Why

  The Mutations Console spec requires that the floating progress indicator
  **persists when the user navigates away from the mutations console**:

  > **Scenario: Submission**
  > - AND the indicator persists when the user navigates away from the mutations console
  > - AND the indicator can be minimized to a compact pill or dismissed after completion

  Task-129 implements the floating indicator using Vue's `<Teleport to="body">` and
  a Pinia store (`useMutationSubmissionStore`). However, neither task-129 nor the
  existing `mutations-submission.test.ts` includes a test that explicitly simulates
  a route change and verifies the indicator remains visible after the
  `MutationsConsolePage` component unmounts.

  Without this test, a developer could break persistence — for example, by
  accidentally placing indicator state in a component-local `ref` instead of the
  Pinia store, or by calling `store.$reset()` in the page's `onUnmounted` hook —
  without any CI gate catching the regression.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Mutations Console — Scenario: Submission**:
    "the indicator persists when the user navigates away from the mutations console"
  - **Requirement: Mutations Console — Scenario: Submission**:
    "the indicator can be minimized to a compact pill or dismissed after completion"

  ## What This Change Does

  Adds a new test file
  `src/dev-ui/app/tests/mutations-indicator-persistence.test.ts`
  containing three focused tests:

  ### `TestFloatingIndicatorPersistsAcrossNavigation`

  **`test_indicator_remains_visible_after_navigating_away`**
  1. Mount the application with the router at `/explore/mutations`.
  2. Set `useMutationSubmissionStore` to `submitting` state (simulating an
     in-progress submission).
  3. Push the router to a different route (e.g., `/data/knowledge-graphs`),
     causing `MutationsConsolePage` to unmount.
  4. Assert that the `FloatingMutationProgress` component is still present in
     `document.body` (Teleport target) after the route change.
  5. Assert that `useMutationSubmissionStore().status` is still `'submitting'`.

  **`test_indicator_in_success_state_persists_after_navigation`**
  1. Set the store to `success` state (submission completed).
  2. Navigate away from the mutations console.
  3. Assert the indicator is still rendered in the document body.
  4. Assert the store still reports `success`.

  **`test_dismiss_removes_indicator_permanently`**
  1. Set the store to `success` state.
  2. Click the dismiss ("×") button on the indicator.
  3. Assert the indicator is removed from the DOM.
  4. Navigate away and back: assert the indicator does NOT reappear
     (store is cleared, not just hidden).

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/mutations-indicator-persistence.test.ts` — new test file
  - `src/dev-ui/app/stores/mutationSubmission.ts` — read to understand store shape;
    no production code changes expected if task-129 implemented it correctly

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test mutations-indicator-persistence
  ```

  If `test_indicator_remains_visible_after_navigating_away` fails, the most likely
  root cause is that `MutationsConsolePage.vue` calls `store.$reset()` (or equivalent)
  in its `onUnmounted` hook. Remove the reset call — persistence is the contract.

  If `test_dismiss_removes_indicator_permanently` fails, verify that the dismiss
  action clears the Pinia store (not just sets a `visible: false` flag), so the
  indicator does not reappear when navigating back to the mutations console.

  ## Implementation Notes for the Agent

  - Use `@nuxt/test-utils` or `@vue/test-utils` with a fake router — the same
    test infrastructure already in use by `mutations-submission.test.ts` and peers.
  - The `<Teleport to="body">` component renders into `document.body`, so the test
    must query `document.body` (not the component wrapper) to assert indicator presence.
  - The Pinia store must be created fresh for each test (use `setActivePinia` with
    `createPinia()` in `beforeEach`) to avoid cross-test state pollution.
  - Write tests FIRST (TDD), then fix any production code needed to make them pass.

  ## Caveats

  - Depends on task-129 providing `FloatingMutationProgress.vue` and
    `useMutationSubmissionStore`. If task-129 is not yet complete, this task is
    blocked.
  - If task-129 chose a different state-management approach (e.g., a composable
    with `ref` rather than Pinia), adjust the test to reference the correct state
    container; the persistence contract (survive route change) is the same.
  - Do not modify `mutations-submission.test.ts` — keep the new persistence tests
    in their own file so they can be run in isolation.
---
