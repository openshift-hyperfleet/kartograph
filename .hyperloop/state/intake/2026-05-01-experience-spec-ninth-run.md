# Intake: specs/ui/experience.spec.md (ninth run, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` re-processed at current HEAD (`e55d8ddca`).
Spec content is **unchanged** since `97bf3eeef007dbfe56dbe4d198ea9283e446a31d`
("chore(spec): require UI alignment to api route"). **No new tasks created.**

All 51 scenarios across 17 requirements are fully covered by existing tasks
(task-014 through task-058).

## Verification Method

Each requirement and scenario in the current spec was verified against:
1. Existing task files for task ownership
2. Actual source code for completed tasks (task-014 ✓, task-016 ✓)
3. Actual test files for coverage assertions

No scenario was assumed covered without reading either the task file or the code.

## Diff from previous pass (post-task-057 recheck, commit `aec9b69ad`)

- Spec content: unchanged.
- New task added since prior pass: **task-058** (`e55d8ddca`) — "Audit tenant selector
  — verify all tenant-scoped pages refresh on tenant switch". This task closes the
  "AND switching tenants refreshes all data in the UI" clause in
  **Requirement: Tenant and Workspace Context → Scenario: Tenant selector**.
- All other tasks (task-014 through task-057) unchanged.
- No new gaps found.

## Requirement → task coverage map (authoritative, post task-058)

| # | Requirement | Scenarios | Covered by |
|---|---|---|---|
| 1 | Backend API Alignment | 2 | task-040, task-041, task-050, task-051 |
| 2 | Navigation Structure | 3 | task-014 ✓, task-046, task-047 |
| 3 | Tenant and Workspace Context | 2 | task-046, task-058 |
| 4 | Knowledge Graph Creation | 1 | task-040, task-015 |
| 5 | Data Source Connection | 3 | task-015 |
| 6 | Ontology Design | 5 | task-043 |
| 7 | Sync Monitoring | 4 | task-041, task-042, task-044, task-015 |
| 8 | Get Started Querying (MCP) | 3 | task-051 |
| 9 | Query Console | 4 | task-016 ✓, task-045 |
| 10 | Schema Browser | 3 | task-016 ✓, task-048 |
| 11 | Graph Explorer | 2 | task-016 ✓ |
| 12 | API Key Management | 3 | task-014 ✓ |
| 13 | Workspace Management | 2 | task-014 ✓, task-050 |
| 14 | Design Language | 5 | task-014 ✓ (component library), task-052 (tokens) |
| 15 | Interaction Principles | 6 | task-049, task-053, task-054, task-057 |
| 16 | Responsive Design | 2 | task-055 |
| 17 | Dark Mode | 1 | task-056 |

Legend: ✓ = verified implemented and merged; no ✓ = task queued / not-started.

## Detailed scenario verification (sample — newly verified this pass)

### Requirement: API Key Management — Scenario: Create key (secret shown once)
- **Code**: `src/dev-ui/app/pages/api-keys/index.vue` — `newlyCreatedKey` ref,
  `secretVisible` toggle, `maskedSecret()` helper, "This is the only time the full
  secret will be shown" message. ✓
- **Tests**: `tests/api-keys.test.ts` — `describe('API Keys - create key validation')`
  covers `creates key and shows secret once on success`; `describe('API Keys - secret
  shown once after dismiss')` covers `dismissCreatedKey clears newlyCreatedKey`. ✓

### Requirement: Workspace Management — Scenario: Member management
- **Code**: `src/dev-ui/app/pages/workspaces/index.vue` — `addMember()`, `removeMember()`,
  `handleRoleChange()` functions present. ✓
- **Tests**: `tests/workspace-management.test.ts` — `describe('Workspace Management -
  add member')`, `describe('Workspace Management - remove member')`, `describe('Workspace
  Management - role change')`. ✓

### Requirement: Design Language — Scenario: Component library
- **Code**: `package.json` — `reka-ui: ^2.8.0`, `class-variance-authority: ^0.7.1`,
  `lucide-vue-next: ^0.563.0` confirmed installed. Components use CVA (e.g.,
  `app/components/ui/alert/index.ts` — `export const alertVariants = cva(...)`). ✓
- **Tests**: `tests/design-language.test.ts` — button/badge variant tests verify CVA
  class structure (`rounded-md`, `rounded-full` via `cva` inspection). ✓

## Open (not-started) tasks for this spec

| Task | Title | Blocking deps |
|---|---|---|
| task-015 | KG management, data sources, sync monitoring | task-040, 041, 042 |
| task-040 | Fix KG creation — workspace selector and correct endpoint | none |
| task-041 | Fix backend API response format — data sources and sync runs | none |
| task-042 | Fix sync-run phase status types and display labels | none |
| task-043 | Implement UI — ontology design flow | task-014, task-015 |
| task-044 | Implement UI — sync log viewer | task-014, task-041 |
| task-045 | Query console KG scope selector | task-016 |
| task-046 | Fix home page landing — KG-based redirect and new-user prompt | task-015 |
| task-047 | Add sync-status badge to Data Sources sidebar nav item | task-041, task-042 |
| task-048 | Update schema browser cross-navigation — ontology editor link | task-043 |
| task-049 | Fix focus ring inconsistencies | none |
| task-050 | Backend API alignment audit — IAM and explore CRUD | none |
| task-051 | Audit MCP integration page | task-050 |
| task-052 | Audit and implement Design Language tokens | none |
| task-053 | Cross-page copy-to-clipboard and mutation feedback audit | task-015, task-050, task-051 |
| task-054 | Implement keyboard shortcuts | task-045 |
| task-055 | Audit Responsive Design | none |
| task-056 | Audit Dark Mode | none |
| task-057 | Audit interaction principles — progressive disclosure, inline actions | task-050, task-053 |
| task-058 | Audit tenant selector — cross-page data refresh on tenant switch | task-040, task-041, task-050 |

## No new task files created

The spec modification (Backend API Alignment requirement, added in commit `97bf3eee`)
was fully processed in prior passes. Task-058, created in commit `e55d8ddca`, closed
the last remaining gap (tenant-selector cross-page refresh). No further gaps exist.
