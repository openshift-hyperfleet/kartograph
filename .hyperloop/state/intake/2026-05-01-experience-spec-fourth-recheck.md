# Intake: specs/ui/experience.spec.md (fourth re-check, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` re-processed at current HEAD
`63d71febf554cbb6a254c6cd691a2fd5795c7b37`. **No new tasks created.**

The spec file is unchanged since `97bf3eeef007dbfe56dbe4d198ea9283e446a31d`
("chore(spec): require UI alignment to api route"). The only substantive change
from the original spec (at `85d49a379a52479b33f9b39994d76795066899a6`, when
task-014 was authored) was the addition of the **Backend API Alignment**
requirement — two scenarios that were captured by task-040 and task-041.

All 51 scenarios across 17 requirements are accounted for by existing tasks.
No new scenarios, no changed GIVEN/WHEN/THEN conditions, no new requirements
have been added since the third re-check.

## Diff from previous intake pass

- No spec changes since third re-check (commit `63d71febf`).
- Two tasks that were listed as `not-started` in the third recheck have
  since shipped per their PR references:
  - **task-046** — PR #508 (home page KG-based redirect)
  - **task-047** — PR #511 (sync-status badge on Data Sources sidebar nav)
  - Task status files may not reflect this yet; orchestrator will reconcile.

## Requirement → task coverage map (authoritative)

| # | Requirement | Scenarios | Covered by |
|---|---|---|---|
| 1 | Backend API Alignment | 2 | task-040, task-041 |
| 2 | Navigation Structure | 3 | task-014 ✓, task-046, task-047 |
| 3 | Tenant and Workspace Context | 2 | task-014 ✓, task-046 |
| 4 | Knowledge Graph Creation | 1 | task-040, task-015 |
| 5 | Data Source Connection | 3 | task-015 |
| 6 | Ontology Design | 5 | task-043 |
| 7 | Sync Monitoring | 4 | task-041, task-042, task-044, task-015 |
| 8 | Get Started Querying (MCP) | 3 | task-014 ✓ |
| 9 | Query Console | 4 | task-016 ✓, task-045 |
| 10 | Schema Browser | 3 | task-016 ✓, task-048 |
| 11 | Graph Explorer | 2 | task-016 ✓ |
| 12 | API Key Management | 3 | task-014 ✓ |
| 13 | Workspace Management | 2 | task-014 ✓ |
| 14 | Design Language | 5 | task-014 ✓ |
| 15 | Interaction Principles | 6 | task-014 ✓, task-016 ✓, task-049 |
| 16 | Responsive Design | 2 | task-014 ✓ |
| 17 | Dark Mode | 1 | task-014 ✓ |

Legend: ✓ = verified implemented in a merged PR; no ✓ = task queued / not-started.

## Open (not-started) tasks remaining for this spec

| Task | Title | Key dependency |
|---|---|---|
| task-015 | KG management, data sources, sync monitoring — integration UX | task-040, 041, 042 |
| task-040 | Fix KG creation — workspace selector and correct API endpoint | none |
| task-041 | Fix backend API response format — data sources and sync runs | none |
| task-042 | Fix sync-run phase status types and display labels | none |
| task-043 | Implement UI — ontology design flow | task-014, task-015 |
| task-044 | Implement UI — sync log viewer | task-014, task-041 |
| task-045 | Query console KG scope selector | task-016 |
| task-048 | Schema browser cross-navigation — ontology editor link | task-043 |
| task-049 | Fix focus ring: ring-2 → ring-[3px] on custom elements | none |

Note: task-046 and task-047 appear shipped (PRs #508, #511) but their task
files may not have been updated to `status: complete` by the orchestrator yet.

## No new task files created
