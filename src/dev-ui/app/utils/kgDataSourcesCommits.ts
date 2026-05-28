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
