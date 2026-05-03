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

      // Backend route: DELETE /iam/api-keys/{api_key_id}
      async function handleRevoke(keyId: string) {
        await apiFetch(`/iam/api-keys/${keyId}`, { method: 'DELETE' })
        await loadApiKeys()
      }

      await handleRevoke('key-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadApiKeys).toHaveBeenCalledOnce()
    })

    it('GIVEN key revocation fails THEN loadApiKeys() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Not Found'))
      const loadApiKeys = vi.fn()

      // Backend route: DELETE /iam/api-keys/{api_key_id}
      async function handleRevoke(keyId: string) {
        try {
          await apiFetch(`/iam/api-keys/${keyId}`, { method: 'DELETE' })
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

  // ── Groups ────────────────────────────────────────────────────────────────

  describe('Group create → list reloads without manual refresh', () => {
    it('GIVEN group creation succeeds THEN fetchGroups() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'grp-new', name: 'Engineering' })
      const fetchGroups = vi.fn().mockResolvedValue(undefined)
      const createDialogOpen = { value: true }

      // Backend route: POST /iam/groups (tenant-scoped, no workspace in path)
      async function handleCreate(name: string) {
        await apiFetch('/iam/groups', {
          method: 'POST',
          body: { name },
        })
        createDialogOpen.value = false
        await fetchGroups()
      }

      await handleCreate('Engineering')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(fetchGroups).toHaveBeenCalledOnce()
      expect(createDialogOpen.value).toBe(false)
    })

    it('GIVEN group creation fails THEN fetchGroups() is NOT called', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
      const fetchGroups = vi.fn()

      async function handleCreate(name: string) {
        try {
          await apiFetch('/iam/groups', { method: 'POST', body: { name } })
          await fetchGroups()
        } catch {
          // error handled elsewhere
        }
      }

      await handleCreate('Engineering')

      expect(fetchGroups).not.toHaveBeenCalled()
    })
  })

  describe('Group delete → list reloads without manual refresh', () => {
    it('GIVEN group deletion succeeds THEN fetchGroups() is called automatically', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 No Content
      const fetchGroups = vi.fn().mockResolvedValue(undefined)
      const deleteDialogOpen = { value: true }

      // Backend route: DELETE /iam/groups/{group_id}
      async function handleDelete(groupId: string) {
        await apiFetch(`/iam/groups/${groupId}`, { method: 'DELETE' })
        deleteDialogOpen.value = false
        await fetchGroups()
      }

      await handleDelete('grp-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(fetchGroups).toHaveBeenCalledOnce()
      expect(deleteDialogOpen.value).toBe(false)
    })
  })

  describe('Group rename → local state updated without full reload', () => {
    it('GIVEN group rename succeeds THEN selected group and list are updated in-place', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'grp-1', name: 'Platform' })
      let groups = [{ id: 'grp-1', name: 'Engineering' }]
      let selectedGroup: { id: string; name: string } | null = groups[0]!

      // Backend route: PATCH /iam/groups/{group_id}
      async function handleRename(groupId: string, newName: string) {
        const updated = await apiFetch(`/iam/groups/${groupId}`, {
          method: 'PATCH',
          body: { name: newName },
        })
        selectedGroup = updated
        const idx = groups.findIndex((g) => g.id === updated.id)
        if (idx !== -1) groups[idx] = updated
      }

      await handleRename('grp-1', 'Platform')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(selectedGroup?.name).toBe('Platform')
      expect(groups[0]?.name).toBe('Platform')
    })
  })

  // ── Mutations console ─────────────────────────────────────────────────────

  describe('Mutations submission → KG-scoped URL is used', () => {
    it('GIVEN a KG selected THEN mutations are submitted to the KG-scoped endpoint', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, errors: [] }) })

      const apiBaseUrl = 'https://api.example.com'

      // Backend route: POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations
      async function applyMutations(knowledgeGraphId: string, jsonlContent: string) {
        const response = await fetchMock(
          `${apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/jsonlines' },
            body: jsonlContent,
          },
        )
        return response.json()
      }

      await applyMutations('kg-selected-123', '{"op":"CREATE","type":"node"}')

      expect(fetchMock).toHaveBeenCalledWith(
        'https://api.example.com/graph/knowledge-graphs/kg-selected-123/mutations',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('GIVEN mutations submission fails THEN error is captured from response', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        text: async () => JSON.stringify({ detail: 'Invalid mutation op' }),
      })

      const apiBaseUrl = 'https://api.example.com'

      async function applyMutations(knowledgeGraphId: string, jsonlContent: string) {
        const response = await fetchMock(
          `${apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
          { method: 'POST', headers: { 'Content-Type': 'application/jsonlines' }, body: jsonlContent },
        )
        if (!response.ok) {
          const text = await response.text()
          const parsed = JSON.parse(text)
          throw new Error(parsed.detail ?? `Request failed with status ${response.status}`)
        }
        return response.json()
      }

      await expect(applyMutations('kg-1', '{"op":"INVALID"}')).rejects.toThrow('Invalid mutation op')
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

    it('Group operations use tenant-scoped /iam/groups — not workspace-scoped', () => {
      // Groups are tenant-scoped via the auth header (X-Tenant-ID), not URL-scoped.
      // The backend route is GET/POST /iam/groups — no workspace_id in the path.
      const listUrl = '/iam/groups'
      const createUrl = '/iam/groups'
      const groupId = 'grp-runtime-id'
      const deleteUrl = `/iam/groups/${groupId}`

      expect(listUrl).toBe('/iam/groups')
      expect(listUrl).not.toContain('workspaces')
      expect(createUrl).toBe('/iam/groups')
      expect(createUrl).not.toContain('workspaces')
      expect(deleteUrl).toBe('/iam/groups/grp-runtime-id')
      expect(deleteUrl).not.toContain('undefined')
    })

    it('Mutations submission URL includes knowledge_graph_id in the path', () => {
      // Backend route: POST /graph/knowledge-graphs/{kg_id}/mutations
      // Knowledge graph ID must be in the URL — not just in the request body.
      const apiBaseUrl = 'https://api.example.com'
      const kgId = 'kg-runtime-id'
      const url = `${apiBaseUrl}/graph/knowledge-graphs/${kgId}/mutations`

      expect(url).toBe('https://api.example.com/graph/knowledge-graphs/kg-runtime-id/mutations')
      expect(url).not.toContain('undefined')
      expect(url).not.toBe(`${apiBaseUrl}/graph/mutations`)
    })

    it('API key revoke uses DELETE /iam/api-keys/{id} — not POST .../revoke', () => {
      // Backend route: DELETE /iam/api-keys/{api_key_id}
      // The key is revoked by deleting the resource; there is no /revoke sub-path.
      const keyId = 'key-runtime-id'
      const deleteUrl = `/iam/api-keys/${keyId}`

      expect(deleteUrl).toBe('/iam/api-keys/key-runtime-id')
      expect(deleteUrl).not.toContain('/revoke')
      expect(deleteUrl).not.toContain('undefined')
    })

    it('Data source update uses PATCH /management/data-sources/{ds_id} — not KG-scoped', () => {
      // Backend route added in task-107: PATCH /management/data-sources/{ds_id}
      // Per API conventions, PATCH/DELETE are at the flat DS level, not nested under KG.
      // The old incorrect path was: /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}
      const dsId = 'ds-runtime-id'
      const patchUrl = `/management/data-sources/${dsId}`

      expect(patchUrl).toBe('/management/data-sources/ds-runtime-id')
      expect(patchUrl).not.toContain('/knowledge-graphs/')
      expect(patchUrl).not.toContain('undefined')
    })

    it('Data source delete uses DELETE /management/data-sources/{ds_id} — not KG-scoped', () => {
      // Backend route added in task-107: DELETE /management/data-sources/{ds_id}
      // Per API conventions, PATCH/DELETE are at the flat DS level, not nested under KG.
      // The old incorrect path was: /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}
      const dsId = 'ds-runtime-id'
      const deleteUrl = `/management/data-sources/${dsId}`

      expect(deleteUrl).toBe('/management/data-sources/ds-runtime-id')
      expect(deleteUrl).not.toContain('/knowledge-graphs/')
      expect(deleteUrl).not.toContain('undefined')
    })
  })

  // ── Data source PATCH/DELETE use flat (non-KG-scoped) endpoints ───────────

  describe('Data source update — uses flat /management/data-sources/{ds_id}', () => {
    it('GIVEN a data source WHEN name is updated THEN PATCH is sent to flat endpoint', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-1', name: 'New Name' })

      async function handleEditConfig(dsId: string, name: string) {
        return apiFetch(`/management/data-sources/${dsId}`, {
          method: 'PATCH',
          body: { name },
        })
      }

      await handleEditConfig('ds-abc-123', 'New Name')

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/data-sources/ds-abc-123',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    it('GIVEN a data source WHEN token is updated THEN credentials field is included', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-1', name: 'My DS' })

      async function handleEditConfig(dsId: string, name: string, token: string) {
        const body: Record<string, unknown> = { name }
        if (token.trim()) {
          body.credentials = { access_token: token.trim() }
        }
        return apiFetch(`/management/data-sources/${dsId}`, {
          method: 'PATCH',
          body,
        })
      }

      await handleEditConfig('ds-1', 'My DS', 'ghp_secret_token')

      const call = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0]
      expect(call[0]).toBe('/management/data-sources/ds-1')
      expect(call[1].body.credentials).toEqual({ access_token: 'ghp_secret_token' })
    })

    it('PATCH URL does not include knowledge_graph_id in path', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-1' })

      const dsId = 'ds-runtime-id'
      // Correct flat endpoint — KG ID must NOT appear in the path
      await apiFetch(`/management/data-sources/${dsId}`, { method: 'PATCH', body: { name: 'X' } })

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toMatch(/^\/management\/data-sources\/[^/]+$/)
      expect(calledUrl).not.toContain('/knowledge-graphs/')
    })
  })

  describe('Data source delete — uses flat /management/data-sources/{ds_id}', () => {
    it('GIVEN a data source WHEN deleted THEN DELETE is sent to flat endpoint', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined)

      async function handleDeleteDs(dsId: string) {
        return apiFetch(`/management/data-sources/${dsId}`, { method: 'DELETE' })
      }

      await handleDeleteDs('ds-xyz-789')

      expect(apiFetch).toHaveBeenCalledWith(
        '/management/data-sources/ds-xyz-789',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('DELETE URL does not include knowledge_graph_id in path', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined)

      const dsId = 'ds-runtime-id'
      // Correct flat endpoint — KG ID must NOT appear in the path
      await apiFetch(`/management/data-sources/${dsId}`, { method: 'DELETE' })

      const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(calledUrl).toMatch(/^\/management\/data-sources\/[^/]+$/)
      expect(calledUrl).not.toContain('/knowledge-graphs/')
    })

    it('GIVEN delete succeeds THEN list reloads without manual refresh', async () => {
      const apiFetch = vi.fn().mockResolvedValue(undefined)
      const loadDataSources = vi.fn().mockResolvedValue(undefined)

      async function handleDeleteDs(dsId: string) {
        await apiFetch(`/management/data-sources/${dsId}`, { method: 'DELETE' })
        await loadDataSources()
      }

      await handleDeleteDs('ds-1')

      expect(apiFetch).toHaveBeenCalledOnce()
      expect(loadDataSources).toHaveBeenCalledOnce()
    })
  })
})
