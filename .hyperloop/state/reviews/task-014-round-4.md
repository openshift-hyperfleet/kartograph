---
task_id: task-014
round: 4
role: spec-reviewer
verdict: fail
---
Fresh spec alignment review against `specs/ui/experience.spec.md`.

All 42 UI tests pass (`pnpm test` — 3 test files, 42 tests). Three of the four
prior FAILs are fully resolved. One remains PARTIAL.

---

## Requirement Status

| # | Requirement | Status |
|---|---|---|
| 1 | Navigation Structure | COVERED |
| 2 | Tenant and Workspace Context | COVERED |
| 3 | Knowledge Graph Creation | COVERED (prior FAIL 1 resolved) |
| 4 | Data Source Connection | COVERED |
| 5 | Ontology Design | COVERED (prior FAIL 2 resolved) |
| 6 | Sync Monitoring | COVERED (prior FAIL 3 resolved) |
| 7 | Get Started Querying (MCP) | COVERED |
| 8 | Query Console — KG context selector | **PARTIAL** (prior FAIL 4 unresolved) |
| 9 | Schema Browser | COVERED |
| 10 | Graph Explorer | COVERED |
| 11 | API Key Management | COVERED |
| 12 | Workspace Management | COVERED |
| 13 | Design Language | COVERED |
| 14 | Interaction Principles | COVERED |
| 15 | Responsive Design | COVERED |
| 16 | Dark Mode | COVERED |

---

## FAIL — Requirement 8: Query Console KG Context Selector Not Wired to Execution

**Spec (SHALL):** "THEN the user can optionally select a specific knowledge graph to
scope queries AND when unscoped, queries span all knowledge graphs the user can access
in the tenant"

### What is implemented

`src/dev-ui/app/pages/query/index.vue`:
- `loadKnowledgeGraphs()` calls `GET /management/knowledge-graphs` and populates
  `knowledgeGraphs` ✓
- Called on `onMounted` (line 354) and in `watch(tenantVersion, ...)` (line 374) ✓
- Selector UI bound to `selectedKgId`, renders KG options, shows Scoped/Unscoped badge ✓
- `kgScopeLabel` computed returns "All knowledge graphs" or the selected name ✓

### What is missing

**`useQueryApi.ts`, lines 33–37:** `queryGraph(cypher, timeoutSeconds?, maxRows?)` —
no `knowledgeGraphId` parameter exists.

**`query/index.vue`, lines 185–189:**
```typescript
const res = await queryGraph(
  cypherQuery,
  Number(timeout.value),
  Number(maxRows.value),
  // selectedKgId.value is NOT passed here
)
```

`selectedKgId.value` is never forwarded to the MCP tool call. The query always runs
without a KG scope, regardless of what the user has selected. The selector UI is fully
functional — it populates and reacts — but selecting a knowledge graph has no effect
on what data is queried.

**Test gap:** The test at `knowledge-graphs.test.ts` lines 446–468 exercises a
standalone `executeQuery` stub that does pass the KG ID. However, this stub does not
reflect the actual component: the real `executeQuery()` calls `queryGraph()` with
three arguments, not four. The test demonstrates the intended behaviour but does not
verify that the component actually implements it.

### Required fix

1. Add a `knowledgeGraphId?: string` parameter to `queryGraph()` in `useQueryApi.ts`.
   When provided, include it as `knowledge_graph_id` in the MCP tool `arguments`
   object (line 53).

2. In `query/index.vue`, pass `selectedKgId.value || undefined` as the fourth
   argument to `queryGraph()` inside `executeQuery()`.

3. Replace or supplement the test stub in `knowledge-graphs.test.ts` lines 446–468
   with an assertion that verifies the actual composable is called with the correct
   `knowledge_graph_id` argument (not a standalone copy of the logic).