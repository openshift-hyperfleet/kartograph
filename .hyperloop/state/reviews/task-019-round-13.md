---
task_id: task-019
round: 13
role: verifier
verdict: fail
---
# Verification — specs/management/credentials.spec.md (task-019)

## Summary

**FAIL.** Two automated checks are failing, and a foreign-task commit is present
on this branch. The spec implementation is substantively correct, but the linting
and type-checking gates must pass before this can be accepted.

---

## Check Results

| Check | Result | Detail |
|---|---|---|
| Unit tests (2565 tests) | PASS | All pass |
| Linting (ruff check) | **FAIL** | F811: duplicate `test_delete_cascades_encrypted_credentials` |
| Formatting (ruff format --check) | PASS | 500 files formatted |
| Type checking (mypy) | **FAIL** | no-redef: same duplicate |
| Architecture boundary tests (40 tests) | PASS | All pass |
| check-no-check-script-deletions | PASS | |
| check-process-overlays-intact | PASS | |
| check-branch-has-commits | PASS | 6 commits |
| check-branch-rebased-on-alpha | PASS | 0 commits behind |
| check-no-state-file-commits | PASS | |
| check-no-source-regressions | PASS | |
| check-no-test-regressions | PASS | |
| check-no-route-handler-removals | **FAIL** | Detects Python function renames as removals (see analysis) |
| check-alpha-local-vs-remote | MISSING | Script absent from both branch and alpha — not a regression |
| check-worker-result-not-committed | MISSING | Script absent from both branch and alpha — not a regression |
| check-no-foreign-task-commits | MISSING | Script absent from both branch and alpha — not a regression |

---

## Finding 1 — Ruff + Mypy FAIL: Duplicate Test Function (BLOCKING)

**File:** `src/api/tests/unit/management/application/test_knowledge_graph_service.py`

Two methods with the identical name `test_delete_cascades_encrypted_credentials`
exist in class `TestKnowledgeGraphServiceDelete`:

- **Line 677–738** (commit `9d2725382`): uses `service_with_secret_store` fixture;
  asserts `secret_store.delete()` is called for each DS with a `credentials_path`.
- **Line 785–839** (commit `bab540b928`, Task-Ref: task-032): uses `service` fixture;
  a different (weaker) variant of the same test.

Python silently ignores the first definition; ruff detects this as F811 and fails.
Mypy raises a `no-redef` error for the same reason.

**Required fix:** Remove the second definition (line 785–839, from the `bab540b928`
commit). The version at line 677 (using `service_with_secret_store`) is the
correct task-019 test and covers the spec scenario more completely (3 data sources,
skips DS without credentials path, correct assertion counts).

---

## Finding 2 — Foreign Task Commit (BLOCKING in principle, but not caught by missing check)

Commit `bab540b928` (`feat(iam): enforce last-admin protection in group member
management (#476)`) carries `Task-Ref: task-032` and is present on this branch.
It changed 46 files with 3791 insertions covering IAM presentation, KG routes,
management dependencies, dev-ui, and more — none of which are task-019 scope.

The `check-no-foreign-task-commits.sh` script that would catch this is absent
from both the branch and alpha (a pre-existing infrastructure gap, not a regression
introduced by this branch).

However, the foreign commit's inclusion is the **root cause** of Finding 1: it
added a `test_delete_cascades_encrypted_credentials` method to the test file,
which then conflicted with the task-019 commit that added another method of the
same name.

**Required fix:** Either:
a) Remove only the duplicate test method (line 785–839) — the remainder of
   `bab540b928`'s changes appear to be valid code that the subsequent task-019
   commits depend on; OR
b) Full cherry-pick cleanup: rebuild the branch from current alpha with only
   the 5 task-019 commits (`2ed4f3e99`, `e993afe1b`, `3a136a070`, `d3e1b3e7f`,
   `9d2725382`) and verify the build succeeds without `bab540b928`.

Option (a) is the minimal fix that will unblock linting and type checking.

---

## Finding 3 — check-no-route-handler-removals (Analysis — Likely False Positive)

The check reports `list_knowledge_graphs`, `get_knowledge_graph`, and
`create_knowledge_graph` as removed.

Manual inspection shows:
- `GET /knowledge-graphs` is still present (served by `list_all_knowledge_graphs`)
- `GET /knowledge-graphs/{kg_id}` is still present (same function name)
- `POST /workspaces/{workspace_id}/knowledge-graphs` is still present (same function name)

The detected "removals" are:
1. `list_knowledge_graphs` renamed to `list_all_knowledge_graphs` — the URL endpoint
   is preserved; only the Python identifier changed. A new `list_knowledge_graphs`
   was added for `GET /workspaces/{workspace_id}/knowledge-graphs`.
2. `get_knowledge_graph` and `create_knowledge_graph` appear as diff `-` lines due
   to reordering in the file, not actual removal; both are present in HEAD.

The check script detects any `-async def foo(` line in the diff as a "removal"
without verifying the function exists in the final file. This is a known
false-positive pattern for renames and reorders.

**Assessment:** The API contract is preserved. This failure can be accepted as a
check script limitation **only if Finding 1 is fixed and Finding 2 is understood
by the orchestrator**. If the check is a hard gate, the implementer must either:
- Avoid renaming `list_knowledge_graphs` (restore original function name and make
  the new workspace-scoped listing use a different function name), OR
- Annotate the check with a justification mechanism (if one exists in the project).

---

## Spec Requirement Coverage (All Covered)

| Requirement | Status |
|---|---|
| Credential Encryption — Fernet store/retrieve | COVERED |
| Composite key (path, tenant_id) | COVERED |
| Not-found raises KeyError | COVERED |
| Tenant Isolation — same path, different tenant | COVERED |
| Key Rotation — MultiFernet fallback | COVERED |
| Credential Lifecycle — DS deletion removes credentials | COVERED |
| Credential Lifecycle — KG cascade deletes all DS credentials | COVERED |

---

## Required Fix (Minimal Path to PASS)

In `src/api/tests/unit/management/application/test_knowledge_graph_service.py`,
remove the second `test_delete_cascades_encrypted_credentials` definition
(lines 785–839, introduced by the task-032 foreign commit `bab540b928`).

After removal:
```bash
cd src/api
uv run ruff check .          # expect: no errors
uv run mypy . --config-file pyproject.toml --ignore-missing-imports  # expect: no errors
uv run pytest tests/unit -q  # expect: all pass
bash .hyperloop/checks/check-run-backend-suite.sh  # expect: only check-no-route-handler-removals still fails (false positive)
```

If `check-no-route-handler-removals` must also pass, additionally revert the
rename of `list_knowledge_graphs` → `list_all_knowledge_graphs` (i.e., keep the
original function name for the `GET /knowledge-graphs` handler).