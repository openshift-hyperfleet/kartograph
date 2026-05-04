/**
 * Pure utility functions for the Ontology Design wizard flow.
 *
 * Extracted from data-sources/index.vue to enable direct unit testing without
 * mounting the Nuxt component. Every function is a pure transformation with no
 * side-effects and no framework imports.
 *
 * Spec: specs/ui/experience.spec.md
 *   - Requirement: Ontology Design
 *     - Scenario: Intent description
 *     - Scenario: Agent-proposed ontology
 *     - Scenario: Ontology review and approval
 *     - Scenario: Individual type editing
 *     - Scenario: Ontology change after initial extraction
 */

// ── Types ──────────────────────────────────────────────────────────────────────

/**
 * A proposed or existing node type in the ontology.
 *
 * The `editing` flag and `edit*` fields are transient UI state that mirror the
 * committed values while the user is modifying them. The canonical fields
 * (`label`, `description`, etc.) are only updated when the user saves.
 */
export interface OntologyNodeType {
  label: string
  description: string
  required_properties: string[]
  optional_properties: string[]
  /** true while the inline editor form is open for this type */
  editing: boolean
  /** transient edit buffer — mirrors label before save */
  editLabel: string
  /** transient edit buffer — mirrors description before save */
  editDescription: string
  /** transient edit buffer — required props as comma-separated string */
  editRequired: string
  /** transient edit buffer — optional props as comma-separated string */
  editOptional: string
  /** validation error message; empty string when no error */
  editError?: string
}

/**
 * A proposed or existing edge type in the ontology.
 */
export interface OntologyEdgeType {
  label: string
  description: string
  /** Source node type label (e.g. 'Repository') */
  from: string
  /** Target node type label (e.g. 'Issue | PullRequest') */
  to: string
  required_properties: string[]
  optional_properties: string[]
  editing: boolean
  editLabel: string
  editDescription: string
  editRequired: string
  editOptional: string
  editError?: string
}

// ── Validation results ─────────────────────────────────────────────────────────

export interface LabelValidationResult {
  /** true when the label is valid and may be committed */
  valid: boolean
  /** Non-empty string describing why validation failed; empty when valid */
  error: string
}

export interface IntentValidationResult {
  valid: boolean
  error: string
}

// ── Label validation ───────────────────────────────────────────────────────────

/**
 * Validates a label for a node or edge type being edited or added.
 *
 * Rules (mirroring data-sources/index.vue saveEditNode / saveEditEdge):
 *   1. Label must not be empty (after trimming whitespace).
 *   2. Label must not duplicate another type's committed label in the same list
 *      (the current item at `currentIndex` is excluded from the duplicate check
 *      so that saving an unchanged label on an existing item always succeeds).
 *
 * @param items        - Current list of types (nodes or edges).
 * @param editLabel    - The draft label entered by the user.
 * @param currentIndex - Index of the item being edited, or -1 when adding a new
 *                       item (so the full list is checked for duplicates).
 *
 * @example
 * // Editing the Repository node at index 0:
 * validateTypeLabel(nodes, 'Repository', 0)  // → { valid: true, error: '' }
 *
 * // Attempting to rename to an empty string:
 * validateTypeLabel(nodes, '   ', 0)          // → { valid: false, error: 'Label is required' }
 *
 * // Attempting to use a label already taken by another node:
 * validateTypeLabel(nodes, 'Issue', 0)        // → { valid: false, error: 'A type with this label already exists' }
 */
export function validateTypeLabel(
  items: Array<{ label: string }>,
  editLabel: string,
  currentIndex: number,
): LabelValidationResult {
  const trimmed = editLabel.trim()

  if (!trimmed) {
    return { valid: false, error: 'Label is required' }
  }

  const duplicate = items.some((item, i) => i !== currentIndex && item.label === trimmed)
  if (duplicate) {
    return { valid: false, error: 'A type with this label already exists' }
  }

  return { valid: true, error: '' }
}

// ── Intent validation ──────────────────────────────────────────────────────────

/**
 * Validates the free-text intent description entered in step 3 of the wizard.
 *
 * Spec: "GIVEN a user who has connected a data source
 *        WHEN the connection is saved
 *        THEN the user is prompted to describe (in free text) what problems or
 *             questions they want to solve with this data"
 *
 * The intent field is required — the user must describe at least something
 * before the agent can propose an ontology.
 */
export function validateIntentText(text: string): IntentValidationResult {
  if (!text.trim()) {
    return { valid: false, error: 'Please describe your intent before continuing.' }
  }
  return { valid: true, error: '' }
}

// ── Property list parsing ──────────────────────────────────────────────────────

/**
 * Parses a comma-separated property string into a trimmed, non-empty array.
 *
 * Used to convert the `editRequired` / `editOptional` text inputs into the
 * structured arrays stored on the ontology type.
 *
 * @example
 * parsePropertyList('name, url, slug')   // → ['name', 'url', 'slug']
 * parsePropertyList('name,,  ,url')      // → ['name', 'url']   (empties filtered)
 * parsePropertyList('')                  // → []
 */
export function parsePropertyList(raw: string): string[] {
  return raw.split(',').map((s) => s.trim()).filter(Boolean)
}

// ── Node type helpers ──────────────────────────────────────────────────────────

/**
 * Creates a new blank node type ready for the user to fill in.
 * The type starts in `editing` mode so the form opens immediately.
 */
export function newBlankNodeType(): OntologyNodeType {
  return {
    label: '',
    description: '',
    required_properties: [],
    optional_properties: [],
    editing: true,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    editError: '',
  }
}

/**
 * Creates a new blank edge type ready for the user to fill in.
 */
export function newBlankEdgeType(): OntologyEdgeType {
  return {
    label: '',
    description: '',
    from: '',
    to: '',
    required_properties: [],
    optional_properties: [],
    editing: true,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    editError: '',
  }
}

// ── Ontology save request builder ──────────────────────────────────────────────

/** Shape of the ontology payload sent to PATCH /management/data-sources/{id} */
export interface OntologySavePayload {
  ontology: {
    node_types: Array<{
      label: string
      description: string
      required_properties: string[]
      optional_properties: string[]
    }>
    edge_types: Array<{
      label: string
      description: string
      from_type: string
      to_type: string
      required_properties: string[]
      optional_properties: string[]
    }>
  }
}

/**
 * Builds the PATCH request body for persisting an ontology to the backend.
 *
 * Spec: Backend API Alignment — Scenario: Resource operations succeed end-to-end
 * "THEN the corresponding backend API call succeeds (2xx response)"
 *
 * Backend endpoint: PATCH /management/data-sources/{ds_id}
 * Note: `from_type` / `to_type` in the request body map to `from` / `to` in the
 * UI types to match the backend's snake_case field names.
 */
export function buildOntologySavePayload(
  nodes: Pick<OntologyNodeType, 'label' | 'description' | 'required_properties' | 'optional_properties'>[],
  edges: Pick<OntologyEdgeType, 'label' | 'description' | 'from' | 'to' | 'required_properties' | 'optional_properties'>[],
): OntologySavePayload {
  return {
    ontology: {
      node_types: nodes.map((n) => ({
        label: n.label,
        description: n.description,
        required_properties: n.required_properties,
        optional_properties: n.optional_properties,
      })),
      edge_types: edges.map((e) => ({
        label: e.label,
        description: e.description,
        from_type: e.from,
        to_type: e.to,
        required_properties: e.required_properties,
        optional_properties: e.optional_properties,
      })),
    },
  }
}
