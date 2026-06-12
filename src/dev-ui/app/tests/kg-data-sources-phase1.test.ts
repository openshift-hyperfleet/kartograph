import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  hasUnpulledCommits,
  isIngestionPreparedAtHead,
  needsIngestionPrepare,
  prepStatusBadgeVariant,
  resolveNewestUnpulledCommit,
  resolvePrepStatusLabel,
  resolveRepoUrl,
  shortCommitHash,
  unpulledCommitStatusLabel,
} from '@/utils/kgDataSourcesCommits'
import { latestSyncRun, sortSyncRunsByRecent } from '@/utils/kgDataSourcesSync'

const phase1Vue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/data-sources/index.vue'),
  'utf-8',
)

const newVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/data-sources/new.vue'),
  'utf-8',
)

describe('KG data sources phase1 layout', () => {
  it('uses wide page container like k-extract phase1', () => {
    expect(phase1Vue).toContain('max-w-7xl')
  })

  it('renders add repositories and overview sections', () => {
    expect(phase1Vue).toContain('Add repositories')
    expect(phase1Vue).toContain('Data sources overview')
    expect(phase1Vue).toContain('Add to project')
  })

  it('renders data sources ready footer with graph management link', () => {
    expect(phase1Vue).toContain('Data Sources ready')
    expect(phase1Vue).toContain('Open Graph Management')
    expect(phase1Vue).toContain('step=graph-management')
  })

  it('renders bulk commit check and prepare actions', () => {
    expect(phase1Vue).toContain('Check for new commits')
    expect(phase1Vue).toContain('Prepare data sources')
    expect(phase1Vue).toContain('prepareAllDataSources')
    expect(phase1Vue).not.toContain('Refresh commits')
    expect(phase1Vue).not.toContain('Adopt baseline')
  })

  it('disables autofill on repository URL inputs', () => {
    expect(phase1Vue).toContain('autocomplete="off"')
    expect(phase1Vue).toContain('data-lpignore="true"')
  })

  it('shows files on branch column', () => {
    expect(phase1Vue).toContain('Files on branch')
    expect(phase1Vue).toContain('formatPreparedFileCount')
  })

  it('refreshes data sources silently while polling', () => {
    expect(phase1Vue).toContain('loadDataSources({ silent: true })')
    expect(phase1Vue).toContain('refreshing')
    expect(phase1Vue).toContain('Updating…')
  })

  it('shows unpulled commit columns', () => {
    expect(phase1Vue).toContain('Newest unpulled')
    expect(phase1Vue).toContain('Last extraction baseline')
    expect(phase1Vue).toContain('Ingested at')
    expect(phase1Vue).not.toContain('Branch tip')
    expect(phase1Vue).toContain('resolveNewestUnpulledCommit')
  })
})

describe('KG wizard parallel ingestion prep', () => {
  it('prepares sources in parallel', () => {
    expect(newVue).toContain('runParallelIngestionPrep')
    expect(newVue).toContain('Promise.allSettled')
    expect(newVue).toContain('pollUntilAllTerminal')
    expect(newVue).not.toContain('runSequentialIngestionPrep')
  })
})

describe('kgDataSourcesCommits helpers', () => {
  it('shortens commit hashes for display', () => {
    expect(shortCommitHash('abcdef1234567890')).toBe('abcdef123456')
    expect(shortCommitHash(null)).toBe('—')
  })

  it('derives repo url from connection config', () => {
    expect(resolveRepoUrl({ repo_url: 'https://github.com/org/repo' })).toBe(
      'https://github.com/org/repo',
    )
    expect(resolveRepoUrl({ owner: 'org', repo: 'repo', branch: 'dev' })).toContain('/tree/dev')
  })

  it('maps sync statuses to prep labels', () => {
    expect(resolvePrepStatusLabel('ingested')).toBe('Prepared')
    expect(prepStatusBadgeVariant('ingested')).toBe('success')
    expect(
      resolveNewestUnpulledCommit({
        tracked_branch_head_commit: 'remote',
        clone_head_commit: 'local',
      }),
    ).toBe('remote')
    expect(unpulledCommitStatusLabel(null, 'remote')).toBe('up to date with branch')
    expect(needsIngestionPrepare({ tracked_branch_head_commit: 'abc', last_prepared_commit: null })).toBe(true)
    expect(hasUnpulledCommits({ tracked_branch_head_commit: 'abc', clone_head_commit: 'abc' })).toBe(false)
    expect(isIngestionPreparedAtHead({ tracked_branch_head_commit: 'abc', clone_head_commit: 'abc' })).toBe(true)
  })
})

describe('sync run ordering helpers', () => {
  it('treats the most recent started_at run as latest', () => {
    const runs = [
      {
        id: 'old-failed',
        status: 'failed' as const,
        error: '403',
        started_at: '2026-06-12T19:02:50.000Z',
      },
      {
        id: 'new-ingested',
        status: 'ingested' as const,
        error: null,
        started_at: '2026-06-12T19:10:49.000Z',
      },
    ]

    expect(latestSyncRun(runs)?.id).toBe('new-ingested')
    expect(sortSyncRunsByRecent(runs).map((run) => run.id)).toEqual([
      'new-ingested',
      'old-failed',
    ])
  })
})
