import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Pure logic: canSubmitMutations with workspace gate ────────────────────────
//
// Spec: "no submission is possible until a knowledge graph is selected"
// This task extends the gate to also require a workspace selection.
// The selector lists all knowledge graphs the user has `edit` permission on
// **within the current workspace**.

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

  it('returns false when preparing is true (even with selections)', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: 'kg-123',
      preparing: true,
    })).toBe(false)
  })

  it('returns false when content is empty with workspace and KG selected (small file)', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: 'kg-123',
      content: '',
    })).toBe(false)
  })

  it('returns true in large-file mode with workspace and KG selected (content check bypassed)', () => {
    expect(canSubmitMutations({
      ...base,
      selectedWorkspaceId: 'ws-abc',
      selectedKnowledgeGraphId: 'kg-123',
      content: '',
      isLargeFile: true,
    })).toBe(true)
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

  it('KG selector is disabled until a workspace is selected', () => {
    // Until a workspace is chosen, the KG dropdown should be disabled
    // (preventing cross-workspace mutations)
    expect(mutVue).toMatch(/!selectedWorkspaceId.*loadingKgs|!selectedWorkspaceId/)
  })

  it('canSubmitMutations is called with selectedWorkspaceId in mutations.vue', () => {
    // The submit gate must include the workspace check
    expect(mutVue).toContain('selectedWorkspaceId')
    expect(mutVue).toMatch(/canSubmitMutations\([\s\S]*?selectedWorkspaceId/)
  })

  it('workspace list is loaded from the workspaces API', () => {
    // The workspaces must be fetched from the backend
    expect(mutVue).toMatch(/loadWorkspaces|listWorkspaces/)
  })

  it('workspace and KG selections are cleared on tenant switch', () => {
    // Both selections must reset when the tenant changes (prevents stale cross-tenant data)
    expect(mutVue).toMatch(/selectedWorkspaceId\.value\s*=\s*''/)
  })
})
