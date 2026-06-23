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

/** Commit we have ingested (local HEAD after pull/prepare). */
export function resolveIngestedHeadCommit(ds: {
  clone_head_commit?: string | null
  last_prepared_commit?: string | null
  ingested_head_commit?: string | null
}): string | null {
  if (ds.ingested_head_commit) return ds.ingested_head_commit
  return ds.clone_head_commit ?? ds.last_prepared_commit ?? null
}

/** Remote branch tip from last check (what git pull would reach). */
export function resolveBranchTipCommit(ds: {
  tracked_branch_head_commit?: string | null
}): string | null {
  return ds.tracked_branch_head_commit ?? null
}

/**
 * Newest commit on the branch we do not have yet.
 * When never ingested, the whole branch tip is unpulled.
 */
export function resolveNewestUnpulledCommit(ds: {
  newest_unpulled_commit?: string | null
  tracked_branch_head_commit?: string | null
  clone_head_commit?: string | null
  last_prepared_commit?: string | null
  ingested_head_commit?: string | null
}): string | null {
  if (ds.newest_unpulled_commit !== undefined) {
    return ds.newest_unpulled_commit
  }
  const tip = resolveBranchTipCommit(ds)
  if (!tip) return null
  const ingested = resolveIngestedHeadCommit(ds)
  if (!ingested) return tip
  return ingested === tip ? null : tip
}

export function hasUnpulledCommits(ds: Parameters<typeof resolveNewestUnpulledCommit>[0]): boolean {
  return resolveNewestUnpulledCommit(ds) !== null
}

export function unpulledCommitStatusLabel(
  unpulled: string | null | undefined,
  branchTip: string | null | undefined,
): string {
  if (!branchTip) return 'check branch to see remote tip'
  if (!unpulled) return 'up to date with branch'
  return 'new commit on branch (not ingested yet)'
}

export function needsJobPackageRematerialize(ds: {
  last_prepared_commit?: string | null
  job_package_available?: boolean | null
}): boolean {
  return Boolean(ds.last_prepared_commit) && ds.job_package_available === false
}

export function needsIngestionPrepare(ds: Parameters<typeof hasUnpulledCommits>[0] & {
  last_prepared_commit?: string | null
  job_package_available?: boolean | null
}): boolean {
  return hasUnpulledCommits(ds) || needsJobPackageRematerialize(ds)
}

export function isIngestionPreparedAtHead(ds: Parameters<typeof hasUnpulledCommits>[0]): boolean {
  const tip = resolveBranchTipCommit(ds)
  const ingested = resolveIngestedHeadCommit(ds)
  return !!tip && !!ingested && ingested === tip
}

/** True once initial ingestion prep has completed (new commits are a maintenance concern). */
export function hasIngestionContextPrepared(ds: Parameters<typeof resolveIngestedHeadCommit>[0]): boolean {
  return resolveIngestedHeadCommit(ds) !== null
}

export function formatPreparedFileCount(count: number | null | undefined): string {
  if (count === null || count === undefined) return '—'
  return count.toLocaleString()
}

/** Files materialized in the local clone (shown when a clone commit exists). */
export function formatFilesOnDisk(ds: {
  clone_head_commit?: string | null
  last_prepared_commit?: string | null
  ingested_head_commit?: string | null
  last_prepared_file_count?: number | null
}): string {
  if (!resolveIngestedHeadCommit(ds)) return '—'
  return (ds.last_prepared_file_count ?? 0).toLocaleString()
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
