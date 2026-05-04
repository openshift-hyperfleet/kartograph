---
task_id: task-100
round: 17
role: verifier
verdict: fail
---
## Summary

Branch `hyperloop/task-100` is **two test-only commits** applied on top of an
implementation that was already merged to `alpha` via separate PRs (#552, #553,
#335). The commits are well-formed and address two outstanding process failures
from the previous review cycle:

1. `test(query): add TestCrossTenantIsolation integration tests` — adds
   per-tenant graph routing integration tests as required by the spec.
2. `fix(tests): split OR-chained assertions in query service tests` — resolves
   the `check-partial-error-assertions.sh` failure from the prior cycle.

All substantive quality checks pass. The branch fails on one procedural
check — the commit-msg hook is not installed in this worktree.

---

## Check Results

| # | Check | Result |
|---|-------|--------|
| 1 | Unit tests (`uv run pytest tests/unit`) | **PASS** — 2990 passed, 0 failures |
| 2 | Linting (`ruff check .`) | **PASS** — zero violations |
| 3 | Formatting (`ruff format --check .`) | **PASS** — 567 files already formatted |
| 4 | Type checking (`mypy .`) | **PASS** — no type errors in 567 source files |
| 5 | Architecture boundary tests | **PASS** — 40 passed |
| 6 | Integration tests | **SKIPPED** — no infrastructure or presentation layer changes; diff is test-only |
| 7 | Code review (diff) | **PASS** — see below |

---

## Code Review

**Diff scope:** Two test files modified.

- `tests/unit/query/test_mcp_query_service.py` — Two OR-chained assertions
  split into independent `assert` statements. Both conditions hold given
  the actual error messages produced by the implementation, so the fix
  is correct and non-fragile.

- `tests/integration/test_query_mcp.py` — New `TestCrossTenantIsolation`
  class added with two integration tests:
  - `test_tenant_a_cannot_see_tenant_b_data`: inserts distinct marker nodes
    into two AGE graphs and confirms the tenant_a-scoped repository returns
    only tenant_a data. Correct isolation check.
  - `test_tenant_graph_not_found_raises_before_db`: drops a graph after
    connecting, then asserts `QueryExecutionError` is raised before any
    Cypher transaction opens. Correctly exercises the pre-DB rejection
    requirement from the spec.

**Observability:** No `logger.*` or `print()` calls introduced. ✓

**Fakes over mocks:** No `MagicMock`/`AsyncMock` introduced. ✓

**Commit trailers:** Both commits carry `Spec-Ref`, `Task-Ref`, and
`Co-Authored-By` trailers in a contiguous block.
`check-all-commits-have-task-ref.sh` → **PASS**.

**No foreign-task commits.** `check-no-foreign-task-commits.sh` → **PASS**.

**Branch rebases cleanly onto alpha.** `check-branch-rebases-cleanly.sh` → **PASS**.

---

## Failing Check

### `check-commit-msg-hook-has-guard.sh` — FAIL

The commit-msg hook is not installed at
`.git/worktrees/task-100/hooks/commit-msg`. This is a **procedural failure**:
the hook was not set up in this worktree before the first commit was made.

**Why this matters:** Without the hook the trailer block is not enforced
at commit time, which can silently corrupt trailers (e.g., a blank line
between `Task-Ref:` and `Co-Authored-By:` that causes git to discard
`Task-Ref` as a non-trailer).

**Mitigating factor:** Both commits already have correct, contiguous
trailer blocks (`check-all-commits-have-task-ref.sh` passes), so no
actual corruption occurred. The risk was real but did not materialise.

**Actionable fix (no code changes required):**

```bash
bash .hyperloop/checks/install-git-commit-msg-hook.sh
# verify existing commits are intact
bash .hyperloop/checks/check-all-commits-have-task-ref.sh
# re-run the suite
bash .hyperloop/checks/check-run-backend-suite.sh
```

After installing the hook and confirming the trailer check still passes,
resubmit for re-verification. No commit amendments should be necessary
since the trailers are already valid.