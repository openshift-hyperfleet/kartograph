/**
 * Knowledge-graph–scoped data source routes (manage workspace entry points).
 *
 * Mirrors k-extract's split between `/designer/new` (first-time onboarding) and
 * `/projects/:name/phase1` (ongoing data source operations).
 */

export type KgDataSourcesFocus = 'maintain'

export function buildKgDataSourcesNewUrl(kgId: string): string {
  return `/knowledge-graphs/${encodeURIComponent(kgId)}/data-sources/new`
}

export function buildKgDataSourcesUrl(kgId: string, opts?: { focus?: KgDataSourcesFocus }): string {
  const base = `/knowledge-graphs/${encodeURIComponent(kgId)}/data-sources`
  if (opts?.focus === 'maintain') {
    return `${base}?focus=maintain`
  }
  return base
}

export function buildKgManageUrl(kgId: string): string {
  return `/knowledge-graphs/${encodeURIComponent(kgId)}/manage`
}

/**
 * Where "Data Sources" from KG manage should land.
 * Zero sources → onboarding wizard; otherwise → operations page (phase1 equivalent).
 */
export function resolveKgDataSourcesEntryUrl(kgId: string, dataSourceCount: number): string {
  if (dataSourceCount <= 0) {
    return buildKgDataSourcesNewUrl(kgId)
  }
  return buildKgDataSourcesUrl(kgId)
}

export function parseKgDataSourcesFocusQuery(focus: unknown): KgDataSourcesFocus | null {
  return focus === 'maintain' ? 'maintain' : null
}
