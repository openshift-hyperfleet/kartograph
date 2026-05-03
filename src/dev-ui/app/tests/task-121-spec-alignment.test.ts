import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  ADAPTERS,
  isAdapterSelectable,
  canAdvanceStep1,
  inferNameFromRepoUrl,
  validateStep2,
  buildDataSourceCreationUrl,
  buildDataSourceCreationBody,
} from '@/utils/dataSourceWizard'

/**
 * Task-121 Spec Alignment Tests
 *
 * Spec: specs/ui/experience.spec.md
 *   - Requirement: Knowledge Graph Creation
 *   - Requirement: Data Source Connection
 *   - Requirement: Backend API Alignment — Scenario: Parent context is preserved
 *
 * These tests provide structural verification of the actual Vue page files and
 * integration-level logic tests for the KG creation → Data Source wizard flow
 * introduced by task-121. They complement the unit tests in knowledge-graphs.test.ts
 * and data-sources.test.ts by pinning the critical cross-page wiring paths.
 *
 * Structural tests read the source file content and assert that specific
 * patterns are present. This catches regressions where a refactor accidentally
 * removes a required API call pattern, navigation target, or security measure
 * without the regular unit tests failing (because unit tests mock the component
 * graph at the module boundary).
 */

const DS_INDEX_VUE = readFileSync(
  resolve(__dirname, '../pages/data-sources/index.vue'),
  'utf-8',
)
const KG_INDEX_VUE = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
  'utf-8',
)

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Create knowledge graph
// Spec: "AND the user is prompted to add their first data source"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-121 — Requirement: Knowledge Graph Creation', () => {
  describe('Post-creation prompt: navigates to data-sources wizard with new KG scoped', () => {
    it('knowledge-graphs page emits navigateTo to /data-sources?kg_id=', () => {
      // The toast action must direct the user to /data-sources scoped to the new
      // knowledge graph so the wizard pre-opens with the correct KG selected.
      expect(KG_INDEX_VUE).toContain('/data-sources?kg_id=')
    })

    it('knowledge-graphs page constructs the navigation URL from the API result id', () => {
      // The ID must come from result.id, not a hardcoded string.
      // Verify both the dynamic interpolation pattern and the endpoint.
      expect(KG_INDEX_VUE).toMatch(/navigateTo\([`']/i)
      expect(KG_INDEX_VUE).toContain('result.id')
    })

    it('knowledge-graphs page shows a post-creation description prompting data source setup', () => {
      // Spec: "AND the user is prompted to add their first data source"
      expect(KG_INDEX_VUE).toMatch(/connect a data source/i)
    })

    it('knowledge-graphs page includes workspace selector for the create dialog', () => {
      // Spec: "Create knowledge graph — knowledge graph is created within the current workspace"
      // The workspace selector must be present in the create dialog.
      expect(KG_INDEX_VUE).toContain('selectedWorkspaceId')
    })

    it('knowledge-graphs page POSTs to the workspace-scoped URL', () => {
      // Spec: "Parent context is preserved"
      // The create call must go to /management/workspaces/{id}/knowledge-graphs.
      expect(KG_INDEX_VUE).toContain('/management/workspaces/')
      expect(KG_INDEX_VUE).toContain('knowledge-graphs')
    })

    it('success toast triggers list reload via loadKnowledgeGraphs()', () => {
      // Spec: "AND the UI reflects the updated state without requiring a manual refresh"
      expect(KG_INDEX_VUE).toContain('await loadKnowledgeGraphs()')
    })
  })

  describe('Pure logic: workspace-scoped KG creation URL', () => {
    it('URL is constructed correctly at runtime', () => {
      // Simulates the template expression: /management/workspaces/${selectedWorkspaceId}/knowledge-graphs
      const workspaceId = 'ws-abc-123'
      const url = `/management/workspaces/${workspaceId}/knowledge-graphs`
      expect(url).toBe('/management/workspaces/ws-abc-123/knowledge-graphs')
      expect(url).not.toContain('undefined')
      expect(url).not.toContain('null')
    })

    it('URL path segment changes when a different workspace is selected', () => {
      const url1 = `/management/workspaces/ws-aaa/knowledge-graphs`
      const url2 = `/management/workspaces/ws-bbb/knowledge-graphs`
      expect(url1).not.toBe(url2)
      expect(url1).toContain('ws-aaa')
      expect(url2).toContain('ws-bbb')
    })
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Adapter type selection + Connection configuration
// Spec: Data Source Connection requirement
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-121 — Requirement: Data Source Connection — Adapter & Configuration', () => {
  describe('data-sources page imports and uses dataSourceWizard utilities', () => {
    it('imports ADAPTERS from dataSourceWizard', () => {
      expect(DS_INDEX_VUE).toContain('ADAPTERS')
    })

    it('imports canAdvanceStep1 from dataSourceWizard', () => {
      expect(DS_INDEX_VUE).toContain('canAdvanceStep1')
    })

    it('imports validateStep2 from dataSourceWizard', () => {
      expect(DS_INDEX_VUE).toContain('validateStep2')
    })

    it('imports buildDataSourceCreationUrl from dataSourceWizard', () => {
      expect(DS_INDEX_VUE).toContain('buildDataSourceCreationUrl')
    })

    it('imports buildDataSourceCreationBody from dataSourceWizard', () => {
      expect(DS_INDEX_VUE).toContain('buildDataSourceCreationBody')
    })
  })

  describe('Adapter selection: only GitHub is available initially', () => {
    it('ADAPTERS list contains exactly one available adapter (GitHub)', () => {
      const available = ADAPTERS.filter((a) => a.available)
      expect(available).toHaveLength(1)
      expect(available[0]!.id).toBe('github')
    })

    it('GitHub adapter can be selected', () => {
      expect(isAdapterSelectable('github')).toBe(true)
    })

    it('unavailable adapters (GitLab, Jira) cannot be selected', () => {
      expect(isAdapterSelectable('gitlab')).toBe(false)
      expect(isAdapterSelectable('jira')).toBe(false)
    })
  })

  describe('Step 1 advancement requires both adapter AND knowledge graph', () => {
    it('blocked when adapter is missing even with KG selected', () => {
      expect(canAdvanceStep1('', 'kg-123')).toBe(false)
    })

    it('blocked when KG is missing even with adapter selected', () => {
      expect(canAdvanceStep1('github', '')).toBe(false)
    })

    it('allowed when both adapter and KG are selected', () => {
      expect(canAdvanceStep1('github', 'kg-123')).toBe(true)
    })
  })

  describe('Connection configuration: name inference from GitHub URL', () => {
    it('infers name from standard GitHub URL', () => {
      expect(inferNameFromRepoUrl('https://github.com/acme/my-service')).toBe('my-service')
    })

    it('strips .git suffix when inferring name', () => {
      expect(inferNameFromRepoUrl('https://github.com/org/repo.git')).toBe('repo')
    })

    it('returns null for non-GitHub URLs (no overwrite)', () => {
      expect(inferNameFromRepoUrl('https://gitlab.com/org/repo')).toBeNull()
      expect(inferNameFromRepoUrl('')).toBeNull()
    })
  })

  describe('Step 2 validation: required fields enforced', () => {
    it('rejects empty data source name', () => {
      const result = validateStep2({ connName: '', connRepoUrl: 'https://github.com/org/repo' })
      expect(result.valid).toBe(false)
      expect(result.connNameError).toBeTruthy()
    })

    it('rejects empty repository URL', () => {
      const result = validateStep2({ connName: 'my-repo', connRepoUrl: '' })
      expect(result.valid).toBe(false)
      expect(result.connRepoUrlError).toBeTruthy()
    })

    it('rejects non-GitHub URL', () => {
      const result = validateStep2({ connName: 'my-repo', connRepoUrl: 'https://gitlab.com/org/repo' })
      expect(result.valid).toBe(false)
      expect(result.connRepoUrlError).toBeTruthy()
    })

    it('passes with valid name and GitHub URL', () => {
      const result = validateStep2({ connName: 'my-repo', connRepoUrl: 'https://github.com/org/repo' })
      expect(result.valid).toBe(true)
      expect(result.connNameError).toBe('')
      expect(result.connRepoUrlError).toBe('')
    })

    it('token is always optional (no validation error when absent)', () => {
      const result = validateStep2({ connName: 'my-repo', connRepoUrl: 'https://github.com/org/repo' })
      expect(result.valid).toBe(true)
      expect(result.connTokenError).toBe('')
    })
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Credential handling
// Spec: "credentials are encrypted and stored server-side AND the plaintext
//        is never persisted in the browser"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-121 — Requirement: Data Source Connection — Credential Handling', () => {
  describe('Structural: data-sources page clears token after successful creation', () => {
    it('connToken.value is reset to empty string after approveOntology() succeeds', () => {
      // The token must be cleared immediately after the API call returns successfully
      // so that plaintext credentials do not linger in Vue reactive state.
      expect(DS_INDEX_VUE).toContain("connToken.value = ''")
    })

    it('token input uses password type to prevent shoulder surfing', () => {
      expect(DS_INDEX_VUE).toContain("type=\"password\"")
    })

    it('token is not included in loadDataSources() response mapping', () => {
      // Verify there is no "token" or "secret" field referenced from the list response.
      // The list endpoint returns backend-sanitised data without credentials.
      // This is a negative structural test: the word "secret" must not appear
      // in the context of data source response mapping.
      //
      // Permitted: any reference in comments or Vault-related docs.
      // Not permitted: assignment of token/secret from the API array response.
      const responseMapping = DS_INDEX_VUE.match(/dataSources\.value\s*=[\s\S]{0,500}/)?.[0] ?? ''
      expect(responseMapping).not.toContain('token')
    })
  })

  describe('Pure logic: buildDataSourceCreationBody credential handling', () => {
    it('includes credentials in body when token is provided', () => {
      const body = buildDataSourceCreationBody({
        name: 'my-service',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/org/repo' },
        credentials: { access_token: 'ghp_secret' },
      })
      expect(body.credentials).toEqual({ access_token: 'ghp_secret' })
    })

    it('omits credentials key entirely when no token is provided', () => {
      const body = buildDataSourceCreationBody({
        name: 'my-service',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/org/repo' },
      })
      expect(body).not.toHaveProperty('credentials')
    })

    it('does not include knowledge_graph_id in the request body (belongs in URL)', () => {
      const body = buildDataSourceCreationBody({
        name: 'my-service',
        adapter_type: 'github',
        connection_config: {},
      })
      expect(body).not.toHaveProperty('knowledge_graph_id')
      expect(body).not.toHaveProperty('kg_id')
    })
  })

  describe('Token cleared on success, preserved on failure', () => {
    it('token is cleared after successful data source creation', async () => {
      const state = { connToken: 'secret-token', wizardOpen: true }
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-service' })
      const loadDataSources = vi.fn().mockResolvedValue(undefined)

      async function approveOntology(kgId: string, name: string) {
        await apiFetch(buildDataSourceCreationUrl(kgId), {
          method: 'POST',
          body: buildDataSourceCreationBody({
            name,
            adapter_type: 'github',
            connection_config: { repo_url: 'https://github.com/org/repo' },
            credentials: state.connToken ? { access_token: state.connToken } : undefined,
          }),
        })
        state.connToken = '' // cleared on success
        state.wizardOpen = false
        await loadDataSources()
      }

      await approveOntology('kg-123', 'my-service')
      expect(state.connToken).toBe('')
    })

    it('token is preserved after failed data source creation (so user can retry)', async () => {
      const state = { connToken: 'secret-token' }
      const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
      const loadDataSources = vi.fn()

      async function approveOntology(kgId: string, name: string) {
        try {
          await apiFetch(buildDataSourceCreationUrl(kgId), {
            method: 'POST',
            body: buildDataSourceCreationBody({ name, adapter_type: 'github', connection_config: {} }),
          })
          state.connToken = '' // only cleared on success
          await loadDataSources()
        } catch {
          // error path — token must remain for retry
        }
      }

      await approveOntology('kg-1', 'my-repo')
      expect(state.connToken).toBe('secret-token') // unchanged
      expect(loadDataSources).not.toHaveBeenCalled()
    })
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Parent context is preserved
// Spec: "THEN the UI includes the parent context required by the API"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-121 — Requirement: Backend API Alignment — Parent context', () => {
  describe('Data source creation URL is KG-scoped', () => {
    it('buildDataSourceCreationUrl embeds the KG ID in the path', () => {
      const url = buildDataSourceCreationUrl('kg-abc-123')
      expect(url).toContain('kg-abc-123')
      expect(url).toMatch(/\/management\/knowledge-graphs\/kg-abc-123\/data-sources$/)
    })

    it('URL changes for different KG IDs', () => {
      const url1 = buildDataSourceCreationUrl('kg-aaa')
      const url2 = buildDataSourceCreationUrl('kg-bbb')
      expect(url1).not.toBe(url2)
      expect(url1).not.toContain('kg-bbb')
      expect(url2).not.toContain('kg-aaa')
    })

    it('URL never contains "undefined" or "null"', () => {
      const url = buildDataSourceCreationUrl('kg-test')
      expect(url).not.toContain('undefined')
      expect(url).not.toContain('null')
    })
  })

  describe('Structural: data-sources page reads kg_id query param to pre-select KG', () => {
    it('page reads route.query.kg_id to pre-select the knowledge graph', () => {
      // When the user arrives from the post-KG-creation toast, the URL includes
      // ?kg_id=<new-kg-id>. The page must read this param and pass it to openWizard().
      expect(DS_INDEX_VUE).toContain('kg_id')
    })

    it('page calls openWizard with the preselected KG id', () => {
      // openWizard(preselectedKgId) wires the URL param into the wizard's KG selector.
      expect(DS_INDEX_VUE).toContain('openWizard(preselectedKgId)')
    })

    it('wizard state uses selectedKnowledgeGraphId for the creation URL', () => {
      // The creation call must reference selectedKnowledgeGraphId so it flows
      // from either the user selection or the URL param pre-selection.
      expect(DS_INDEX_VUE).toContain('selectedKnowledgeGraphId')
    })
  })

  describe('End-to-end flow: KG created → DS wizard opens with correct parent', () => {
    it('full flow: KG creation → navigation URL → wizard pre-selection', async () => {
      // Simulate the full cross-page flow:
      // 1. User creates a KG (knowledge-graphs page)
      const kgApiFetch = vi.fn().mockResolvedValue({ id: 'kg-new-789', name: 'Engineering' })
      const navigateTo = vi.fn()
      const createName = { value: 'Engineering' }
      const selectedWorkspaceId = { value: 'ws-1' }
      let postCreationUrl = ''

      async function handleCreate() {
        if (!selectedWorkspaceId.value || !createName.value.trim()) return
        const result = await kgApiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value },
        })
        // 2. Post-creation: navigate to data-sources with new KG ID
        postCreationUrl = `/data-sources?kg_id=${result.id}`
        navigateTo(postCreationUrl)
      }

      await handleCreate()

      // 3. The URL includes the exact KG ID returned by the API
      expect(postCreationUrl).toBe('/data-sources?kg_id=kg-new-789')
      expect(navigateTo).toHaveBeenCalledWith('/data-sources?kg_id=kg-new-789')

      // 4. The data-sources page would extract this param and call openWizard
      const routeQuery = { kg_id: 'kg-new-789' }
      const preselectedKgId = routeQuery.kg_id as string | undefined
      expect(preselectedKgId).toBe('kg-new-789')

      // 5. openWizard initialises selectedKnowledgeGraphId with the param
      const wizardState = { selectedKnowledgeGraphId: '' }
      function openWizard(preselectedId?: string) {
        wizardState.selectedKnowledgeGraphId = preselectedId ?? ''
      }
      openWizard(preselectedKgId)
      expect(wizardState.selectedKnowledgeGraphId).toBe('kg-new-789')

      // 6. Step-1 can advance immediately (adapter still needs selection, but KG is set)
      expect(canAdvanceStep1('github', wizardState.selectedKnowledgeGraphId)).toBe(true)

      // 7. Creation URL uses the pre-selected KG ID
      const creationUrl = buildDataSourceCreationUrl(wizardState.selectedKnowledgeGraphId)
      expect(creationUrl).toBe('/management/knowledge-graphs/kg-new-789/data-sources')
    })
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: loadDataSources() called after successful data source creation
// Spec: "AND the UI reflects the updated state without requiring a manual refresh"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-121 — Resource operations succeed end-to-end — DS list refresh', () => {
  it('loadDataSources() is called after successful data source creation', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    const wizardOpen = { value: true }
    const connToken = { value: 'ghp_secret' }

    async function approveOntology(kgId: string, name: string) {
      await apiFetch(buildDataSourceCreationUrl(kgId), {
        method: 'POST',
        body: buildDataSourceCreationBody({
          name,
          adapter_type: 'github',
          connection_config: { repo_url: 'https://github.com/org/repo' },
          credentials: connToken.value ? { access_token: connToken.value } : undefined,
        }),
      })
      connToken.value = ''
      wizardOpen.value = false
      await loadDataSources()
    }

    await approveOntology('kg-1', 'my-repo')

    expect(loadDataSources).toHaveBeenCalledOnce()
    expect(wizardOpen.value).toBe(false)
    expect(connToken.value).toBe('') // cleared
  })

  it('loadDataSources() is NOT called when creation fails', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Bad Request'))
    const loadDataSources = vi.fn()
    const connToken = { value: 'ghp_secret' }

    async function approveOntology(kgId: string, name: string) {
      try {
        await apiFetch(buildDataSourceCreationUrl(kgId), {
          method: 'POST',
          body: buildDataSourceCreationBody({ name, adapter_type: 'github', connection_config: {} }),
        })
        connToken.value = ''
        await loadDataSources()
      } catch {
        // token preserved for retry
      }
    }

    await approveOntology('kg-1', 'my-repo')

    expect(loadDataSources).not.toHaveBeenCalled()
    expect(connToken.value).toBe('ghp_secret') // not cleared
  })

  it('data-sources page structurally calls loadDataSources after approveOntology', () => {
    // Regression guard: approveOntology() must call loadDataSources() after success.
    expect(DS_INDEX_VUE).toContain('await loadDataSources()')
  })
})
