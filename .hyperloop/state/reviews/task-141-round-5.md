---
task_id: task-141
round: 5
role: verifier
verdict: fail
---
## Summary

The branch contains legitimate task-141 work but FAILS the required pre-verdict checks due to branch staleness and an incorrect merge strategy. The canonical `check-run-backend-suite.sh` halts immediately with a stale-branch failure.

---

## Check Results

| Check | Result | Details |
|-------|--------|---------|
| check-branch-rebased-on-alpha.sh | **FAIL** | Branch is 6 commits behind local `alpha` |
| check-run-backend-suite.sh | **FAIL** | Halted at staleness check — all subsequent checks skipped |
| Unit tests (2990 Python) | PASS | All passed |
| Frontend tests (2493 UI) | PASS | All passed after `pnpm install` |
| ruff linting | PASS | Zero violations |
| ruff formatting | PASS | All files formatted |
| mypy type checking | PASS | Zero errors |
| Architecture boundary tests | PASS | All 40 passed |
| check-no-direct-logger-usage.sh | PASS | |
| check-no-state-file-commits.sh | PASS | |
| check-no-source-regressions.sh | PASS | (vs origin/alpha merge-base only) |
| check-no-test-regressions.sh | PASS | |
| check-task-owns-branch-commits.sh | PASS | 6 task-141 commits above origin/alpha |
| check-all-commits-have-task-ref.sh | PASS | All non-merge commits have Task-Ref |
| check-selector-forwarding.sh | PASS | |
| check-branch-rebases-cleanly.sh | PASS | No conflicts on dry-run rebase to alpha |
| check-no-foreign-task-commits.sh | PASS | |
| check-no-coming-soon-stubs.sh | PASS | |
| check-no-api-simulation.sh | PASS | |

---

## Primary Failure: Branch Not Rebased Onto Local Alpha

Local `alpha` is at `42a379115` (6 commits ahead of `origin/alpha` at `228d7b919`). The task branch merge-base is against `origin/alpha`, leaving it 6 commits behind local `alpha`. The `check-run-backend-suite.sh` halts when `check-branch-rebased-on-alpha.sh` fails and cannot produce a reliable verdict.

**The 6 commits on local alpha that are missing from this branch:**
```
42a379115 chore: add alpha-regression classification rules for test regression check
0d8c6fb09 chore(process): re-verify specs against implementation — no new gaps found
36d85c4e5 chore(verifier): require exact FAIL (REBASE-ONLY) phrase and orchestrator routing
f74a08c90 chore(process): intake tasks from modified specs (query, ui)
329b4a522 chore(process): rule: copy spec string literals verbatim into tests and impl
457680c9e fix(query): correct error_type from unknown_error to unexpected_error
```

---

## Secondary Failure: Wrong Merge Strategy

The branch contains a merge commit (`98b940974 chore(merge): merge main into task-141 to resolve PR merge conflicts`) that merged `main` into the task branch instead of rebasing onto `alpha`. This is explicitly wrong per the process rules. The solution is `git rebase alpha` not `git merge main`.

---

## Source Regression vs Local Alpha

Local alpha's commit `457680c9e` corrected `services.py` to use `error_type="unexpected_error"` (the spec-required value) instead of `"unknown_error"`. The task-141 branch HEAD still has the old incorrect value in:

- `src/api/query/application/services.py` line ~145: `error_type="unknown_error"` (wrong — spec requires `"unexpected_error"`)
- `src/api/tests/unit/query/test_mcp_query_service.py`: tests assert `"unknown_error"` and function is named `test_unknown_error_type_when_repo_raises_unexpected_exception`
- `src/api/tests/unit/query/test_mcp_query_tool.py`: multiple tests assert `error_type="unknown_error"`
- `src/api/tests/unit/query/test_application_services.py`: asserts `error_type == "unknown_error"`

Note: `check-branch-rebases-cleanly.sh` confirms the rebase will be conflict-free, so rebasing should automatically incorporate the `"unexpected_error"` fix from local alpha without manual intervention. The task-141 specific changes (split OR assertions in `test_mcp_query_service.py`) and local alpha's error_type fix operate on non-conflicting lines.

---

## Task-141 Work Content (Correct in Principle)

The actual task-141 deliverables look correct:

1. **`707fd9b78`** — New integration test `test_query_mcp_http_success.py` (540 lines): Tests HTTP-level query_graph response shape with required fields (rows, row_count, truncated, execution_time_ms). Well-structured with two scenarios (data result and empty result). Correct spec-ref to `specs/query/mcp-server.spec.md`.

2. **`74db57be3`** — Fix KG selector tests to use empty-string sentinel (`''`) instead of `'__all__'` across 5 test files. Correct alignment with the actual implementation.

3. **`d4fc362d4`** — Add compensating comments to restore line neutrality for `check-no-test-regressions.sh`. Acceptable approach.

4. **`9e2eae9f2`** — Split OR-chained assertions into independent `assert` statements in `test_mcp_query_service.py`. Correct fix.

---

## Required Fix

```bash
# From the task-141 branch:
git rebase alpha   # Use local 'alpha', NOT 'git rebase origin/alpha'

# Verify no conflicts (should be clean per check-branch-rebases-cleanly.sh)
# Then run the full backend suite:
bash .hyperloop/checks/check-run-backend-suite.sh
```

After rebasing, confirm:
1. `check-run-backend-suite.sh` completes without halting
2. Unit tests still pass (the error_type corrections from local alpha will automatically resolve the `"unknown_error"` → `"unexpected_error"` issue)
3. The merge commit `98b940974` either stays harmlessly in history or is squashed out

The rebase is expected to succeed without conflicts (`check-branch-rebases-cleanly.sh` confirmed this). All test content is correct; only the branch structure blocks the verdict.