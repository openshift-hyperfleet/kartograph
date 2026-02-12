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

  function applyMutations(jsonlContent: string): Promise<MutationResult> {
    return apiFetch<MutationResult>('/graph/mutations', {
      method: 'POST',
      body: jsonlContent,
      headers: { 'Content-Type': 'application/x-ndjson' },
    })
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
