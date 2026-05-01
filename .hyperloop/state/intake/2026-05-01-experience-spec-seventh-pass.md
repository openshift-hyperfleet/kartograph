# Intake: specs/ui/experience.spec.md (seventh pass, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` re-processed at current HEAD
`64e42a1cb`. Spec content is unchanged since
`97bf3eeef007dbfe56dbe4d198ea9283e446a31d`
("chore(spec): require UI alignment to api route"). **No new tasks created.**

All 51 scenarios across 17 requirements remain fully covered by existing tasks.

## Diff from previous pass (sixth pass, commit `64e42a1cb`)

- No spec content changes.
- Additional tasks have shipped since the sixth pass:
  - **task-048** — PR #512 (`7824648dd`): schema browser cross-navigation updated
    to link to ontology editor instead of raw mutations console.
  - **task-049** — PR #513 (`ff72e98e3`): focus-ring tests added + ring-2 → ring-[3px]
    fixes applied to `default.vue`, `mcp.vue`, `tenants/index.vue`.
  - Task file statuses not yet updated by orchestrator.

## Requirement → task coverage map (authoritative)

| # | Requirement | Scenarios | Covered by |
|---|---|---|---|
| 1 | Backend API Alignment | 2 | task-040, task-041 ✓ |
| 2 | Navigation Structure | 3 | task-014 ✓, task-046 ✓, task-047 ✓ |
| 3 | Tenant and Workspace Context | 2 | task-014 ✓, task-046 ✓ |
| 4 | Knowledge Graph Creation | 1 | task-040, task-015 |
| 5 | Data Source Connection | 3 | task-015 |
| 6 | Ontology Design | 5 | task-043 |
| 7 | Sync Monitoring | 4 | task-041 ✓, task-042 ✓, task-044, task-015 |
| 8 | Get Started Querying (MCP) | 3 | task-014 ✓ |
| 9 | Query Console | 4 | task-016 ✓, task-045 |
| 10 | Schema Browser | 3 | task-016 ✓, task-048 ✓ |
| 11 | Graph Explorer | 2 | task-016 ✓ |
| 12 | API Key Management | 3 | task-014 ✓ |
| 13 | Workspace Management | 2 | task-014 ✓ |
| 14 | Design Language | 5 | task-014 ✓ |
| 15 | Interaction Principles | 6 | task-014 ✓, task-016 ✓, task-049 ✓ |
| 16 | Responsive Design | 2 | task-014 ✓ |
| 17 | Dark Mode | 1 | task-014 ✓ |

Legend: ✓ = verified implemented in a merged PR; no ✓ = task queued / not-started.

## Open (not-started) tasks remaining for this spec

| Task | Title | Key dependency |
|---|---|---|
| task-015 | KG management, data sources, sync monitoring — integration UX | task-040, 041, 042 |
| task-040 | Fix KG creation — workspace selector and correct API endpoint | none |
| task-043 | Implement UI — ontology design flow | task-014, task-015 |
| task-044 | Implement UI — sync log viewer | task-014, task-041 |
| task-045 | Query console KG scope selector | task-016 |

Note: task-047, task-048, task-049 appear shipped (PRs #511, #512, #513) but task files
may not yet reflect `status: complete`. Orchestrator will reconcile.

## No new task files created
