import { describe, expect, it } from 'vitest'
import {
  filterSchemaRailItems,
  graphManagementArtifactRowClass,
  graphManagementRailItemDone,
  resolveSchemaRailSelection,
} from '../utils/kgGraphManagementArtifacts'
import { buildGraphManagementRailItems } from '../utils/kgGraphManagement'

describe('kgGraphManagementArtifacts', () => {
  const items = buildGraphManagementRailItems({
    workspaceMode: 'schema_bootstrap',
    transitionEligible: false,
    blockingReasonCount: 1,
    prepopulatedGapCount: 0,
    hasMinimumEntityTypes: false,
    hasMinimumRelationshipTypes: false,
    sessionUpdatedAt: '2026-01-01',
    hasActiveSession: true,
  })

  it('excludes session pointers from schema artifact navigation', () => {
    const schemaItems = filterSchemaRailItems(items)
    expect(schemaItems.map((item) => item.id)).not.toContain('session-pointers')
    expect(schemaItems.length).toBeGreaterThan(0)
  })

  it('resolves schema selection for the active mode', () => {
    expect(
      resolveSchemaRailSelection(null, 'initial-schema-design', items),
    ).toBe('schema-entities')
    expect(
      resolveSchemaRailSelection('schema-readiness', 'extraction-jobs', items),
    ).toBe('extraction-jobs-setup')
  })

  it('defaults one-off mutations mode to schema entities', () => {
    const operationsItems = buildGraphManagementRailItems({
      workspaceMode: 'extraction_operations',
      transitionEligible: true,
      blockingReasonCount: 0,
      prepopulatedGapCount: 0,
      hasMinimumEntityTypes: true,
      hasMinimumRelationshipTypes: true,
      sessionUpdatedAt: null,
      hasActiveSession: true,
    })
    expect(
      resolveSchemaRailSelection(null, 'one-off-mutations', operationsItems),
    ).toBe('schema-entities')
  })

  it('maps ready status to done artifact rows', () => {
    expect(graphManagementRailItemDone('ready')).toBe(true)
    expect(graphManagementArtifactRowClass(true, true)).toContain('ring-primary')
    expect(graphManagementArtifactRowClass(false, true)).toContain('green')
  })
})
