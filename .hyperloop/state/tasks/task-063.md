---
id: task-063
title: Ontology wizard and editor — add new node and edge types from scratch
spec_ref: "specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3"
status: not-started
phase: null
deps:
  - task-043
round: 0
branch: null
pr: null
pr_title: "feat(ui): add new-type buttons to ontology wizard step 4 and post-extraction editor"
pr_description: |
  ## What & Why

  The Ontology Design spec requires that users can **add** relationship types (edge types)
  and node types during both the initial review wizard and subsequent ontology edits. The
  current implementation only renders AI-proposed types and allows editing or removing them;
  there is no path to add a brand-new type from scratch.

  Without this capability, a user whose data source has an unusual entity the AI did not
  propose (e.g., a `Milestone` or `Dependency` node) is stuck — they cannot extend the
  ontology beyond what the AI returned.

  ## Spec Requirements Satisfied

  **Requirement: Ontology Design — Scenario: Individual type editing**
  > GIVEN a proposed or existing ontology
  > WHEN the user edits a specific type
  > THEN they can modify the label, description, required properties, and optional properties
  > AND **they can add or remove relationship types**
  > AND they can specify exact property requirements

  **Requirement: Ontology Design — Scenario: Ontology review and approval**
  > THEN they can approve the ontology as-is
  > OR **iterate by editing individual types and relationships**

  The "add" path for both node types and edge types is not present in the current wizard
  (step 4 of `src/dev-ui/app/pages/data-sources/index.vue`) or the post-extraction ontology
  editor dialog.

  ## Key Design Decisions

  - **"Add Node Type" button** appears below the Node Types list in both the wizard and the
    ontology editor; it inserts a new blank `ProposedNodeType` entry and immediately opens it
    in edit mode so the user can fill in label, description, and properties.
  - **"Add Edge Type" button** appears below the Edge Types list in both the wizard and the
    ontology editor; it inserts a new blank `ProposedEdgeType` entry (from/to fields editable)
    and opens it in edit mode.
  - New types open in edit mode immediately so the user cannot accidentally approve a type
    with an empty label.
  - Empty label on Save is rejected with an inline validation error.
  - Duplicate label detection: if a type with the same label already exists, show a warning.
  - Consistent UI: the Add buttons use the same card/badge/icon design as existing type cards.
  - Design language: `Button` with `variant="outline"` and a `Plus` Lucide icon. Cards use
    `rounded-xl`, buttons `rounded-md`, consistent with the Kartograph design system.

  ## Files Affected

  - `src/dev-ui/app/pages/data-sources/index.vue` — wizard step 4 Node/Edge sections and
    the post-extraction ontology editor dialog: add "Add Node Type" / "Add Edge Type" buttons,
    `addNode()` / `addEdge()` composable functions, and inline validation for empty labels and
    duplicate detection.
  - `src/dev-ui/app/tests/ontology-add-types.test.ts` — new test file (TDD-first) covering:
    1. Add Node Type button renders in wizard step 4 and editor dialog
    2. Clicking Add Node Type inserts a new entry in edit mode
    3. Saving with empty label shows validation error, does not close edit mode
    4. Duplicate label shows warning
    5. Saving with valid label adds type to the list in view mode
    6. Add Edge Type button renders and inserts a blank edge with editable from/to
    7. Saving a new edge type with valid data adds it to the edge list

  ## How to Verify

  1. Open the data source wizard. On step 4 (Ontology Review), below the "Node Types" section,
     a "+ Add Node Type" button is visible.
  2. Click it — a new card appears in edit mode with empty label/description/properties.
  3. Type a label (e.g. "Milestone"), description, required props, click Save — card appears
     in view mode with the new type.
  4. Repeat for Edge Type — the new edge type card shows editable "From" and "To" fields.
  5. Try saving with an empty label — inline error "Label is required" appears.
  6. Approve the ontology including the user-added types — all types (AI-proposed + added)
     are included in the `createDataSource` payload.
  7. Open the post-extraction ontology editor (Edit Ontology button on a data source card)
     and confirm the same Add buttons appear there.
  8. Run `cd src/dev-ui && pnpm test` — all tests in `ontology-add-types.test.ts` pass.

  ## Caveats

  - Depends on task-043 (which implements the individual type editor structure, TDD tests,
    and the `ProposedNodeType` / `ProposedEdgeType` interfaces). task-063 extends that work
    by adding the "Add" path.
  - The ontology is currently front-end only (AI proposal is mocked). When the real AI
    endpoint lands (AIHCM-174), the Add buttons will still work because they operate on
    the `proposedNodes` / `proposedEdges` reactive refs, not on the API response.
  - Re-extraction warning (task-043 scenario 5) should fire after adding types to an
    existing ontology with completed extraction, exactly as it does for edits — no additional
    changes needed here.
---

## Spec Coverage

**Requirement: Ontology Design — Scenario: Individual type editing** from
`specs/ui/experience.spec.md`:

> GIVEN a proposed or existing ontology
> WHEN the user edits a specific type
> THEN they can modify the label, description, required properties, and optional properties
> AND **they can add or remove relationship types**
> AND they can specify exact property requirements (e.g., "documentation_page must have source_url")

**Requirement: Ontology Design — Scenario: Ontology review and approval**:
> OR iterate by **editing individual types and relationships**

## Gap

The ontology wizard (`data-sources/index.vue`, step 4) and the post-extraction ontology
editor dialog both render a list of AI-proposed node types and edge types. Each type has
**Edit** (pencil) and **Remove** (trash) action buttons.

There is **no Add path** — no button to create a new node type or edge type from scratch.
The `proposedNodes` and `proposedEdges` refs are only ever populated via `beginOntologyProposal()`
(which fills from `GITHUB_PROPOSAL_NODES` / `GITHUB_PROPOSAL_EDGES`). There is no `addNode()`
or `addEdge()` function.

task-043 (old blob SHA) covers individual type **editing** — modifying existing types'
labels, descriptions, required/optional properties, and connected relationship types. It
does not cover creating brand-new types beyond the AI proposal. No existing task with the
current spec blob SHA covers this gap.

## Scope

### TDD — write tests first

Create `src/dev-ui/app/tests/ontology-add-types.test.ts` with the following tests:

```typescript
import { describe, it, expect } from 'vitest'

// Types (mirroring data-sources/index.vue)
interface ProposedNodeType {
  label: string; description: string
  required_properties: string[]; optional_properties: string[]
  editing: boolean
  editLabel: string; editDescription: string; editRequired: string; editOptional: string
}

interface ProposedEdgeType {
  label: string; description: string; from: string; to: string
  required_properties: string[]; optional_properties: string[]
  editing: boolean
  editLabel: string; editDescription: string; editRequired: string; editOptional: string
}

function newBlankNode(): ProposedNodeType {
  return {
    label: '', description: '', required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  }
}

function newBlankEdge(): ProposedEdgeType {
  return {
    label: '', description: '', from: '', to: '',
    required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  }
}

function saveNode(nodes: ProposedNodeType[], idx: number): { error?: string } {
  const n = nodes[idx]
  if (!n.editLabel.trim()) return { error: 'Label is required' }
  if (nodes.some((x, i) => i !== idx && x.label === n.editLabel.trim())) {
    return { error: 'A type with this label already exists' }
  }
  n.label = n.editLabel.trim()
  n.description = n.editDescription
  n.required_properties = n.editRequired.split(',').map(s => s.trim()).filter(Boolean)
  n.optional_properties = n.editOptional.split(',').map(s => s.trim()).filter(Boolean)
  n.editing = false
  return {}
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('Ontology wizard — add new node types', () => {
  it('newBlankNode returns an entry in edit mode with empty label', () => {
    const node = newBlankNode()
    expect(node.editing).toBe(true)
    expect(node.label).toBe('')
  })

  it('addNode() appends a blank node in edit mode to the list', () => {
    const nodes: ProposedNodeType[] = []
    nodes.push(newBlankNode())
    expect(nodes).toHaveLength(1)
    expect(nodes[0].editing).toBe(true)
  })

  it('saveNode() with empty label returns a validation error', () => {
    const nodes = [newBlankNode()]
    const result = saveNode(nodes, 0)
    expect(result.error).toBe('Label is required')
    expect(nodes[0].editing).toBe(true)
  })

  it('saveNode() with a duplicate label returns a validation error', () => {
    const existing: ProposedNodeType = {
      label: 'Repository', description: '', required_properties: [],
      optional_properties: [], editing: false, editLabel: 'Repository',
      editDescription: '', editRequired: '', editOptional: '',
    }
    const nodes: ProposedNodeType[] = [existing, newBlankNode()]
    nodes[1].editLabel = 'Repository'
    const result = saveNode(nodes, 1)
    expect(result.error).toBe('A type with this label already exists')
  })

  it('saveNode() with valid data updates the type and closes edit mode', () => {
    const nodes = [newBlankNode()]
    nodes[0].editLabel = 'Milestone'
    nodes[0].editDescription = 'A project milestone'
    nodes[0].editRequired = 'title, due_date'
    const result = saveNode(nodes, 0)
    expect(result.error).toBeUndefined()
    expect(nodes[0].editing).toBe(false)
    expect(nodes[0].label).toBe('Milestone')
    expect(nodes[0].required_properties).toEqual(['title', 'due_date'])
  })
})

describe('Ontology wizard — add new edge types', () => {
  it('newBlankEdge returns an entry in edit mode with empty label and from/to', () => {
    const edge = newBlankEdge()
    expect(edge.editing).toBe(true)
    expect(edge.label).toBe('')
    expect(edge.from).toBe('')
    expect(edge.to).toBe('')
  })

  it('addEdge() appends a blank edge in edit mode to the list', () => {
    const edges: ProposedEdgeType[] = []
    edges.push(newBlankEdge())
    expect(edges).toHaveLength(1)
    expect(edges[0].editing).toBe(true)
  })
})
```

### Implementation

If tests fail, implement in `src/dev-ui/app/pages/data-sources/index.vue`:

#### 1. `addNode()` / `addEdge()` functions

```typescript
function addNode() {
  proposedNodes.value.push({
    label: '', description: '', required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  })
}

function addEdge() {
  proposedEdges.value.push({
    label: '', description: '', from: '', to: '',
    required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  })
}
```

Also add `editFrom` / `editTo` fields to `ProposedEdgeType` for the new-type edit form.

#### 2. Extend `saveEditNode()` to validate empty label and duplicate

```typescript
const nodeEditError = ref('')  // per-type error; could be array-indexed

function saveEditNode(index: number) {
  const n = proposedNodes.value[index]
  const trimmedLabel = n.editLabel.trim()
  if (!trimmedLabel) {
    nodeEditError.value = 'Label is required'
    return
  }
  if (proposedNodes.value.some((x, i) => i !== index && x.label === trimmedLabel)) {
    nodeEditError.value = 'A type with this label already exists'
    return
  }
  nodeEditError.value = ''
  n.label = trimmedLabel
  // ... rest of existing save logic
}
```

#### 3. Template additions in wizard step 4

Below the node types list (inside `v-else-if="ontologyReady"`):
```html
<!-- Add Node Type -->
<Button variant="outline" size="sm" class="mt-2 w-full gap-2" @click="addNode">
  <Plus class="size-4" />
  Add Node Type
</Button>
```

Below the edge types list:
```html
<!-- Add Edge Type -->
<Button variant="outline" size="sm" class="mt-2 w-full gap-2" @click="addEdge">
  <Plus class="size-4" />
  Add Edge Type
</Button>
```

Update the edge type edit form to include From/To fields (currently missing when creating
new edge types).

#### 4. Mirror changes in the post-extraction ontology editor dialog

The `editOntologyOpen` dialog renders `editNodes` and `editEdges`. Add the same "Add"
buttons below each list with `addEditNode()` / `addEditEdge()` variants that operate on
the `editNodes.value` / `editEdges.value` refs instead.

## Acceptance Criteria

- Wizard step 4 shows an "+ Add Node Type" button below the Node Types list.
- Wizard step 4 shows an "+ Add Edge Type" button below the Edge Types list.
- Clicking either button appends a new entry **in edit mode** (with empty fields).
- Saving with an empty label shows an inline error "Label is required" and keeps the entry
  in edit mode.
- Saving with a duplicate label shows "A type with this label already exists."
- Saving with a valid, unique label closes edit mode and displays the type in view mode.
- The new types are included when `approveOntology()` submits the data source.
- The same Add buttons appear in the post-extraction ontology editor dialog.
- All tests in `src/dev-ui/app/tests/ontology-add-types.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test`

## TDD Cycle

1. Create `src/dev-ui/app/tests/ontology-add-types.test.ts` with the tests above (RED).
2. Add `addNode()` / `addEdge()` functions and update `saveEditNode()` / `saveEditEdge()`
   with validation in `data-sources/index.vue`.
3. Add the "+ Add Node Type" / "+ Add Edge Type" buttons to step 4 and the editor dialog.
4. Run tests (GREEN).
5. Commit atomically.
