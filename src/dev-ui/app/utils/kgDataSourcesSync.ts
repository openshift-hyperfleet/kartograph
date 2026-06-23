export type SyncRunStatus =
  | 'pending'
  | 'ingesting'
  | 'ai_extracting'
  | 'applying'
  | 'ingested'
  | 'completed'
  | 'failed'

export const ACTIVE_SYNC_STATUSES: SyncRunStatus[] = [
  'pending',
  'ingesting',
  'ai_extracting',
  'applying',
]

export function isActiveSyncStatus(status: SyncRunStatus | undefined): boolean {
  if (!status) return false
  return ACTIVE_SYNC_STATUSES.includes(status)
}

export function isSyncTerminal(status: SyncRunStatus | undefined): boolean {
  return status === 'ingested' || status === 'completed' || status === 'failed'
}

export interface SyncRunSummary {
  id: string
  status: SyncRunStatus
  error: string | null
  started_at?: string
  token_usage_total?: number | null
  cost_total_usd?: number | null
}

export function sortSyncRunsByRecent<T extends SyncRunSummary>(
  runs: T[] | undefined,
): T[] {
  if (!runs?.length) return []
  return [...runs].sort((left, right) => {
    const leftTime = left.started_at ? Date.parse(left.started_at) : 0
    const rightTime = right.started_at ? Date.parse(right.started_at) : 0
    return rightTime - leftTime
  })
}

export function latestSyncRun<T extends SyncRunSummary>(runs: T[] | undefined): T | undefined {
  return sortSyncRunsByRecent(runs)[0]
}

export function hasAnyActiveSync<T extends { sync_runs?: SyncRunSummary[] }>(
  sources: T[],
): boolean {
  return sources.some((ds) => isActiveSyncStatus(latestSyncRun(ds.sync_runs)?.status))
}
