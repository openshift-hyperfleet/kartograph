import type {
  MutationResult,
  NodeRecord,
  NodeNeighborsResult,
  SchemaLabelsResponse,
  TypeDefinition,
} from '~/types'

/**
 * Typed API client for the Graph bounded context.
 *
 * Covers mutations, node look-ups, and schema introspection.
 */
export function useGraphApi() {
  const { apiFetch } = useApiClient()

  // ── Mutations ──────────────────────────────────────────────────────────

  /**
   * Apply JSONL mutations to the graph.
   *
   * Uses native `fetch` instead of `$fetch`/ofetch because large mutation
   * payloads can take 30+ seconds to process. `$fetch` and browser-level
   * CORS preflight caching can cause spurious "NetworkError" / CORS failures
   * on long-running requests. Native `fetch` with explicit signal handling
   * is more reliable for these cases.
   */
  async function applyMutations(
    jsonlContent: string,
    options?: { signal?: AbortSignal },
  ): Promise<MutationResult> {
    const config = useRuntimeConfig()
    const { accessToken } = useAuth()
    const currentTenantId = useState<string | null>('tenant:current', () => null)

    const headers: Record<string, string> = {
      'Content-Type': 'application/jsonlines',
    }
    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`
    }
    if (currentTenantId.value) {
      headers['X-Tenant-ID'] = currentTenantId.value
    }

    const response = await fetch(
      `${config.public.apiBaseUrl}/graph/mutations`,
      {
        method: 'POST',
        headers,
        body: jsonlContent,
        signal: options?.signal,
      },
    )

    if (!response.ok) {
      const errorBody = await response.text().catch(() => '')
      let message = `Request failed with status ${response.status}`
      try {
        const parsed = JSON.parse(errorBody)
        if (parsed.detail) message = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail)
      } catch {
        if (errorBody) message = errorBody
      }
      throw new Error(message)
    }

    return response.json() as Promise<MutationResult>
  }

  // ── Nodes ──────────────────────────────────────────────────────────────

  function findNodesBySlug(
    slug: string,
    nodeType?: string,
  ): Promise<{ nodes: NodeRecord[] }> {
    const query: Record<string, string> = { slug }
    if (nodeType) query.node_type = nodeType

    return apiFetch<{ nodes: NodeRecord[] }>('/graph/nodes/by-slug', { query })
  }

  function getNodeNeighbors(nodeId: string): Promise<NodeNeighborsResult> {
    return apiFetch<NodeNeighborsResult>(`/graph/nodes/${nodeId}/neighbors`)
  }

  // ── Schema ─────────────────────────────────────────────────────────────

  function listNodeLabels(
    search?: string,
    hasProperty?: string,
  ): Promise<SchemaLabelsResponse> {
    const query: Record<string, string> = {}
    if (search) query.search = search
    if (hasProperty) query.has_property = hasProperty

    return apiFetch<SchemaLabelsResponse>('/graph/schema/nodes', { query })
  }

  function listEdgeLabels(search?: string): Promise<SchemaLabelsResponse> {
    const query: Record<string, string> = {}
    if (search) query.search = search

    return apiFetch<SchemaLabelsResponse>('/graph/schema/edges', { query })
  }

  function getNodeSchema(label: string): Promise<TypeDefinition> {
    return apiFetch<TypeDefinition>(`/graph/schema/nodes/${label}`)
  }

  function getEdgeSchema(label: string): Promise<TypeDefinition> {
    return apiFetch<TypeDefinition>(`/graph/schema/edges/${label}`)
  }

  return {
    applyMutations,
    findNodesBySlug,
    getNodeNeighbors,
    listNodeLabels,
    listEdgeLabels,
    getNodeSchema,
    getEdgeSchema,
  }
}
