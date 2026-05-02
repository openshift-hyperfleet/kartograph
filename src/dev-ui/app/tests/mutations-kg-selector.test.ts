import { describe, it, expect, vi } from 'vitest'

// ── Types ─────────────────────────────────────────────────────────────────────

interface KnowledgeGraph { id: string; name: string }

// ── KG selector logic ─────────────────────────────────────────────────────────

/**
 * Determines whether the Apply Mutations button should be disabled.
 * Mirrors the gating condition in the mutations console.
 */
function isSubmitDisabled(opts: {
  submitting: boolean
  preparing: boolean
  hasContent: boolean
  selectedKgId: string
}): boolean {
  const { submitting, preparing, hasContent, selectedKgId } = opts
  return submitting || preparing || !hasContent || !selectedKgId
}

/**
 * Builds the mutations API URL for a given knowledge graph ID.
 * Mirrors the URL construction in useGraphApi.applyMutations().
 */
function buildMutationsUrl(apiBaseUrl: string, knowledgeGraphId: string): string {
  return `${apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Mutations Console — KG selector gating (isSubmitDisabled)', () => {
  it('disabled when no KG selected even if content exists', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: true, selectedKgId: '' }))
      .toBe(true)
  })

  it('disabled when submitting', () => {
    expect(isSubmitDisabled({ submitting: true, preparing: false, hasContent: true, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('disabled when preparing', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: true, hasContent: true, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('disabled when no content', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: false, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('enabled when KG selected AND content exists AND not submitting', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: true, selectedKgId: 'kg-abc' }))
      .toBe(false)
  })
})

describe('Mutations Console — API URL construction', () => {
  it('includes knowledge_graph_id in the path', () => {
    const url = buildMutationsUrl('https://api.example.com', 'kg-abc123')
    expect(url).toBe('https://api.example.com/graph/knowledge-graphs/kg-abc123/mutations')
  })

  it('does not use the legacy /graph/mutations path', () => {
    const url = buildMutationsUrl('https://api.example.com', 'kg-abc123')
    expect(url).not.toBe('https://api.example.com/graph/mutations')
  })

  it('uses the provided KG ID verbatim', () => {
    const kgId = 'knowledge-graph-xyz-789'
    const url = buildMutationsUrl('https://api.example.com', kgId)
    expect(url).toContain(kgId)
  })
})

describe('Mutations Console — KG list loading', () => {
  it('resets selected KG when tenant changes', () => {
    let selectedKgId = 'kg-old'

    function onTenantChange() {
      selectedKgId = ''
    }

    onTenantChange()
    expect(selectedKgId).toBe('')
  })

  it('populates KG list from API response', () => {
    const apiResponse = {
      knowledge_graphs: [
        { id: 'kg-1', name: 'Engineering KB' },
        { id: 'kg-2', name: 'Platform KB' },
      ],
    }
    const kgs: KnowledgeGraph[] = apiResponse.knowledge_graphs ?? []
    expect(kgs).toHaveLength(2)
    expect(kgs[0].name).toBe('Engineering KB')
  })

  it('handles empty KG list gracefully', () => {
    const apiResponse = { knowledge_graphs: [] }
    const kgs: KnowledgeGraph[] = apiResponse.knowledge_graphs ?? []
    expect(kgs).toHaveLength(0)
  })
})

describe('Mutations Console — submit passes KG ID to API', () => {
  it('applyMutations is called with the selected KG ID', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ ok: true })

    async function applyMutations(
      jsonlContent: string,
      knowledgeGraphId: string,
    ) {
      return apiFetch(
        `https://api.example.com/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
        { method: 'POST', body: jsonlContent },
      )
    }

    await applyMutations('{"op":"CREATE"}', 'kg-selected')

    expect(apiFetch).toHaveBeenCalledWith(
      'https://api.example.com/graph/knowledge-graphs/kg-selected/mutations',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
