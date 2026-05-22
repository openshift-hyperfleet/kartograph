export interface MutationLogRunRecord {
  id: string
  data_source_id: string
  data_source_name?: string
  status: string
  started_at: string
  completed_at: string | null
  mutation_log_id: string | null
  knowledge_graph_id: string | null
  session_id: string | null
  actor_id: string | null
  operation_counts: Record<string, number>
  token_usage_total: number | null
  cost_total_usd: number | null
  error: string | null
}

export interface MutationLogEntryPreview {
  line_number: number
  operation_class: string
  summary: string
}

export interface MutationLogEntryPreviewPage {
  entries: MutationLogEntryPreview[]
  total: number
  offset: number
  limit: number
  preview_available: boolean
}

export const MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE = 20

export const MUTATION_LOG_NO_PREVIEW_MESSAGE =
  'Detailed entry previews are not available for this run yet.'

export function isMutationLogRunForKnowledgeGraph(
  run: Pick<MutationLogRunRecord, 'mutation_log_id' | 'knowledge_graph_id'>,
  kgId: string,
): boolean {
  if (!run.mutation_log_id) return false
  if (run.knowledge_graph_id != null && run.knowledge_graph_id !== kgId) return false
  return true
}

export function sortMutationLogRunsNewestFirst<T extends { started_at: string }>(
  runs: T[],
): T[] {
  return [...runs].sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
  )
}

export function resolveDefaultSelectedMutationLogRunId(
  runs: Array<{ id: string }>,
  currentId: string | null,
): string | null {
  if (currentId && runs.some((run) => run.id === currentId)) return currentId
  return runs[0]?.id ?? null
}

export function collectScopedMutationLogRuns(
  kgId: string,
  dataSources: Array<{ id: string; name: string }>,
  runsByDataSourceId: Record<string, MutationLogRunRecord[]>,
): MutationLogRunRecord[] {
  const collected: MutationLogRunRecord[] = []

  for (const ds of dataSources) {
    const runs = runsByDataSourceId[ds.id] ?? []
    for (const run of runs) {
      if (!isMutationLogRunForKnowledgeGraph(run, kgId)) continue
      collected.push({
        ...run,
        data_source_name: ds.name,
      })
    }
  }

  return sortMutationLogRunsNewestFirst(collected)
}

export function buildMutationLogEntryPreviewUrl(
  dataSourceId: string,
  runId: string,
  offset = 0,
  limit = MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE,
): string {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })
  return `/management/data-sources/${encodeURIComponent(dataSourceId)}/sync-runs/${encodeURIComponent(runId)}/mutation-log-entries?${params}`
}

export function hasMutationLogEntryPreviewPage(
  page: MutationLogEntryPreviewPage | null,
): boolean {
  return page?.preview_available === true && page.entries.length > 0
}
