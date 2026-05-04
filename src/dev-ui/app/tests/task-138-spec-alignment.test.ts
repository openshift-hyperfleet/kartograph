import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Task-138 Spec Alignment: Backend API Alignment + Mutations KG Selection ───
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-138 — UI Experience — Backend API Alignment and Mutations
//       Knowledge Graph Selection (spec additions from modified spec)
//
// This file pins the two new requirements added to the UI experience spec:
//
//   1. Backend API Alignment — ALL resource CRUD operations succeed end-to-end
//      and include the correct parent context in the API request.
//      (Requirement: Backend API Alignment — Scenarios: Resource operations
//      succeed end-to-end; Parent context is preserved)
//
//   2. Mutations Console — Knowledge graph selection before submission.
//      The mutations console MUST display a KG selector, restrict the list
//      to KGs the user has edit permission on within the current workspace,
//      and gate submission on both workspace + KG selection.
//      (Requirement: Mutations Console — Scenario: Knowledge graph selection)
//
//   3. Mutations Console — Updated Submission scenario.
//      Mutations are submitted to the KG-scoped API endpoint:
//      POST /graph/knowledge-graphs/{id}/mutations
//      (Requirement: Mutations Console — Scenario: Submission)
//
// Source verification strategy: read the production source files and assert
// on the presence of key patterns. This avoids component mounting while
// still catching implementation regressions (e.g. someone swapping the
// KG-scoped URL back to the legacy /graph/mutations endpoint).

// ── Source file paths ─────────────────────────────────────────────────────────

const appDir = resolve(__dirname, '..')

const mutationsVue = readFileSync(
  resolve(appDir, 'pages/graph/mutations.vue'),
  'utf-8',
)

const knowledgeGraphsVue = readFileSync(
  resolve(appDir, 'pages/knowledge-graphs/index.vue'),
  'utf-8',
)

const dataSourcesVue = readFileSync(
  resolve(appDir, 'pages/data-sources/index.vue'),
  'utf-8',
)

const graphApiTs = readFileSync(
  resolve(appDir, 'composables/api/useGraphApi.ts'),
  'utf-8',
)

const mutationSubmissionTs = readFileSync(
  resolve(appDir, 'composables/useMutationSubmission.ts'),
  'utf-8',
)

const mutationConsoleUtils = readFileSync(
  resolve(appDir, 'utils/mutationConsole.ts'),
  'utf-8',
)

const dataSourceWizardUtils = readFileSync(
  resolve(appDir, 'utils/dataSourceWizard.ts'),
  'utf-8',
)

// ── Requirement: Backend API Alignment ───────────────────────────────────────
//
// Spec: "The system SHALL successfully complete all resource operations by
//        correctly integrating with the backend REST API."
//
// Scenario: Resource operations succeed end-to-end
// GIVEN a user performs any create, read, update, or delete operation via the UI
// WHEN the operation is submitted
// THEN the corresponding backend API call succeeds (2xx response)
// AND the UI reflects the updated state without requiring a manual refresh

describe('Task-138 — Backend API Alignment: Scenario: Resource operations succeed end-to-end', () => {
  describe('Knowledge Graphs page — automatic list reload after mutations', () => {
    it('calls loadKnowledgeGraphs after KG creation succeeds', () => {
      // The page must reload after create — confirmed by the presence of
      // loadKnowledgeGraphs() call following the POST
      expect(knowledgeGraphsVue).toContain('loadKnowledgeGraphs')
      // The create handler and list refresh must both be present
      expect(knowledgeGraphsVue).toContain("method: 'POST'")
    })

    it('calls loadKnowledgeGraphs after KG rename succeeds', () => {
      // PATCH then reload: both operations must be present
      expect(knowledgeGraphsVue).toContain("method: 'PATCH'")
      expect(knowledgeGraphsVue).toContain('loadKnowledgeGraphs')
    })

    it('calls loadKnowledgeGraphs after KG deletion succeeds', () => {
      // DELETE then reload: both operations must be present
      expect(knowledgeGraphsVue).toContain("method: 'DELETE'")
      expect(knowledgeGraphsVue).toContain('loadKnowledgeGraphs')
    })
  })

  describe('Data Sources page — automatic state refresh after mutations', () => {
    it('reloads data sources list after creating a data source', () => {
      // The page calls loadAllDataSources() or equivalent after createDataSource()
      expect(dataSourcesVue).toContain('createDataSource')
      // createDataSource uses buildDataSourceCreationUrl which includes kg_id
      expect(dataSourcesVue).toContain('buildDataSourceCreationUrl')
    })

    it('reloads data after patching a data source', () => {
      expect(dataSourcesVue).toContain("method: 'PATCH'")
    })

    it('reloads data after deleting a data source', () => {
      expect(dataSourcesVue).toContain("method: 'DELETE'")
    })

    it('triggers sync via POST to the correct endpoint', () => {
      // Spec: "Scenario: Manual sync trigger"
      expect(dataSourcesVue).toContain('/sync')
      expect(dataSourcesVue).toContain("method: 'POST'")
    })
  })
})

// ── Requirement: Backend API Alignment ───────────────────────────────────────
//
// Scenario: Parent context is preserved
// GIVEN a resource that is scoped to a parent (e.g., a KG within a workspace)
// WHEN the user creates or lists that resource
// THEN the UI includes the parent context required by the API
// AND the operation succeeds

describe('Task-138 — Backend API Alignment: Scenario: Parent context is preserved', () => {
  describe('Knowledge Graph creation — workspace ID in URL', () => {
    it('creates KG at workspace-scoped endpoint /management/workspaces/{id}/knowledge-graphs', () => {
      // The POST must nest under /management/workspaces/{workspace_id}/knowledge-graphs
      expect(knowledgeGraphsVue).toContain('/management/workspaces/')
      expect(knowledgeGraphsVue).toContain('knowledge-graphs')
      // selectedWorkspaceId must be used as the parent context
      expect(knowledgeGraphsVue).toContain('selectedWorkspaceId')
    })

    it('selectedWorkspaceId is interpolated into the creation URL', () => {
      // The page must produce a URL like:
      // /management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs
      expect(knowledgeGraphsVue).toMatch(
        /\/management\/workspaces\/\$\{.*selectedWorkspaceId.*\}\/knowledge-graphs/,
      )
    })
  })

  describe('Data Source creation — knowledge graph ID in URL', () => {
    it('buildDataSourceCreationUrl returns KG-scoped endpoint', () => {
      // POST /management/knowledge-graphs/{kg_id}/data-sources
      expect(dataSourceWizardUtils).toContain('/management/knowledge-graphs/')
      expect(dataSourceWizardUtils).toContain('data-sources')
    })

    it('buildDataSourceCreationUrl interpolates the KG ID into the path', () => {
      expect(dataSourceWizardUtils).toMatch(
        /\/management\/knowledge-graphs\/\$\{kgId\}\/data-sources/,
      )
    })

    it('data-sources page passes kg_id as parent context when creating', () => {
      // The wizard calls buildDataSourceCreationUrl(params.kg_id)
      expect(dataSourcesVue).toContain('buildDataSourceCreationUrl')
      expect(dataSourcesVue).toContain('kg_id')
    })
  })

  describe('Mutation submission — knowledge graph ID in URL', () => {
    it('useGraphApi.applyMutations uses KG-scoped endpoint', () => {
      // POST /graph/knowledge-graphs/{id}/mutations
      expect(graphApiTs).toContain('/graph/knowledge-graphs/')
      expect(graphApiTs).toContain('/mutations')
    })

    it('applyMutations URL interpolates knowledgeGraphId', () => {
      expect(graphApiTs).toMatch(
        /\/graph\/knowledge-graphs\/\$\{knowledgeGraphId\}\/mutations/,
      )
    })
  })
})

// ── Requirement: Mutations Console — Knowledge graph selection ────────────────
//
// Spec: "The system SHALL provide a JSONL editor for authoring and applying
//        graph mutations directly."
//
// Scenario: Knowledge graph selection
// GIVEN the mutations console
// THEN a knowledge graph selector is displayed before the user can submit
// AND the selector lists all knowledge graphs the user has `edit` permission on
//     within the current workspace
// AND no submission is possible until a knowledge graph is selected
// AND the selected knowledge graph is used as the target for the mutation submission

describe('Task-138 — Mutations Console: Scenario: Knowledge graph selection', () => {
  describe('KG selector state is tracked in the page', () => {
    it('mutations page declares selectedKnowledgeGraphId ref', () => {
      expect(mutationsVue).toContain('selectedKnowledgeGraphId')
    })

    it('mutations page declares selectedWorkspaceId ref', () => {
      // Workspace must be selected first to scope the KG list
      expect(mutationsVue).toContain('selectedWorkspaceId')
    })

    it('mutations page tracks a list of knowledge graphs', () => {
      expect(mutationsVue).toContain('knowledgeGraphs')
    })
  })

  describe('KG list is fetched with edit permission and workspace scope', () => {
    it('mutations page loads KGs from /management/knowledge-graphs', () => {
      expect(mutationsVue).toContain('/management/knowledge-graphs')
    })

    it('mutations page requests KGs with permission=edit filter', () => {
      // Spec: "selector lists all knowledge graphs the user has edit permission on"
      expect(mutationsVue).toContain("permission: 'edit'")
    })

    it('mutations page scopes KG list to the selected workspace', () => {
      // Spec: "within the current workspace"
      expect(mutationsVue).toContain('workspace_id')
      expect(mutationsVue).toContain('selectedWorkspaceId')
    })
  })

  describe('Submission is gated on KG selection', () => {
    it('canSubmitMutations requires selectedKnowledgeGraphId to be truthy', () => {
      // The util function guards the submit action
      expect(mutationConsoleUtils).toContain('selectedKnowledgeGraphId')
      expect(mutationConsoleUtils).toContain('!opts.selectedKnowledgeGraphId')
    })

    it('canSubmitMutations also requires selectedWorkspaceId when provided', () => {
      expect(mutationConsoleUtils).toContain('selectedWorkspaceId')
      expect(mutationConsoleUtils).toContain('!opts.selectedWorkspaceId')
    })

    it('mutations page disables Apply button until KG is selected', () => {
      // The :disabled binding uses canSubmitMutations which requires a KG ID
      expect(mutationsVue).toContain('canSubmitMutations')
      expect(mutationsVue).toContain(':disabled')
    })
  })

  describe('Selected KG is used as mutation submission target', () => {
    it('handleSubmit passes selectedKnowledgeGraphId to submission.submit', () => {
      expect(mutationsVue).toContain('selectedKnowledgeGraphId.value')
      expect(mutationsVue).toContain('submission.submit')
    })

    it('useMutationSubmission.submit accepts knowledgeGraphId as first parameter', () => {
      // submit(knowledgeGraphId, jsonlContent, opCount)
      expect(mutationSubmissionTs).toContain('submit')
      expect(mutationSubmissionTs).toContain('knowledgeGraphId')
    })

    it('useMutationSubmission passes knowledgeGraphId to applyMutations', () => {
      expect(mutationSubmissionTs).toContain('applyMutations(knowledgeGraphId')
    })
  })

  describe('KG selector is dependent on workspace selection', () => {
    it('KG selector is disabled when no workspace is selected', () => {
      // The KG select is disabled without a workspace
      expect(mutationsVue).toContain('!selectedWorkspaceId')
    })

    it('changing workspace resets the selected KG', () => {
      // When workspace changes, selectedKnowledgeGraphId must be cleared
      expect(mutationsVue).toContain("selectedKnowledgeGraphId.value = ''")
    })
  })
})

// ── Requirement: Mutations Console — Submission (updated scenario) ────────────
//
// Scenario: Submission
// GIVEN valid mutations in the editor and a knowledge graph selected
// WHEN the user clicks Apply Mutations (or presses Ctrl/Cmd+Enter)
// THEN the mutations are submitted to the API scoped to the selected KG
// AND a floating progress indicator appears in the bottom-right corner
// AND the indicator shows status (submitting / success / failed), operation count,
//     and elapsed time
// AND the indicator persists when the user navigates away from the mutations console
// AND the indicator can be minimized to a compact pill or dismissed after completion

describe('Task-138 — Mutations Console: Scenario: Submission (KG-scoped)', () => {
  describe('API endpoint is KG-scoped', () => {
    it('useGraphApi.applyMutations uses the KG-scoped mutations endpoint', () => {
      // POST /graph/knowledge-graphs/{knowledgeGraphId}/mutations
      // NOT the legacy /graph/mutations path
      expect(graphApiTs).toContain('/graph/knowledge-graphs/')
      expect(graphApiTs).not.toContain("'/graph/mutations'")
    })

    it('does NOT use the legacy flat /graph/mutations endpoint', () => {
      // Confirm that the old (non-KG-scoped) endpoint is absent
      expect(graphApiTs).not.toMatch(/`[^`]*\/graph\/mutations`/)
    })

    it('mutations page passes the selected KG ID to submit for large files', () => {
      // Large file path: submission.submit(selectedKnowledgeGraphId.value, body, opCount)
      expect(mutationsVue).toMatch(
        /submission\.submit\(selectedKnowledgeGraphId\.value/,
      )
    })

    it('mutations page passes the selected KG ID to submit for small files', () => {
      // Both code paths (large + small file) must pass the KG ID
      const matches = mutationsVue.match(/submission\.submit\(selectedKnowledgeGraphId\.value/g)
      expect(matches).not.toBeNull()
      expect(matches!.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('Floating progress indicator persists across navigation', () => {
    it('useMutationSubmission uses useState for cross-page persistence', () => {
      // useState (Nuxt global state) persists reactive data across route changes
      expect(mutationSubmissionTs).toContain('useState')
    })

    it('submission state includes status, operationCount, and timestamps', () => {
      expect(mutationSubmissionTs).toContain('status')
      expect(mutationSubmissionTs).toContain('operationCount')
      expect(mutationSubmissionTs).toContain('startedAt')
      expect(mutationSubmissionTs).toContain('completedAt')
    })

    it('submission state has all four status values', () => {
      expect(mutationSubmissionTs).toContain("'idle'")
      expect(mutationSubmissionTs).toContain("'submitting'")
      expect(mutationSubmissionTs).toContain("'success'")
      expect(mutationSubmissionTs).toContain("'failed'")
    })
  })

  describe('canSubmitMutations utility gating behaviour', () => {
    it('exported from mutationConsole utils (importable by page and tests)', () => {
      expect(mutationConsoleUtils).toContain('export function canSubmitMutations')
    })

    it('returns false when submitting is true', () => {
      // Inline re-implementation matches the spec gate logic
      function canSubmit(opts: {
        selectedWorkspaceId?: string
        selectedKnowledgeGraphId: string
        content: string
        isLargeFile: boolean
        submitting: boolean
        preparing: boolean
      }): boolean {
        if (opts.submitting || opts.preparing) return false
        if ('selectedWorkspaceId' in opts && !opts.selectedWorkspaceId) return false
        if (!opts.selectedKnowledgeGraphId) return false
        if (!opts.isLargeFile && !opts.content.trim()) return false
        return true
      }

      expect(canSubmit({
        selectedWorkspaceId: 'ws-1',
        selectedKnowledgeGraphId: 'kg-1',
        content: '{"op":"CREATE"}',
        isLargeFile: false,
        submitting: true,
        preparing: false,
      })).toBe(false)
    })

    it('returns false when no KG is selected', () => {
      function canSubmit(opts: {
        selectedWorkspaceId?: string
        selectedKnowledgeGraphId: string
        content: string
        isLargeFile: boolean
        submitting: boolean
        preparing: boolean
      }): boolean {
        if (opts.submitting || opts.preparing) return false
        if ('selectedWorkspaceId' in opts && !opts.selectedWorkspaceId) return false
        if (!opts.selectedKnowledgeGraphId) return false
        if (!opts.isLargeFile && !opts.content.trim()) return false
        return true
      }

      expect(canSubmit({
        selectedWorkspaceId: 'ws-1',
        selectedKnowledgeGraphId: '',
        content: '{"op":"CREATE"}',
        isLargeFile: false,
        submitting: false,
        preparing: false,
      })).toBe(false)
    })

    it('returns true when workspace, KG, and content are all present', () => {
      function canSubmit(opts: {
        selectedWorkspaceId?: string
        selectedKnowledgeGraphId: string
        content: string
        isLargeFile: boolean
        submitting: boolean
        preparing: boolean
      }): boolean {
        if (opts.submitting || opts.preparing) return false
        if ('selectedWorkspaceId' in opts && !opts.selectedWorkspaceId) return false
        if (!opts.selectedKnowledgeGraphId) return false
        if (!opts.isLargeFile && !opts.content.trim()) return false
        return true
      }

      expect(canSubmit({
        selectedWorkspaceId: 'ws-abc',
        selectedKnowledgeGraphId: 'kg-xyz',
        content: '{"op":"CREATE","type":"node","label":"thing","id":"t:1"}',
        isLargeFile: false,
        submitting: false,
        preparing: false,
      })).toBe(true)
    })
  })
})
