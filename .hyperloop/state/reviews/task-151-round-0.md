---
task_id: task-151
round: 0
role: spec-reviewer
verdict: fail
---
16 tests fail across 5 test files. All failures are in the same area: the Query Console Knowledge Graph Context Selector uses empty string `''` as the "all knowledge graphs" sentinel, but every test suite expects the `'__all__'` string sentinel.

### REQ-Query Console: Knowledge graph context
Status: PARTIAL
- Code: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/pages/query/index.vue:73` — `const selectedKgId = ref('')` (empty string sentinel)
- Code: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/pages/query/index.vue:490` — `<SelectItem value="">All knowledge graphs</SelectItem>` (value="" for unscoped option)
- Code: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/pages/query/index.vue:197` — `selectedKgId.value || undefined` (|| undefined gate, not `=== '__all__'` ternary)
- Code: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/pages/query/index.vue:500` — `<Badge v-if="selectedKgId">Scoped</Badge>` (truthiness check, not `!== '__all__'` comparison)
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query-kg-selector.test.ts:57` — expects `selectedKgId = ref('__all__')`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query-kg-selector.test.ts:50` — expects `<SelectItem value="__all__">`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query-kg-selector.test.ts:62` — expects `selectedKgId !== '__all__'` for Scoped badge
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query-kg-selector.test.ts:186` — expects `selectedKgId.value === '__all__'` gate in executeQuery
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query.test.ts:56` — expects `selectedKgId.value === '__all__'`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query.test.ts:105` — expects `selectedKgId !== '__all__'`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query.test.ts:129` — expects `selectedKgId = ref('__all__')`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query.test.ts:220` — expects `<SelectItem value="__all__">`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/query-history.test.ts` — 3 failures, all requiring `__all__` sentinel
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/task-125-spec-alignment.test.ts:384` — expects `selectedKgId = ref('__all__')`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/task-125-spec-alignment.test.ts:390` — expects `<SelectItem value="__all__">`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/task-125-spec-alignment.test.ts:400-401` — expects `selectedKgId !== '__all__'`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/task-125-spec-alignment.test.ts:436` — expects `selectedKgId.value === '__all__'`
- Test: `/home/jsell/code/kartograph/worktrees/workers/task-151/src/dev-ui/app/tests/task-129-spec-alignment.test.ts:1109` — expects `selectedKgId.value === '__all__'`
- Notes: The implementation uses empty string as unscoped sentinel but tests require `'__all__'`. Commit fcf5e4e86 ("fix(ui): use empty string sentinel for unscoped KG selector") introduced the regression by switching from `'__all__'` to `''`, but the tests were written against the `'__all__'` sentinel (which Reka UI documentation requires since `value=""` is reserved for clearing selection). The functional behavior (scoping queries correctly) is implemented, but the sentinel value in the source code does not match what the tests expect. Test suite: 16 failed | 2477 passed across 5 failed files | 48 passed files.

### Failing tests (16 total across 5 files)

**query-kg-selector.test.ts (4 failures):**
- `the selector includes an "All knowledge graphs" unscoped option` — expects `value="__all__"`, found `value=""`
- `selectedKgId is initialised to the __all__ sentinel (unscoped by default)` — expects `ref('__all__')`, found `ref('')`
- `the selector shows a Scoped badge when a KG is selected` — expects `selectedKgId !== '__all__'`, found truthiness check
- `query/index.vue gates selectedKgId using __all__ sentinel check before passing to queryGraph` — expects `selectedKgId.value === '__all__'`, found `|| undefined`

**query.test.ts (4 failures):**
- `query/index.vue uses __all__ sentinel gate to omit knowledge_graph_id when unscoped`
- `query/index.vue renders a "Scoped" badge when selectedKgId differs from __all__ sentinel`
- `selectedKgId is initialised to __all__ sentinel so Unscoped is the default`
- `the "All knowledge graphs" SelectItem has value="__all__" to produce the unscoped state`

**query-history.test.ts (3 failures):**
- `declares selectedKgId ref initialised to __all__ sentinel (unscoped default)`
- `includes "All knowledge graphs" as the unscoped option in the Select`
- `gates knowledge_graph_id via __all__ sentinel check in executeQuery`

**task-125-spec-alignment.test.ts (4 failures):**
- `selectedKgId defaults to __all__ sentinel (unscoped)`
- `All knowledge graphs option has value="__all__" to represent unscoped state`
- `Scoped badge is shown when a KG is selected`
- `the __all__ sentinel gate is present in executeQuery in query/index.vue`

**task-129-spec-alignment.test.ts (1 failure):**
- `query page passes selectedKgId to the API call when scoped`

### All Other Requirements
All other spec requirements (Navigation Structure, Tenant Context, Knowledge Graph Creation, Data Source Connection, Sync Monitoring, MCP Connection, Schema Browser, Graph Explorer, Mutations Console, API Key Management, Workspace Management, Design Language, Interaction Principles, Responsive Design, Dark Mode, Backend API Alignment, Ontology Design) are COVERED by their respective test files, all of which PASS.