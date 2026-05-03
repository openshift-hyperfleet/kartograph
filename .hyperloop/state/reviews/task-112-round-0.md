---
task_id: task-112
round: 0
role: verifier
verdict: fail
---
## Review Summary

The implementation adds `tests/integration/test_query_mcp_http.py` — a well-structured integration test that exercises the full MCP HTTP transport stack for forbidden-query correlation_id responses. The commit has correct Spec-Ref and Task-Ref trailers, follows conventional commit style, and uses no direct logger/print calls.

However, **mypy type checking fails** with 2 errors introduced by this PR.

---

## Checks

| Check | Result | Notes |
|---|---|---|
| Unit Tests | PASS | 2858 passed, 52 warnings |
| Ruff lint | PASS | Zero violations |
| Ruff format | PASS | All files formatted |
| Mypy type check | **FAIL** | 2 errors in the new file |
| Architecture boundary tests | PASS | 40 passed |
| Direct logger/print usage | PASS | None found |
| Commit trailers (Spec-Ref, Task-Ref) | PASS | Present |
| Repo-port mocks check | pre-existing FAIL | 13 pre-existing files on alpha; not introduced by this PR |

---

## Failing Check Detail

### Mypy — 2 errors in `tests/integration/test_query_mcp_http.py`

```
tests/integration/test_query_mcp_http.py:221: error: Argument "httpx_client_factory" to
  "StreamableHttpTransport" has incompatible type "AsyncClient";
  expected "McpHttpClientFactory | None"  [arg-type]

tests/integration/test_query_mcp_http.py:289: error: Same error
```

**Root cause:** `_make_asgi_httpx_factory` (line 145) is annotated `-> httpx.AsyncClient` but
actually returns the inner `factory` callable. The `# type: ignore[return-value]` on line 176
silences the return-site error, but mypy then believes the function returns an `AsyncClient`.
At call sites (lines 221 and 289) mypy reports that `AsyncClient` is not callable and therefore
cannot satisfy the `McpHttpClientFactory` protocol.

**Fix:** Correct the return type annotation to reflect that the function returns a callable.
The simplest correct annotation:

```python
from collections.abc import Callable

def _make_asgi_httpx_factory(
    asgi_app,
) -> Callable[..., httpx.AsyncClient]:
    ...
    return factory   # no type: ignore needed
```

Alternatively, import `McpHttpClientFactory` from `fastmcp.client.transports` (if it is
publicly exported) and use it as the return type directly, which would also eliminate the
`type: ignore` comment.

---

## Pre-existing Failures (not introduced by this PR)

`check-no-repo-port-mocks.sh` reports 13 files using `create_autospec` for repository ports
and probe protocols. All 13 files (`test_schema_learning.py`, `test_schema_service.py`,
`test_application_services.py` in graph; various IAM application tests) exist on `alpha`
and were failing before this branch. This PR does not introduce or worsen that violation.

---

## Action Required

Fix the return type annotation of `_make_asgi_httpx_factory` so `uv run mypy . --config-file pyproject.toml --ignore-missing-imports` reports zero errors.