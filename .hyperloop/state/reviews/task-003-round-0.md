---
task_id: task-003
round: 0
role: verifier
verdict: fail
---
## Verification Report — task-003 (Graph Mutations)

### Automated Check Results

| Check | Result | Detail |
|-------|--------|--------|
| 1. Unit Tests | PASS | 2031 passed, 0 failures, 40 warnings |
| 2. Linting (ruff check) | PASS | All checks passed |
| 3. Formatting (ruff format) | PASS | 441 files already formatted |
| 4. Type Checking (mypy) | PASS | No issues found in 441 source files |
| 5. Architecture Boundary Tests | PASS | 40 pytest-archon tests pass |
| 6. Integration Tests | N/A | Not run — no infrastructure available in worktree |
| 7. Code Review | FAIL | Direct `logger.error` usage in presentation layer violates DOO pattern |

---

### Failing Finding: DOO Violation in routes.py

**File:** `src/api/graph/presentation/routes.py`
**Introduced by:** commit `ab10f485` ("fix(graph): address CodeRabbit PR feedback — security and correctness hardening")

The function `_build_mutation_error_response` at line 69 calls `logger.error()` directly:

```python
logger.error(
    "graph_mutation_server_error",
    errors=result.errors,
    error_kind=result.error_kind,
)
```

**Why this fails:** AGENTS.md states: *"Domain probes should be 100% preferred over `logger.*` and `print()`."* The verification checklist explicitly requires: *"No direct logger/print usage (must use domain probes)."* This is new code on this branch (not pre-existing), added to prevent internal error detail leakage in HTTP 500 responses.

**How to fix:** Add a `server_error_occurred(errors: list[str]) -> None` method to the `GraphServiceProbe` protocol (`graph/application/observability/graph_service_probe.py`) and its default implementation (`default_graph_service_probe.py`), then inject the probe into the route handler (via a dependency or a dedicated presentation-layer probe) and call `probe.server_error_occurred(result.errors)` instead of `logger.error(...)`.

---

### Positive Findings

All 10 spec requirements are well-covered:

- **Per-Tenant Graph Isolation:** `get_tenant_graph_name()` correctly derives `tenant_{tenant_id}`; tested in `TestTenantGraphRouting`.
- **KnowledgeGraph Scoping:** SpiceDB `edit` permission check before any service call; `_stamp_knowledge_graph_id` overwrites caller-supplied values; service now rejects CREATE/UPDATE batches when `knowledge_graph_id is None` (defense-in-depth).
- **Mutation Log Format:** JSONL parsing handles valid input, invalid JSON (with line number + preview), empty lines, and whitespace-only lines.
- **DEFINE, CREATE, UPDATE, DELETE operations:** All implemented with schema learning, idempotent merge, cascading delete, and required-property validation.
- **Mandatory System Properties:** Validated at `value_objects.py` layer using `PLATFORM_STAMPED_PROPERTIES` constant (single source of truth).
- **Deterministic Entity IDs:** `ID_REGEX` enforced by Pydantic `Field(pattern=...)`.
- **Referential Integrity Ordering:** `MutationApplier._sort_operations()` enforces DEFINE → DELETE(edge/node) → CREATE(node/edge) → UPDATE order with 3 test classes verifying all positions.
- **Commit trailers:** `Spec-Ref` and `Task-Ref` are present on implementation commits.
- **No MagicMock for domain collaborators:** MagicMock in `test_mutation_applier_sort.py` is used only as a structural placeholder for infrastructure ports; the tested method (`_sort_operations`) never calls them. Acceptable.

---

### Required Action

Fix the `logger.error` in `_build_mutation_error_response` (routes.py) to use a domain probe instead of a direct structlog call. All other checks pass cleanly.