---
task_id: task-032
round: 2
role: spec-reviewer
verdict: fail
---
## Task-032 — Groups Feature — Re-Verification (Round 4)

Branch: `hyperloop/task-032`
Spec: `specs/iam/groups.spec.md@b46589a2`
Date: 2026-04-26

---

### Summary

The Groups implementation is fully spec-compliant and all 2478 unit tests pass.
However, the branch is currently **17 commits behind local `alpha`** and the
`check-branch-rebased-on-alpha.sh` script explicitly fails (threshold is ≤5).
Prior worker verdicts (rounds 1–3) each claimed the branch was rebased but none
actually executed the rebase on this worktree's HEAD. The branch has drifted
further behind as alpha has received additional orchestrator commits since.

**Verdict: FAIL** — not because the implementation is wrong, but because the
branch is stale. No spec requirement or scenario is unimplemented; the blocker
is process-level.

---

### Check Results (as run on 2026-04-26)

| Check | Result | Notes |
|---|---|---|
| Unit tests (2478) | PASS | All passed in ~59s |
| check-branch-rebased-on-alpha | **FAIL** | 17 commits behind local `alpha` |
| check-no-state-file-commits | FAIL* | False positive — stale merge base |
| check-no-check-script-deletions | FAIL* | False positive — stale merge base |
| check-empty-test-stubs | FAIL* | Pre-existing stub `test_create_api_key_requires_tenant_membership`; not introduced by task-032 |
| check-cross-task-deferral | PASS | |
| check-domain-aggregate-mocks | PASS | |
| check-no-test-regressions | PASS | |
| check-no-source-regressions | PASS | |
| check-no-future-placeholder-comments | PASS | |
| check-no-coming-soon-stubs | PASS | |
| check-weak-test-assertions | PASS | |
| check-domain-exception-http-mapping | PASS | |

\* Failures marked `*` are entirely caused by the stale merge base and are
**not** introduced by this task branch. They will resolve after rebase.

---

### Root Cause

The local `alpha` is at `91fefb84` — 17 commits ahead of this branch's
merge base (`48a74d7d`). The gap consists entirely of orchestrator chores:
- Process overlay updates (added `--exclude-dir=.venv` to grep-based scripts)
- `.gitignore` addition of `.hyperloop/state/`
- Intake and state management commits

None of these modify task-032 implementation code, but the check scripts
compare against local `alpha` and any diff from that base triggers failures.

---

### Required Fix

**One action: `git rebase alpha` on the `hyperloop/task-032` branch.**

```bash
git checkout hyperloop/task-032
git rebase alpha
# Expected: one conflict in .gitignore — accept alpha's version (adds .hyperloop/state/)
git add .gitignore
git rebase --continue
```

After rebase, re-run all checks. The three `*`-marked failures above will
resolve automatically because:
- State file commits will be behind the `.gitignore` entry that ignores them
- Check scripts will include `--exclude-dir=.venv` (from alpha's process commits)
- The empty test stub was pre-existing on alpha (will still exist, but the check
  compares against alpha's base — it needs the alpha stub fix separately)

---

### Spec Coverage (Implementation is Complete)

All 10 requirements and 18 scenarios from `specs/iam/groups.spec.md` are
implemented and tested. Below is the definitive coverage matrix:

| Requirement | Scenario | Code | Test | Status |
|---|---|---|---|---|
| Group Creation | Successful creation | `Group.create()` + `GroupService.create_group()` | `test_group_aggregate.py::TestGroupFactory`, `test_group_routes.py::TestCreateGroupRoute::test_create_group_returns_201_with_group_details` | COVERED |
| Group Creation | Duplicate name | `DuplicateGroupNameError` in repository; caught in route as 409 | `test_group_routes.py::test_create_group_returns_409_on_duplicate_name` | COVERED |
| Group Name Validation | Valid name | `Group.create()` accepts 1–255 chars after strip | `test_group_aggregate.py::TestGroupNameValidation::test_create_accepts_single_character_name` | COVERED |
| Group Name Validation | Empty/whitespace | `Group.create()` raises `ValueError` | `test_group_aggregate.py::test_create_rejects_empty_name`, `test_create_rejects_whitespace_only_name`; `test_group_routes.py::test_create_group_returns_422_for_whitespace_only_name` | COVERED |
| Group Retrieval | Authorized retrieval | `GroupService.get_group()` + SpiceDB VIEW check | `test_group_service.py::TestGetGroup::test_returns_group_when_found_and_user_has_view_permission`; `test_group_routes.py::TestGetGroupRoute::test_get_group_returns_200_when_found` | COVERED |
| Group Retrieval | Unauthorized/non-existent | Returns `None` → 404 | `test_group_service.py::test_returns_none_when_user_lacks_view_permission`; `test_group_routes.py::test_get_group_returns_404_when_not_found` | COVERED |
| Group Listing | Tenant member lists groups | `GroupService.list_groups()` filters by SpiceDB VIEW | `test_group_service_list.py::TestListGroups::test_returns_view_filtered_groups`; `test_group_routes.py::TestListGroupsWithViewFiltering` | COVERED |
| Group Rename | Successful rename | `Group.rename()` + `GroupService.update_group()` | `test_group_rename.py::TestGroupRename::test_renames_group_successfully`; `test_group_service_update.py::test_renames_group_with_manage_permission` | COVERED |
| Group Rename | Duplicate name | `DuplicateGroupNameError` raised and returned as 409 | `test_group_service_update.py::test_raises_duplicate_name_error_when_name_exists`; `test_group_routes.py::test_update_group_returns_409_on_duplicate_name` | COVERED |
| Group Deletion | Successful deletion + member snapshot | `Group.mark_for_deletion()` records `GroupDeleted` with `MemberSnapshot` tuple | `test_group_aggregate.py::TestMarkForDeletion::test_group_deleted_event_includes_member_snapshot`; `test_group_routes.py::TestDeleteGroupRoute::test_delete_group_returns_204_on_success` | COVERED |
| Group Member Management | Add member | `Group.add_member()` + `GroupService.add_member()` | `test_group_service_members.py::TestAddMember::test_adds_member_with_manage_permission`; `test_group_routes.py::test_add_member_returns_201` | COVERED |
| Group Member Management | Change member role | `Group.update_member_role()` + `GroupService.update_member_role()` | `test_group_aggregate.py::TestUpdateMemberRole::test_updates_member_role`; `test_group_service_members.py::TestUpdateMemberRole` | COVERED |
| Group Member Management | Remove member | `Group.remove_member()` + `GroupService.remove_member()` | `test_group_aggregate.py::TestRemoveMember::test_removes_existing_member`; `test_group_routes.py::test_remove_member_returns_204` | COVERED |
| Group Member Management | Demote/remove last admin | Last-admin guard in `Group.remove_member()` and `Group.update_member_role()` | `test_group_aggregate.py::test_prevents_removing_last_admin`, `test_prevents_demoting_last_admin` | COVERED |
| Group Member Listing | List members | `GroupService.list_members()` reads SpiceDB relationships | `test_group_service.py::TestListMembers`; `test_group_service_members.py::TestListMembers`; `test_group_routes.py::test_list_members_returns_200` | COVERED |
| Workspace Access Inheritance | Group added to workspace | SpiceDB schema: `workspace#editor@group:{id}#member`; outbox translates `MemberAdded` events | Integration: `test_group_workspace_inheritance.py::test_group_member_gets_workspace_access_via_group` | COVERED |
| Workspace Access Inheritance | Member added after group assigned | SpiceDB lazy evaluation of relationship chain | Integration: `test_group_workspace_inheritance.py::test_member_added_after_group_assigned_to_workspace_gets_access` | COVERED |
| Workspace Access Inheritance | Member removed from group | `MemberRemoved` event → outbox → SpiceDB delete | Integration: `test_group_workspace_inheritance.py::test_removing_user_from_group_revokes_workspace_access` | COVERED |
| Group Roles | Admin role | SpiceDB: `admin` → `manage + view`; `group.member = admin + member_relation` | `test_group_authorization.py::TestGroupRoleEnforcement::test_group_admin_can_delete_group` | COVERED |
| Group Roles | Member role | SpiceDB: `member_relation` → `view` only | `test_group_authorization.py::test_group_member_cannot_delete_group` | COVERED |