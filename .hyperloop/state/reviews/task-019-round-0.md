---
task_id: task-019
round: 0
role: verifier
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 7)

Branch contamination persists across all rounds. This round also surfaces a NEW
concern: the task-019 branch has WEAKER tests than what alpha already carries,
meaning cherry-picking as recommended in prior rounds would REGRESS alpha.

---

## Check Results

| Check | Result |
|---|---|
| Unit tests (2468 passed) | PASS |
| Ruff linting | PASS |
| Ruff formatting | PASS |
| mypy type checking (0 errors, 495 files) | PASS |
| Architecture boundary tests (40 passed) | PASS |
| check-no-direct-logger-usage.sh | PASS |
| check-domain-aggregate-mocks.sh | PASS |
| check-empty-test-stubs.sh | PASS |
| check-no-coming-soon-stubs.sh | PASS |
| check-cascade-delete-empty-collection-mocks.sh | PASS |
| check-no-check-script-deletions.sh | PASS |
| check-process-overlays-intact.sh | PASS |
| check-no-source-regressions.sh | PASS |
| check-no-test-regressions.sh | PASS (from merge-base; see note below) |
| check-di-wiring-updated.sh | PASS |
| check-pytest-env-skip-if-set.sh | PASS |
| check-all-commits-have-task-ref.sh | PASS |
| **check-branch-rebased-on-alpha.sh** | **FAIL** (11 commits behind alpha) |
| **check-no-state-file-commits.sh** | **FAIL** (.hyperloop/state/intake/2026-04-27-nfr-specs.md) |
| **check-no-foreign-task-commits.sh** | **FAIL** (3 foreign commits: process-improvement ×2, intake ×1) |
| **check-new-checks-pass-on-head.sh** | **FAIL** (check-worker-result-not-committed.sh detects 07a0ac83f) |

---

## Critical Finding: Implementation Already Merged to Alpha

Alpha now contains `4f4c54a5f feat(management): implement Fernet credential key
rotation without re-encryption (#478)` (Task-Ref: task-034), which includes
IDENTICAL source changes to what's on this branch:

- `management/application/services/knowledge_graph_service.py` — identical (0 diff vs alpha)
- `management/dependencies/knowledge_graph.py` — identical (0 diff vs alpha)

All spec requirements are therefore already satisfied on alpha. The task-019
branch's unique contribution is test modifications only.

---

## NEW: Test Regressions vs Alpha (round 7 finding)

The test changes on this branch are WEAKER than what alpha already has.
`check-no-test-regressions.sh` reported PASS because it compares from the
merge-base (be25b37a3, pre-4f4c54a5f), not from current alpha. The actual
regression is:

**`test_fernet_secret_store.py`**: Branch (339 lines) < alpha (356 lines)

Tests PRESENT on alpha but ABSENT on this branch:
- `test_delete_with_wrong_tenant_does_not_delete` — verifies delete() with wrong
  tenant_id finds no row and returns False (covers a distinct defense-in-depth path)

Tests WEAKER on branch vs alpha:
- `test_same_path_different_tenant_raises_key_error` — alpha's version also
  verifies tenant-A CAN retrieve (tests both directions); branch only tests
  tenant-B cannot (missing positive case confirmation in the same test)

If prior rounds' recommendation is followed (cherry-pick delivery commits onto
clean branch from alpha), these weaker tests would REPLACE alpha's stronger
tests, regressing the suite.

**Other test changes** (vs alpha):
- `test_tenant_service.py`: renames test, removes `assert result is True`,
  replaces list-based assertions with `assert_any_call` — minor style change,
  functionally neutral
- `test_knowledge_graph_service.py`: renames test, extracts shared fixture —
  structural refactor, no coverage change

---

## Foreign Commits on Branch (FAIL)

```
FOREIGN: bac124e35c  Task-Ref=process-improvement
         chore(process): enforce Task-Ref trailers and prohibit direct duplicate-test edits
FOREIGN: b2309fc27a  Task-Ref=intake
         docs(intake): record NFR spec review — no tasks created
FOREIGN: 38865dd8b0  Task-Ref=process-improvement
         fix(process): fix stdin-leak in new-check runner; enforce local-alpha rebase
```

---

## State File in Branch History (FAIL)

`.hyperloop/state/intake/2026-04-27-nfr-specs.md` was added by a commit on
this branch. State files are orchestrator-managed and must never appear in
task-branch history.

---

## Worker-Result Committed (FAIL)

Commit `07a0ac83f chore(task-019): write worker verdict — pass` contains
`.hyperloop/worker-result.yaml` in branch history. This file must ONLY exist
as an uncommitted working-directory artifact; committing it contaminates the
branch and causes the new `check-worker-result-not-committed.sh` check to fail.

---

## Required Fix (Updated for Round 7)

Given that alpha already has the complete implementation (from task-034), the
orchestrator must determine the correct disposition. Options:

**Option A — Close task-019 as superseded.**
Alpha already satisfies all spec requirements. The task-019 branch's test
changes would regress alpha if merged. Recommended if task-034 is confirmed
to have been the canonical delivery.

**Option B — Cherry-pick ONLY the non-regressing test changes onto alpha.**
If unique task-019 test additions are desired:
1. Identify which test additions don't conflict with or regress alpha's existing tests
2. `test_knowledge_graph_service.py` refactor (fixture extraction) — safe to cherry-pick
3. `test_tenant_service.py` simplification — largely safe (minor regression: removes `result is True` assertion)
4. `test_fernet_secret_store.py` TestTenantIsolation — **DO NOT cherry-pick**; would remove alpha's stronger tests

**Option C — Full branch rebuild from current alpha (if unique work remains).**
```bash
git fetch origin alpha
git checkout -b hyperloop/task-019-v2 origin/alpha
# Cherry-pick ONLY the fixture refactor and non-regressing test additions
# Verify: git diff origin/alpha HEAD -- src/ shows ONLY additions, no regressions
bash .hyperloop/checks/check-branch-rebased-on-alpha.sh    # expect PASS
bash .hyperloop/checks/check-no-state-file-commits.sh       # expect PASS
bash .hyperloop/checks/check-no-foreign-task-commits.sh     # expect PASS
bash .hyperloop/checks/check-new-checks-pass-on-head.sh     # expect PASS
uv run pytest tests/unit -q                                  # expect all pass
git push --force-with-lease origin HEAD:hyperloop/task-019
```

This fix must be performed by the orchestrator — force-pushing to
`hyperloop/task-019` is beyond the spec reviewer's scope.