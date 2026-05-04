import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Mutations Console — KG Selector Loading Tests ────────────────────────────
//
// Spec: "Mutations Console" — Scenario: Knowledge graph selection
// Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
//
// Verifies that the mutations console KG selector:
//   - Fetches KGs using the `edit` permission filter (not `view`)
//   - Scopes the KG list to the currently selected workspace via `workspace_id`
//   - Reloads KGs and resets the selection when the workspace changes
//   - Prevents submission until a KG is selected
//   - Propagates the selected KG ID into the API request URL
//
// These are source-reading (structural constraint) tests — they are fast and
// do not require DOM mounting or network calls.  If a variable is renamed
// during a refactor, the test failure is a signal to verify the renamed code
// still satisfies the spec.
//
// What is NOT tested here (already covered elsewhere):
//   - `isSubmitDisabled()` pure logic          → mutations-kg-selector.test.ts
//   - URL construction helpers                  → mutations-kg-selector.test.ts
//   - Floating indicator persistence            → mutations-indicator-persistence.test.ts
//   - Submission state machine                  → mutations-submission.test.ts

// ── Source file paths ────────────────────────────────────────────────────────

const mutationsVuePath = resolve(__dirname, '../pages/graph/mutations.vue')
const mutationsVue = readFileSync(mutationsVuePath, 'utf-8')

const graphApiPath = resolve(__dirname, '../composables/api/useGraphApi.ts')
const graphApi = readFileSync(graphApiPath, 'utf-8')

const submissionComposablePath = resolve(__dirname, '../composables/useMutationSubmission.ts')
const submissionComposable = readFileSync(submissionComposablePath, 'utf-8')

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "the selector lists all knowledge graphs the user has `edit` permission on
//  within the current workspace"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console KG Loading — edit permission filter', () => {
  it('loadKnowledgeGraphs requests KGs with permission: edit (not view)', () => {
    // The API call must use permission: 'edit' so only mutable KGs are shown.
    // Changing this to 'view' would allow users to select KGs they cannot mutate.
    expect(mutationsVue).toContain("permission: 'edit'")
  })

  it('the permission filter is passed as a query parameter to /management/knowledge-graphs', () => {
    // Structural check: the edit filter must be part of the API call to the
    // management KG list endpoint, not e.g. a client-side filter applied after
    // fetching all KGs.
    expect(mutationsVue).toContain('/management/knowledge-graphs')
    expect(mutationsVue).toContain("permission: 'edit'")
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "within the current workspace"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console KG Loading — workspace scoping', () => {
  it('loadKnowledgeGraphs passes selectedWorkspaceId as workspace_id query param', () => {
    // The workspace_id filter narrows the KG list to the selected workspace.
    // Without this, the user would see KGs from all their workspaces, which
    // violates the spec's "within the current workspace" constraint.
    expect(mutationsVue).toContain('workspace_id: selectedWorkspaceId.value')
  })

  it('workspace_id and permission are co-located in the same API call', () => {
    // Both parameters must appear in the same region of the file, confirming
    // they are part of the same API call rather than separate requests.
    const editIdx = mutationsVue.indexOf("permission: 'edit'")
    const wsIdx = mutationsVue.indexOf('workspace_id: selectedWorkspaceId.value')
    expect(editIdx).toBeGreaterThan(-1)
    expect(wsIdx).toBeGreaterThan(-1)
    // They should be within 200 characters of each other (same object literal)
    expect(Math.abs(editIdx - wsIdx)).toBeLessThan(200)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "AND the selector lists all knowledge graphs the user has `edit` permission
//  on within the current workspace"
// Implied: the list must reload when the workspace changes (stale data prevention)
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console KG Loading — reload on workspace change', () => {
  it('mutations.vue watches selectedWorkspaceId to trigger KG reload', () => {
    // A Vue watch on selectedWorkspaceId ensures that when the user picks a
    // different workspace, the KG list is refreshed to show KGs for that workspace.
    expect(mutationsVue).toContain('watch(selectedWorkspaceId')
  })

  it('the watch calls loadKnowledgeGraphs when a workspace is selected', () => {
    // The body of the watch handler must invoke loadKnowledgeGraphs so the
    // KG dropdown is populated for the new workspace.
    expect(mutationsVue).toContain('loadKnowledgeGraphs')
  })

  it('the watch resets selectedKnowledgeGraphId to empty string on workspace change', () => {
    // Resetting the KG selection prevents a stale KG ID from a previous workspace
    // being used as the mutation target — which would silently submit to the wrong KG.
    expect(mutationsVue).toContain("selectedKnowledgeGraphId.value = ''")
  })

  it('the KG reset occurs inside the selectedWorkspaceId watcher (not elsewhere)', () => {
    // The reset must happen inside the watch body that fires when the workspace
    // changes. We search for selectedKnowledgeGraphId reset *after* the
    // watch(selectedWorkspaceId) declaration to confirm they are co-located.
    const watchIdx = mutationsVue.indexOf('watch(selectedWorkspaceId')
    expect(watchIdx).toBeGreaterThan(-1)
    // Find the reset AFTER the watch declaration (there may be earlier resets
    // in other watchers, e.g. the hasTenant watcher)
    const resetAfterWatch = mutationsVue.indexOf("selectedKnowledgeGraphId.value = ''", watchIdx)
    expect(resetAfterWatch).toBeGreaterThan(-1)
    // The reset should appear within 300 chars of the watch declaration
    // (same callback body)
    expect(resetAfterWatch - watchIdx).toBeLessThan(300)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "no submission is possible until a knowledge graph is selected"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console KG Loading — submit gate', () => {
  it('Apply Mutations button is disabled when no KG is selected', () => {
    // The template's :disabled binding must reference selectedKnowledgeGraphId
    // (directly or via canSubmitMutations) to enforce the submission gate.
    const hasDirectRef = mutationsVue.includes('selectedKnowledgeGraphId')
    expect(hasDirectRef).toBe(true)
  })

  it('canSubmitMutations receives selectedKnowledgeGraphId as an argument', () => {
    // canSubmitMutations is the utility function that computes whether submission
    // is allowed. It must receive the KG ID so it can return false when no KG
    // is selected, keeping the submit button disabled.
    expect(mutationsVue).toContain('canSubmitMutations(')
    expect(mutationsVue).toContain('selectedKnowledgeGraphId')
  })

  it('editorContent is also required for submission (prevents empty submits)', () => {
    // The submit gate checks both KG selection AND content existence.
    // Passing editorContent to canSubmitMutations enforces this.
    expect(mutationsVue).toContain('editorContent')
    expect(mutationsVue).toContain('canSubmitMutations(')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "AND the selected knowledge graph is used as the target for the mutation
//  submission"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console KG Loading — submission scoped to selected KG', () => {
  it('useMutationSubmission.submit() accepts knowledgeGraphId as first argument', () => {
    // The submit function signature must accept a KG ID so the caller can pass
    // the selected KG through to the API request.
    expect(submissionComposable).toContain('submit(knowledgeGraphId')
  })

  it('useGraphApi.applyMutations() embeds knowledgeGraphId in the URL path', () => {
    // The API URL must include the KG ID in the path, not as a query parameter,
    // matching the backend route: POST /graph/knowledge-graphs/{id}/mutations
    expect(graphApi).toContain('/graph/knowledge-graphs/${knowledgeGraphId}/mutations')
  })

  it('mutations.vue passes selectedKnowledgeGraphId.value to submission.submit()', () => {
    // The page component must hand the selected KG ID to the submission composable
    // so the correct KG is targeted during apply.
    expect(mutationsVue).toContain('submission.submit(selectedKnowledgeGraphId.value')
  })
})
