---
task_id: task-045
round: 21
role: verifier
verdict: fail
---
## Verification Summary

**Branch:** hyperloop/task-045 (8 commits ahead of alpha @ 1892b50c)

---

## Check Results

### 1. Unit Tests — PASS
2700 backend unit tests pass with zero failures.

### 2. Linting (ruff check) — PASS
Zero ruff violations.

### 3. Formatting (ruff format) — PASS
All 545 files correctly formatted.

### 4. Type Checking (mypy) — PASS
Zero mypy errors across 545 source files.

### 5. Architecture Boundary Tests — PASS
All 40 pytest-archon tests pass. No bounded-context import leakage detected.

### 6. Integration Tests — NOT RUN
Task touches only presentation/UI layers plus the management `POST /ontology-proposals`
endpoint (pure add, no infrastructure changes). Integration tests not required.

### 7. Code Review — PASS

- No `logger.*` or `print()` calls. Domain probes used correctly.
- No `MagicMock`/`AsyncMock` on repository ports or probe protocols in application-layer
  tests. The refactoring commit (`fea86354`) correctly replaced all violations with
  in-memory fakes (`RecordingDataSourceServiceProbe`, `InMemoryDataSourceSyncRunRepository`).
- No DDD layer-boundary violations detected in the diff.
- All commits carry `Spec-Ref` and `Task-Ref: task-045` trailers.
- Conventional commit prefixes used throughout (feat, fix, test, refactor).
- No hardcoded credentials or environment-specific secrets.
- The `tracer-bullet` ontology proposal endpoint is appropriately scoped:
  deterministic GitHub proposals are wired end-to-end; the AI-inference path is
  deferred correctly with explanatory comments (not `TODO` stubs blocked by
  check-no-future-placeholder-comments.sh).

---

## Failing Check

### check-watch-handler-reload-tests.sh — FAIL

```
WARN: src/dev-ui/app/pages/api-keys/index.vue — watch handler calls `loadKeys()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/data-sources/index.vue — watch handler calls `loadDataSources()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/groups/index.vue — watch handler calls `fetchGroups()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/knowledge-graphs/index.vue — watch handler calls `loadKnowledgeGraphs()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/query/index.vue — watch handler calls `fetchSchema()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/query/index.vue — watch handler calls `loadKnowledgeGraphs()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
WARN: src/dev-ui/app/pages/workspaces/index.vue — watch handler calls `fetchWorkspaces()` but no assertion found in test file(s): src/dev-ui/app/tests/index.test.ts
FAIL: 7 watch-handler reload call(s) appear to lack test assertions.
```

**Root cause:** The check script uses `basename "$vue_file" .vue` to locate the
companion test file. Every subdirectory page named `index.vue` (api-keys, data-sources,
groups, knowledge-graphs, query, workspaces) maps to the single
`src/dev-ui/app/tests/index.test.ts`, which tests `pages/index.vue` (the home redirect
page) and contains none of the fetch-call references the check is looking for.
The actual test coverage lives in the domain-specific test files
(e.g., `knowledge-graphs.test.ts` has the `tenantVersion` watcher assertions for
`query/index.vue`; `data-sources.test.ts` covers `data-sources/index.vue`).

Five of the seven failing pages (api-keys, groups, knowledge-graphs, workspaces, and
the existing watch handlers in data-sources and query) existed on alpha unchanged before
this branch was created, so the check was already failing on alpha when the branch was
started. This branch's modifications to `data-sources/index.vue` (ontology proposal API
wiring) and `query/index.vue` (add `selectedKgId.value = ''` reset) did not add or
change the watch handlers that trigger the check.

**Actionable fix required — two options:**

**Option A (recommended):** Add explicit watch-reload assertions to the domain-specific
test files (`api-keys.test.ts`, `data-sources.test.ts`, `groups.test.ts`,
`knowledge-graphs.test.ts`, `workspaces.test.ts`) **and** to `knowledge-graphs.test.ts`
for `query/index.vue`. After incrementing `tenantVersion` in any test that exercises the
clear path, assert that the fetch/load function is called:

```typescript
// Example for data-sources.test.ts (data-sources/index.vue watch handler)
it('calls loadDataSources() when tenant changes', async () => {
  // arrange: mock loadDataSources
  const loadDataSources = vi.fn().mockResolvedValue(undefined)
  // ... wire into component ...
  // act: simulate tenantVersion increment
  tenantVersion.value++
  await nextTick()
  // assert both the clear AND the reload
  expect(dataSources.value).toEqual([])
  expect(loadDataSources).toHaveBeenCalled()
})
```

The check's grep pattern is `(${fetch_call}|mock.*${fetch_call}|${fetch_call}.*mock)`,
so naming the mock `loadDataSources` (or using `vi.mocked(loadDataSources)` in an
`expect`) satisfies it.

**IMPORTANT:** The check maps test files by basename, so these assertions must appear in
files named `<component-basename>.test.ts` — e.g., `api-keys.test.ts` for
`pages/api-keys/index.vue`. A file named `index.test.ts` only satisfies the check for
the root `pages/index.vue`.

**Option B:** Raise a process-improvement task to fix the check script's file-discovery
heuristic (using parent directory name for `index.vue` files instead of basename). This
cannot be done on a task branch (check-no-check-script-modifications.sh blocks it), but
a dedicated process task could update the script and retroactively satisfy all seven
warnings.

Until one of these options is addressed and the check exits 0, this branch cannot merge.

---

## All Passing Check Scripts (canonical backend suite + frontend-specific)

check-no-check-script-deletions.sh ✓
check-no-check-script-modifications.sh ✓
check-process-overlays-intact.sh ✓
check-process-overlay-content-intact.sh ✓
check-new-checks-pass-on-head.sh ✓
check-branch-has-commits.sh ✓
check-alpha-local-vs-remote.sh ✓
check-branch-rebased-on-alpha.sh ✓
check-branch-rebases-cleanly.sh ✓
check-no-state-file-commits.sh ✓
check-worker-result-not-committed.sh ✓
check-no-foreign-task-commits.sh ✓
check-no-ruff-violations.sh ✓
check-no-mypy-violations.sh ✓
check-no-source-regressions.sh ✓
check-no-route-handler-removals.sh ✓
check-no-test-regressions.sh ✓
check-empty-test-stubs.sh ✓
check-domain-aggregate-mocks.sh ✓
check-no-repo-port-mocks.sh ✓
check-no-direct-logger-usage.sh ✓
check-no-coming-soon-stubs.sh ✓
check-weak-test-assertions.sh ✓
check-di-wiring-updated.sh ✓
check-event-handlers-registered.sh ✓
check-domain-events-have-consumers.sh ✓
check-pytest-env-skip-if-set.sh ✓
check-cascade-delete-cleanup.sh ✓
check-cascade-delete-empty-collection-mocks.sh ✓
check-cascade-delete-rollback-test.sh ✓
check-unused-fixtures.sh ✓
check-no-future-placeholder-comments.sh ✓
check-no-api-simulation.sh ✓
check-pages-have-tests.sh ✓
check-frontend-tests-exist.sh ✓
check-all-commits-have-task-ref.sh ✓
check-no-state-file-commits.sh ✓
check-selector-forwarding.sh ✓
check-partial-error-assertions.sh ✓
check-cascade-delete-rollback-test.sh ✓
check-no-domain-exception-deletions.sh (N/A — no exceptions deleted) ✓

Frontend test suite (vitest): 1241 tests across 29 files — ALL PASS ✓
Backend unit tests (pytest): 2700 tests — ALL PASS ✓