import type { CypherResult, GraphData, GraphNode, GraphEdge } from '~/types'

function isNodeObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const obj = value as Record<string, unknown>
  return 'id' in obj && 'label' in obj && 'properties' in obj && !('start_id' in obj)
}

function isEdgeObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const obj = value as Record<string, unknown>
  return 'id' in obj && 'label' in obj && 'start_id' in obj && 'end_id' in obj
}

function resolveDisplayName(props: Record<string, unknown>, label: string): string {
  if (typeof props.name === 'string' && props.name) return props.name
  if (typeof props.slug === 'string' && props.slug) return props.slug
  if (typeof props.title === 'string' && props.title) return props.title
  return label
}

function scanValue(
  value: unknown,
  nodeMap: Map<string, GraphNode>,
  edgeMap: Map<string, GraphEdge>,
): void {
  if (!value || typeof value !== 'object') return

  if (Array.isArray(value)) {
    for (const item of value) scanValue(item, nodeMap, edgeMap)
    return
  }

  // Check edge first (edges have all node fields plus start_id/end_id)
  if (isEdgeObject(value)) {
    const id = String(value.id)
    if (!edgeMap.has(id)) {
      const props = (value.properties as Record<string, unknown>) ?? {}
      edgeMap.set(id, {
        id,
        label: String(value.label),
        source: String(value.start_id),
        target: String(value.end_id),
        properties: props,
      })
    }
    return
  }

  if (isNodeObject(value)) {
    const id = String(value.id)
    if (!nodeMap.has(id)) {
      const props = (value.properties as Record<string, unknown>) ?? {}
      nodeMap.set(id, {
        id,
        label: String(value.label),
        properties: props,
        displayName: resolveDisplayName(props, String(value.label)),
      })
    }
    return
  }

  // Recurse into map/object values
  for (const v of Object.values(value as Record<string, unknown>)) {
    scanValue(v, nodeMap, edgeMap)
  }
}

/**
 * Extract graph nodes and edges from a CypherResult.
 * Recursively scans all row values for AGE node/edge objects,
 * deduplicates by id, and filters edges with missing endpoints.
 */
export function extractGraphData(result: CypherResult): GraphData {
  const nodeMap = new Map<string, GraphNode>()
  const edgeMap = new Map<string, GraphEdge>()

  for (const row of result.rows) {
    for (const value of Object.values(row)) {
      scanValue(value, nodeMap, edgeMap)
    }
  }

  const nodes = Array.from(nodeMap.values())
  // Only include edges where both endpoints exist in our node set
  const edges = Array.from(edgeMap.values()).filter(
    e => nodeMap.has(e.source) && nodeMap.has(e.target),
  )

  return { nodes, edges }
}
