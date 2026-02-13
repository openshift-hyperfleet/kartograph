// ---------------------------------------------------------------------------
// Kartograph UI – Shared Type Definitions
// Maps 1-to-1 with the API response schemas from each bounded context.
// ---------------------------------------------------------------------------

// ── IAM Types ──────────────────────────────────────────────────────────────

export interface TenantResponse {
  id: string
  name: string
}

export interface TenantMemberResponse {
  user_id: string
  role: string
}

export interface WorkspaceResponse {
  id: string
  tenant_id: string
  name: string
  parent_workspace_id: string | null
  is_root: boolean
  created_at: string
  updated_at: string
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceResponse[]
  count: number
}

export type WorkspaceMemberType = 'user' | 'group'
export type WorkspaceRole = 'admin' | 'editor' | 'member'

export interface WorkspaceMemberResponse {
  member_id: string
  member_type: WorkspaceMemberType
  role: WorkspaceRole
}

export interface GroupMemberResponse {
  user_id: string
  role: string
}

export interface GroupResponse {
  id: string
  name: string
  members: GroupMemberResponse[]
}

export interface APIKeyResponse {
  id: string
  name: string
  prefix: string
  created_by_user_id: string
  created_at: string
  expires_at: string
  last_used_at: string | null
  is_revoked: boolean
}

export interface APIKeyCreatedResponse extends APIKeyResponse {
  secret: string
}

// ── Graph Types ────────────────────────────────────────────────────────────

export interface NodeRecord {
  id: string
  label: string
  properties: Record<string, unknown>
}

export interface EdgeRecord {
  id: string
  label: string
  start_id: string
  end_id: string
  properties: Record<string, unknown>
}

export interface TypeDefinition {
  label: string
  entity_type: 'node' | 'edge'
  description: string
  required_properties: string[]
  optional_properties: string[]
}

export interface SchemaLabelsResponse {
  labels: string[]
  count: number
}

export interface MutationResult {
  success: boolean
  operations_applied: number
  errors: string[]
}

export interface NodeNeighborsResult {
  central_node: NodeRecord
  nodes: NodeRecord[]
  edges: EdgeRecord[]
}

// ── Query Types ────────────────────────────────────────────────────────────

export interface CypherResult {
  rows: Record<string, unknown>[]
  row_count: number
}

// ── Query History Types ─────────────────────────────────────────────────────

export interface HistoryEntry {
  query: string
  timestamp: number
  rowCount: number | null
}

export interface HistoryGroup {
  label: string
  entries: (HistoryEntry & { originalIndex: number })[]
}

// ── Graph Visualization Types ──────────────────────────────────────────────

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, unknown>
  /** Resolved from properties.name, properties.slug, or label */
  displayName: string
}

export interface GraphEdge {
  id: string
  label: string
  source: string
  target: string
  properties: Record<string, unknown>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}
