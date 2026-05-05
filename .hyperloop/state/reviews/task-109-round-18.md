---
task_id: task-109
round: 18
role: verifier
verdict: fail
---
## Summary

The check suite (check-run-backend-suite.sh) has one failing check. All substantive
code-quality and implementation checks pass. The failure is caused by a pre-existing
alpha infrastructure issue that this task branch did not introduce, but it must be
fixed before this branch can merge.

---

## Check Results

### 1. Unit Tests — PASS
2990 tests passed, 0 failures, 0 errors.
`cd src/api && uv run pytest tests/unit -v`

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format --check) — PASS
568 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero type errors in 568 source files.

### 5. Architecture Boundary Tests — PASS
40 tests passed. All DDD layer boundaries respected.

### 6. Integration Tests — NOT RUN
Requires a running dev instance (`make instance-up`). The integration test file
`tests/integration/query/test_tenant_routing.py` is well-structured and marked
`@pytest.mark.integration` correctly. Two layers of coverage are provided:
- TestPerTenantGraphRouting: Infrastructure-layer (repository → DB)
- TestPerTenantGraphRoutingHTTP: Full HTTP stack (auth middleware → MCP → AGE)

### 7. Code Review — PASS
- No direct logger.* / print() usage; domain probes used throughout.
- No MagicMock/AsyncMock for domain collaborators; fakes used in unit tests.
- No DDD import boundary violations.
- All commits carry `Task-Ref: task-109` trailers (5 of 6 task commits; 1 is an
  upstream PR merge `eccda51cf` which is exempt per check-all-commits-have-task-ref).
- Conventional commit messages throughout.
- No hardcoded secrets or environment-specific values.
- `error_type="unknown_error"` in the catch-all handler correctly matches the spec
  ("Scenario: Unexpected error → error type is 'unknown_error'").
- OR-chained assertions replaced with independent assertions (two tests in
  test_mcp_query_service.py).

### 8. Check Suite (check-run-backend-suite.sh) — FAIL (1 of 37 checks)

**Failing check:** `check-no-check-script-deletions.sh`

**Root cause:** `.hyperloop/checks/string-constants-match-spec.sh` uses
`grep -r --include="*.py"` without `--exclude-dir=.venv`. The
`check-no-check-script-deletions.sh` script requires all grep-based check scripts
to include this guard to prevent scanning third-party packages in the virtual
environment.

**This is a pre-existing alpha issue — NOT introduced by this branch:**
```
git diff alpha..HEAD -- .hyperloop/checks/string-constants-match-spec.sh
# → (empty — file is identical to alpha)
```
The script was added in commit `4eb1ad7fa` (the alpha branch tip / merge-base)
without the required flag. The `check-no-check-script-deletions.sh` check
inspects ALL scripts on disk, not just changed ones, so it flags this pre-existing
omission on every branch rebased onto alpha.

---

## Required Fix

Add `--exclude-dir=.venv` to the grep command in
`.hyperloop/checks/string-constants-match-spec.sh`:

```bash
# Before:
if ! grep -r --include="*.py" -q "\"${constant}\"" "${SRC_DIR}"; then

# After:
if ! grep -r --include="*.py" --exclude-dir=.venv -q "\"${constant}\"" "${SRC_DIR}"; then
```

This is a one-line fix. After making it, re-run `check-run-backend-suite.sh` to
confirm all 37 checks pass.

---

## Implementation Quality

The task deliverables are solid:

1. **Per-tenant graph routing** is correctly implemented in
   `query/infrastructure/tenant_routing.py` with `TenantAwareQueryGraphRepository`
   and `AGEGraphExistenceChecker`. The graph name convention (`tenant_{tenant_id}`)
   matches the spec.

2. **Defense-in-depth read-only enforcement** is correct in
   `query/infrastructure/query_repository.py`:
   - Primary: `SET TRANSACTION READ ONLY`
   - Secondary: keyword blacklist (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD)

3. **Timeout enforcement** uses `SET LOCAL statement_timeout = {ms}` at the DB level.

4. **Result limiting** correctly handles the three scenarios: no LIMIT (append 1000),
   within MAX_LIMIT (keep), exceeds MAX_LIMIT=10000 (cap).

5. **Error categorization** correctly maps to spec-defined types:
   - `forbidden` (mutation keywords)
   - `timeout` (statement_timeout cancellation)
   - `execution_error` (QueryExecutionError, including graph-not-found)
   - `unknown_error` (unexpected exceptions — fixed in last commit)

The integration tests provide genuine value: the HTTP-layer tests catch regressions
in auth-context propagation and error serialization that the infrastructure-layer
tests cannot detect.