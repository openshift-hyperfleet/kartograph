---
task_id: task-013
round: 2
role: verifier
verdict: fail
---
## Task-013 Verification — specs/ingestion/sync-lifecycle.spec.md

**Re-verification required.** The prior PASS verdict (commit 9edfb80d) was recorded on a
contaminated, stale branch. This run discovers the branch fails four check scripts and
mypy type checking. The underlying implementation is correct but the branch must be
cleaned before the verdict can become PASS.

---

## Check Results

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Unit tests (2567) | **PASS** | All green |
| 2 | Ruff linting | **PASS** | Zero violations |
| 3 | Ruff formatting | **PASS** | 528 files already formatted |
| 4 | mypy type checking | **FAIL** | 6 errors (see below) |
| 5 | Architecture boundary tests (40) | **PASS** | All green |
| — | check-no-state-file-commits.sh | **FAIL** | 28 `.hyperloop/state/intake/` files on branch |
| — | check-no-foreign-task-commits.sh | **FAIL** | 9 foreign commits (Task-Ref: intake / process-improvement) |
| — | check-branch-rebased-on-alpha.sh | **FAIL** | Branch is 22 commits behind local `alpha` |
| — | check-no-direct-logger-usage.sh | **FAIL** | `print()` in `src/api/query/presentation/mcp.py:197` |
| — | check-domain-aggregate-mocks.sh | PASS | Zero violations |
| — | check-no-coming-soon-stubs.sh | PASS | Zero markers |
| — | check-no-source-regressions.sh | PASS | Clean |
| — | check-service-route-coverage.sh | PASS | All CRUD routes covered |
| — | Commit trailers (Spec-Ref / Task-Ref) | PASS | Present on all delivery commits |

---

## Failure Details

### FAIL 1 — mypy (check #4)

```
src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py:231:
  error: Module has no attribute "HTTP_422_UNPROCESSABLE_CONTENT"  [attr-defined]
  (same error at lines 247, 644, 660)

src/api/query/presentation/mcp.py:26:
  error: Need type annotation for "mcp"  [var-annotated]
src/api/query/presentation/mcp.py:214:
  error: Unexpected keyword argument "annotations" for "resource" of "FastMCP"  [call-arg]
```

**Root cause:** Branch is 22 commits behind `alpha`. Alpha already carries fixes
for both files (`7359aaf3 fix(query): replace print() in docstring…`,
`a7f5a7e0 fix: resolve all backend check suite failures after alpha merge`).
Rebasing onto `alpha` will incorporate those fixes and clear these errors.
Neither file was touched by any task-013 commit.

### FAIL 2 — check-no-direct-logger-usage.sh

`src/api/query/presentation/mcp.py:197: print(source["content"])`

Same root cause as mypy FAIL: this `print()` in a docstring example was already
removed on `alpha` (commit `7359aaf3`) but is absent from this stale branch.

### FAIL 3 — check-no-state-file-commits.sh

28 `.hyperloop/state/intake/` files (e.g. `2026-04-26-index-and-nfr-specs-run4.md`
through `run28.md`, plus several consolidated entries) appear in branch commits.
These were written by orchestrator intake processes during parallel runs and
inadvertently rebased onto this branch when the implementer used
`git rebase origin/alpha` instead of `git rebase alpha`.

### FAIL 4 — check-no-foreign-task-commits.sh

9 commits with `Task-Ref: intake` or `Task-Ref: process-improvement` are present
on this branch for the same reason: stale `origin/alpha` rebase contamination.

---

## Implementation Quality (separate from branch hygiene)

The task-013 delivery commits themselves are **correct**. All 11 spec scenarios
are addressed:

| Requirement | Scenario | Status |
|---|---|---|
| Sync Orchestration | Successful sync | COVERED |
| Sync Orchestration | Extraction failure | COVERED |
| Lifecycle State Machine | State transitions (all 7) | COVERED |
| Lifecycle State Machine | Terminal states | COVERED |
| Event-Driven Side Effects | Status updates | COVERED |
| Event-Driven Side Effects | Extraction trigger | COVERED |
| Event-Driven Side Effects | Mutation trigger | COVERED |
| Sync Initiation | Manual trigger | COVERED |
| Sync Initiation | Scheduled trigger (INTERVAL) | COVERED |
| Staleness-Based Node Lifecycle | Stale node detection | COVERED |
| Staleness-Based Node Lifecycle | Active node | COVERED |

No bare MagicMock/AsyncMock on domain aggregates. DOO probes used correctly in all
task-013 files. No hardcoded secrets. Architecture boundaries clean.

---

## Required Fix (cherry-pick onto clean alpha base)

All four failures are resolved by cleaning the branch. The check scripts give
the exact procedure; follow them precisely:

```bash
# Step 1 — identify the task-013 delivery commits
git log --oneline $(git merge-base HEAD alpha)..HEAD

# Step 2 — create a fresh branch from current local alpha
git checkout alpha
git checkout -b hyperloop/task-013-clean

# Step 3 — cherry-pick only the task-013 commits (commits with Task-Ref: task-013
#           or no Task-Ref; skip all intake/process-improvement commits)
git cherry-pick b4e1bdc8 25935a07 e733f4ec 9865a1dd 08905505 \
               34be3c53 d8803c5e 9f52f84a adad4387 6d10d6ef

# Step 4 — verify
bash .hyperloop/checks/check-no-state-file-commits.sh
bash .hyperloop/checks/check-no-foreign-task-commits.sh
bash .hyperloop/checks/check-branch-rebased-on-alpha.sh
bash .hyperloop/checks/check-no-direct-logger-usage.sh
cd src/api && uv run mypy . --config-file pyproject.toml --ignore-missing-imports

# Step 5 — force-push to preserve PR / orchestrator state
git push origin hyperloop/task-013-clean:hyperloop/task-013 --force-with-lease
```

After the cherry-pick onto current `alpha` the mypy errors, print() violation,
state-file commits, and foreign-task commits will all be gone. Unit tests and
architecture checks will continue to pass. Record a new PASS verdict.