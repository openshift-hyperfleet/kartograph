---
task_id: task-109
round: 5
role: verifier
verdict: fail
---
## Summary

All code-quality checks pass. The branch rebases cleanly on alpha. The single commit has the required `Task-Ref` trailer. However, the implementation **does not satisfy the spec** for task-109 because the delivered integration tests exercise the wrong layer of the stack.

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| 1. Unit tests (2931) | ✅ PASS | All pass, no failures |
| 2. Ruff linting | ✅ PASS | Zero violations |
| 3. Ruff formatting | ✅ PASS | 562 files formatted |
| 4. mypy type checking | ✅ PASS | Zero errors |
| 5. Architecture boundary tests (40) | ✅ PASS | All pass |
| 6. Integration tests | ⚠️ SKIP | Require running instance — not exercised in review |
| 7. Code review (logger/mocks/secrets/trailers) | ✅ PASS | Clean |
| Backend check suite (`check-run-backend-suite.sh`) | ✅ PASS | ALL PASS |
| Branch rebase check | ✅ PASS | 0 commits behind alpha |
| Rebase-cleanly check | ✅ PASS | No conflicts |
| Task-Ref trailer check | ✅ PASS | Trailer present on the single commit |

---

## Spec-Alignment Failure (Actionable)

### What the spec requires

The task description (`task-109.md`) is unambiguous:

> "What is missing is end-to-end integration coverage exercising the **full call chain**: API key auth middleware → `get_mcp_query_service()` dependency → `TenantAwareQueryGraphRepository` → real PostgreSQL/AGE."

The two required tests must:

1. **`test_query_executes_in_tenant_graph`** — obtain an API key scoped to a specific tenant, call the MCP `query_graph` tool via HTTP, and assert the correct tenant's data is returned (and no cross-tenant data leaks).

2. **`test_tenant_graph_not_found_returns_structured_error`** — obtain an API key for a tenant whose AGE graph does not exist, call the MCP `query_graph` tool via HTTP, and assert the HTTP response body contains `success: False` and `error_type: "execution_error"`.

### What was delivered

Both tests call `QueryGraphRepository` and `TenantAwareQueryGraphRepository` **directly** (infrastructure-layer objects), bypassing the entire MCP/HTTP transport, FastAPI dependency injection, and auth middleware:

```python
# Delivered — infrastructure layer only, no HTTP
repo_a = QueryGraphRepository(client=tenant_a_client)
results_a = repo_a.execute_cypher("MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}")

# Delivered — raises Python exception, no HTTP response checked
with pytest.raises(QueryExecutionError) as exc_info:
    tenant_repo.execute_cypher("MATCH (n) RETURN n")
```

This means:
- A regression where `get_mcp_query_service()` does **not** propagate `tenant_id` from the auth context would pass these tests silently.
- A regression in `mcp.py`'s `_build_error_response()` that drops `error_type` from the JSON response would pass these tests silently.
- The auth middleware is never exercised.

### What the tests should look like

Follow the pattern in `tests/integration/test_query_mcp_http.py`, which uses `LifespanManager`, `AsyncClient` (ASGI transport), and `fastmcp.Client` (StreamableHttpTransport) to drive the full HTTP stack. The per-tenant tests should:

1. Provision two AGE graphs (e.g., `tenant_<uuid_a>` and `tenant_<uuid_b>`) with distinct seed nodes.
2. Mint or reuse a test API key scoped to `tenant_id = <uuid_a>` (the fake OIDC provider or existing auth fixtures supply this).
3. Call the MCP `query_graph` tool through the HTTP client.
4. Assert tenant-A data is present and tenant-B data is absent from the HTTP response.
5. For the "not found" scenario: call with an API key scoped to a tenant whose graph was **not** provisioned and assert the HTTP response body carries `error_type: "execution_error"`.

---

## Recommendation

Re-implement both tests as HTTP-level integration tests following the `test_query_mcp_http.py` pattern. The infrastructure-layer tests already added may be kept as supplementary coverage but cannot substitute for the full-stack tests the spec requires.