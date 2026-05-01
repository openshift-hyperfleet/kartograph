---
task_id: task-053
round: 3
role: spec-reviewer
verdict: fail
---
All 822 frontend unit tests pass. The implementation correctly covers most spec requirements including navigation structure (Mutations Console in Explore sidebar), interaction principles (copy-to-clipboard, mutation feedback), and the sync-status badge. However, two spec requirements are violated in the completed implementation.

## Requirement Status

### Requirement: Backend API Alignment — FAIL (partial)

**Scenario: Resource operations succeed end-to-end** — FAIL for mutations.

The `applyMutations()` function in `/src/dev-ui/app/composables/api/useGraphApi.ts` posts to `POST /graph/mutations`. The backend route (in `src/api/graph/presentation/routes.py`) is `POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations`. There is no `/graph/mutations` endpoint. Every mutation submission from the current dev-UI will return a 404.

```
Spec: mutations submitted to the API scoped to the selected knowledge graph
Code: fetch(`${config.public.apiBaseUrl}/graph/mutations`, ...)
FAIL: Wrong endpoint — 404 on every submission
```

**Scenario: Parent context is preserved** — FAIL for mutations.

The knowledge graph ID (parent context) is never passed into `applyMutations`. Even if the URL were corrected, the `submit(jsonlContent, opCount)` signature in `useMutationSubmission.ts` has no `knowledgeGraphId` parameter to thread through.

### Requirement: Navigation Structure — PASS

Sidebar presents Explore (Query Console, Schema Browser, Graph Explorer, Mutations Console), Data, Connect, Settings. Tests in `default.layout.test.ts` verify order and presence. Implementation in `default.vue` matches spec exactly.

### Requirement: Mutations Console — FAIL (Scenario: Knowledge graph selection missing)

**Scenario: Knowledge graph selection** — FAIL. The spec (lines 245-250) requires:

- A knowledge graph selector displayed before the user can submit
- Selector lists all knowledge graphs the user has `edit` permission on
- No submission possible until a knowledge graph is selected
- Selected knowledge graph used as the target for the mutation submission

None of these are implemented. The `mutations.vue` page has no KG selector UI. The Apply Mutations button is gated only on `submitting || preparing || !editorContent.trim()` — not on `selectedKgId`. No test file `mutations-kg-selector.test.ts` exists. The `mutations-console.test.ts` does not cover this scenario.

**Scenario: Submission** — FAIL (related to above). The spec clause "mutations are submitted to the API scoped to the selected knowledge graph" is not satisfied because no KG ID is selected or passed.

All other Mutations Console scenarios (empty state, JSONL editing, live preview, file upload, submission failure, template insertion, deep-link) are COVERED with tests.

### Requirement: Design Language — FAIL (Scenario: Typography)

**Scenario: Typography** — FAIL.

Spec: "font weights are limited to regular (400), medium (500), and semibold (600)"

Thirteen occurrences of `font-bold` (700) exist across 11 page files:

- `pages/api-keys/index.vue`
- `pages/data-sources/index.vue`
- `pages/graph/explorer.vue`
- `pages/graph/mutations.vue`
- `pages/graph/schema.vue`
- `pages/groups/index.vue`
- `pages/integrate/mcp.vue`
- `pages/knowledge-graphs/index.vue`
- `pages/query/index.vue`
- `pages/tenants/index.vue`
- `pages/workspaces/index.vue`
- `pages/index.vue` (two occurrences)

The existing `design-language.test.ts` guards only `Button` and `Badge` component files; no test scans page files for `font-bold`, so the violation passes CI undetected.

### Requirement: Tenant and Workspace Context — COVERED

Tenant selector present in sidebar (desktop + mobile) with multi-tenant dropdown. Workspace guidance toast fires when entering a tenant with no workspaces. Tests in `default.layout.test.ts` cover badge logic.

### Requirement: Knowledge Graph Creation — COVERED

Tests in `knowledge-graphs.test.ts` cover validation, API call to correct workspace-scoped endpoint, and feedback.

### Requirement: Data Source Connection — COVERED

Tests in `data-sources.test.ts` cover adapter type, connection config, and credential handling (server-side storage assertion).

### Requirement: Ontology Design — COVERED (excluding agent-proposed scenarios which are not yet implemented in this branch)

### Requirement: Sync Monitoring — COVERED

`sync-monitoring-extended.test.ts` and `sync-phase-indicator.test.ts` cover active sync progress and history.

### Requirement: Get Started Querying (MCP Connection) — COVERED

`mcp-integration.test.ts` covers API key inline creation, copy-paste snippet, and secret shown once.

### Requirement: Query Console — COVERED

`query-history.test.ts` and related tests cover query editing, execution, history, and KG context scoping.

### Requirement: Schema Browser — COVERED

`schema-browser.test.ts` covers type listing, type detail, and cross-navigation.

### Requirement: Graph Explorer — COVERED

`graph-explorer.test.ts` covers node search and neighbor exploration.

### Requirement: API Key Management — COVERED

`api-keys.test.ts` covers create, list, revoke, copy-to-clipboard, and mutation feedback.

### Requirement: Workspace Management — COVERED

`workspace-management.test.ts` covers create, member management, copy-to-clipboard, and mutation feedback.

### Requirement: Interaction Principles — COVERED

`interaction-principles.test.ts` and per-page tests cover copy-to-clipboard, mutation feedback, keyboard shortcuts, and focus indicators.

### Requirement: Responsive Design — COVERED

`responsive-design.test.ts` covers desktop and tablet/mobile layout behaviors.

### Requirement: Dark Mode — COVERED

`color-mode.test.ts` covers toggle and persistence.

## Summary of Failures

1. **Backend API Alignment / Mutations Console — Scenario: Knowledge graph selection** (MISSING): No KG selector UI, no `knowledgeGraphId` parameter in `useMutationSubmission.submit()` or `useGraphApi.applyMutations()`, wrong API endpoint URL (`/graph/mutations` instead of `/graph/knowledge-graphs/{id}/mutations`), no test coverage.

2. **Design Language — Scenario: Typography** (PARTIAL): 13 occurrences of `font-bold` (weight 700) across 11 page files violate the spec's cap of semibold (600). No regression test guards page files.