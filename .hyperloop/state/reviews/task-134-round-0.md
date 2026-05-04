---
task_id: task-134
round: 0
role: verifier
verdict: fail
---
## Verification Summary

### Check Results

| Check | Result | Detail |
|-------|--------|--------|
| Unit Tests (2986) | PASS | All pass, zero failures |
| Ruff Linting | PASS | Zero violations |
| Ruff Formatting | PASS | 564 files already formatted |
| MyPy Type Check | PASS | Zero type errors |
| Architecture Boundary Tests | PASS | 40/40 passed |
| No Direct Logger Usage | PASS | Zero violations |
| No Empty Test Stubs | PASS | Zero stubs |
| Task-134 Implementation | **FAIL** | See below |

---

### Critical Finding: No task-134 Implementation

**The branch contains zero commits tagged `Task-Ref: task-134`.** The two commits
ahead of local `alpha` are:

```
d51e921b9  test(query): add HTTP integration tests for query_graph timeout error response (#599)
           Task-Ref: task-132   ← wrong task
           Files: src/api/tests/integration/test_query_mcp_http.py

42502fea3  test(ui): add 5-property collapsed view tests for graph explorer (task-127) (#598)
           Task-Ref: task-127   ← wrong task
           Files: src/dev-ui/app/pages/graph/explorer.vue, src/dev-ui/app/tests/graph-explorer.test.ts
```

Both commits are already present on `origin/alpha` (the branch HEAD equals the
`origin/alpha` HEAD at `d51e921b9`). There is no task-134-specific work anywhere
on this branch.

---

### What task-134 Must Deliver

Per `.hyperloop/state/tasks/task-134.md` (current spec as of the most recent intake):

**Spec:** `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`
**Requirement:** Per-Tenant Graph Routing — Scenario: Tenant graph not found

The task requires adding a new class `TestMCPTenantGraphNotFoundHTTPResponse` to
`src/api/tests/integration/test_query_mcp_http.py` containing two tests:

1. **`test_query_without_provisioned_graph_returns_execution_error`**
   - Create an API key (default tenant exists, but do NOT provision its AGE graph)
   - Send `query_graph` call via MCP HTTP transport with a valid read-only query
   - Assert `result["success"] is False`
   - Assert `result["error_type"] == "execution_error"`
   - Assert message contains "does not exist" or similar graph-not-found language

2. **`test_query_without_provisioned_graph_error_occurs_before_database`**
   - Same setup (no provisioned graph)
   - Submit a write query that would be caught by keyword blacklist if graph existed
   - Assert `result["error_type"] == "execution_error"` (NOT `"forbidden"`)
   - Confirms graph-existence check runs before keyword validation

Unit tests for this scenario already exist in `test_tenant_routing.py` and
`test_query_repository.py`, but the HTTP-level integration test is missing.

---

### What the Implementer Must Do

1. Start from `origin/alpha` (local `alpha` is two commits behind — fetch first):
   ```bash
   git fetch origin
   git rebase origin/alpha
   ```

2. Add `TestMCPTenantGraphNotFoundHTTPResponse` to
   `src/api/tests/integration/test_query_mcp_http.py` per the task description.
   Follow the same fixture pattern (`_make_asgi_httpx_factory`, `fastmcp.Client`,
   `StreamableHttpTransport`) used by `TestMCPForbiddenQueryHTTPResponse`.

3. Key implementation note: do NOT include the `provisioned_tenant_graph` fixture
   in the new test methods' parameters. Use only `async_client` and `api_key_secret`.

4. Commit with:
   ```
   Task-Ref: task-134
   Spec-Ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
   ```

5. Run integration tests to verify:
   ```bash
   make instance-up
   source .instances/$(basename $(pwd))/.env.instance
   cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \
       -v -m integration -k "graph_not_found"
   make instance-down
   ```