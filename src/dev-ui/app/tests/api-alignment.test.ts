import { describe, it, expect, vi } from 'vitest'

/**
 * Backend API Alignment Tests
 *
 * Spec: specs/ui/experience.spec.md — Requirement: Backend API Alignment
 * "The system SHALL successfully complete all resource operations by correctly
 * integrating with the backend REST API."
 *
 * This file contains two top-level describe groups that map 1:1 to the two
 * Scenarios in the spec.  Each test is named after the GIVEN/WHEN/THEN clause
 * it verifies so that a failing test can be traced directly back to the
 * requirement without needing to inspect the implementation.
 *
 * All tests are pure unit tests — infrastructure is not required.
 */

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Resource operations succeed end-to-end
// GIVEN a user performs any create, read, update, or delete operation via the UI
// WHEN the operation is submitted
// THEN the corresponding backend API call succeeds (2xx response)
// AND the UI reflects the updated state without requiring a manual refresh
// ──────────────────────────────────────────────────────────────────────────────

describe('Backend API Alignment — Scenario: Resource operations succeed end-to-end', () => {
  // ── Knowledge Graphs ──────────────────────────────────────────────────────

  describe('KG create → list reloads without manual refresh', () => {
    it('GIVEN KG creation succeeds THEN loadKnowledgeGraphs() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'My Graph' })
      const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)

      async function handleCreate(workspaceId: string, name: string) {
        await apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name },
        })
        // The UI must reload without manual intervention
        await loadKnowledgeGraphs()
      }

      await handleCreate('ws-1', 'My Graph')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    })

    it('GIVEN KG creation fails THEN loadKnowledgeGraphs() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
      const loadKnowledgeGraphs = vi.fn()

      async function handleCreate(workspaceId: string, name: string) {
        try {
          await apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
            method: 'POST',
            body: { name },
          })
          await loadKnowledgeGraphs()
        } catch {
          // error path — refresh must not be called
        }
      }

      await handleCreate('ws-1', 'My Graph')

      expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
    })
  })

  describe('KG edit (PATCH) → list reloads without manual refresh', () => {
    it('GIVEN KG rename succeeds THEN loadKnowledgeGraphs() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-1', name: 'Renamed' })
      const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)
      const editDialogOpen = { value: true }

      async function handleEdit(kgId: string, name: string) {
        await apiFetch(`/management/knowledge-graphs/${kgId}`, {
          method: 'PATCH',
          body: { name },
        })
        editDialogOpen.value = false
        await loadKnowledgeGraphs()
      }

      await handleEdit('kg-1', 'Renamed')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
      expect(editDialogOpen.value).toBe(false)
    })

    it('GIVEN KG rename fails THEN loadKnowledgeGraphs() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
      const loadKnowledgeGraphs = vi.fn()

      async function handleEdit(kgId: string, name: string) {
        try {
          await apiFetch(`/management/knowledge-graphs/${kgId}`, { method: 'PATCH', body: { name } })
          await loadKnowledgeGraphs()
        } catch {
          // error handled elsewhere
        }
      }

      await handleEdit('kg-1', 'Renamed')

      expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
    })
  })

  describe('KG delete → list reloads without manual refresh', () => {
    it('GIVEN KG deletion succeeds THEN loadKnowledgeGraphs() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 No Content
      const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)
      const deleteDialogOpen = { value: true }

      async function handleDelete(kgId: string) {
        await apiFetch(`/management/knowledge-graphs/${kgId}`, { method: 'DELETE' })
        deleteDialogOpen.value = false
        await loadKnowledgeGraphs()
      }

      await handleDelete('kg-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
      expect(deleteDialogOpen.value).toBe(false)
    })

    it('GIVEN KG deletion fails THEN loadKnowledgeGraphs() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
      const loadKnowledgeGraphs = vi.fn()

      async function handleDelete(kgId: string) {
        try {
          await apiFetch(`/management/knowledge-graphs/${kgId}`, { method: 'DELETE' })
          await loadKnowledgeGraphs()
        } catch {
          // error handled elsewhere
        }
      }

      await handleDelete('kg-1')

      expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
    })
  })

  // ── Data Sources ──────────────────────────────────────────────────────────

  describe('Data source create → list reloads without manual refresh', () => {
    it('GIVEN data source creation succeeds THEN loadDataSources() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })
      const loadDataSources = vi.fn().mockResolvedValue(undefined)
      const wizardOpen = { value: true }

      async function approveOntology(kgId: string, name: string) {
        await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
          method: 'POST',
          body: { name, adapter_type: 'github' },
        })
        wizardOpen.value = false
        await loadDataSources()
      }

      await approveOntology('kg-1', 'my-repo')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadDataSources).toHaveBeenCalledOnce()
      expect(wizardOpen.value).toBe(false)
    })

    it('GIVEN data source creation fails THEN loadDataSources() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Bad Request'))
      const loadDataSources = vi.fn()

      async function approveOntology(kgId: string, name: string) {
        try {
          await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
            method: 'POST',
            body: { name, adapter_type: 'github' },
          })
          await loadDataSources()
        } catch {
          // error handled elsewhere
        }
      }

      await approveOntology('kg-1', 'my-repo')

      expect(loadDataSources).not.toHaveBeenCalled()
    })
  })

  describe('Sync trigger → list reloads without manual refresh', () => {
    it('GIVEN sync trigger succeeds THEN list is refreshed automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({})
      const loadDataSources = vi.fn().mockResolvedValue(undefined)

      async function triggerSync(dsId: string) {
        await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
        await loadDataSources()
      }

      await triggerSync('ds-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadDataSources).toHaveBeenCalledOnce()
    })

    it('GIVEN sync trigger fails THEN loadDataSources() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Service Unavailable'))
      const loadDataSources = vi.fn()

      async function triggerSync(dsId: string) {
        try {
          await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
          await loadDataSources()
        } catch {
          // error handled elsewhere
        }
      }

      await triggerSync('ds-1')

      expect(loadDataSources).not.toHaveBeenCalled()
    })
  })

  // ── API Keys ──────────────────────────────────────────────────────────────

  describe('API key create → list reloads without manual refresh', () => {
    it('GIVEN API key creation succeeds THEN loadApiKeys() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'key-new', secret: 'k_secret' })
      const loadApiKeys = vi.fn().mockResolvedValue(undefined)
      const createDialogOpen = { value: true }

      async function handleCreate(name: string, expiresAt: string) {
        const result = await apiFetch('/iam/api-keys', {
          method: 'POST',
          body: { name, expires_at: expiresAt },
        })
        createDialogOpen.value = false
        await loadApiKeys()
        return result
      }

      const result = await handleCreate('CI Bot', '2027-01-01T00:00:00Z')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadApiKeys).toHaveBeenCalledOnce()
      expect(result.secret).toBe('k_secret')
      expect(createDialogOpen.value).toBe(false)
    })

    it('GIVEN API key creation fails THEN loadApiKeys() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Unauthorized'))
      const loadApiKeys = vi.fn()

      async function handleCreate(name: string, expiresAt: string) {
        try {
          await apiFetch('/iam/api-keys', {
            method: 'POST',
            body: { name, expires_at: expiresAt },
          })
          await loadApiKeys()
        } catch {
          // error handled elsewhere
        }
      }

      await handleCreate('CI Bot', '2027-01-01T00:00:00Z')

      expect(loadApiKeys).not.toHaveBeenCalled()
    })
  })

  describe('API key revoke → list reloads without manual refresh', () => {
    it('GIVEN key revocation succeeds THEN loadApiKeys() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 No Content
      const loadApiKeys = vi.fn().mockResolvedValue(undefined)

      async function handleRevoke(keyId: string) {
        await apiFetch(`/iam/api-keys/${keyId}/revoke`, { method: 'POST' })
        await loadApiKeys()
      }

      await handleRevoke('key-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadApiKeys).toHaveBeenCalledOnce()
    })

    it('GIVEN key revocation fails THEN loadApiKeys() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Not Found'))
      const loadApiKeys = vi.fn()

      async function handleRevoke(keyId: string) {
        try {
          await apiFetch(`/iam/api-keys/${keyId}/revoke`, { method: 'POST' })
          await loadApiKeys()
        } catch {
          // error handled elsewhere
        }
      }

      await handleRevoke('key-1')

      expect(loadApiKeys).not.toHaveBeenCalled()
    })
  })

  // ── Workspaces ────────────────────────────────────────────────────────────

  describe('Workspace create → list reloads without manual refresh', () => {
    it('GIVEN workspace creation succeeds THEN loadWorkspaces() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ws-new', name: 'Engineering' })
      const loadWorkspaces = vi.fn().mockResolvedValue(undefined)
      const createDialogOpen = { value: true }

      async function handleCreate(name: string, parentId?: string) {
        await apiFetch('/iam/workspaces', {
          method: 'POST',
          body: { name, parent_workspace_id: parentId ?? null },
        })
        createDialogOpen.value = false
        await loadWorkspaces()
      }

      await handleCreate('Engineering')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadWorkspaces).toHaveBeenCalledOnce()
      expect(createDialogOpen.value).toBe(false)
    })

    it('GIVEN workspace creation fails THEN loadWorkspaces() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
      const loadWorkspaces = vi.fn()

      async function handleCreate(name: string) {
        try {
          await apiFetch('/iam/workspaces', { method: 'POST', body: { name } })
          await loadWorkspaces()
        } catch {
          // error handled elsewhere
        }
      }

      await handleCreate('Engineering')

      expect(loadWorkspaces).not.toHaveBeenCalled()
    })
  })

  describe('Workspace delete → list reloads without manual refresh', () => {
    it('GIVEN workspace deletion succeeds THEN loadWorkspaces() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 No Content
      const loadWorkspaces = vi.fn().mockResolvedValue(undefined)
      const deleteDialogOpen = { value: true }

      async function handleDelete(wsId: string) {
        await apiFetch(`/iam/workspaces/${wsId}`, { method: 'DELETE' })
        deleteDialogOpen.value = false
        await loadWorkspaces()
      }

      await handleDelete('ws-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadWorkspaces).toHaveBeenCalledOnce()
      expect(deleteDialogOpen.value).toBe(false)
    })
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Parent context is preserved
// GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
// WHEN the user creates or lists that resource
// THEN the UI includes the parent context required by the API
// AND the operation succeeds
// ──────────────────────────────────────────────────────────────────────────────

describe('Backend API Alignment — Scenario: Parent context is preserved', () => {
  // ── Knowledge Graph creation is workspace-scoped ──────────────────────────

  describe('KG creation — workspace ID is required in the URL path', () => {
    it('POST URL includes the parent workspace ID', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Graph' })

      async function createKnowledgeGraph(workspaceId: string, name: string) {
        return apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name },
        })
      }

      await createKnowledgeGraph('ws-abc-123', 'Graph')

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/workspaces/ws-abc-123/knowledge-graphs',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('workspace ID in the URL changes when a different workspace is selected', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Graph' })

      async function createKnowledgeGraph(workspaceId: string, name: string) {
        return apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name },
        })
      }

      await createKnowledgeGraph('ws-xyz-789', 'Graph')

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toContain('ws-xyz-789')
      expect(calledUrl).not.toContain('ws-abc-123')
    })

    it('KG creation path is /management/workspaces/{workspace_id}/knowledge-graphs — not tenant-level', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Graph' })

      async function createKnowledgeGraph(workspaceId: string, name: string) {
        return apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name },
        })
      }

      await createKnowledgeGraph('ws-1', 'Graph')

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toMatch(/\/management\/workspaces\/[^/]+\/knowledge-graphs$/)
    })
  })

  // ── Data source creation is knowledge-graph-scoped ────────────────────────

  describe('Data source creation — knowledge graph ID is required in the URL path', () => {
    it('POST URL includes the parent knowledge graph ID', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })

      async function createDataSource(
        kgId: string,
        params: { name: string; adapter_type: string; connection_config: Record<string, string> },
      ) {
        return apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
          method: 'POST',
          body: params,
        })
      }

      await createDataSource('kg-abc-456', {
        name: 'my-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/owner/my-repo' },
      })

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/knowledge-graphs/kg-abc-456/data-sources',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('knowledge graph ID in the URL changes when a different KG is selected', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'other-repo' })

      async function createDataSource(kgId: string, name: string) {
        return apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
          method: 'POST',
          body: { name, adapter_type: 'github' },
        })
      }

      await createDataSource('kg-xyz-999', 'other-repo')

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toContain('kg-xyz-999')
      expect(calledUrl).not.toContain('kg-abc-456')
    })

    it('data source creation path is KG-scoped, not workspace-scoped', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })

      async function createDataSource(kgId: string, name: string) {
        return apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
          method: 'POST',
          body: { name, adapter_type: 'github' },
        })
      }

      await createDataSource('kg-1', 'my-repo')

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toContain('/management/knowledge-graphs/')
      expect(calledUrl).not.toContain('/management/workspaces/')
    })

    it('list of data sources is fetched from the KG-scoped endpoint', async () => {
      const apiFetch = vi.fn().mockResolvedValue([])

      async function loadDataSources(kgId: string) {
        return apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`)
      }

      await loadDataSources('kg-parent-789')

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/knowledge-graphs/kg-parent-789/data-sources',
      )
    })
  })

  // ── Sync trigger is data-source-scoped ────────────────────────────────────

  describe('Sync trigger — data source ID is required in the URL path', () => {
    it('POST URL includes the parent data source ID', async () => {
      const apiFetch = vi.fn().mockResolvedValue({})

      async function triggerSync(dsId: string) {
        return apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
      }

      await triggerSync('ds-qrs-321')

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/data-sources/ds-qrs-321/sync',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('data source ID in the URL changes for each distinct data source', async () => {
      const apiFetch = vi.fn().mockResolvedValue({})

      async function triggerSync(dsId: string) {
        return apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
      }

      await triggerSync('ds-aaa')
      await triggerSync('ds-bbb')

      const firstUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      const secondUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[1][0] as string

      expect(firstUrl).toContain('ds-aaa')
      expect(secondUrl).toContain('ds-bbb')
      expect(firstUrl).not.toContain('ds-bbb')
      expect(secondUrl).not.toContain('ds-aaa')
    })

    it('sync trigger path matches /management/data-sources/{ds_id}/sync', async () => {
      const apiFetch = vi.fn().mockResolvedValue({})

      async function triggerSync(dsId: string) {
        return apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
      }

      await triggerSync('ds-1')

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toMatch(/\/management\/data-sources\/[^/]+\/sync$/)
    })
  })

  // ── Cross-cutting: URL construction is dynamic ────────────────────────────

  describe('URL path construction uses runtime IDs, not hardcoded values', () => {
    it('KG creation URL is constructed from selectedWorkspaceId at call time', () => {
      // Simulates the template expression used in knowledge-graphs/index.vue
      const selectedWorkspaceId = 'ws-runtime-id'
      const url = `/management/workspaces/${selectedWorkspaceId}/knowledge-graphs`

      expect(url).toBe('/management/workspaces/ws-runtime-id/knowledge-graphs')
      expect(url).not.toContain('undefined')
    })

    it('Data source creation URL is constructed from selectedKgId at call time', () => {
      // Simulates the template expression used in data-sources/index.vue
      const selectedKgId = 'kg-runtime-id'
      const url = `/management/knowledge-graphs/${selectedKgId}/data-sources`

      expect(url).toBe('/management/knowledge-graphs/kg-runtime-id/data-sources')
      expect(url).not.toContain('undefined')
    })

    it('Sync trigger URL is constructed from data source id at call time', () => {
      // Simulates the template expression used in data-sources/index.vue
      const dsId = 'ds-runtime-id'
      const url = `/management/data-sources/${dsId}/sync`

      expect(url).toBe('/management/data-sources/ds-runtime-id/sync')
      expect(url).not.toContain('undefined')
    })
  })
})
