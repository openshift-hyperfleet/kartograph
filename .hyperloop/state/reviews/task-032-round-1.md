---
task_id: task-032
round: 1
role: verifier
verdict: fail
---
## Task-032 — Groups Feature Verification (Re-Review)

Branch: `hyperloop/task-032`
Spec: `specs/iam/groups.spec.md@b46589a2`
Date: 2026-04-25

---

### Summary

The Groups feature implementation is complete and correct in all functional
respects. All 2460 unit tests pass, linting is clean, mypy has zero errors,
and architecture boundary tests all pass. However, the branch fails the
**`check-branch-rebased-on-alpha.sh`** check: it is **12 commits behind
the local `alpha` branch**, which prevents clean merging.

---

### Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2460) | PASS | All passed in ~64s |
| ruff check | PASS | 0 violations |
| ruff format | PASS | 483 files already formatted |
| mypy | PASS | 0 errors in 483 source files |
| Architecture boundary tests (40) | PASS | IAM context isolation enforced |
| check-branch-rebased-on-alpha | **FAIL** | 12 commits behind local `alpha` |
| check-no-state-file-commits | FAIL* | False positive from stale merge-base |
| check-no-check-script-deletions | FAIL* | Pre-existing on `alpha` too (not introduced here) |
| check-empty-test-stubs | FAIL* | `test_create_api_key_requires_tenant_membership` — pre-existing on `alpha` |
| check-auth-status-codes | REVIEW* | 403 assertions pre-exist on `alpha` |
| check-cross-task-deferral | PASS | |
| check-domain-aggregate-mocks | PASS | |
| check-no-test-regressions | PASS | |
| check-no-source-regressions | PASS | |
| check-no-future-placeholder-comments | PASS | |
| check-no-coming-soon-stubs | PASS | |
| check-weak-test-assertions | PASS | |

\* Failures marked with `*` are pre-existing on local `alpha` or are
false positives caused by the stale merge-base. They are **not** introduced
by this task branch.

---

### Root Cause: Stale Branch

The local `alpha` branch is at `7a1c69c3` (12 commits ahead of where this
branch diverged). The `check-branch-rebased-on-alpha.sh` script compares
against the **local** `alpha` (not `origin/alpha`). The 12 commits on local
`alpha` that this branch is missing are all orchestrator-level chores:

```
7a1c69c3 chore(intake): no new tasks — batch identical to prior run
...
971d0247 chore(process): enforce DOO mandate with direct-logger check and overlay rules
ce482a01 chore(intake): no new tasks — all specs in batch already covered
```

None of these touch implementation source code, but they include:
- Additional `.gitignore` entry for `.hyperloop/state/` (added in `971d0247`)
- Process overlay updates

The `.gitignore` conflict was confirmed: local `alpha` adds `.hyperloop/state/`
to `.gitignore`; this branch does not have that entry.

---

### Required Fix

**Action: `git rebase alpha`**

1. From the `hyperloop/task-032` branch, run `git rebase alpha`
2. Resolve any conflicts (expected: `.gitignore` — accept alpha's version to
   include `.hyperloop/state/` as an ignored path)
3. After rebase, re-run all checks — the `check-branch-rebased-on-alpha`,
   `check-no-state-file-commits`, and `check-no-check-script-deletions`
   failures should resolve automatically (as alpha itself passes or they
   become no longer attributable to this branch's diff)
4. Re-commit the `worker-result.yaml` with updated verdict if all checks pass

---

### Implementation Quality (Unblocked by Staleness)

The Groups implementation is fully spec-compliant:

**Domain** (`iam/domain/aggregates/group.py`):
- `Group` aggregate with `create()` factory, `add_member()`, `remove_member()`,
  `update_member_role()`, `rename()`, `mark_for_deletion()`, `collect_events()`
- Business rules: last-admin guard, name validation, duplicate member prevention
- Domain events: `GroupCreated`, `GroupDeleted`, `MemberAdded`, `MemberRemoved`,
  `MemberRoleChanged` (with `MemberSnapshot` for deletion cleanup)
- No direct logger/print usage; `GroupServiceProbe` used for DOO observability

**Ports** (`iam/ports/repositories.py`):
- `IGroupRepository` protocol: `save`, `get_by_id`, `get_by_name`,
  `list_by_tenant`, `delete`

**Application** (`iam/application/services/group_service.py`):
- Full use-case orchestration: create, get, list, delete, member CRUD
- SpiceDB permission checks (VIEW, MANAGE) before every mutating operation
- Tenant scoping enforced on every operation

**Presentation** (`iam/presentation/groups/`):
- FastAPI routes covering all spec scenarios
- Correct status codes: 201, 204, 404, 409, 403

**Commit trailers**: Both commits on this branch have `Spec-Ref` and
`Task-Ref` trailers. ✓

---

### Spec Coverage (All 18 Scenarios)

All requirements from `specs/iam/groups.spec.md` are covered by unit tests
that pass. The only action needed is the rebase.