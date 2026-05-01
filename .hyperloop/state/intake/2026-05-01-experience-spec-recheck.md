# Intake: specs/ui/experience.spec.md (re-check, 2026-05-01)

## Summary

Spec `specs/ui/experience.spec.md` was re-processed at its current version
`97bf3eeef007dbfe56dbe4d198ea9283e446a31d`. No new tasks were created — every
requirement and scenario is covered by existing tasks.

## Verification

The spec was last modified in commit `97bf3eeef` (chore(spec): require UI alignment to api route),
which added the **Backend API Alignment** requirement (two scenarios). Tasks
`task-040` through `task-049` were created from that version and remain
comprehensive. The spec has not changed since.

### Requirement-to-task coverage map

| Requirement | Scenarios | Covered by |
|---|---|---|
| Backend API Alignment | Resource operations end-to-end | task-015 (integration validation) |
| Backend API Alignment | Parent context preserved | task-040 (KG endpoint bug fix) |
| Navigation Structure | Primary navigation | task-014 ✅ complete |
| Navigation Structure | Default landing (returning user) | task-046 |
| Navigation Structure | New user landing | task-046 |
| Tenant and Workspace Context | Tenant selector | task-014 ✅ complete |
| Tenant and Workspace Context | Workspace guidance | task-014 ✅ complete (WORKSPACE_GUIDANCE_KEY toast in index.vue) |
| Knowledge Graph Creation | Create knowledge graph | task-040 (adds workspace selector, fixes endpoint) |
| Data Source Connection | Adapter type selection | task-015 (wizard exists in data-sources/index.vue) |
| Data Source Connection | Connection configuration | task-015 |
| Data Source Connection | Credential handling | task-015 |
| Ontology Design | Intent description | task-043 |
| Ontology Design | Agent-proposed ontology | task-043 |
| Ontology Design | Ontology review and approval | task-043 |
| Ontology Design | Individual type editing | task-043 |
| Ontology Design | Ontology change after extraction | task-043 |
| Sync Monitoring | Active sync progress | task-015 + task-042 (phase status fix) |
| Sync Monitoring | Sync history | task-015 + task-041 (response format fix) |
| Sync Monitoring | Sync logs | task-044 |
| Sync Monitoring | Manual sync trigger | task-015 |
| MCP Connection | API key creation inline | task-014 ✅ complete |
| MCP Connection | Copy-paste connection command | task-014 ✅ complete |
| MCP Connection | Secret shown once | task-014 ✅ complete |
| Query Console | Query editing (syntax, autocomplete) | task-016 ✅ complete |
| Query Console | Query execution (Ctrl/Cmd+Enter) | task-016 ✅ complete |
| Query Console | Query history | task-016 ✅ complete |
| Query Console | Knowledge graph context (scope) | task-045 |
| Schema Browser | Type listing | task-016 ✅ complete |
| Schema Browser | Type detail | task-016 ✅ complete |
| Schema Browser | Cross-navigation | task-048 (adds ontology editor link) |
| Graph Explorer | Node search | task-016 ✅ complete |
| Graph Explorer | Neighbor exploration | task-016 ✅ complete |
| API Key Management | Create key | task-014 ✅ complete |
| API Key Management | List keys | task-014 ✅ complete |
| API Key Management | Revoke key | task-014 ✅ complete |
| Workspace Management | Create workspace | task-014 ✅ complete |
| Workspace Management | Member management | task-014 ✅ complete |
| Design Language | Component library (shadcn/vue, CVA) | task-014 ✅ complete |
| Design Language | Color theme (OKLCH) | task-014 ✅ complete |
| Design Language | Typography | task-014 ✅ complete |
| Design Language | Border radius | task-014 ✅ complete |
| Design Language | Elevation | task-014 ✅ complete |
| Interaction Principles | Progressive disclosure | task-014 ✅ complete |
| Interaction Principles | Inline actions over navigation | task-014 ✅ complete |
| Interaction Principles | Copy-to-clipboard | task-014 ✅ complete |
| Interaction Principles | Mutation feedback (toast) | task-014 ✅ complete |
| Interaction Principles | Keyboard shortcuts | task-014 ✅ complete |
| Interaction Principles | Focus indicators (3px ring) | task-049 (fixes ring-2 → ring-[3px]) |
| Responsive Design | Desktop layout | task-014 ✅ complete |
| Responsive Design | Tablet/mobile layout | task-014 ✅ complete |
| Dark Mode | Toggle (persisted) | task-014 ✅ complete |

## Conclusion

**No new tasks created.** All 17 requirements and 37 scenarios are tracked.
The data source wizard (adapter selection, connection config, credential handling)
is implemented in `src/dev-ui/app/pages/data-sources/index.vue` — task-015
serves as the end-to-end integration validation once the prerequisite bug-fix
tasks (040, 041, 042) are complete.
