---
task_id: task-085
round: 0
role: verifier
verdict: fail
---
## Verification Results

### 1. Unit Tests — PASS
2730 passed, 0 failed, 0 errors (74s)
`uv run pytest tests/unit -v`

### 2. Linting — PASS
Zero ruff violations.

### 3. Formatting — PASS
544 files already formatted.

### 4. Type Checking — PASS
Zero mypy errors across 544 source files.

### 5. Architecture Boundary Tests — PASS
All 40 pytest-archon tests passed. The new `query/ports/` module correctly
stays within bounds (no infrastructure imports), and
`infrastructure/mcp_dependencies.py` is whitelisted for cross-context
composition (`test_infrastructure_mcp_dependencies_can_compose_contexts`).

### 6. Commit Trailers — PASS
Both commits carry `Spec-Ref` and `Task-Ref: task-085` trailers.
`check-all-commits-have-task-ref.sh` reports: "All commits have Task-Ref trailers."

### 7. Code Review — FAIL

**Finding 1 (blocking): `MagicMock` used for domain aggregates**

File: `tests/unit/query/test_mcp_knowledge_graphs_resource.py`, lines 359 and 364

```python
fake_kg_1 = MagicMock()
fake_kg_1.id.value = "kg-prod-001"
fake_kg_1.name = "Production"
fake_kg_1.description = "Production graph"
```

The project guidelines explicitly forbid `MagicMock`/`AsyncMock` for domain
or application collaborators — fakes must be used instead. `KnowledgeGraph`
is a domain aggregate from the Management bounded context. Using `MagicMock`
here allows the test to pass even if the aggregate's attribute structure
changes, making the test fragile and misleading.

**Fix:** Replace the `MagicMock` objects with a simple fake dataclass:

```python
from dataclasses import dataclass

@dataclass
class _FakeKGId:
    value: str

@dataclass
class _FakeKG:
    id: _FakeKGId
    name: str
    description: str

fake_kg_1 = _FakeKG(id=_FakeKGId("kg-prod-001"), name="Production", description="Production graph")
fake_kg_2 = _FakeKG(id=_FakeKGId("kg-staging-002"), name="Staging", description="Staging graph")
```

---

**Finding 2 (non-blocking, design note): `IAccessibleKnowledgeGraphService`
port is defined but never used in production code**

`query/ports/knowledge_graphs.py` defines `IAccessibleKnowledgeGraphService`
as a `Protocol`, but the actual MCP resource handler
(`get_accessible_knowledge_graphs()` in `query/presentation/mcp.py`) calls
`get_accessible_knowledge_graphs_for_mcp()` directly — it never receives or
uses an `IAccessibleKnowledgeGraphService` instance. The port is only
referenced in tests via `FakeKnowledgeGraphProvider`.

This creates a dead protocol definition. Either:
- Inject an `IAccessibleKnowledgeGraphService` into the resource (or via a
  module-level default set at startup) and test the actual resource function
  rather than the fake in `TestKnowledgeGraphsResourceBehavior`; or
- Remove `IAccessibleKnowledgeGraphService` if the direct infrastructure call
  is the intended permanent pattern.

This finding does not block the pass/fail decision on its own, but combined
with Finding 1, the overall verdict is **fail**.