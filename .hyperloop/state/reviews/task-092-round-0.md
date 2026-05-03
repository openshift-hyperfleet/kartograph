---
task_id: task-092
round: 0
role: verifier
verdict: fail
---
## Verification Results

### 1. Unit Tests — PASS
All 2784 unit tests pass, including all 10 new tests in `tests/unit/query/test_mcp_agent_instructions.py`.

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format) — PASS
552 files already formatted, no changes needed.

### 4. Type Checking (mypy) — FAIL

The `check-no-mypy-violations.sh` script reports FAIL. Six mypy errors are introduced by the new test file at lines 103, 125, and 126:

```
tests/unit/query/test_mcp_agent_instructions.py:103: error: Item "Resource" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
tests/unit/query/test_mcp_agent_instructions.py:103: error: Item "ResourceTemplate" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
tests/unit/query/test_mcp_agent_instructions.py:125: error: Item "Resource" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
tests/unit/query/test_mcp_agent_instructions.py:125: error: Item "ResourceTemplate" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
tests/unit/query/test_mcp_agent_instructions.py:126: error: Item "Resource" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
tests/unit/query/test_mcp_agent_instructions.py:126: error: Item "ResourceTemplate" of "Resource | ResourceTemplate" has no attribute "fn"  [union-attr]
```

**Root cause**: The tests access `mcp_module.get_agent_instructions.fn()` to invoke the raw function underlying the `@mcp.resource()`-decorated callable. FastMCP's `FunctionResource` does expose `.fn` at runtime, but mypy resolves the type of the decorated name as `Resource | ResourceTemplate`, neither of which has a `.fn` attribute in the type stubs.

**Required fix**: Add a `FunctionResource` type assertion before accessing `.fn`, e.g.:

```python
from mcp.server.fastmcp.resources.types import FunctionResource

resource = mcp_module.get_agent_instructions
assert isinstance(resource, FunctionResource), "expected FunctionResource"
result = resource.fn()
```

Or use `cast(FunctionResource, mcp_module.get_agent_instructions).fn()` if an isinstance check is undesirable. Apply this fix in `test_resource_function_delegates_to_prompt_repository` (line ~103) and `test_resource_function_calls_prompt_repository_exactly_once` (lines ~125–126).

### 5. Architecture Boundary Tests — PASS
All 40 pytest-archon tests pass.

### 6. Integration Tests — Not run (task is tests-only; no infrastructure layer changes).

### 7. Code Review — PASS (with notes)

- No direct `logger.*` or `print()` calls: PASS
- Commit trailers present (`Spec-Ref` and `Task-Ref`): PASS
- No hardcoded secrets: PASS
- `MagicMock` is used for `_prompt_repository` in two tests. This is an infrastructure-layer object (not a domain aggregate), and the mock is scoped via `patch.object` — acceptable here. The `check-domain-aggregate-mocks.sh` and `check-no-repo-port-mocks.sh` (which only scans `application/test_*.py` files) both pass on the new file.
- Pre-existing `check-no-repo-port-mocks.sh` failures in `test_schema_learning.py` and `test_schema_service.py` are not introduced by this PR and not counted against it.

## Summary

The sole blocking issue is the 6 mypy `[union-attr]` errors introduced in `tests/unit/query/test_mcp_agent_instructions.py`. Fix the `.fn` attribute access by asserting or casting to `FunctionResource` before use, then re-run `check-no-mypy-violations.sh` to confirm zero errors.