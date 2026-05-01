# Intake Review: UI Experience Spec — 2026-05-01

Spec: `specs/ui/experience.spec.md` (blob `86a2b5c71ec6c6af7ed222eae46139acec3974b3`)

## Decision: No new tasks

All 17 requirements and every scenario in the spec are covered by existing tasks.
The spec's last modification (`97bf3eeef` — added "Backend API Alignment") was
processed when tasks 040–046 were created. Task-046 has since been implemented
(commit `d5caeed8f` on `alpha`).

## Requirement Coverage Map

| Requirement | Scenarios | Tasks |
|---|---|---|
| Backend API Alignment | Resource operations, Parent context | task-041, task-040 |
| Navigation Structure | Primary nav, Default landing, New user landing | task-014 ✓, task-046 |
| Tenant and Workspace Context | Tenant selector, Workspace guidance | task-014 ✓, task-046 |
| Knowledge Graph Creation | Create knowledge graph | task-040, task-015 |
| Data Source Connection | Adapter selection, Config, Credential handling | task-015 |
| Ontology Design | Intent, Proposal, Review, Type editing, Re-extraction warning | task-043 |
| Sync Monitoring | Active progress, History, Logs, Manual trigger | task-042, task-041, task-044, task-015 |
| Get Started Querying (MCP) | API key inline, Copy-paste snippet, Secret once | task-014 ✓ (impl verified) |
| Query Console | Editing, Execution, History, KG context | task-016 ✓, task-045 |
| Schema Browser | Type listing, Type detail, Cross-navigation | task-016 ✓ |
| Graph Explorer | Node search, Neighbor exploration | task-016 ✓ |
| API Key Management | Create, List, Revoke | task-014 ✓ (impl verified) |
| Workspace Management | Create workspace, Member management | task-014 ✓ |
| Design Language | Component library, Color theme, Typography, Border radius, Elevation | task-014 ✓ |
| Interaction Principles | Progressive disclosure, Inline actions, Copy, Mutation feedback, Shortcuts, Focus | task-014 ✓ |
| Responsive Design | Desktop layout, Tablet/mobile layout | task-014 ✓ |
| Dark Mode | Toggle + persistence | task-014 ✓ |

✓ = task is `complete` with merged PR

## Verified Implementation (complete tasks)

### Get Started Querying — MCP Connection (task-014)

All three scenarios verified against `src/dev-ui/app/pages/integrate/mcp.vue`:

- **API key creation inline**: lines 437-482 — when `activeKeys.length === 0` the template
  renders a "No API keys found. Create one to generate connection configs." section with an
  inline "Create API Key" dialog. ✓

- **Copy-paste connection command**: lines 488-594 — config tabs (Claude Code, Cursor,
  Claude Desktop, cURL) each render a `<pre>` block containing the MCP endpoint URL and
  `configSecret` (either the real key or `<YOUR_API_KEY>` placeholder). Each tab has a
  copy button. ✓

- **Secret shown once**: `newlyCreatedKey` is component state (reset to `null` on mount).
  A `tenantVersion` watcher explicitly clears it on tenant switch. The "Copy Key" button
  sets `secretCopied = true`. Once the user navigates away, the component unmounts and the
  secret is gone. ✓

Tests in `src/dev-ui/app/tests/mcp-integration.test.ts` and `api-keys.test.ts` cover all
three scenarios with dedicated describe blocks.

### API Key Management (task-014)

Verified against `src/dev-ui/app/pages/api-keys/index.vue`:

- **Create key**: dialog with name + expiration fields; secret shown in an amber banner on
  success; `dismissCreatedKey()` clears it. ✓
- **List keys**: three separate sections (Active, Expired, Revoked) with status, creation
  date, last used, and expiration columns. ✓
- **Revoke key**: confirmation dialog → `revokeApiKey()` call → key reloaded as revoked. ✓

### Task-046 Implementation (d5caeed8f on alpha)

`src/dev-ui/app/pages/index.vue` updated with:
- KG-based redirect: fetches `/management/knowledge-graphs` on mount; redirects to `/query`
  when `kgCount > 0` (session-guarded via `SESSION_REDIRECT_KEY`). ✓
- Onboarding checklist: "Create a knowledge graph" step at index 1, `done: kgCount > 0`,
  `actionTo: /knowledge-graphs`. ✓
- Workspace guidance: `showWorkspaceGuidanceIfNeeded()` shows a toast once per tenant when
  `workspaceCount === 0`, guarded by a per-tenant localStorage key. ✓

Tests in `src/dev-ui/app/tests/index.test.ts` cover redirect logic, checklist shape,
workspace guidance (shown once, suppressed on repeat).
