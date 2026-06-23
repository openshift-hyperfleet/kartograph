import { describe, it, expect } from 'vitest'
import {
  buildKgDataSourcesNewUrl,
  buildKgDataSourcesUrl,
  buildKgManageUrl,
  parseKgDataSourcesFocusQuery,
  resolveKgDataSourcesEntryUrl,
} from '../utils/kgDataSourcesNavigation'

describe('kgDataSourcesNavigation', () => {
  it('builds new onboarding URL', () => {
    expect(buildKgDataSourcesNewUrl('kg-1')).toBe('/knowledge-graphs/kg-1/data-sources/new')
  })

  it('builds operations URL with optional maintain focus', () => {
    expect(buildKgDataSourcesUrl('kg-1')).toBe('/knowledge-graphs/kg-1/data-sources')
    expect(buildKgDataSourcesUrl('kg-1', { focus: 'maintain' })).toBe(
      '/knowledge-graphs/kg-1/data-sources?focus=maintain',
    )
  })

  it('resolves entry URL from data source count', () => {
    expect(resolveKgDataSourcesEntryUrl('kg-1', 0)).toBe(
      '/knowledge-graphs/kg-1/data-sources/new',
    )
    expect(resolveKgDataSourcesEntryUrl('kg-1', 2)).toBe(
      '/knowledge-graphs/kg-1/data-sources',
    )
  })

  it('builds manage workspace return URL', () => {
    expect(buildKgManageUrl('kg-abc')).toBe('/knowledge-graphs/kg-abc/manage')
  })

  it('parses maintain focus query', () => {
    expect(parseKgDataSourcesFocusQuery('maintain')).toBe('maintain')
    expect(parseKgDataSourcesFocusQuery('other')).toBeNull()
  })
})
