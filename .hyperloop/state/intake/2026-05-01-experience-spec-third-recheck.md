# Intake: specs/ui/experience.spec.md (third re-check, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` re-processed at current HEAD
`97bf3eeef007dbfe56dbe4d198ea9283e446a31d`. **No new tasks created.**

All 17 requirements and 51 scenarios are accounted for by existing tasks
(task-014, task-016, task-040 through task-049). Since the previous
re-check, two additional tasks have been shipped:

- **task-046** — home page KG-based redirect and new-user prompt
  (commit `d5caeed8f`, PR #508)
- **task-047** — sync-status badge on Data Sources sidebar nav item
  (commit `4cdc40b38`, PR #511)

The spec itself is unchanged; no new requirements were added.

## Verification: scenario count

Counted 51 scenarios across 17 requirements (not 37 as stated in the
first recheck — the earlier count was understated; this is the correct
figure from the current spec text).

## Requirement → task coverage map

| Requirement | Scenarios | Covered by |
|---|---|---|
| Backend API Alignment | 2 | task-040 ✓, task-041 ✓ |
| Navigation Structure | 3 | task-014 ✓, task-046 ✓, task-047 ✓ |
| Tenant and Workspace Context | 2 | task-014 ✓, task-046 ✓ |
| Knowledge Graph Creation | 1 | task-040 ✓, task-015 |
| Data Source Connection | 3 | task-015 |
| Ontology Design | 5 | task-043 ✓ |
| Sync Monitoring | 4 | task-041 ✓, task-042 ✓, task-044 ✓, task-015 |
| Get Started Querying (MCP) | 3 | task-014 ✓ |
| Query Console | 4 | task-016 ✓, task-045 ✓ |
| Schema Browser | 3 | task-016 ✓, task-048 |
| Graph Explorer | 2 | task-016 ✓ |
| API Key Management | 3 | task-014 ✓ |
| Workspace Management | 2 | task-014 ✓ |
| Design Language | 5 | task-014 ✓ |
| Interaction Principles | 6 | task-014 ✓, task-016 ✓, task-049 |
| Responsive Design | 2 | task-014 ✓ |
| Dark Mode | 1 | task-014 ✓ |

Legend: ✓ = verified implemented; unmarked = task exists and is queued.

## Open (not-started) tasks remaining for this spec

| Task | Title | Key dependency |
|---|---|---|
| task-015 | KG management, data sources, sync monitoring — integration UX | task-040, 041, 042 |
| task-048 | Schema browser cross-navigation — ontology editor link | task-043 |
| task-049 | Fix focus ring: ring-2 → ring-[3px] on custom elements | none |

## Test suite health

All 500 unit tests pass as of this check: `cd src/dev-ui && pnpm test`.

## No new task files created
