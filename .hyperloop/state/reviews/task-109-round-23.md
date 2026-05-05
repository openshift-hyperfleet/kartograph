---
task_id: task-109
round: 23
role: verifier
verdict: fail
---
## Code Review Summary — task-109 (Query Execution: Per-Tenant Graph Routing)

### Checks Run

| Check | Result | Notes |
|---|---|---|
| Unit tests (2993 tests) | PASS | All pass in 89.84s |
| Ruff linting | PASS | Zero violations |
| Ruff formatting | PASS | All files formatted |
| Mypy type checking | PASS | Zero errors (notes only, no errors) |
| Architecture boundary tests (40 tests) | PASS | All DDD boundaries intact |
| No direct logger usage | PASS | Domain probes used correctly |
| No MagicMock on domain aggregates | PASS | |
| Commit trailers (Spec-Ref, Task-Ref) | PASS | All 4 commits carry both trailers |
| No foreign task commits | PASS | All commits owned by task-109 |
| Branch rebases cleanly onto alpha | PASS | Dry-run rebase succeeded with no conflicts |
| **check-no-test-regressions.sh** | **FAIL** | See below |

### Failing Check: check-no-test-regressions.sh

The check compares this branch's HEAD against current alpha HEAD and finds:

```
--- Test files present on alpha HEAD but DELETED on this branch ---
  src/api/tests/integration/query/test_tenant_routing_integration.py
  (present on alpha, deleted on this branch)

FAIL (pass 2 — alpha HEAD): This branch has weaker tests than alpha HEAD.
```

**Root cause:** After this branch's merge-base with alpha, task-150 landed on alpha and added `test_tenant_routing_integration.py` (a richer integration test suite covering `TestTenantQueryRoutedToCorrectGraph`, `TestTenantGraphNotFound` with three sub-tests including a `_RecordingFakeRepo` that verifies the inner repository is never called). This branch independently introduced `test_tenant_routing.py` with both infrastructure-layer and HTTP-layer tests, but never picked up task-150's file from alpha.

**What merging would leave on alpha:** This branch's `test_tenant_routing.py` (756 lines, infrastructure + HTTP layer coverage) but NOT `test_tenant_routing_integration.py` (from task-150, ~500 lines, with three granular not-found scenarios). Net result: alpha would lose `test_tenant_routing_integration.py` after this merge.

**The good news:** The dry-run rebase check confirms the branch rebases cleanly — no conflicts. Rebasing onto current alpha would incorporate `test_tenant_routing_integration.py` from task-150 automatically.

### Required Fix

**Option A (preferred):** Rebase the branch onto latest alpha:
```bash
git rebase alpha
```
This will pick up `test_tenant_routing_integration.py` from task-150. After rebasing, verify that both test files coexist and unit tests still pass:
```bash
cd src/api && uv run pytest tests/unit -v
```
Then re-submit.

**Option B:** If `test_tenant_routing.py` is intended to supersede `test_tenant_routing_integration.py` entirely, explicitly retain the three additional scenarios from the alpha file (especially `test_tenant_aware_repository_raises_before_reaching_database` which uses a `_RecordingFakeRepo` to prove the inner repo is never called) inside `test_tenant_routing.py` and document the supersession in a commit message.

### Code Quality Observations (non-blocking)

- The new `test_tenant_routing.py` is well-structured with clear infrastructure-layer and HTTP-layer test classes.
- The HTTP-layer tests (`TestPerTenantGraphRoutingHTTP`) are a genuine improvement over the alpha version: they exercise the full call chain including auth middleware and FastMCP serialisation.
- The `fix(query)` commit correctly aligns `error_type` to `"unknown_error"` per the spec.
- The `fix(tests)` commit correctly splits OR-chained assertions into independent checks.
- No observability violations, no MagicMock on domain types, no architectural boundary leaks.

The implementation quality is high. The only blocker is the stale rebase state that drops a test file present on alpha HEAD.