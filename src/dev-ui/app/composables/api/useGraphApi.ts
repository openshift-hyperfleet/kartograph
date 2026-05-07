import type {
  MutationResult,
  NodeRecord,
  NodeNeighborsResult,
  SchemaLabelsResponse,
  TypeDefinition,
  VisualizerNode,
  VisualizerEdge,
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
   * Apply JSONL mutations to the graph scoped to a specific knowledge graph.
   *
   * Uses native `fetch` instead of `$fetch`/ofetch because large mutation
   * payloads can take 30+ seconds to process. `$fetch` and browser-level
   * CORS preflight caching can cause spurious "NetworkError" / CORS failures
   * on long-running requests. Native `fetch` with explicit signal handling
   * is more reliable for these cases.
   *
   * @param knowledgeGraphId - The ID of the target knowledge graph. The backend
   *   enforces `edit` permission on this resource and stamps it on all
   *   CREATE/UPDATE operations.
   */
  async function applyMutations(
    knowledgeGraphId: string,
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
      `${config.public.apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
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

  // ── Visualizer ────────────────────────────────────────────────────────

  async function getBulkGraphData(
    knowledgeGraphId?: string,
    options?: {
      signal?: AbortSignal
      onProgress?: (received: number, total: number | null) => void
    },
  ): Promise<{ nodes: VisualizerNode[]; edges: VisualizerEdge[] }> {
    const config = useRuntimeConfig()
    const { accessToken } = useAuth()
    const currentTenantId = useState<string | null>('tenant:current', () => null)

    const params = new URLSearchParams()
    if (knowledgeGraphId) params.set('knowledge_graph_id', knowledgeGraphId)
    const qs = params.toString()
    const url = `${config.public.apiBaseUrl}/graph/visualizer/data${qs ? `?${qs}` : ''}`

    const headers: Record<string, string> = {}
    if (accessToken.value) headers['Authorization'] = `Bearer ${accessToken.value}`
    if (currentTenantId.value) headers['X-Tenant-ID'] = currentTenantId.value

    const response = await fetch(url, { headers, signal: options?.signal })

    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(text || `Request failed with status ${response.status}`)
    }

    const contentLength = response.headers.get('content-length')
    const total = contentLength ? parseInt(contentLength, 10) : null
    const reader = response.body?.getReader()

    if (!reader) return response.json()

    const chunks: Uint8Array[] = []
    let received = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      received += value.length
      options?.onProgress?.(received, total)
    }

    const all = new Uint8Array(received)
    let pos = 0
    for (const chunk of chunks) {
      all.set(chunk, pos)
      pos += chunk.length
    }

    return JSON.parse(new TextDecoder().decode(all))
  }

  return {
    applyMutations,
    findNodesBySlug,
    getNodeNeighbors,
    listNodeLabels,
    listEdgeLabels,
    getNodeSchema,
    getEdgeSchema,
    getBulkGraphData,
  }
}
