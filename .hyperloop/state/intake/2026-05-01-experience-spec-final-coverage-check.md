# Intake: specs/ui/experience.spec.md (modified) — 2026-05-01

**Spec blob SHA:** `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Summary

Processed `specs/ui/experience.spec.md` against current task list (task-001 through
task-065). Performed line-by-line verification of every requirement and scenario against
existing tasks.

## Spec Changes vs. Prior Version (`14b2efabc5d0910e59494fd9b111b00c8a4383b3`)

The diff introduced two additions to the **Mutations Console** requirement:

1. **New — Scenario: Knowledge graph selection**
   > GIVEN the mutations console
   > THEN a knowledge graph selector is displayed before the user can submit
   > AND the selector lists all knowledge graphs the user has `edit` permission on within the current workspace
   > AND no submission is possible until a knowledge graph is selected
   > AND the selected knowledge graph is used as the target for the mutation submission

2. **Updated — Scenario: Submission** (two clauses modified)
   > GIVEN valid mutations in the editor **and a knowledge graph selected**
   > ...
   > THEN the mutations are submitted to the API **scoped to the selected knowledge graph**...

## Coverage Verdict

**No new tasks required.**

Both changes are fully covered by **task-065** ("Mutations Console — knowledge graph
selector and scoped API submission"), which was committed at `53845ac55` with
`spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"`.

task-065 addresses:
- KG selector UI in `pages/graph/mutations.vue`
- API URL fix: `/graph/mutations` → `/graph/knowledge-graphs/{id}/mutations`
- Submit button gating on KG selection (disabled until a KG is chosen)
- `Ctrl/Cmd+Enter` blocked when no KG selected
- KG ID threaded through `useMutationSubmission.submit()` to `useGraphApi.applyMutations()`
- Tenant-switch clears selection and reloads KG list

## Full Requirement Coverage Map (current spec)

| Requirement | Scenarios | Covered By |
|---|---|---|
| Backend API Alignment | Resource ops end-to-end | task-050, task-040, task-041, task-065 |
| Backend API Alignment | Parent context preserved | task-040, task-050, task-065 |
| Navigation Structure | Primary nav grouping | task-059 |
| Navigation Structure | Default landing | task-046 |
| Navigation Structure | New user landing | task-046 |
| Tenant & Workspace Context | Tenant selector | task-058 |
| Tenant & Workspace Context | Workspace guidance | task-062 |
| Knowledge Graph Creation | Create KG | task-040 |
| Data Source Connection | Adapter selection | task-015, task-043 |
| Data Source Connection | Connection config | task-015, task-043 |
| Data Source Connection | Credential handling | task-015, task-043 |
| Ontology Design | Intent description | task-043 |
| Ontology Design | Agent-proposed ontology | task-043 |
| Ontology Design | Ontology review/approval | task-043 |
| Ontology Design | Individual type editing | task-043, task-063 |
| Ontology Design | Change after extraction | task-043 |
| Sync Monitoring | Active sync progress | task-041, task-064 |
| Sync Monitoring | Sync history | task-041 |
| Sync Monitoring | Sync logs | task-044 |
| Sync Monitoring | Manual sync trigger | task-041 |
| Get Started Querying | API key creation inline | task-051 |
| Get Started Querying | Copy-paste snippet | task-051 |
| Get Started Querying | Secret shown once | task-051 |
| Query Console | Query editing | task-016 (complete) |
| Query Console | Query execution | task-016 (complete) |
| Query Console | Query history | task-016 (complete) |
| Query Console | KG context | task-045 |
| Schema Browser | Type listing | task-016 (complete) |
| Schema Browser | Type detail | task-016 (complete) |
| Schema Browser | Cross-navigation | task-048 |
| Graph Explorer | Node search | task-016 (complete), task-050 |
| Graph Explorer | Neighbor exploration | task-016 (complete), task-050 |
| Mutations Console | Empty state | task-060 |
| Mutations Console | JSONL editing | task-060 |
| Mutations Console | Live preview | task-060 |
| Mutations Console | File upload | task-060 |
| Mutations Console | **Knowledge graph selection** | **task-065** ← spec addition |
| Mutations Console | Submission | task-061, **task-065** ← spec update |
| Mutations Console | Submission failure | task-061 |
| Mutations Console | Template insertion | task-060 |
| Mutations Console | Deep-link | task-060 |
| API Key Management | Create key | task-016 (complete), task-050 |
| API Key Management | List keys | task-050 |
| API Key Management | Revoke key | task-050 |
| Workspace Management | Create workspace | task-050 |
| Workspace Management | Member management | task-050 |
| Design Language | Component library | task-052 |
| Design Language | Color theme | task-052 |
| Design Language | Typography | task-052 |
| Design Language | Border radius | task-052 |
| Design Language | Elevation | task-052 |
| Interaction Principles | Progressive disclosure | task-057 |
| Interaction Principles | Inline actions | task-057 |
| Interaction Principles | Copy-to-clipboard | task-053 |
| Interaction Principles | Mutation feedback | task-053 |
| Interaction Principles | Keyboard shortcuts | task-054 |
| Interaction Principles | Focus indicators | task-049 |
| Responsive Design | Desktop layout | task-055 |
| Responsive Design | Tablet/mobile layout | task-055 |
| Dark Mode | Toggle | task-056 |
