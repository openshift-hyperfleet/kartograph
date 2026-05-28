import type { SyncRunStatus } from '@/utils/kgDataSourcesSync'

export function shortCommitHash(hash: string | null | undefined): string {
  if (!hash) return '—'
  return hash.length > 12 ? hash.slice(0, 12) : hash
}

export function commitStatusClass(
  current: string | null | undefined,
  remote: string | null | undefined,
): string {
  if (!current || !remote) return 'text-muted-foreground'
  return current === remote
    ? 'text-green-600 dark:text-green-400'
    : 'text-amber-600 dark:text-amber-400'
}

export function commitStatusLabel(
  current: string | null | undefined,
  remote: string | null | undefined,
): string {
  if (!current || !remote) return 'not set'
  return current === remote ? 'matches branch head' : 'new commits on branch'
}

export function prepareCommitStatusLabel(
  prepared: string | null | undefined,
  tracked: string | null | undefined,
): string {
  if (!tracked) return 'branch head unknown'
  if (!prepared) return 'not prepared yet'
  return prepared === tracked ? 'prepared at branch head' : 'new commits to prepare'
}

export function needsIngestionPrepare(ds: {
  last_prepared_commit?: string | null
  tracked_branch_head_commit?: string | null
}): boolean {
  const tracked = ds.tracked_branch_head_commit
  if (!tracked) return false
  return ds.last_prepared_commit !== tracked
}

export function isIngestionPreparedAtHead(ds: {
  last_prepared_commit?: string | null
  tracked_branch_head_commit?: string | null
}): boolean {
  const tracked = ds.tracked_branch_head_commit
  const prepared = ds.last_prepared_commit
  return !!tracked && !!prepared && prepared === tracked
}

export function formatPreparedFileCount(count: number | null | undefined): string {
  if (count === null || count === undefined) return '—'
  return count.toLocaleString()
}

export function resolveRepoUrl(connectionConfig: Record<string, string> | undefined): string {
  if (!connectionConfig) return '—'
  if (connectionConfig.repo_url) return connectionConfig.repo_url
  if (connectionConfig.owner && connectionConfig.repo) {
    const branch = connectionConfig.branch ?? 'main'
    return `https://github.com/${connectionConfig.owner}/${connectionConfig.repo}/tree/${branch}`
  }
  return '—'
}

export function resolveTrackedBranch(connectionConfig: Record<string, string> | undefined): string {
  if (!connectionConfig) return 'main'
  return connectionConfig.branch ?? 'main'
}

export type PrepStatusLabel = 'Prepared' | 'Synced' | 'Preparing' | 'Failed' | 'Not prepared'

export function resolvePrepStatusLabel(status: SyncRunStatus | undefined): PrepStatusLabel {
  switch (status) {
    case 'ingested':
      return 'Prepared'
    case 'completed':
      return 'Synced'
    case 'failed':
      return 'Failed'
    case 'pending':
    case 'ingesting':
    case 'ai_extracting':
    case 'applying':
      return 'Preparing'
    default:
      return 'Not prepared'
  }
}

export function prepStatusBadgeVariant(
  status: SyncRunStatus | undefined,
): 'success' | 'destructive' | 'secondary' | 'outline' {
  switch (status) {
    case 'ingested':
    case 'completed':
      return 'success'
    case 'failed':
      return 'destructive'
    case 'pending':
    case 'ingesting':
    case 'ai_extracting':
    case 'applying':
      return 'secondary'
    default:
      return 'outline'
  }
}
