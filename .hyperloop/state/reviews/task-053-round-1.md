---
task_id: task-053
round: 1
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — UI/UX Experience Spec

All 723 unit tests pass (21 test files, no failures).

### Requirement Status

**Backend API Alignment** — COVERED
- Tests in workspace-management.test.ts, api-keys.test.ts, mcp-integration.test.ts, knowledge-graphs.test.ts, data-sources.test.ts verify exact endpoint URLs (GET/POST/PATCH/DELETE) and request/response shapes.
- Parent context (workspace_id, knowledge_graph_id) is tested to be present in request bodies.

**Navigation Structure** — PARTIAL
- Primary navigation: the sidebar implementation at `/src/dev-ui/app/layouts/default.vue` (lines 247–252) includes Query Console, Schema Browser, and Graph Explorer in the Explore section — but omits "Mutations Console".
- The spec defines the Explore section as: "Query Console, Schema Browser, Graph Explorer, Mutations Console".
- The Mutations Console page exists at `/src/dev-ui/app/pages/graph/mutations.vue` and is fully implemented, but it has no sidebar nav entry.
- The nav structure test in `interaction-principles.test.ts` (lines 252–326) only checks for Query Console, Schema Browser, Graph Explorer — it does NOT assert that "Mutations Console" is present in the Explore nav section. This means the omission is untested.
- NOTE: The spec has a duplicated "Explore" bullet (the identical line appears twice). This may be an authoring error, but the spec text is unambiguous that Mutations Console belongs in Explore.
- Default landing: COVERED (index.test.ts)
- New user landing: COVERED (index.test.ts, interaction-principles.test.ts)

**Tenant and Workspace Context** — COVERED
- Tenant selector and data refresh on tenant switch tested in interaction-principles.test.ts.
- Workspace guidance tested in index.test.ts.

**Knowledge Graph Creation** — COVERED
- knowledge-graphs.test.ts covers name validation, workspace context, API call, and "Add Data Source" prompt after creation.

**Data Source Connection** — COVERED
- data-sources.test.ts covers adapter type selection, connection configuration, credential (token) handling, and name inference from URL.

**Ontology Design** — COVERED
- data-sources.test.ts covers intent description, individual type editing (label, description, required/optional properties, add/remove), ontology change after extraction (confirmation gate).
- Agent-proposed ontology review/approval flows are tested at the logic layer (ontology editor dialogs).

**Sync Monitoring** — COVERED
- sync-monitoring-extended.test.ts covers active sync progress (phase labels), sync history (status, timestamps, duration), manual sync trigger, and sync logs.
- data-sources.test.ts covers sync logs API call and view logs toggle.

**Get Started Querying (MCP Connection)** — COVERED
- mcp-integration.test.ts covers inline API key creation prompt, copy-paste connection snippet (Claude Code and Cursor formats), and secret shown once/dismiss pattern.

**Query Console** — COVERED
- query-history.test.ts covers Cypher syntax highlighting (lang-cypher LanguageSupport tested), autocomplete (cypherAutocomplete tested), linting (ageCypherLinter tested), query execution with execution time and row count, query history (add, deduplicate, cap at 20, persist), KG context selector.

**Schema Browser** — COVERED
- schema-browser.test.ts covers type listing with search/filtering, type detail (required/optional properties), cross-navigation (query console, graph explorer, ontology editor).

**Graph Explorer** — COVERED
- graph-explorer.test.ts covers node search by type/name/slug, neighbor exploration with edge labels and direction, exploration trail/breadcrumb.

**Mutations Console** — PARTIAL
- The page (`/src/dev-ui/app/pages/graph/mutations.vue`) is fully implemented with JSONL editing, live preview, file upload, templates, submission with floating progress indicator, keyboard shortcuts, deep-link support.
- However, there are NO test scenarios in any test file specifically for the Mutations Console page behavior (empty state, JSONL editing, live preview, file upload, submission, failure, template insertion, deep-link).
- The schema-browser.test.ts references `/graph/mutations` only to assert the schema browser does NOT navigate there.

**API Key Management** — COVERED
- api-keys.test.ts covers create key (validation, secret shown once), list keys (active/expired/revoked status), revoke key.

**Workspace Management** — COVERED
- workspace-management.test.ts covers create workspace, member management (add, remove, role change).

**Design Language** — COVERED
- design-language.test.ts and design-language-extended.test.ts cover color theme (OKLCH), typography (text-sm body, text-[11px] headers, tracking-wider), border radius (base 0.625rem, cards rounded-xl, buttons/inputs rounded-md, badges rounded-full), elevation (cards shadow-sm, buttons shadow-xs).

**Interaction Principles** — COVERED
- interaction-principles.test.ts covers copy-to-clipboard, mutation feedback, progressive disclosure, inline actions.
- Copy-to-clipboard is additionally covered per-resource in workspace-management.test.ts, api-keys.test.ts, knowledge-graphs.test.ts, data-sources.test.ts, groups.test.ts, tenants.test.ts.
- Keyboard shortcuts (Ctrl/Cmd+Enter): covered in query-history.test.ts.
- Focus indicators: covered in focus-ring.test.ts.

**Responsive Design** — COVERED
- responsive-design.test.ts covers desktop layout (sidebar hidden md:flex, collapsible, transition), tablet/mobile layout (Sheet overlay, route watcher closes mobile sheet), sidebar localStorage persistence.

**Dark Mode** — COVERED
- color-mode.test.ts covers toggle, localStorage persistence, system preference fallback, CSS class application.
- dark-mode toggle in header verified in color-mode.test.ts (reads layout file).

### Specific Failures

1. **Navigation Structure — Explore section missing "Mutations Console" nav item**
   - Spec: "Explore — Query Console, Schema Browser, Graph Explorer, Mutations Console"
   - Code: `default.vue` navSections Explore items = [Query Console, Schema Browser, Graph Explorer] — Mutations Console is absent.
   - Test gap: `interaction-principles.test.ts` navSections test does not assert Mutations Console presence.

2. **Mutations Console — no unit tests for page scenarios**
   - Spec defines 8 scenarios: Empty state, JSONL editing, Live preview, File upload, Submission, Submission failure, Template insertion, Deep-link.
   - Code: `pages/graph/mutations.vue` is fully implemented.
   - Tests: zero test coverage for any Mutations Console scenario. No test file exercises mutations.vue logic.

### Memory Update

2026-05-01 | UI experience.spec.md | FAIL | Two misalignments
- Pattern: Mutations Console exists as a page but is absent from the sidebar nav (Explore section). The spec clearly lists it under Explore.
- Pattern: No test file covers the Mutations Console page scenarios despite the spec defining 8 explicit scenarios.
- Action: Check nav sections computed in default.vue for missing items; search for test files covering mutations.vue page logic.
- Context: All other 721 tests pass. The workspace-management.test.ts known rebase conflict resolved cleanly — test file runs without issues.