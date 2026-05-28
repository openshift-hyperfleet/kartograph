import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  commitStatusLabel,
  prepStatusBadgeVariant,
  resolvePrepStatusLabel,
  resolveRepoUrl,
  shortCommitHash,
} from '@/utils/kgDataSourcesCommits'

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

  it('does not render legacy per-card commit status layout', () => {
    expect(phase1Vue).not.toContain('Commit Status')
    expect(phase1Vue).not.toContain('Local clone commit')
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
    expect(commitStatusLabel('abc', 'abc')).toBe('matches branch head')
  })
})
