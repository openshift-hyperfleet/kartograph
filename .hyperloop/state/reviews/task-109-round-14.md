---
task_id: task-109
round: 14
role: verifier
verdict: fail
---
## Verification Summary for task-109 — Query Execution (Per-Tenant Graph Routing Integration Tests)

### What was delivered

This branch adds integration tests covering the Per-Tenant Graph Routing requirement from the query-execution spec. Core implementation (`query_repository.py`, `tenant_routing.py`) was already merged to alpha via PRs #552 and #553. The branch-specific work is:

- `test_tenant_routing.py` (new): Infrastructure-layer and HTTP-layer integration tests for Per-Tenant Graph Routing — two test classes, four scenarios.
- `test_mcp_query_service.py` (modified): Split OR-chained assertions into independent checks (fixes `check-partial-error-assertions.sh`).
- `uv.lock`: Aligned with alpha after rebase conflict resolution.

---

## Numbered Checks (Guidelines §1–6)

### 1. Unit Tests — PASS
2990 passed, 0 failures, 0 errors (91.67s).

### 2. Linting — PASS
`uv run ruff check .` — All checks passed.

### 3. Formatting — PASS
`uv run ruff format --check .` — 568 files already formatted.

### 4. Type Checking — PASS
`uv run mypy . --config-file pyproject.toml --ignore-missing-imports` — Success: no issues found in 568 source files.

### 5. Architecture Boundary Tests — PASS
`pytest tests/unit/test_architecture.py` — 40 passed.

### 6. Integration Tests — NOT VERIFIED
This task adds integration tests that touch the infrastructure layer (QueryGraphRepository, AGEGraphExistenceChecker) and the presentation/HTTP layer (MCP endpoint). Per the guidelines these must be run. No running instance was available in the review environment; the tests could not be executed.

---

## Check Scripts (check-run-backend-suite.sh)

**Result: FAIL — 1 failing check**

### check-commit-msg-hook-has-guard.sh — FAIL
The commit-msg git hook is not installed in the worktree:
```
Hook path: /home/jsell/code/kartograph/.git/worktrees/task-109/hooks/commit-msg
FAIL: commit-msg hook not found
```
**Fix:** Run `bash .hyperloop/checks/install-git-commit-msg-hook.sh` from the worktree root before resubmitting.

Note: `check-all-commits-have-task-ref.sh` PASSES independently — all commits on this branch carry valid `Spec-Ref:` and `Task-Ref: task-109` trailers. The missing hook is a process-setup issue, not a trailer content issue. The fix is trivial but required.

All other backend-suite checks PASS:
- check-no-direct-logger-usage: PASS
- check-partial-error-assertions: PASS (the OR-chained assertions were fixed)
- check-domain-aggregate-mocks: PASS
- check-no-test-regressions: PASS
- check-no-foreign-task-commits: PASS
- check-branch-rebased-on-alpha: PASS (0 commits behind)
- check-implementation-commits-exist: PASS (4 implementation commits)
- check-no-source-regressions: PASS
- check-weak-test-assertions: PASS
- check-empty-test-stubs: PASS

---

## Code Review

### Commit Trailers — PASS
Three task-specific commits carry both `Spec-Ref: specs/query/query-execution.spec.md@dbcf0d7c…` and `Task-Ref: task-109`. The upstream PR cherry-pick (`54f3b739` — SpiceDB TLS fix) has no trailer, which `check-no-foreign-task-commits.sh` correctly identifies as an upstream PR and excludes.

### No Direct Logger/Print Usage — PASS
No `logger.*` or `print()` calls in the new test file.

### No MagicMock/AsyncMock on Domain Collaborators — PASS
Integration tests use real production components wired to a real database.

### No DDD Boundary Violations — PASS
`test_tenant_routing.py` imports only from appropriate layers:
- `query.domain.value_objects` — correct
- `query.infrastructure.*` — correct (infrastructure-layer test)
- `graph.infrastructure.*` — acceptable for provisioning helpers in integration tests

### Minor Code Issue (non-blocking observation)
Fixture name typo: `unprovisionied_tenant_id` (double `i`) appears in the fixture definition and two references. This is not a correctness issue but should be corrected for readability: rename to `unprovisioned_tenant_id`.

---

## Actionable Items for Implementer

1. **REQUIRED (blocks merge):** Install the commit-msg hook:
   ```bash
   bash .hyperloop/checks/install-git-commit-msg-hook.sh
   ```

2. **REQUIRED (not verified):** Run integration tests against a live instance to confirm the new tests pass:
   ```bash
   make instance-up
   source .instances/$(basename $(pwd))/.env.instance
   cd src/api && uv run pytest tests/integration/query/test_tenant_routing.py -v -m integration
   make instance-down
   ```

3. **OPTIONAL (cosmetic):** Fix typo in fixture name `unprovisionied_tenant_id` → `unprovisioned_tenant_id` in `test_tenant_routing.py` (lines 321, 702, 703, 723).