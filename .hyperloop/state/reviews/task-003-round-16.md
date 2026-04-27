---
task_id: task-003
round: 16
role: verifier
verdict: fail
---
## Worker Result — task-003 (specs/graph/mutations.spec.md)

Worker: verifier
Date: 2026-04-27
Run: 3 (re-verification after prior FAIL ×2)

---

### Verification Checks

#### 1. Unit Tests — PASS
All 2603 tests pass (83.18s). Zero failures, zero errors.

#### 2. Linting (ruff check) — PASS
Zero violations across all source files.

#### 3. Formatting (ruff format --check) — PASS
All 502 files are correctly formatted.

#### 4. Type Checking (mypy) — PASS
`Success: no issues found in 502 source files`

#### 5. Architecture Boundary Tests — PASS
All 40 archon tests pass. DDD layer boundaries enforced across Graph,
Query, IAM, Shared Kernel, and Outbox contexts.

#### 6. Integration Tests — SKIPPED
No infrastructure stack available. Unit tests provide full spec coverage.

#### 7. Code Review — PASS (implementation quality)
- No direct `logger.*` or `print()` calls in implementation files
- No bare `MagicMock`/`AsyncMock` on domain collaborators — fakes used throughout
- No imports violating DDD layer rules
- No hardcoded secrets or credentials
- No stub markers, no future-placeholder comments, no empty test stubs
- No weak test assertions, no test regressions

#### 8. Check Scripts — FAIL

**Backend suite result: 3 failures**

```
PASSED (22):
  ✓ check-no-check-script-deletions.sh
  ✓ check-process-overlays-intact.sh
  ✓ check-branch-has-commits.sh
  ✓ check-alpha-local-vs-remote.sh
  ✓ check-branch-rebased-on-alpha.sh
  ✓ check-no-state-file-commits.sh
  ✓ check-no-source-regressions.sh
  ✓ check-no-route-handler-removals.sh
  ✓ check-no-test-regressions.sh
  ✓ check-empty-test-stubs.sh
  ✓ check-domain-aggregate-mocks.sh
  ✓ check-no-direct-logger-usage.sh
  ✓ check-no-coming-soon-stubs.sh
  ✓ check-weak-test-assertions.sh
  ✓ check-di-wiring-updated.sh
  ✓ check-event-handlers-registered.sh
  ✓ check-domain-events-have-consumers.sh
  ✓ check-pytest-env-skip-if-set.sh
  ✓ check-cascade-delete-cleanup.sh
  ✓ check-cascade-delete-empty-collection-mocks.sh
  ✓ check-unused-fixtures.sh
  ✓ check-no-future-placeholder-comments.sh

FAILED (3):
  ✗ check-new-checks-pass-on-head.sh
  ✗ check-worker-result-not-committed.sh (MISSING)
  ✗ check-no-foreign-task-commits.sh
```

---

### Finding 1 — FAIL: Foreign task commits on branch (BLOCKER, unchanged from runs 1 and 2)

`check-no-foreign-task-commits.sh` detects **7 foreign commits** (non-task-003
`Task-Ref` values) on the branch beyond alpha:

```
cf27f9f631  Task-Ref=task-032     feat(iam): enforce last-admin protection in group member management (#476)
1ebcfab146  Task-Ref=process-improvement  chore(process): enforce non-empty cascade test ordering to prevent task-032 pattern
20f156bfcb  Task-Ref=process-improvement  test(iam): add non-empty cascade-delete coverage for TestDeleteTenant
aea8b82f63  Task-Ref=intake       chore(intake): record run 50 — no tasks for NFR and index specs
fcf7ae791e  Task-Ref=intake       chore(intake): record run 44 — no tasks for NFR and index specs
793103939e  Task-Ref=intake       chore(intake): record run 50 — no tasks for NFR and index specs
f6d4d5bc77  Task-Ref=intake       chore(intake): record run 44 — no tasks for NFR and index specs
```

None of these commits are on `alpha`. All are foreign to task-003.

`cf27f9f631` (task-032) is the primary foreign implementation commit — it brings
in last-admin protection work from task-032 that has no relationship to mutations.

The `intake` and `process-improvement` commits are orchestrator-managed commits
that were included in the branch via a bad rebase; they do not belong on a task
branch.

**Root cause** (same as previous runs): The branch was rebased against a stale
`origin/alpha` rather than local `alpha`, which caused commits from other
in-flight tasks (task-032, intake/process-improvement) to be included.

**Fix required:**

```bash
# 1. Identify all task-003-only commits (Task-Ref: task-003)
git log --format="%H %(trailers:key=Task-Ref,valueonly=true)" alpha..HEAD \
  | awk '$2 == "task-003" {print $1}'

# 2. Create a clean branch from current local alpha
git checkout alpha
git checkout -b hyperloop/task-003-clean

# 3. Cherry-pick ONLY the task-003 commits (skip cf27f9f631, 1ebcfab146,
#    20f156bfcb, aea8b82f63, fcf7ae791e, 793103939e, f6d4d5bc77, and
#    any verifier/worker-result commits)
git cherry-pick <sha1> <sha2> ...

# 4. Force-push to replace the remote branch
git push --force-with-lease origin hyperloop/task-003-clean:hyperloop/task-003
```

### Finding 2 — FAIL: check-new-checks-pass-on-head.sh (new bug in run 3)

`check-cited-tests-exist.sh` (introduced by this branch) fails when run by
`check-new-checks-pass-on-head.sh`. **This is a false positive caused by a
stdin-inheritance bug in `check-new-checks-pass-on-head.sh`.**

Root cause: `check-new-checks-pass-on-head.sh` iterates over new check scripts
via `while IFS= read -r check_path; do ... done <<< "$new_checks"`. When it
calls `bash check-cited-tests-exist.sh` within this loop, the child process
inherits the parent's stdin (the here-string). Since `check-cited-tests-exist.sh`
reads from stdin when no arguments are given (via `mapfile -t test_names`), it
reads the remaining here-string content — specifically the next script path
`.hyperloop/checks/check-fake-success-notifications.sh` — and interprets it as
a test function name to look up. The grep finds no `def .hyperloop/checks/...`
in `src/api/tests`, so it exits 1.

**Fix:** In `check-new-checks-pass-on-head.sh`, redirect stdin to `/dev/null`
when running child scripts:

```bash
# Change:
if bash "$check_path"; then
# To:
if bash "$check_path" < /dev/null; then
```

This is a real bug in the check script that this branch introduced, so it counts
as a FAIL even though the underlying behavior of `check-cited-tests-exist.sh` is
correct.

### Finding 3 — PRE-EXISTING: check-worker-result-not-committed.sh (MISSING)

This script is listed in the backend suite catalogue but does not exist on alpha
or on this branch. This is a pre-existing alpha issue, not a regression from
task-003. `check-no-check-script-deletions.sh` passes because the file was never
present on alpha.

---

### Commit Trailers

Most task-003 implementation commits carry proper `Spec-Ref` and
`Task-Ref: task-003` trailers. The foreign commits have their own trailers
(`Task-Ref: task-032`, `Task-Ref: intake`, `Task-Ref: process-improvement`).
Verifier commits in this run are untrailered (not implementation commits).

---

### Implementation Quality Summary

The mutations implementation (ignoring foreign commit contamination) is
well-structured and covers all spec requirements:

- **DEFINE, CREATE, UPDATE, DELETE** operations with correct ordering
  (DEFINE → DELETE → CREATE → UPDATE)
- **Tenant graph isolation** via `tenant_{tenant_id}` AGE graph routing
- **KnowledgeGraph scoping** with SpiceDB authorization check (`edit` permission)
- **knowledge_graph_id stamping** on CREATE/UPDATE; caller-supplied value rejected
- **System properties** (`data_source_id`, `source_path`, `slug`, `knowledge_graph_id`)
  enforced as mandatory for CREATE
- **Idempotent CREATE merge** using JSONB `||` operator for property accumulation
- **Schema learning** on CREATE and UPDATE operations
- **Domain probes** used throughout; no `logger.*` or `print()` calls
- **FakeAuthorizationProvider** replaces AsyncMock in all route tests

The implementation is high quality. There are two blockers:
1. Foreign commit contamination (7 commits with wrong Task-Ref) must be excised.
2. `check-new-checks-pass-on-head.sh` has a stdin-leak bug that must be fixed.