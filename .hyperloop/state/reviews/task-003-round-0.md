---
task_id: task-003
round: 0
role: verifier
verdict: fail
---
## Verification Results

### Check 1 – Unit Tests: PASS
2013 tests passed, 0 failed, 0 errors.
```
cd src/api && uv run pytest tests/unit -v
====================== 2013 passed, 38 warnings in 45.73s ======================
```

### Check 2 – Linting: PASS
```
cd src/api && uv run ruff check .
All checks passed!
```

### Check 3 – Formatting: PASS
```
cd src/api && uv run ruff format --check .
439 files already formatted
```

### Check 4 – Type Checking: PASS
```
cd src/api && uv run mypy . --config-file pyproject.toml --ignore-missing-imports
Success: no issues found in 439 source files
```

### Check 5 – Architecture Boundary Tests: PASS
All 40 pytest-archon tests pass. No DDD layer violations.

### Check 6 – Integration Tests: SKIPPED
No graph-mutations integration tests exist. The only integration test touching mutations
(`test_auth_enforcement.py`) only checks for 401 (unauthenticated) and does not exercise
the service or applier.

### Check 7 – Code Review: FAIL

#### FAIL – Regression in legacy `/graph/mutations` route for CREATE operations

The implementation adds `knowledge_graph_id` validation to `validate_operation()` in
`graph/domain/value_objects.py`:

```python
if "knowledge_graph_id" not in self.set_properties:
    raise ValueError(
        "CREATE requires 'knowledge_graph_id' in set_properties. ..."
    )
```

This is correct for the new KG-scoped route, where the service stamps `knowledge_graph_id`
**before** the applier validates. However, the legacy `POST /graph/mutations` route calls:

```python
service.apply_mutations_from_jsonl(jsonl_content=jsonl_content)  # no knowledge_graph_id
```

With no `knowledge_graph_id` argument, `_stamp_knowledge_graph_id` is never called. The
real `MutationApplier.apply_batch()` then calls `op.validate_operation()` on each operation
and will reject every CREATE operation with:

> "CREATE requires 'knowledge_graph_id' in set_properties."

The old route is now silently broken for CREATE operations in real (non-mocked) use.

**Why unit tests don't catch it:** `TestApplyMutationsRoute` uses `mock_mutation_service`
(a `Mock()`), which returns the pre-configured `MutationResult` without invoking real
service/applier logic. The service-layer tests (`TestGraphMutationServiceApplyMutations`)
use `mock_applier` (another `Mock()`), which skips `validate_operation()`. The regression
is invisible to the unit test suite.

**Spec obligation:** The spec states "The system SHALL require a target KnowledgeGraph for
all mutations." Leaving the old route in place without a KG requirement means the system
does not fully enforce this SHALL.

**Actionable fix — pick one:**

1. **Remove the old route** (`POST /graph/mutations`) entirely. Since the spec requires all
   mutations to be KG-scoped, the old route is no longer spec-compliant. Its two existing
   tests (`TestApplyMutationsRoute`) should be deleted alongside it.

2. **Block CREATE on the old route** — add a guard in the old route handler or in
   `apply_mutations_from_jsonl` that rejects the operation when no `knowledge_graph_id`
   is provided but CREATE ops are present, and add a unit test that exercises this guard
   using the real service + mock applier.

3. **Move the `knowledge_graph_id` check out of `validate_operation()`** into the new
   KG-scoped route's service call path only (e.g., check it in a separate method called
   only when a KG ID is expected). This is the most invasive change and carries risk of
   weakening the invariant.

Option 1 is strongly preferred given the spec wording.

#### CONCERN – `AsyncMock` used for `AuthorizationProvider` in route tests

```python
authz = AsyncMock()
authz.check_permission.return_value = True
```

`AuthorizationProvider` is a protocol/infrastructure boundary, so this is borderline
acceptable (the guideline restricts AsyncMock for *domain/application* collaborators).
This is logged as a concern, not a hard FAIL, but a lightweight fake or a real
`FakeAuthorizationProvider` would be preferred for consistency with the project's
fake-over-mock policy.

#### PASS – All new spec requirements correctly implemented

- **Per-tenant graph isolation:** `get_tenant_graph_name()` → `tenant_{tenant_id}` ✅
- **KG authorization:** SpiceDB `edit` permission checked on `knowledge_graph:{id}` ✅
- **403 when permission denied, service never called** ✅
- **`knowledge_graph_id` stamping on CREATE/UPDATE** ✅
- **Anti-spoofing (overwrites caller-supplied value)** ✅
- **Schema learning exclusion via `PLATFORM_STAMPED_PROPERTIES`** ✅
- **Commit trailers (Spec-Ref, Task-Ref)** present on all implementation commits ✅
- **No logger/print usage** (domain probes used) ✅
- **No hardcoded secrets** ✅

## Summary

The new KG-scoped mutations route is correct and well-tested. The failure is a regression:
adding `knowledge_graph_id` validation to `validate_operation()` silently breaks the
legacy `POST /graph/mutations` route for CREATE operations in real (non-mocked) use.
The unit test suite does not expose this because both the route-layer and service-layer
tests use mocks that bypass the real applier. The fix is straightforward — preferably
remove the old route as required by the spec's "all mutations need a KG" requirement.