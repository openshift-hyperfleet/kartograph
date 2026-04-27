---
task_id: audit-specs/ui/experience.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Worker Result — Spec Alignment Audit: specs/ui/experience.spec.md

Auditor: spec-alignment-reviewer
Date: 2026-04-27
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6

---

### Summary

The UI codebase (`src/dev-ui/`) implements the vast majority of the spec faithfully.
Navigation, design language, interaction patterns, dark mode, responsive layout, API key
management, MCP integration, query console, schema browser, graph explorer, sync monitoring,
and workspace management all align well with the spec.

**Three concrete gaps** were found under the **Ontology Design** requirement. Verdict: **FAIL**.

---

### Requirement-by-Requirement Findings

#### Navigation Structure — PASS
`src/dev-ui/app/layouts/default.vue` sidebar correctly groups Explore, Data, Connect, and
Settings with the exact items listed in the spec. Responsive collapse to sheet overlay on
mobile/tablet is implemented.

#### Tenant and Workspace Context — PASS
Tenant selector with dropdown (multi-tenant) and static display (single-tenant) implemented
in `default.vue` lines 309–449. `useTenant()` composable refreshes all data on tenant
switch. New-user workspace guidance toast fires when no workspaces exist.

#### Knowledge Graph Creation — PASS
`src/dev-ui/app/pages/knowledge-graphs/index.vue`: dialog-based create flow with name +
description fields; on success, toast includes "Add data source" action link.

#### Data Source Connection — PASS (partial concern noted below)
`src/dev-ui/app/pages/data-sources/index.vue`: 4-step wizard (adapter selection →
connection config → intent description → ontology review/approval). Adapter-specific fields
shown per selection. Name inferred from repo URL (`watch(connRepoUrl, …)` line 271).
Credentials sent to API in `createDataSource()` (line 484) and NOT stored in component
state after the wizard closes.

#### Ontology Design — FAIL (3 gaps)

**Gap 1 — Agent-proposed ontology is entirely simulated**
`src/dev-ui/app/pages/data-sources/index.vue`, lines 358–373:
```js
// Simulate a lightweight scan of the data source (1.5s) followed by AI proposal
await new Promise<void>((resolve) => setTimeout(resolve, 1500))
proposedNodes.value = GITHUB_PROPOSAL_NODES.map(toProposedNode)
proposedEdges.value = GITHUB_PROPOSAL_EDGES.map(toProposedEdge)
```
No backend API call is made. The "scan" is a 1.5-second sleep; the "AI-proposed" ontology
is hardcoded constant data (lines 175–241). The spec requires:
> "the system performs a lightweight scan of the data source AND an AI agent explores the
> scanned data and proposes an ontology (node types, edge types, properties) AND the
> proposed ontology is presented to the user for review"

The presentation and review flow are present, but neither the scan nor the AI proposal
happen — the data is static.

**Gap 2 — Edge type editing omits required/optional property fields**
`src/dev-ui/app/pages/data-sources/index.vue`, lines 1371–1390 (edge edit form):
The form renders only Label and Description inputs. The `saveEditEdge()` function (lines
412–418) reads `editRequired`/`editOptional` to persist properties, but those fields are
never shown to the user. The spec requires:
> "they can modify the label, description, required properties, and optional properties"
for any type. Node types satisfy this (lines 1319–1348); edge types do not.

**Gap 3 — No mechanism to add new relationship types**
Neither `addEdge` nor `addNode` functions exist. The ontology editor (lines 1282–1399)
allows editing and removing existing types (via `removeNode`/`removeEdge`) but provides
no button or control to add a new node type or edge type. The spec requires:
> "they can add or remove relationship types"
Only removal is supported.

#### Sync Monitoring — PASS
Active sync progress (status phases), sync history with timestamps/duration, sync logs via
sheet panel, and manual sync trigger are all implemented.

#### Get Started Querying (MCP Connection) — PASS
`src/dev-ui/app/pages/integrate/mcp.vue`: copy-paste config snippets for Claude/Cursor/
Desktop/curl, endpoint URL with copy button, inline API key creation, secret shown once
with copy option.

#### Query Console — PASS
CodeMirror integration with Cypher syntax, autocomplete, linting; Ctrl/Cmd+Enter keyboard
shortcut; results table with execution time and row count; query history via localStorage;
knowledge graph scoping selector.

#### Schema Browser — PASS
Tab-based node/edge listing with search/filter, expandable type detail showing description
and required/optional properties, virtual scrolling, cross-navigation hooks present.

#### Graph Explorer — PASS
Node search by type/name/slug, neighbor traversal with direction-aware edges, card display
with expandable properties.

#### API Key Management — PASS
Create with name/expiration, secret shown exactly once with copy button, list with
status/dates/last-used, revoke with confirmation dialog.

#### Workspace Management — PASS
Create workspace dialog; member add/remove/role-change implemented in
`src/dev-ui/app/pages/workspaces/index.vue`.

#### Design Language — PASS
- shadcn/vue (Reka UI) primitives throughout `src/dev-ui/app/components/ui/`
- CVA variants in `button/index.ts` lines 6–38
- Lucide Vue Next icons used globally
- Primary color `oklch(0.5768 0.2469 29.23)` light / `oklch(0.6857 0.1560 17.57)` dark
  confirmed in `src/dev-ui/app/assets/css/main.css` lines 52, 86
- 5-color chart palette (lines 64–68 light, 98–102 dark)
- Base radius `0.625rem` (line 45); cards `rounded-xl`, buttons/inputs `rounded-md`
- `shadow-sm` / `shadow-xs` elevation confirmed
- Typography: section headers `text-[11px] font-semibold uppercase tracking-wider`,
  body `text-sm`

#### Interaction Principles — PASS
`CopyableText.vue` provides copy-to-clipboard with toast. Mutation toasts confirmed
on all write pages. Focus ring `focus-visible:ring-ring/50 focus-visible:ring-[3px]`
in `button/index.ts` line 7. Progressive disclosure (expandable schema, collapsible
sidebar). Inline editing for workspace/group names.

#### Responsive Design — PASS
Desktop: sidebar `hidden md:flex`, collapsible; multi-column stats cards. Mobile: sidebar
Sheet overlay, single-column layouts, mobile-specific breadcrumb/tenant controls.

#### Dark Mode — PASS
`useColorMode.ts`: toggle, localStorage persistence (`kartograph-color-mode`), system
preference fallback, `dark` class on document root. Sun/Moon icon toggle in header with
tooltip.

---

### Gaps Requiring Remediation

| # | Requirement | Scenario | File | Lines | Description |
|---|-------------|----------|------|-------|-------------|
| 1 | Ontology Design | Agent-proposed ontology | `src/dev-ui/app/pages/data-sources/index.vue` | 358–373 | `beginOntologyProposal()` is a 1.5s sleep with hardcoded data; no real backend scan or AI agent call |
| 2 | Ontology Design | Individual type editing | `src/dev-ui/app/pages/data-sources/index.vue` | 1371–1390 | Edge type edit form missing required/optional property inputs (present for nodes at 1319–1348) |
| 3 | Ontology Design | Individual type editing | `src/dev-ui/app/pages/data-sources/index.vue` | 1282–1399 | No "add new node type" or "add new edge type" controls in the ontology editor |