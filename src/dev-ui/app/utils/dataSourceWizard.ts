/**
 * Pure utility functions for the Data Source Connection Wizard.
 *
 * Extracted from data-sources/index.vue to enable direct unit testing without
 * mounting the Nuxt component. Every function is a pure transformation with no
 * side-effects and no framework imports.
 *
 * Spec: specs/ui/experience.spec.md
 *   - Requirement: Data Source Connection
 *   - Requirement: Backend API Alignment — Scenario: Parent context is preserved
 */

// ── Adapter definitions ────────────────────────────────────────────────────────

/**
 * Describes a data-source adapter offered in the wizard.
 * The `icon` field is intentionally omitted here so that this module remains
 * framework-free; the Vue component resolves icon components separately.
 */
export interface AdapterDefinition {
  id: string
  label: string
  description: string
  available: boolean
}

/**
 * The canonical list of supported (and unavailable/future) adapters.
 *
 * Regression guard: adding a new adapter without updating the tests in
 * `data-source-connection-wizard.test.ts` will surface the change immediately.
 */
export const ADAPTERS: AdapterDefinition[] = [
  {
    id: 'github',
    label: 'GitHub',
    description: 'Repositories, issues, pull requests, commits, and contributors',
    available: true,
  },
  {
    id: 'gitlab',
    label: 'GitLab',
    description: 'Repositories, issues, merge requests, and pipelines',
    available: false,
  },
  {
    id: 'jira',
    label: 'Jira',
    description: 'Issues, epics, sprints, and project structure',
    available: false,
  },
]

// ── Adapter selection guard ────────────────────────────────────────────────────

/**
 * Returns true if the given adapter ID maps to an available adapter.
 * Unavailable adapters must not be selectable via the wizard UI.
 *
 * @param adapterId - The adapter ID to check (e.g. `'github'`, `'gitlab'`).
 */
export function isAdapterSelectable(adapterId: string): boolean {
  const adapter = ADAPTERS.find((a) => a.id === adapterId)
  return adapter?.available ?? false
}

// ── Step 1 navigation gate ─────────────────────────────────────────────────────

/**
 * Returns true when all conditions needed to advance past Step 1 are met:
 *   - An adapter has been selected (`selectedAdapterId` is non-empty).
 *   - A knowledge graph has been chosen (`selectedKnowledgeGraphId` is non-empty).
 *
 * Note: availability of the selected adapter is enforced by `isAdapterSelectable`
 * at selection time; the template disables unavailable adapter cards.
 */
export function canAdvanceStep1(
  selectedAdapterId: string,
  selectedKnowledgeGraphId: string,
): boolean {
  return !!selectedAdapterId && !!selectedKnowledgeGraphId
}

// ── Name inference ─────────────────────────────────────────────────────────────

/**
 * Infers a human-readable data-source name from a GitHub repository URL.
 *
 * Extracts the repository slug (the last path segment) and strips any `.git`
 * suffix. Returns `null` when the URL does not match the expected GitHub
 * pattern so callers can leave any existing name unchanged.
 *
 * Examples:
 *   `'https://github.com/acme/my-service'`       → `'my-service'`
 *   `'https://github.com/org/repo.git'`           → `'repo'`
 *   `'https://gitlab.com/org/repo'`               → `null`
 *   `'not-a-url'`                                 → `null`
 */
export function inferNameFromRepoUrl(url: string): string | null {
  const match = url.trim().match(/github\.com\/[^/]+\/([^/]+?)(?:\.git)?\/?$/)
  if (!match || !match[1]) return null
  return match[1]
}

// ── Step 2 validation ──────────────────────────────────────────────────────────

/** Result returned by `validateStep2`. */
export interface Step2ValidationResult {
  /** `true` when all required fields are valid and the wizard may advance. */
  valid: boolean
  /** Non-empty string when the data-source name field has a problem. */
  connNameError: string
  /** Non-empty string when the repository URL field has a problem. */
  connRepoUrlError: string
  /**
   * Always empty — the access token is optional in the wizard.
   * Present in the result shape so callers can safely clear all error fields
   * from a single destructuring assignment.
   */
  connTokenError: string
}

/**
 * Validates the fields collected during Step 2 (connection configuration).
 *
 * **Token is intentionally optional**: users may omit the access token when
 * the repository is public or when they intend to rotate credentials later.
 * The backend accepts connections without credentials.
 *
 * @param opts.connName      - The user-provided data-source name.
 * @param opts.connRepoUrl   - The user-provided GitHub repository URL.
 */
export function validateStep2(opts: {
  connName: string
  connRepoUrl: string
}): Step2ValidationResult {
  const result: Step2ValidationResult = {
    valid: true,
    connNameError: '',
    connRepoUrlError: '',
    connTokenError: '',
  }

  if (!opts.connName.trim()) {
    result.connNameError = 'Data source name is required.'
    result.valid = false
  }

  if (!opts.connRepoUrl.trim()) {
    result.connRepoUrlError = 'Repository URL is required.'
    result.valid = false
  } else if (!opts.connRepoUrl.includes('github.com')) {
    result.connRepoUrlError = 'Enter a valid GitHub repository URL.'
    result.valid = false
  }

  // Access token is OPTIONAL — no validation performed.

  return result
}

// ── API request builders ───────────────────────────────────────────────────────

/**
 * Builds the URL for creating a data source under a specific knowledge graph.
 *
 * Per API conventions, data source creation is a nested operation:
 *   POST /management/knowledge-graphs/{kg_id}/data-sources
 *
 * The knowledge graph ID must always be present in the URL path so the backend
 * can associate the new data source with the correct parent graph.
 *
 * @param kgId - The ID of the parent knowledge graph.
 */
export function buildDataSourceCreationUrl(kgId: string): string {
  return `/management/knowledge-graphs/${kgId}/data-sources`
}

/** Shape of the request body sent when creating a data source. */
export interface CreateDataSourceBody {
  name: string
  adapter_type: string
  connection_config: Record<string, string>
  credentials?: Record<string, string>
}

/**
 * Builds the JSON request body for creating a data source.
 *
 * The knowledge graph ID is intentionally **not** included in the body — it
 * belongs in the URL path per API conventions (nested creation, flat retrieval).
 *
 * Credentials are optional: when omitted from `opts` the resulting body does
 * not include a `credentials` key, which prevents `null`/`undefined` from
 * being serialised over the wire.
 */
export function buildDataSourceCreationBody(opts: {
  name: string
  adapter_type: string
  connection_config: Record<string, string>
  credentials?: Record<string, string>
}): CreateDataSourceBody {
  const body: CreateDataSourceBody = {
    name: opts.name,
    adapter_type: opts.adapter_type,
    connection_config: opts.connection_config,
  }
  if (opts.credentials) {
    body.credentials = opts.credentials
  }
  return body
}
