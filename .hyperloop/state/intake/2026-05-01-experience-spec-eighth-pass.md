# Intake: specs/ui/experience.spec.md (eighth pass, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` re-processed at current HEAD
`5dc3ff7a8`. Spec content is unchanged since
`97bf3eeef007dbfe56dbe4d198ea9283e446a31d`
("chore(spec): require UI alignment to api route"). **No new tasks created.**

All 51 scenarios across 17 requirements remain fully covered by existing tasks.

## Diff from previous pass (seventh pass, commit `5dc3ff7a8`)

- No spec content changes.
- No new PRs merged since the seventh pass (seventh pass is the current HEAD).
- Task coverage map is identical to the seventh pass.

## Requirement → task coverage map (authoritative)

| # | Requirement | Scenarios | Covered by |
|---|---|---|---|
| 1 | Backend API Alignment | 2 | task-040, task-041 |
| 2 | Navigation Structure | 3 | task-014 ✓, task-046, task-047 ✓ |
| 3 | Tenant and Workspace Context | 2 | task-014 ✓, task-046 |
| 4 | Knowledge Graph Creation | 1 | task-040, task-015 |
| 5 | Data Source Connection | 3 | task-015 |
| 6 | Ontology Design | 5 | task-043 |
| 7 | Sync Monitoring | 4 | task-041, task-042, task-044, task-015 |
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
| task-041 | Fix backend API response format — data sources and sync runs | none |
| task-042 | Fix sync-run phase status types and display labels in UI | none |
| task-043 | Implement UI — ontology design flow | task-014, task-015 |
| task-044 | Implement UI — sync log viewer | task-014, task-041 |
| task-045 | Query console KG scope selector | task-016 |
| task-046 | Fix home page landing — KG-based redirect and new-user KG creation prompt | task-015 |

Note: task-047, task-048, task-049 were shipped in PRs #511, #512, #513 but task file
status fields may not yet reflect `status: complete`. Orchestrator will reconcile.

## No new task files created
