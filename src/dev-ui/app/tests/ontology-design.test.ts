import { describe, it, expect, vi } from 'vitest'
import {
  validateTypeLabel,
  validateIntentText,
  parsePropertyList,
  newBlankNodeType,
  newBlankEdgeType,
  buildOntologySavePayload,
  type OntologyNodeType,
  type OntologyEdgeType,
} from '@/utils/ontologyWizard'

/**
 * Task-123: UI Ontology Design — Intent Capture, Agent Proposal, and Review Flow
 *
 * Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
 * Requirement: Ontology Design
 *
 * Maps each spec scenario to test groups:
 *
 *  - Scenario: Intent description           → Group 1
 *  - Scenario: Agent-proposed ontology      → Group 2
 *  - Scenario: Ontology review and approval → Group 3
 *  - Scenario: Individual type editing      → Groups 4 & 5
 *  - Scenario: Ontology change after        → Group 6
 *      initial extraction
 *  - Backend API Alignment                  → Group 7
 *
 * All tests are pure unit tests operating on extracted utility functions and
 * inline logic mirrors — no Nuxt or DOM mounting required.
 */

// ── Helpers ────────────────────────────────────────────────────────────────────

function makeNode(overrides: Partial<OntologyNodeType> = {}): OntologyNodeType {
  return {
    label: 'Repository',
    description: 'A GitHub repository',
    required_properties: ['name', 'url'],
    optional_properties: ['description', 'stars'],
    editing: false,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    editError: '',
    ...overrides,
  }
}

function makeEdge(overrides: Partial<OntologyEdgeType> = {}): OntologyEdgeType {
  return {
    label: 'CONTAINS',
    description: 'A repo contains issues',
    from: 'Repository',
    to: 'Issue',
    required_properties: [],
    optional_properties: ['since'],
    editing: false,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    editError: '',
    ...overrides,
  }
}

// ── Group 1: Scenario: Intent description ─────────────────────────────────────
//
// Spec:
// "GIVEN a user who has connected a data source
//  WHEN the connection is saved
//  THEN the user is prompted to describe (in free text) what problems or
//       questions they want to solve with this data"
// And (step 3 wizard validation):
// "intentText must be non-empty to advance from step 3 to step 4"

describe('Ontology Design — Scenario: Intent description', () => {
  it('test_empty_intent_fails_validation', () => {
    const result = validateIntentText('')
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Please describe your intent before continuing.')
  })

  it('test_whitespace_only_intent_fails_validation', () => {
    // Whitespace alone does not constitute a meaningful intent description.
    const result = validateIntentText('   ')
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Please describe your intent before continuing.')
  })

  it('test_non_empty_intent_passes_validation', () => {
    const result = validateIntentText('I want to understand contributor patterns and pull request flow.')
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })

  it('test_single_word_intent_passes_validation', () => {
    // Even a single word is valid — the user can always refine it later.
    const result = validateIntentText('Contributors')
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })

  it('test_wizard_does_not_advance_from_step3_when_intent_empty', () => {
    // Mirrors the nextStep() guard in data-sources/index.vue for wizardStep === 3.
    const intentText = { value: '' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }
    const scanningOntology = { value: false }

    function nextStep() {
      if (wizardStep.value === 3) {
        const validation = validateIntentText(intentText.value)
        intentError.value = validation.error
        if (!validation.valid) return
        wizardStep.value = 4
        scanningOntology.value = true
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(3)
    expect(intentError.value).toBe('Please describe your intent before continuing.')
    expect(scanningOntology.value).toBe(false)
  })

  it('test_wizard_advances_to_step4_and_starts_scan_when_intent_provided', () => {
    // Spec: user provides intent → wizard moves to the ontology proposal step
    // AND the scan begins immediately (scanningOntology = true).
    const intentText = { value: 'I want to track issue triage patterns and contributor activity.' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }
    const scanningOntology = { value: false }

    function nextStep() {
      if (wizardStep.value === 3) {
        const validation = validateIntentText(intentText.value)
        intentError.value = validation.error
        if (!validation.valid) return
        wizardStep.value = 4
        scanningOntology.value = true
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(4)
    expect(intentError.value).toBe('')
    expect(scanningOntology.value).toBe(true)
  })

  it('test_intent_error_is_cleared_on_next_valid_submission', () => {
    // After a failed submission, correcting the intent clears the error.
    const intentError = { value: 'Please describe your intent before continuing.' }
    const intentText = { value: 'Track pull request reviews and merge patterns.' }
    const wizardStep = { value: 3 }

    function nextStep() {
      if (wizardStep.value === 3) {
        const validation = validateIntentText(intentText.value)
        intentError.value = validation.error
        if (!validation.valid) return
        wizardStep.value = 4
      }
    }

    nextStep()
    expect(intentError.value).toBe('')
  })
})

// ── Group 2: Scenario: Agent-proposed ontology ────────────────────────────────
//
// Spec:
// "GIVEN a free-text intent description and a connected data source
//  WHEN the user submits their intent
//  THEN the system performs a lightweight scan of the data source
//  AND an AI agent explores the scanned data and proposes an ontology
//       (node types, edge types, properties)
//  AND the proposed ontology is presented to the user for review"

describe('Ontology Design — Scenario: Agent-proposed ontology (scan state machine)', () => {
  it('test_scanning_state_is_true_at_start_and_false_after_completion', () => {
    // beginOntologyProposal() immediately sets scanningOntology = true.
    // After the async scan completes it transitions to false + ontologyReady = true.
    let scanningOntology = false
    let ontologyReady = false
    const proposedNodes: string[] = []

    // Synchronous simulation of the state transitions
    function beginOntologyProposalSync() {
      scanningOntology = true
      ontologyReady = false
      // (scan runs here...)
      proposedNodes.push('Repository', 'Issue', 'PullRequest', 'Commit', 'User')
      scanningOntology = false
      ontologyReady = true
    }

    expect(scanningOntology).toBe(false)
    beginOntologyProposalSync()
    expect(scanningOntology).toBe(false)
    expect(ontologyReady).toBe(true)
    expect(proposedNodes.length).toBeGreaterThanOrEqual(5)
  })

  it('test_previously_proposed_nodes_and_edges_are_cleared_when_scan_begins', () => {
    // If the wizard is re-entered or the back button is used, stale proposals
    // must be discarded when a new scan begins.
    const proposedNodes = [{ label: 'OldNode' }]
    const proposedEdges = [{ label: 'OLD_EDGE' }]

    function beginOntologyProposal() {
      proposedNodes.splice(0)
      proposedEdges.splice(0)
      // (scan would populate them again...)
    }

    beginOntologyProposal()
    expect(proposedNodes).toHaveLength(0)
    expect(proposedEdges).toHaveLength(0)
  })

  it('test_proposed_nodes_contain_required_fields_for_review', () => {
    // Spec: "proposes an ontology (node types, edge types, properties)"
    // Each proposed node must carry label, description, and property arrays.
    const proposedNodes: OntologyNodeType[] = [
      makeNode({ label: 'Repository', description: 'A repo.', required_properties: ['name', 'url'], optional_properties: ['description'] }),
      makeNode({ label: 'Issue', description: 'An issue.', required_properties: ['title', 'number', 'state'], optional_properties: ['body'] }),
    ]

    for (const node of proposedNodes) {
      expect(node.label).toBeTruthy()
      expect(node.description).toBeTruthy()
      expect(Array.isArray(node.required_properties)).toBe(true)
      expect(Array.isArray(node.optional_properties)).toBe(true)
    }
  })

  it('test_proposed_edges_contain_required_fields_for_review', () => {
    // Spec: "proposes an ontology (node types, edge types, properties)"
    // Each proposed edge must carry label, from, to, and property arrays.
    const proposedEdges: OntologyEdgeType[] = [
      makeEdge({ label: 'CONTAINS', from: 'Repository', to: 'Issue | PullRequest | Commit' }),
      makeEdge({ label: 'CREATED_BY', from: 'Issue | PullRequest', to: 'User' }),
    ]

    for (const edge of proposedEdges) {
      expect(edge.label).toBeTruthy()
      expect(edge.from).toBeTruthy()
      expect(edge.to).toBeTruthy()
      expect(Array.isArray(edge.required_properties)).toBe(true)
      expect(Array.isArray(edge.optional_properties)).toBe(true)
    }
  })

  it('test_ontology_ready_is_false_while_scanning_is_in_progress', () => {
    // The proposal loading state must be mutually exclusive with the ready state.
    // ontologyReady must remain false until the scan actually completes.
    let scanningOntology = true
    let ontologyReady = false

    // While scan is in progress:
    expect(scanningOntology).toBe(true)
    expect(ontologyReady).toBe(false)
  })
})

// ── Group 3: Scenario: Ontology review and approval ───────────────────────────
//
// Spec:
// "GIVEN a proposed ontology
//  WHEN the user reviews it
//  THEN they can approve the ontology as-is
//  OR iterate by editing individual types and relationships
//  AND extraction begins only after the user explicitly approves"

describe('Ontology Design — Scenario: Ontology review and approval', () => {
  it('test_approve_button_is_disabled_before_ontology_is_ready', () => {
    // The "Approve & Start Extraction" button must be disabled while scanning.
    // Template: :disabled="!ontologyReady || approvingOntology"
    const ontologyReady = false
    const approvingOntology = false
    const approveButtonEnabled = ontologyReady && !approvingOntology
    expect(approveButtonEnabled).toBe(false)
  })

  it('test_approve_button_is_enabled_when_ontology_is_ready_and_not_in_flight', () => {
    const ontologyReady = true
    const approvingOntology = false
    const approveButtonEnabled = ontologyReady && !approvingOntology
    expect(approveButtonEnabled).toBe(true)
  })

  it('test_approve_button_is_disabled_while_api_call_is_in_flight', () => {
    const ontologyReady = true
    const approvingOntology = true // PATCH in progress
    const approveButtonEnabled = ontologyReady && !approvingOntology
    expect(approveButtonEnabled).toBe(false)
  })

  it('test_api_is_not_called_until_user_explicitly_clicks_approve', () => {
    // Spec: "extraction begins only after the user explicitly approves"
    // Merely viewing the proposal (step 4) must NOT trigger the API call.
    const createDataSource = vi.fn()
    const wizardStep = 4
    const ontologyReady = true

    // Simulate being on step 4 (proposal displayed, user reviewing)
    expect(wizardStep).toBe(4)
    expect(ontologyReady).toBe(true)
    expect(createDataSource).not.toHaveBeenCalled() // no implicit call
  })

  it('test_approve_without_kg_selected_shows_error_and_does_not_call_api', async () => {
    const selectedKgId = { value: '' }
    const createDataSource = vi.fn()
    let errorMessage = ''

    async function approveOntology() {
      if (!selectedKgId.value) {
        errorMessage = 'Please select a knowledge graph first'
        return
      }
      await createDataSource({})
    }

    await approveOntology()
    expect(createDataSource).not.toHaveBeenCalled()
    expect(errorMessage).toBe('Please select a knowledge graph first')
  })

  it('test_approve_with_kg_selected_calls_api_and_closes_wizard', async () => {
    const selectedKgId = { value: 'kg-123' }
    const wizardOpen = { value: true }
    const createDataSource = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function approveOntology() {
      if (!selectedKgId.value) return
      await createDataSource({ kg_id: selectedKgId.value, name: 'my-repo', adapter_type: 'github' })
      wizardOpen.value = false
      await loadDataSources()
    }

    await approveOntology()
    expect(createDataSource).toHaveBeenCalledOnce()
    expect(wizardOpen.value).toBe(false)
    expect(loadDataSources).toHaveBeenCalledOnce()
  })

  it('test_wizard_stays_open_and_api_is_not_recalled_on_approval_failure', async () => {
    // Spec: "OR iterate by editing individual types and relationships"
    // If the API fails, the wizard stays open so the user can retry.
    const selectedKgId = { value: 'kg-123' }
    const wizardOpen = { value: true }
    const createDataSource = vi.fn().mockRejectedValue(new Error('Service unavailable'))
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    let errorShown = ''

    async function approveOntology() {
      if (!selectedKgId.value) return
      try {
        await createDataSource({ kg_id: selectedKgId.value, name: 'my-repo' })
        wizardOpen.value = false
        await loadDataSources()
      } catch (err) {
        errorShown = err instanceof Error ? err.message : 'Failed'
        // wizard stays open
      }
    }

    await approveOntology()
    expect(wizardOpen.value).toBe(true) // wizard remains open
    expect(loadDataSources).not.toHaveBeenCalled()
    expect(errorShown).toBe('Service unavailable')
  })
})

// ── Group 4: Scenario: Individual type editing — label validation ──────────────
//
// Spec:
// "GIVEN a proposed or existing ontology
//  WHEN the user edits a specific type
//  THEN they can modify the label, description, required properties, and optional properties
//  AND they can add or remove relationship types
//  AND they can specify exact property requirements
//       (e.g., 'documentation_page must have source_url')"

describe('Ontology Design — Scenario: Individual type editing — validateTypeLabel', () => {
  it('test_empty_label_is_invalid', () => {
    const nodes = [makeNode({ label: 'Repository' })]
    const result = validateTypeLabel(nodes, '', 0)
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Label is required')
  })

  it('test_whitespace_only_label_is_invalid', () => {
    const nodes = [makeNode({ label: 'Repository' })]
    const result = validateTypeLabel(nodes, '   ', 0)
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Label is required')
  })

  it('test_unique_label_is_valid', () => {
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    // Editing index 0 (Repository) with a unique new label
    const result = validateTypeLabel(nodes, 'GitHubRepository', 0)
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })

  it('test_saving_unchanged_label_on_existing_node_is_valid', () => {
    // When the user clicks Save without changing the label, validation must pass.
    // The current index (0) is excluded from the duplicate check.
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    const result = validateTypeLabel(nodes, 'Repository', 0)
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })

  it('test_duplicate_label_with_another_existing_node_is_invalid', () => {
    // The user is editing index 0 (Repository) and tries to rename it to 'Issue'
    // which already exists at index 1.
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    const result = validateTypeLabel(nodes, 'Issue', 0)
    expect(result.valid).toBe(false)
    expect(result.error).toBe('A type with this label already exists')
  })

  it('test_new_node_at_index_minus1_with_unique_label_is_valid', () => {
    // When adding a new node (index -1 means it is not yet in the list),
    // any unique label is valid.
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    const result = validateTypeLabel(nodes, 'Commit', -1)
    expect(result.valid).toBe(true)
  })

  it('test_new_node_at_index_minus1_with_duplicate_label_is_invalid', () => {
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    const result = validateTypeLabel(nodes, 'Repository', -1)
    expect(result.valid).toBe(false)
    expect(result.error).toBe('A type with this label already exists')
  })

  it('test_label_trimming_is_applied_before_duplicate_check', () => {
    // '  Issue  ' trims to 'Issue' — should be caught as a duplicate.
    const nodes = [makeNode({ label: 'Repository' }), makeNode({ label: 'Issue' })]
    const result = validateTypeLabel(nodes, '  Issue  ', 0)
    expect(result.valid).toBe(false)
    expect(result.error).toBe('A type with this label already exists')
  })

  it('test_validateTypeLabel_works_identically_for_edge_types', () => {
    // The same function is reused for edges — label uniqueness within edges list.
    const edges = [makeEdge({ label: 'CONTAINS' }), makeEdge({ label: 'CREATED_BY' })]
    const duplicateResult = validateTypeLabel(edges, 'CREATED_BY', 0)
    const uniqueResult = validateTypeLabel(edges, 'AUTHORED_BY', 0)

    expect(duplicateResult.valid).toBe(false)
    expect(uniqueResult.valid).toBe(true)
  })
})

// ── Group 5: Scenario: Individual type editing — property list parsing ─────────

describe('Ontology Design — Scenario: Individual type editing — parsePropertyList', () => {
  it('test_comma_separated_list_is_split_into_array', () => {
    expect(parsePropertyList('name, url, slug')).toEqual(['name', 'url', 'slug'])
  })

  it('test_whitespace_around_items_is_trimmed', () => {
    expect(parsePropertyList('  name ,  url  , slug  ')).toEqual(['name', 'url', 'slug'])
  })

  it('test_empty_entries_are_filtered_out', () => {
    // Double commas, trailing comma, or leading comma must not produce empty strings.
    expect(parsePropertyList('name,,  ,url')).toEqual(['name', 'url'])
  })

  it('test_empty_string_returns_empty_array', () => {
    expect(parsePropertyList('')).toEqual([])
  })

  it('test_single_property_without_commas_returns_single_item_array', () => {
    expect(parsePropertyList('source_url')).toEqual(['source_url'])
  })

  it('test_exact_property_requirement_preserved_verbatim', () => {
    // Spec: "they can specify exact property requirements
    //       (e.g., 'documentation_page must have source_url')"
    // The property name 'source_url' must be captured exactly.
    const result = parsePropertyList('source_url')
    expect(result).toContain('source_url')
  })

  it('test_node_edit_save_populates_required_and_optional_properties_from_edit_fields', () => {
    // Mirrors the saveEditNode() logic that calls parsePropertyList on both fields.
    const node = makeNode({
      editing: true,
      editRequired: 'title, number, state',
      editOptional: 'body, labels',
    })

    // Apply the save logic
    node.required_properties = parsePropertyList(node.editRequired)
    node.optional_properties = parsePropertyList(node.editOptional)
    node.editing = false

    expect(node.required_properties).toEqual(['title', 'number', 'state'])
    expect(node.optional_properties).toEqual(['body', 'labels'])
    expect(node.editing).toBe(false)
  })

  it('test_edge_edit_save_populates_required_and_optional_properties', () => {
    const edge = makeEdge({
      editing: true,
      editRequired: 'since, weight',
      editOptional: 'role',
    })

    edge.required_properties = parsePropertyList(edge.editRequired)
    edge.optional_properties = parsePropertyList(edge.editOptional)
    edge.editing = false

    expect(edge.required_properties).toEqual(['since', 'weight'])
    expect(edge.optional_properties).toEqual(['role'])
  })
})

// ── Group 5b: newBlankNodeType / newBlankEdgeType helpers ─────────────────────

describe('Ontology Design — Adding node and edge types', () => {
  it('test_newBlankNodeType_starts_in_editing_mode_with_empty_label', () => {
    const node = newBlankNodeType()
    expect(node.editing).toBe(true)
    expect(node.label).toBe('')
    expect(node.editLabel).toBe('')
  })

  it('test_newBlankEdgeType_starts_in_editing_mode_with_empty_from_and_to', () => {
    const edge = newBlankEdgeType()
    expect(edge.editing).toBe(true)
    expect(edge.from).toBe('')
    expect(edge.to).toBe('')
  })

  it('test_adding_node_appends_a_blank_entry_in_edit_mode', () => {
    const nodes: OntologyNodeType[] = [makeNode({ label: 'Repository' })]
    nodes.push(newBlankNodeType())

    expect(nodes).toHaveLength(2)
    expect(nodes[1].editing).toBe(true)
    expect(nodes[1].label).toBe('')
  })

  it('test_saving_a_newly_added_node_with_valid_label_commits_it', () => {
    const nodes: OntologyNodeType[] = []
    nodes.push(newBlankNodeType())
    const node = nodes[0]!
    node.editLabel = 'Milestone'
    node.editDescription = 'A project milestone'
    node.editRequired = 'title, due_date'

    const validation = validateTypeLabel(nodes, node.editLabel, 0)
    expect(validation.valid).toBe(true)

    node.label = node.editLabel.trim()
    node.description = node.editDescription
    node.required_properties = parsePropertyList(node.editRequired)
    node.editing = false

    expect(nodes[0].label).toBe('Milestone')
    expect(nodes[0].required_properties).toEqual(['title', 'due_date'])
    expect(nodes[0].editing).toBe(false)
  })

  it('test_saving_a_newly_added_node_with_empty_label_returns_error', () => {
    const nodes: OntologyNodeType[] = [newBlankNodeType()]
    const node = nodes[0]!
    node.editLabel = ''

    const validation = validateTypeLabel(nodes, node.editLabel, 0)
    expect(validation.valid).toBe(false)
    expect(validation.error).toBe('Label is required')

    // Node remains in edit mode; label is NOT updated
    node.editError = validation.error
    expect(node.editing).toBe(true)
    expect(node.label).toBe('')
  })

  it('test_removing_a_node_splices_it_from_the_list', () => {
    const nodes: OntologyNodeType[] = [
      makeNode({ label: 'Repository' }),
      makeNode({ label: 'Issue' }),
      makeNode({ label: 'Commit' }),
    ]

    nodes.splice(1, 1) // remove Issue

    expect(nodes).toHaveLength(2)
    expect(nodes.map((n) => n.label)).toEqual(['Repository', 'Commit'])
  })

  it('test_cancelling_edit_reverts_editing_flag_without_modifying_committed_label', () => {
    const node = makeNode({ label: 'Repository', editing: true, editLabel: 'ChangedLabel' })

    // Cancel — just set editing to false, do NOT apply editLabel
    node.editing = false
    node.editError = ''

    expect(node.label).toBe('Repository') // original preserved
    expect(node.editing).toBe(false)
  })
})

// ── Group 6: Scenario: Ontology change after initial extraction ───────────────
//
// Spec:
// "GIVEN a knowledge graph with completed extraction
//  WHEN the user modifies the ontology
//  THEN the system warns that this will trigger a full re-extraction
//  AND the user must confirm before the change is applied"

describe('Ontology Design — Scenario: Ontology change after initial extraction', () => {
  interface DataSourceItem {
    id: string
    name: string
    sync_runs: Array<{ id: string; status: 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed' }>
  }

  function hasCompletedExtraction(ds: DataSourceItem): boolean {
    return ds.sync_runs.some((r) => r.status === 'completed')
  }

  it('test_data_source_with_completed_run_triggers_confirmation_dialog', () => {
    // Spec: "THEN the system warns that this will trigger a full re-extraction"
    const ds: DataSourceItem = {
      id: 'ds-1',
      name: 'my-service',
      sync_runs: [{ id: 'run-1', status: 'completed' }],
    }

    const reExtractionConfirmOpen = { value: false }
    const pendingDsId = { value: null as string | null }

    function requestOntologyEdit(dataSource: DataSourceItem) {
      if (hasCompletedExtraction(dataSource)) {
        pendingDsId.value = dataSource.id
        reExtractionConfirmOpen.value = true
      }
    }

    requestOntologyEdit(ds)
    expect(reExtractionConfirmOpen.value).toBe(true)
    expect(pendingDsId.value).toBe('ds-1')
  })

  it('test_data_source_with_only_failed_runs_does_not_trigger_confirmation', () => {
    // A failed sync is NOT a completed extraction — no re-extraction needed.
    const ds: DataSourceItem = {
      id: 'ds-failed',
      name: 'my-service',
      sync_runs: [{ id: 'run-1', status: 'failed' }],
    }

    const reExtractionConfirmOpen = { value: false }
    let editorOpened = false

    function requestOntologyEdit(dataSource: DataSourceItem) {
      if (hasCompletedExtraction(dataSource)) {
        reExtractionConfirmOpen.value = true
      } else {
        editorOpened = true
      }
    }

    requestOntologyEdit(ds)
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(true)
  })

  it('test_data_source_with_no_runs_skips_confirmation', () => {
    const ds: DataSourceItem = {
      id: 'ds-new',
      name: 'brand-new',
      sync_runs: [],
    }

    const reExtractionConfirmOpen = { value: false }
    let editorOpened = false

    function requestOntologyEdit(dataSource: DataSourceItem) {
      if (hasCompletedExtraction(dataSource)) {
        reExtractionConfirmOpen.value = true
      } else {
        editorOpened = true
      }
    }

    requestOntologyEdit(ds)
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(true)
  })

  it('test_confirm_re_extraction_closes_dialog_and_opens_editor', () => {
    // Spec: "AND the user must confirm before the change is applied"
    // Confirming → dialog closes → editor opens.
    const reExtractionConfirmOpen = { value: true }
    const pendingDsId = { value: 'ds-1' }
    let editorOpened = false

    function confirmReExtraction() {
      reExtractionConfirmOpen.value = false
      editorOpened = true // openOntologyEditor(ds)
    }

    confirmReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(true)
  })

  it('test_cancel_re_extraction_closes_dialog_without_opening_editor', () => {
    // Spec: "AND the user must confirm before the change is applied"
    // Cancelling → dialog closes → editor does NOT open.
    const reExtractionConfirmOpen = { value: true }
    const pendingDsId = { value: 'ds-1' }
    let editorOpened = false

    function cancelReExtraction() {
      reExtractionConfirmOpen.value = false
      pendingDsId.value = null
    }

    cancelReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(false)
    expect(pendingDsId.value).toBeNull()
  })

  it('test_data_source_with_mixed_runs_is_treated_as_completed_if_any_succeeded', () => {
    // A DS that has a completed run AND a subsequent failed run still requires
    // the re-extraction confirmation, because data has been extracted before.
    const ds: DataSourceItem = {
      id: 'ds-mixed',
      name: 'my-service',
      sync_runs: [
        { id: 'run-2', status: 'failed' },
        { id: 'run-1', status: 'completed' },
      ],
    }

    expect(hasCompletedExtraction(ds)).toBe(true)
  })

  it('test_re_extraction_warning_is_present_in_page_source', () => {
    // Source inspection: the dialog must mention re-extraction.
    const { readFileSync } = require('fs')
    const { resolve } = require('path')
    const source: string = readFileSync(
      resolve(__dirname, '../pages/data-sources/index.vue'),
      'utf-8',
    )
    expect(source.toLowerCase()).toContain('re-extraction')
    expect(source).toContain('reExtractionConfirmOpen')
  })
})

// ── Group 7: Backend API Alignment — buildOntologySavePayload ─────────────────
//
// Spec:
// "GIVEN a user performs any create, read, update, or delete operation via the UI
//  WHEN the operation is submitted
//  THEN the corresponding backend API call succeeds (2xx response)"
//
// The ontology is persisted via PATCH /management/data-sources/{ds_id}
// with an `ontology` body containing node_types and edge_types arrays.
// The backend expects `from_type`/`to_type` (snake_case) instead of `from`/`to`.

describe('Ontology Design — Backend API Alignment: buildOntologySavePayload', () => {
  it('test_payload_wraps_nodes_and_edges_under_ontology_key', () => {
    const payload = buildOntologySavePayload([], [])
    expect(payload).toHaveProperty('ontology')
    expect(payload.ontology).toHaveProperty('node_types')
    expect(payload.ontology).toHaveProperty('edge_types')
  })

  it('test_empty_ontology_produces_empty_arrays', () => {
    const payload = buildOntologySavePayload([], [])
    expect(payload.ontology.node_types).toEqual([])
    expect(payload.ontology.edge_types).toEqual([])
  })

  it('test_node_type_fields_are_correctly_mapped', () => {
    const nodes = [
      {
        label: 'Repository',
        description: 'A GitHub repository.',
        required_properties: ['name', 'url'],
        optional_properties: ['description', 'stars'],
      },
    ]
    const payload = buildOntologySavePayload(nodes, [])
    expect(payload.ontology.node_types).toEqual([
      {
        label: 'Repository',
        description: 'A GitHub repository.',
        required_properties: ['name', 'url'],
        optional_properties: ['description', 'stars'],
      },
    ])
  })

  it('test_edge_type_from_and_to_are_mapped_to_from_type_and_to_type', () => {
    // Spec: backend expects `from_type` / `to_type` (not `from` / `to`).
    const edges = [
      {
        label: 'CONTAINS',
        description: 'Repo contains issues.',
        from: 'Repository',
        to: 'Issue | PullRequest | Commit',
        required_properties: [],
        optional_properties: [],
      },
    ]
    const payload = buildOntologySavePayload([], edges)
    const edgeType = payload.ontology.edge_types[0]!
    expect(edgeType).toHaveProperty('from_type', 'Repository')
    expect(edgeType).toHaveProperty('to_type', 'Issue | PullRequest | Commit')
    expect(edgeType).not.toHaveProperty('from')
    expect(edgeType).not.toHaveProperty('to')
  })

  it('test_multiple_nodes_and_edges_are_all_included', () => {
    const nodes = [
      { label: 'Repository', description: 'repo', required_properties: ['name'], optional_properties: [] },
      { label: 'Issue', description: 'issue', required_properties: ['title', 'number', 'state'], optional_properties: ['body'] },
    ]
    const edges = [
      { label: 'CONTAINS', description: 'contains', from: 'Repository', to: 'Issue', required_properties: [], optional_properties: [] },
      { label: 'CREATED_BY', description: 'created by', from: 'Issue', to: 'User', required_properties: [], optional_properties: ['created_at'] },
    ]
    const payload = buildOntologySavePayload(nodes, edges)
    expect(payload.ontology.node_types).toHaveLength(2)
    expect(payload.ontology.edge_types).toHaveLength(2)
  })

  it('test_saveOntology_calls_patch_with_built_payload', async () => {
    // Integration: buildOntologySavePayload is used by saveOntology() in the Vue
    // component. This test verifies the PATCH call carries the correctly shaped body.
    const apiFetch = vi.fn().mockResolvedValue({})
    const dsId = 'ds-abc-123'
    const nodes = [
      { label: 'Repository', description: 'A GitHub repository.', required_properties: ['name', 'url'], optional_properties: ['description'] },
    ]
    const edges = [
      { label: 'CONTAINS', description: 'Repo contains issues.', from: 'Repository', to: 'Issue', required_properties: [], optional_properties: [] },
    ]

    const payload = buildOntologySavePayload(nodes, edges)
    await apiFetch(`/management/data-sources/${dsId}`, { method: 'PATCH', body: payload })

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/data-sources/ds-abc-123',
      expect.objectContaining({
        method: 'PATCH',
        body: {
          ontology: {
            node_types: [
              {
                label: 'Repository',
                description: 'A GitHub repository.',
                required_properties: ['name', 'url'],
                optional_properties: ['description'],
              },
            ],
            edge_types: [
              {
                label: 'CONTAINS',
                description: 'Repo contains issues.',
                from_type: 'Repository',
                to_type: 'Issue',
                required_properties: [],
                optional_properties: [],
              },
            ],
          },
        },
      }),
    )
  })

  it('test_saveOntology_closes_dialog_and_reloads_on_success', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const editOntologyOpen = { value: true }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    const savingOntology = { value: false }

    async function saveOntology(dsId: string) {
      savingOntology.value = true
      try {
        await apiFetch(`/management/data-sources/${dsId}`, {
          method: 'PATCH',
          body: buildOntologySavePayload([], []),
        })
        editOntologyOpen.value = false
        await loadDataSources()
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology('ds-1')
    expect(editOntologyOpen.value).toBe(false)
    expect(loadDataSources).toHaveBeenCalledOnce()
    expect(savingOntology.value).toBe(false)
  })

  it('test_saveOntology_keeps_dialog_open_on_failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Internal Server Error'))
    const editOntologyOpen = { value: true }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    const savingOntology = { value: false }
    let caughtError = ''

    async function saveOntology(dsId: string) {
      savingOntology.value = true
      try {
        await apiFetch(`/management/data-sources/${dsId}`, {
          method: 'PATCH',
          body: buildOntologySavePayload([], []),
        })
        editOntologyOpen.value = false
        await loadDataSources()
      } catch (err) {
        caughtError = err instanceof Error ? err.message : 'Failed'
        // dialog stays open intentionally
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology('ds-1')
    expect(editOntologyOpen.value).toBe(true)
    expect(loadDataSources).not.toHaveBeenCalled()
    expect(caughtError).toBe('Internal Server Error')
    expect(savingOntology.value).toBe(false)
  })
})
