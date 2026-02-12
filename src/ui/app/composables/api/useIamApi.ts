import type {
  TenantResponse,
  TenantMemberResponse,
  WorkspaceResponse,
  WorkspaceListResponse,
  GroupResponse,
  APIKeyResponse,
  APIKeyCreatedResponse,
} from '~/types'

/**
 * Typed API client for the IAM bounded context.
 *
 * Covers Tenants, Workspaces, Groups, and API Keys.
 */
export function useIamApi() {
  const { apiFetch } = useApiClient()

  // ── Tenants ────────────────────────────────────────────────────────────

  function listTenants(): Promise<TenantResponse[]> {
    return apiFetch<TenantResponse[]>('/iam/tenants')
  }

  function getTenant(tenantId: string): Promise<TenantResponse> {
    return apiFetch<TenantResponse>(`/iam/tenants/${tenantId}`)
  }

  function createTenant(data: { name: string }): Promise<TenantResponse> {
    return apiFetch<TenantResponse>('/iam/tenants', {
      method: 'POST',
      body: data,
    })
  }

  function deleteTenant(tenantId: string): Promise<void> {
    return apiFetch<void>(`/iam/tenants/${tenantId}`, {
      method: 'DELETE',
    })
  }

  function listTenantMembers(tenantId: string): Promise<TenantMemberResponse[]> {
    return apiFetch<TenantMemberResponse[]>(`/iam/tenants/${tenantId}/members`)
  }

  function addTenantMember(
    tenantId: string,
    data: { user_id: string; role: 'admin' | 'member' },
  ): Promise<TenantMemberResponse> {
    return apiFetch<TenantMemberResponse>(`/iam/tenants/${tenantId}/members`, {
      method: 'POST',
      body: data,
    })
  }

  function removeTenantMember(tenantId: string, userId: string): Promise<void> {
    return apiFetch<void>(`/iam/tenants/${tenantId}/members/${userId}`, {
      method: 'DELETE',
    })
  }

  // ── Workspaces ─────────────────────────────────────────────────────────

  function listWorkspaces(): Promise<WorkspaceListResponse> {
    return apiFetch<WorkspaceListResponse>('/iam/workspaces')
  }

  function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
    return apiFetch<WorkspaceResponse>(`/iam/workspaces/${workspaceId}`)
  }

  function createWorkspace(data: {
    name: string
    parent_workspace_id: string
  }): Promise<WorkspaceResponse> {
    return apiFetch<WorkspaceResponse>('/iam/workspaces', {
      method: 'POST',
      body: data,
    })
  }

  function deleteWorkspace(workspaceId: string): Promise<void> {
    return apiFetch<void>(`/iam/workspaces/${workspaceId}`, {
      method: 'DELETE',
    })
  }

  // ── Groups ─────────────────────────────────────────────────────────────

  function createGroup(data: { name: string }): Promise<GroupResponse> {
    return apiFetch<GroupResponse>('/iam/groups', {
      method: 'POST',
      body: data,
    })
  }

  function getGroup(groupId: string): Promise<GroupResponse> {
    return apiFetch<GroupResponse>(`/iam/groups/${groupId}`)
  }

  function deleteGroup(groupId: string): Promise<void> {
    return apiFetch<void>(`/iam/groups/${groupId}`, {
      method: 'DELETE',
    })
  }

  // ── API Keys ───────────────────────────────────────────────────────────

  function createApiKey(data: {
    name: string
    expires_in_days?: number
  }): Promise<APIKeyCreatedResponse> {
    return apiFetch<APIKeyCreatedResponse>('/iam/api-keys', {
      method: 'POST',
      body: data,
    })
  }

  function listApiKeys(userId?: string): Promise<APIKeyResponse[]> {
    const query: Record<string, string> = {}
    if (userId) query.user_id = userId

    return apiFetch<APIKeyResponse[]>('/iam/api-keys', { query })
  }

  function revokeApiKey(apiKeyId: string): Promise<void> {
    return apiFetch<void>(`/iam/api-keys/${apiKeyId}`, {
      method: 'DELETE',
    })
  }

  return {
    // Tenants
    listTenants,
    getTenant,
    createTenant,
    deleteTenant,
    listTenantMembers,
    addTenantMember,
    removeTenantMember,
    // Workspaces
    listWorkspaces,
    getWorkspace,
    createWorkspace,
    deleteWorkspace,
    // Groups
    createGroup,
    getGroup,
    deleteGroup,
    // API Keys
    createApiKey,
    listApiKeys,
    revokeApiKey,
  }
}
