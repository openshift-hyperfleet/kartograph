---
task_id: task-044
round: 10
role: verifier
verdict: fail
---
## Verification Summary

### Check Results

1. **Unit Tests (backend)** — PASS
   2689 tests passed, 52 warnings. Zero failures or errors.

2. **Linting (ruff check)** — PASS
   Zero violations.

3. **Formatting (ruff format)** — PASS
   546 files already formatted.

4. **Type Checking (mypy)** — PASS
   Zero type errors in 546 source files.

5. **Architecture Boundary Tests** — PASS
   40 tests passed.

6. **Frontend Tests** — FAIL
   `data-sources.test.ts` fails to compile due to **duplicate top-level `const` declarations**.

   Commit `799209e7c` ("test(ui): add agent-proposed ontology scenario tests") added a new
   test section that re-declares `GITHUB_PROPOSAL_NODES` and `GITHUB_PROPOSAL_EDGES` at
   module scope (lines 1138 and 1171). These symbols were already declared at module scope
   in lines 625 and 658 (with explicit type annotations `RawNodeProposal[]` /
   `RawEdgeProposal[]`). esbuild rejects the file with:

   ```
   ERROR: The symbol "GITHUB_PROPOSAL_NODES" has already been declared (line 1138)
   ERROR: The symbol "GITHUB_PROPOSAL_EDGES" has already been declared (line 1171)
   ```

   **Fix required:** In the "Ontology Design - Agent-Proposed Ontology" section (around
   line 1138), remove the duplicate `const GITHUB_PROPOSAL_NODES` and `const
   GITHUB_PROPOSAL_EDGES` declarations and instead reference the already-declared
   constants from line 625/658. The two blocks are identical in content, so the second
   declarations can be deleted outright — `runOntologyProposalSync()` and all tests below
   it will continue to work using the existing module-level constants.

7. **Watch-Handler Reload Tests** — FAIL
   `check-watch-handler-reload-tests.sh` reports 3 watch handlers whose fetch calls lack
   test assertions:

   - `data-sources/index.vue` → `loadDataSources()` (test: `index.test.ts`)
   - `groups/index.vue` → `fetchGroups()` (test: `index.test.ts`)
   - `workspaces/index.vue` → `fetchWorkspaces()` (test: `index.test.ts`)

   Commit `ffcd86d57` added reload assertions for api-keys, schema, knowledge-graphs, and
   query pages, but missed these three pages. Each needs a test that:
   1. Simulates a tenant switch (e.g., increment `tenantVersion`)
   2. Asserts the relevant fetch function was called (e.g., `vi.mocked(loadDataSources).toHaveBeenCalled()`)

8. **Commit Trailers** — PASS
   All 6 commits carry both `Task-Ref: task-044` and `Spec-Ref:` trailers.

9. **No direct logger/print usage** — PASS

10. **No MagicMock/AsyncMock in application tests** — PASS

11. **No foreign-task commits** — PASS

12. **No state-file commits** — PASS

13. **Backend suite (check-run-backend-suite.sh)** — PASS
    All sub-checks passed including cascade-delete, rollback, unused fixtures, etc.

---

## Required Fixes Before Resubmission

**Fix 1 (blocking — compile error):**
In `src/dev-ui/app/tests/data-sources.test.ts`, delete the duplicate declarations at
lines 1138–1199 (`const GITHUB_PROPOSAL_NODES = [...]` and `const GITHUB_PROPOSAL_EDGES
= [...]`). The `runOntologyProposalSync()` function and the describe blocks below already
reference the module-level constants declared at lines 625 and 658 — removing the
duplicates is sufficient.

**Fix 2 (check failure):**
In `src/dev-ui/app/tests/index.test.ts`, add watch-handler reload assertions for the
three pages that still lack them:
- After a tenant switch, assert `loadDataSources()` is called (data-sources page watch)
- After a tenant switch, assert `fetchGroups()` is called (groups page watch)
- After a tenant switch, assert `fetchWorkspaces()` is called (workspaces page watch)