# Intake: specs/ui/experience.spec.md (modified) — 2026-05-02 (post task-076 merge)

**Spec blob SHA:** `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Context

Triggered after task-076 merged to `origin/alpha` (commit `a26222bb4`, PR #540).
The orchestrator detected `experience.spec.md` as "(modified)" because the last formal
intake commit (`b69aedef9`) used blob SHA `14b2efabc5d0910e59494fd9b111b00c8a4383b3`.
The current blob SHA (`e77913c2c`) has now been processed across three passes today.

## Result

**No new tasks required.** The spec is fully covered by tasks 014–076.

## What Changed Since Last Formal Intake

The spec changed from `14b2efabc` → `e77913c2c` via commit `e3d22bccf`, which added:

1. **Mutations Console — Scenario: Knowledge graph selection** (new scenario)
2. **Mutations Console — Scenario: Submission** (modified to require KG selection)

These changes were addressed by tasks 065, 074, and 076, all of which have been
implemented and merged to `origin/alpha`:

| Task | PR | Implementation Commit |
|---|---|---|
| task-065 | — | `fab25ee15` (workspace + KG selector, part of PR #538 scope) |
| task-074 | #538 | `fab25ee15` feat(ui): add workspace selector to Mutations Console |
| task-076 | #540 | `a26222bb4` test(ui): verify permission=edit query param |

## Implementation Verified

Spot-check of `src/dev-ui/app/pages/graph/mutations.vue` confirms:
- `selectedWorkspaceId` ref (line 112) — workspace selector state ✓
- `selectedKnowledgeGraphId` ref (line 137) — KG selector state ✓
- `permission: 'edit'` in KG list API call (line 150) — edit-only filter ✓
- `workspace_id: selectedWorkspaceId.value` in KG list API call (line 150) ✓
- KG selector disabled when no workspace selected (line 841) ✓
- `canSubmitMutations({ selectedWorkspaceId, selectedKnowledgeGraphId, ... })` gate (line 341) ✓

All "Knowledge graph selection" scenario clauses are implemented and tested:

| Scenario clause | Covered by |
|---|---|
| selector displayed before submit | task-065 (isSubmitDisabled gating test) |
| lists KGs with `edit` permission | task-076 ✓ merged |
| within the current workspace | task-074 ✓ merged |
| no submission until KG selected | task-065 (isSubmitDisabled empty-KG case) |
| selected KG is submission target | task-065 (URL includes KG ID in path) |

## Conclusion

No new task files created. All 18 requirements and 59 scenarios in
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`
are covered by existing tasks 014–076. See the full coverage map in
`2026-05-02-experience-spec-final-recheck.md`.
