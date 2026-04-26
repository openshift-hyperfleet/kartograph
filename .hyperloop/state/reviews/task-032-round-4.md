---
task_id: task-032
round: 4
role: spec-reviewer
verdict: fail
---
## Task-032 — Groups Feature — Round 9

Branch: `hyperloop/task-032`
Spec: `specs/iam/groups.spec.md`
Date: 2026-04-26

---

### Summary

Spec implementation is complete and all 2478 unit tests pass. However, two
process checks FAIL, blocking the verdict. The round-8 PASS verdict was
incorrect — the check scripts were not re-run against the actual alpha HEAD
at submission time.

**Verdict: FAIL**

---

### Failing Process Checks

1. **FAIL: check-branch-rebased-on-alpha**
   - Branch is **30 commits behind** current alpha HEAD (`7a8b7122`).
   - Alpha has advanced significantly since the last rebase (`e5a53916`).
   - Fix: `git rebase alpha` and resolve any conflicts.

2. **FAIL: check-no-state-file-commits**
   - Merge-base is `48a74d7d`, not current alpha HEAD.
   - Four `.hyperloop/state/` files added on this branch are not present on
     alpha at the merge-base:
     - `.hyperloop/state/intake/2026-04-25-eighth-run.md`
     - `.hyperloop/state/intake/2026-04-25-ninth-run.md`
     - `.hyperloop/state/intake/2026-04-25-seventh-run.md`
     - `.hyperloop/state/tasks/task-038.md`
   - Fix (per check script output):
     1. `git log --oneline --diff-filter=A,M -- '.hyperloop/state/**' $(git merge-base HEAD alpha)..HEAD`
     2. Strip offending commits via interactive rebase.
     3. Verify: `git diff --name-only $(git merge-base HEAD alpha)..HEAD -- '.hyperloop/state/'`
     4. Then rebase onto alpha HEAD.

---

### Required Remediation (in order)

1. Remove the four `.hyperloop/state/` file commits from branch history
   (interactive rebase to drop or edit the offending commits).
2. Rebase onto current alpha HEAD (currently `7a8b7122`).
3. Re-run both failing checks and confirm PASS:
   - `bash .hyperloop/checks/check-branch-rebased-on-alpha.sh`
   - `bash .hyperloop/checks/check-no-state-file-commits.sh`
4. Re-run full unit suite to confirm 2478/2478 still pass.

---

### Spec Coverage (all COVERED — implementation is complete)

| Requirement | Status |
|---|---|
| Group Creation — ULID generated, creator gets `admin` role | COVERED |
| Group Creation — duplicate name in tenant returns 409 | COVERED |
| Group Name Validation — 1–255 chars (trimmed) accepted | COVERED |
| Group Name Validation — empty/whitespace returns 422 | COVERED |
| Group Retrieval — authorized user returns 200 with details | COVERED |
| Group Retrieval — unauthorized/non-existent returns 404 | COVERED |
| Group Listing — only groups with `view` permission returned | COVERED |
| Group Rename — `manage` permission, unique name succeeds | COVERED |
| Group Rename — duplicate name returns 409 | COVERED |
| Group Deletion — `manage` permission, member snapshot captured | COVERED |
| Member Add — `manage` permission, `member` role granted | COVERED |
| Member Role Change — old role revoked, new granted | COVERED |
| Member Remove — role revoked | COVERED |
| Last-admin guard — demote or remove last admin rejected | COVERED |
| Member Listing — `view` permission returns all members with roles | COVERED |
| Workspace Access Inheritance — group→workspace role propagation | COVERED |
| Member added after group assigned to workspace gets workspace perms | COVERED |
| Member removed from group loses inherited workspace permissions | COVERED |
| Group Roles — admin has `manage`+`view`, included in workspace inheritance | COVERED |
| Group Roles — member has `view`, included in workspace inheritance | COVERED |

**Key implementation files:**
- `iam/domain/aggregates/group.py` — aggregate with all domain logic
- `iam/application/services/group_service.py` — application service
- `iam/presentation/groups/routes.py` — FastAPI route handlers
- `iam/presentation/groups/models.py` — request/response models
- `shared_kernel/authorization/spicedb/schema.zed` — SpiceDB schema
- `tests/unit/iam/` — unit test suite
- `tests/integration/iam/` — integration test suite

---

### Check Script Results

| Check | Result |
|---|---|
| check-branch-rebased-on-alpha | **FAIL** (30 commits behind alpha) |
| check-no-state-file-commits | **FAIL** (4 state files committed; merge-base stale) |
| check-branch-has-commits | PASS |
| check-no-check-script-deletions | PASS |
| check-cross-task-deferral | PASS |
| check-no-test-regressions | PASS |
| check-no-source-regressions | PASS |
| check-no-future-placeholder-comments | PASS |
| check-no-coming-soon-stubs | PASS |
| check-process-overlays-intact | PASS |
| check-existing-verdict | PASS |
| check-domain-aggregate-mocks | PASS |
| check-weak-test-assertions | PASS |
| check-empty-test-stubs | PASS |
| check-no-direct-logger-usage | PASS |
| check-domain-exception-http-mapping | PASS |
| check-fake-success-notifications | PASS |
| check-route-handler-mock-coverage | PASS |
| check-partial-error-assertions | PASS |
| check-task-branch-exists | PASS |
| Unit tests (2478) | PASS |