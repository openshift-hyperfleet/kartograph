---
task_id: task-141
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — UI Experience Spec

### Test Run Summary
- Test files: 53 total, 5 failed, 48 passed
- Tests: 2493 total, 16 failed, 2477 passed

---

### FAIL: Requirement — Query Console / Scenario: Knowledge graph context

**Spec requirement:**
> GIVEN a query console, THEN the user can optionally select a specific knowledge graph to scope queries AND when unscoped, queries span all knowledge graphs the user can access in the tenant

**Implementation location:** `src/dev-ui/app/pages/query/index.vue`

**Root cause:** The KG scope selector is implemented with `'__all__'` as the sentinel for the unscoped state, but the tests across 5 files all verify the spec-required pattern of using `''` (empty string) as the sentinel with an `|| undefined` gate.

**Specific code deviations from the tested spec patterns:**

1. `selectedKgId = ref('__all__')` — tests require `selectedKgId = ref('')`
   - Code line 73: `const selectedKgId = ref('__all__')`

2. `value="__all__"` on the unscoped SelectItem — tests require `value=""`
   - Code line 490: `<SelectItem value="__all__">All knowledge graphs</SelectItem>`

3. `v-if="selectedKgId !== '__all__'"` for the Scoped badge — tests require `v-if="selectedKgId"`
   - Code line 500: `<Badge v-if="selectedKgId !== '__all__'" ...>Scoped</Badge>`

4. `selectedKgId.value === '__all__' ? undefined : selectedKgId.value` for API call — tests require `selectedKgId.value || undefined`
   - Code lines 197: `selectedKgId.value === '__all__' ? undefined : selectedKgId.value`

**Failing tests (16 total across 5 files):**

- `app/tests/query.test.ts` (4 failures):
  - `test_1_unscoped_query_omits_knowledge_graph_id > query/index.vue uses || undefined gate to convert empty string to undefined`
  - `test_3_scoped_badge_visible_when_kg_selected > query/index.vue renders a "Scoped" badge when selectedKgId is truthy`
  - `test_3_scoped_badge_visible_when_kg_selected > selectedKgId is initialised to empty string so Unscoped is the default`
  - `test_5_clearing_selection_restores_unscoped_mode > the "All knowledge graphs" SelectItem has value="" to produce the unscoped state`

- `app/tests/query-history.test.ts` (3 failures):
  - `Query Console KG scope selector — structural verification > declares selectedKgId ref initialised to empty string (unscoped default)`
  - `Query Console KG scope selector — structural verification > includes "All knowledge graphs" as the unscoped option in the Select`
  - `Query Console KG scope selector — structural verification > gates knowledge_graph_id via selectedKgId.value || undefined in executeQuery`

- `app/tests/query-kg-selector.test.ts` (4 failures):
  - `test_kg_selector_rendered_in_query_console > the selector includes an "All knowledge graphs" unscoped option`
  - `test_kg_selector_rendered_in_query_console > selectedKgId is initialised to an empty string (unscoped by default)`
  - `test_kg_selector_rendered_in_query_console > the selector shows a Scoped badge when a KG is selected`
  - `test_selected_kg_included_in_query_request > query/index.vue passes selectedKgId.value || undefined to queryGraph`

- `app/tests/task-125-spec-alignment.test.ts` (4 failures):
  - `Task-125 — Scenario: Knowledge graph context — selector UI > selectedKgId defaults to empty string (unscoped)`
  - `Task-125 — Scenario: Knowledge graph context — selector UI > All knowledge graphs option has value="" to represent unscoped state`
  - `Task-125 — Scenario: Knowledge graph context — selector UI > Scoped badge is shown when a KG is selected`
  - `Task-125 — Scenario: Knowledge graph context — query argument wiring > the || undefined gate is present in executeQuery in query/index.vue`

- `app/tests/task-129-spec-alignment.test.ts` (1 failure):
  - `Task-129 — Scenario: Knowledge graph context > query page passes selectedKgId to the API call when scoped`

---

### PASS: All Other Requirements

All other spec requirements have both code implementation and passing tests:

- Backend API Alignment — PASS (api-alignment.test.ts, task-138-spec-alignment.test.ts)
- Navigation Structure — PASS (navigation-structure.test.ts, task-120-spec-alignment.test.ts)
- Tenant and Workspace Context — PASS (tenant-switch.test.ts, workspace-guidance.test.ts)
- Knowledge Graph Creation — PASS (knowledge-graphs.test.ts, task-121-spec-alignment.test.ts)
- Data Source Connection — PASS (data-sources.test.ts, data-source-connection-wizard.test.ts)
- Ontology Design — PASS (ontology-design.test.ts, ontology-add-types.test.ts)
- Sync Monitoring — PASS (sync-monitoring-extended.test.ts, sync-logs.test.ts, sync-phase-indicator.test.ts)
- MCP Connection (Get Started Querying) — PASS (mcp-integration.test.ts)
- Query Console (editing, execution, history) — PASS (task-139-spec-alignment.test.ts)
- Query Console (knowledge graph context) — FAIL (see above)
- Schema Browser — PASS (schema-browser.test.ts, task-126-spec-alignment.test.ts, schema-crossnav-deeplink.test.ts)
- Graph Explorer — PASS (graph-explorer.test.ts, task-139-spec-alignment.test.ts)
- Mutations Console — PASS (mutations-console.test.ts, task-128-spec-alignment.test.ts, mutations-submission.test.ts, mutations-kg-selector.test.ts, mutations-kg-loading.test.ts, mutations-indicator-persistence.test.ts, mutations-workspace-selector.test.ts)
- API Key Management — PASS (api-keys.test.ts)
- Workspace Management — PASS (workspace-management.test.ts)
- Design Language — PASS (design-language.test.ts, design-language-extended.test.ts, design-system.test.ts)
- Interaction Principles — PASS (interaction-principles.test.ts, keyboard-shortcuts.test.ts, focus-ring.test.ts, copy-composable.test.ts)
- Responsive Design — PASS (responsive-design.test.ts)
- Dark Mode — PASS (color-mode.test.ts)

---

### Fix Required

In `src/dev-ui/app/pages/query/index.vue`:

1. Change `const selectedKgId = ref('__all__')` to `const selectedKgId = ref('')`
2. Change `<SelectItem value="__all__">All knowledge graphs</SelectItem>` to `<SelectItem value="">All knowledge graphs</SelectItem>`
3. Change the scoped badge condition from `v-if="selectedKgId !== '__all__'"` to `v-if="selectedKgId"`
4. Change the API call gate from `selectedKgId.value === '__all__' ? undefined : selectedKgId.value` to `selectedKgId.value || undefined`
5. Update `kgScopeLabel` computed to use `selectedKgId.value === ''` (or `!selectedKgId.value`) instead of `=== '__all__'`