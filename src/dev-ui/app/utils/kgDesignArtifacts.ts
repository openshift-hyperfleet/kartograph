/** Shared helpers for Graph Management design artifact panels. */

export type PrepopulationMode = 'true' | 'hard-coded' | 'false'

export function prepopulationMode(raw: string | boolean | undefined): PrepopulationMode {
  if (raw === true) return 'true'
  const normalized = String(raw ?? 'false').toLowerCase().trim()
  if (normalized === 'true') return 'true'
  if (normalized === 'hard-coded') return 'hard-coded'
  return 'false'
}

export function prepopulationLabel(raw: string | boolean | undefined): string {
  const mode = prepopulationMode(raw)
  if (mode === 'true') return 'prepopulated: true'
  if (mode === 'hard-coded') return 'prepopulated: hard-coded'
  return 'prepopulated: false'
}

export function prepopulationBadgeClass(raw: string | boolean | undefined): string {
  const mode = prepopulationMode(raw)
  if (mode === 'true') return 'border-cyan-500/40 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300'
  if (mode === 'hard-coded') return 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300'
  return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
}

export function prepopulationCardClass(raw: string | boolean | undefined): string {
  const mode = prepopulationMode(raw)
  if (mode === 'true') return 'border-l-4 border-l-cyan-500/70'
  if (mode === 'hard-coded') return 'border-l-4 border-l-amber-500/70'
  return 'border-l-4 border-l-emerald-500/70'
}

export interface DesignArtifactInstance {
  slug?: string
  source_slug?: string
  target_slug?: string
  properties?: Record<string, unknown>
}

export interface DesignArtifactEntityType {
  type: string
  description?: string
  required_properties?: string[]
  optional_properties?: string[]
  property_definitions?: Record<string, string>
  prepopulated_instances?: string | boolean
  instance_count: number
  instances_returned?: number
  instances_truncated?: boolean
  instances?: DesignArtifactInstance[]
}

export interface DesignArtifactRelationshipType {
  key: string
  source_entity_type: string
  target_entity_type: string
  relationship_type: string
  reverse_relationship_type: string | null
  reverse_relationship_description: string | null
  prepopulated_instances?: string | boolean
  description: string | null
  instance_count: number
  instances_returned?: number
  instances_truncated?: boolean
  instances: DesignArtifactInstance[]
  required_parameters: string[]
  optional_parameters: string[]
  parameter_definitions: Record<string, string>
}

export interface DesignArtifactsResponse {
  found: boolean
  knowledge_graph_id: string
  entities: Record<string, Omit<DesignArtifactEntityType, 'type'>>
  relationships: DesignArtifactRelationshipType[]
  counts: {
    entity_types: number
    relationship_types: number
    entity_instances: number
    relationship_instances: number
  }
  limits: {
    requested: number
    instances_per_type?: number
    entity_instances_returned: number
    relationship_instances_returned: number
    entity_instances_truncated: boolean
    relationship_instances_truncated: boolean
  }
}

export const DESIGN_ARTIFACTS_PAGE_SIZE = 20
export const DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE = 100
export const DEFAULT_DESIGN_ARTIFACTS_INSTANCES_PER_TYPE = 100

export interface OntologyEdgeTypeRef {
  label: string
  auto_generated?: boolean
  inverse_of?: string | null
}

/** Match backend `is_primary_relationship_for_display` — one row per logical relationship. */
export function isPrimaryRelationshipTypeForDisplay(edge: OntologyEdgeTypeRef): boolean {
  return !edge.auto_generated && !edge.inverse_of
}

export function primaryRelationshipTypeLabels(edgeTypes: OntologyEdgeTypeRef[]): string[] {
  return edgeTypes.filter(isPrimaryRelationshipTypeForDisplay).map((edge) => edge.label)
}

export function primaryRelationshipTypeCount(edgeTypes: OntologyEdgeTypeRef[]): number {
  return primaryRelationshipTypeLabels(edgeTypes).length
}

export function searchableEntityProperties(row: DesignArtifactEntityType): string[] {
  const keys = new Set<string>(['slug', 'data_source_id'])
  for (const key of row.required_properties ?? []) keys.add(key)
  for (const key of row.optional_properties ?? []) keys.add(key)
  for (const key of Object.keys(row.property_definitions ?? {})) keys.add(key)
  return [...keys].sort()
}

export function searchableRelationshipProperties(row: DesignArtifactRelationshipType): string[] {
  const keys = new Set<string>(['data_source_id'])
  for (const key of row.required_parameters ?? []) keys.add(key)
  for (const key of row.optional_parameters ?? []) keys.add(key)
  for (const key of Object.keys(row.parameter_definitions ?? {})) keys.add(key)
  return [...keys].sort()
}

export function pageSlice<T>(
  pageByKey: Record<string, number>,
  key: string,
  items: T[],
  pageSize = DESIGN_ARTIFACTS_PAGE_SIZE,
) {
  const page = pageByKey[key] ?? 0
  const start = page * pageSize
  return {
    items: items.slice(start, start + pageSize),
    page,
    totalPages: Math.max(1, Math.ceil(items.length / pageSize)),
    total: items.length,
  }
}
