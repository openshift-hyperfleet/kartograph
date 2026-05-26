export type SyncRunStatus =
  | 'pending'
  | 'ingesting'
  | 'ai_extracting'
  | 'applying'
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
  return status === 'completed' || status === 'failed'
}

export interface SyncRunSummary {
  id: string
  status: SyncRunStatus
  error: string | null
  token_usage_total?: number | null
  cost_total_usd?: number | null
}

export function latestSyncRun<T extends SyncRunSummary>(runs: T[] | undefined): T | undefined {
  return runs?.[0]
}

export function hasAnyActiveSync<T extends { sync_runs?: SyncRunSummary[] }>(
  sources: T[],
): boolean {
  return sources.some((ds) => isActiveSyncStatus(latestSyncRun(ds.sync_runs)?.status))
}
