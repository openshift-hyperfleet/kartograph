import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const manageWorkspaceVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/manage.vue'),
  'utf-8',
)

describe('Knowledge Graph Manage Workspace - mode-aware controls', () => {
  it('loads workspace status projection from management API', () => {
    expect(manageWorkspaceVue).toContain('/workspace-status')
    expect(manageWorkspaceVue).toContain('loadWorkspaceStatus')
  })

  it('exposes Validate action calling workspace validate endpoint', () => {
    expect(manageWorkspaceVue).toContain('validateWorkspace')
    expect(manageWorkspaceVue).toContain('/workspace/validate')
    expect(manageWorkspaceVue).toContain('Validate')
  })

  it('exposes Go to Extraction/Mutations action calling transition endpoint', () => {
    expect(manageWorkspaceVue).toContain('transitionToExtraction')
    expect(manageWorkspaceVue).toContain('/workspace/transition-to-extraction')
    expect(manageWorkspaceVue).toContain('Go to Extraction/Mutations')
  })

  it('renders readiness result blocks and blocking reasons list', () => {
    expect(manageWorkspaceVue).toContain('Readiness Results')
    expect(manageWorkspaceVue).toContain('blocking_reasons')
    expect(manageWorkspaceVue).toContain('prepopulated_types_ready')
  })

  it('renders session pointer references for bootstrap and extraction modes', () => {
    expect(manageWorkspaceVue).toContain('Session Pointers')
    expect(manageWorkspaceVue).toContain('active_schema_bootstrap_session_id')
    expect(manageWorkspaceVue).toContain('active_extraction_operations_session_id')
  })

  it('keeps extraction conversation panel visible in extraction mode', () => {
    expect(manageWorkspaceVue).toContain('Extraction Conversation')
    expect(manageWorkspaceVue).toContain('message_history')
    expect(manageWorkspaceVue).toContain('statusProjection.workspace_mode === \'extraction_operations\'')
  })

  it('supports explicit Clear chat reset for extraction session', () => {
    expect(manageWorkspaceVue).toContain('clearChat')
    expect(manageWorkspaceVue).toContain('/sessions/extraction_operations/clear-chat')
    expect(manageWorkspaceVue).toContain('Clear chat')
  })

  it('provides tabbed lower operations area for extraction workflows', () => {
    expect(manageWorkspaceVue).toContain('Operations Workspace')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="extraction-jobs"')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="manual-mutations"')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="run-logs"')
  })
})
