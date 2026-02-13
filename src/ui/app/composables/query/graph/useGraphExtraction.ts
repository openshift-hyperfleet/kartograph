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

/** Prefer the application-level ID from properties over the AGE numeric ID. */
function resolveId(ageId: unknown, props: Record<string, unknown>, key = 'id'): string {
  const appId = props[key]
  if (typeof appId === 'string' && appId) return appId
  return String(ageId)
}

// Raw edge data collected during scanning — edge endpoints reference AGE IDs
// which must be remapped to application-level node IDs after all nodes are processed.
interface RawEdge {
  id: string
  label: string
  ageStartId: string
  ageEndId: string
  properties: Record<string, unknown>
}

function scanValue(
  value: unknown,
  nodeMap: Map<string, GraphNode>,
  rawEdges: RawEdge[],
  ageIdToAppId: Map<string, string>,
): void {
  if (!value || typeof value !== 'object') return

  if (Array.isArray(value)) {
    for (const item of value) scanValue(item, nodeMap, rawEdges, ageIdToAppId)
    return
  }

  // Check edge first (edges have all node fields plus start_id/end_id)
  if (isEdgeObject(value)) {
    const props = (value.properties as Record<string, unknown>) ?? {}
    const id = resolveId(value.id, props)
    rawEdges.push({
      id,
      label: String(value.label),
      ageStartId: String(value.start_id),
      ageEndId: String(value.end_id),
      properties: props,
    })
    return
  }

  if (isNodeObject(value)) {
    const props = (value.properties as Record<string, unknown>) ?? {}
    const ageId = String(value.id)
    const appId = resolveId(value.id, props)

    // Track AGE numeric ID → application ID mapping for edge resolution
    ageIdToAppId.set(ageId, appId)

    if (!nodeMap.has(appId)) {
      nodeMap.set(appId, {
        id: appId,
        label: String(value.label),
        properties: props,
        displayName: resolveDisplayName(props, String(value.label)),
      })
    }
    return
  }

  // Recurse into map/object values
  for (const v of Object.values(value as Record<string, unknown>)) {
    scanValue(v, nodeMap, rawEdges, ageIdToAppId)
  }
}

/**
 * Extract graph nodes and edges from a CypherResult.
 * Recursively scans all row values for AGE node/edge objects,
 * deduplicates by id, remaps AGE numeric IDs to application-level IDs,
 * and filters edges with missing endpoints.
 */
export function extractGraphData(result: CypherResult): GraphData {
  const nodeMap = new Map<string, GraphNode>()
  const rawEdges: RawEdge[] = []
  const ageIdToAppId = new Map<string, string>()

  for (const row of result.rows) {
    for (const value of Object.values(row)) {
      scanValue(value, nodeMap, rawEdges, ageIdToAppId)
    }
  }

  // Remap edge endpoints from AGE numeric IDs to application-level IDs,
  // then deduplicate and filter edges with missing endpoints.
  const edgeMap = new Map<string, GraphEdge>()
  for (const raw of rawEdges) {
    if (edgeMap.has(raw.id)) continue
    const source = ageIdToAppId.get(raw.ageStartId) ?? raw.ageStartId
    const target = ageIdToAppId.get(raw.ageEndId) ?? raw.ageEndId
    if (nodeMap.has(source) && nodeMap.has(target)) {
      edgeMap.set(raw.id, {
        id: raw.id,
        label: raw.label,
        source,
        target,
        properties: raw.properties,
      })
    }
  }

  return {
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
  }
}
