---
task_id: task-032
round: 3
role: spec-reviewer
verdict: fail
---
## Task-032 — Groups Feature — Verification (Round 7)

Branch: `hyperloop/task-032`
Spec: `specs/iam/groups.spec.md`
Date: 2026-04-26

---

### Summary

The Groups spec implementation is complete and all unit tests pass (2478/2478).
However two process checks FAIL, preventing a pass verdict:

1. **FAIL: check-branch-rebased-on-alpha** — Branch merge-base is `48a74d7d`;
   alpha HEAD is `49529f11`. The branch is 25 commits behind alpha (threshold
   is 5). A rebase is required.

2. **FAIL: check-no-state-file-commits** — The following orchestrator-managed
   state files are committed on this branch (must never appear in task branches):
   - `.hyperloop/state/intake/2026-04-25-eighth-run.md`
   - `.hyperloop/state/intake/2026-04-25-ninth-run.md`
   - `.hyperloop/state/intake/2026-04-25-seventh-run.md`
   - `.hyperloop/state/tasks/task-038.md`

**Verdict: FAIL**

---

### Required Remediation

1. Remove state file commits from the branch history (interactive rebase to
   drop the commits that added `.hyperloop/state/` files, or reset from alpha
   and cherry-pick only task commits).
2. Rebase onto current alpha HEAD (`49529f11`).
3. Re-run all check scripts to confirm 0 failures before resubmitting.

---

### Spec Coverage (all COVERED — implementation is complete)

| Requirement | Status |
|---|---|
| Group Creation — ULID generated, creator gets admin | COVERED |
| Group Creation — duplicate name in tenant returns 409 | COVERED |
| Group Name Validation — 1–255 chars (trimmed) accepted | COVERED |
| Group Name Validation — empty/whitespace returns 422 | COVERED |
| Group Retrieval — authorized user returns 200 with details | COVERED |
| Group Retrieval — unauthorized/non-existent returns 404 | COVERED |
| Group Listing — only groups with view permission returned | COVERED |
| Group Rename — manage permission, unique name succeeds | COVERED |
| Group Rename — duplicate name returns 409 | COVERED |
| Group Deletion — manage permission, member snapshot captured | COVERED |
| Member Add — manage permission, role assigned | COVERED |
| Member Role Change — old role revoked, new granted | COVERED |
| Member Remove — role revoked | COVERED |
| Last-admin guard — demote or remove last admin rejected | COVERED |
| Member Listing — view permission returns all members with roles | COVERED |
| Workspace Access Inheritance — group→workspace role propagation | COVERED |
| Member added after group assigned to workspace gets workspace perms | COVERED |
| Member removed from group loses inherited workspace permissions | COVERED |

---

### Check Script Results

| Check | Result |
|---|---|
| check-branch-rebased-on-alpha | **FAIL** (25 commits behind) |
| check-no-state-file-commits | **FAIL** (4 state files committed) |
| check-branch-has-commits | PASS (62 ahead of alpha) |
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
| check-route-handler-mock-coverage | PASS (2 warnings, no blocking failures) |
| check-partial-error-assertions | PASS |
| check-task-branch-exists | PASS |
| Unit tests (2478) | PASS |