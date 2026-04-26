---
task_id: task-039
round: 1
role: spec-reviewer
verdict: fail
---
Fresh spec-alignment review performed against the branch after the prior verifier crash.
All 2408 unit tests pass. Four new tests (introduced by this branch) are valid TDD
additions. However, one SHALL requirement lacks test coverage.

## Per-Requirement Status

### Requirement: Tenant Creation — COVERED
- **Successful creation**: `TestCreateTenant::{test_creates_tenant, test_grants_creator_admin_access, test_creates_root_workspace_on_tenant_creation}` (unit) + `TestCreateTenantWithoutTenantContext` (presentation unit).
- **Duplicate name**: Integration test `test_tenant_api.py::TestCreateTenant::test_returns_409_for_duplicate_name` exercises the full path. Code: `tenants/routes.py:69-71` catches `DuplicateTenantNameError` and returns 409.
- **Single-tenant mode**: `TestCreateTenantBlockedInSingleTenantMode::{test_returns_403_in_single_tenant_mode, test_service_not_called_in_single_tenant_mode}` (unit).
- **Tenant graph provisioning**: `TestTenantAGEGraphHandlerGraphProvisioning` (idempotent provisioning), `TestAGEGraphProvisionerIdempotency` (create-if-not-exists). **New tests** added by this branch:
  - `test_rollback_or_commit_called_on_no_op_path` — verifies no-op path commits or rolls back (spec: "connection MUST be properly committed or rolled back").
  - `test_advisory_lock_acquired_for_atomicity` — verifies advisory lock precedes existence check (spec: "existence check and graph creation MUST be performed atomically").

### Requirement: Tenant Retrieval — COVERED
- **Authorized retrieval**: `TestGetTenant::{test_returns_tenant_when_user_has_view_permission, test_checks_view_permission_via_spicedb}` (unit).
- **Unauthorized or non-existent**: `TestGetTenant::{test_returns_none_when_tenant_not_found, test_returns_none_when_user_lacks_view_permission}` (unit) — both return None with no distinction.

### Requirement: Tenant Listing — COVERED
- **User belongs to multiple tenants**: `TestListTenants::test_returns_only_tenants_user_can_view` (unit) — A and C visible, B excluded.
- **User belongs to no tenants**: `TestListTenants::test_returns_empty_list_when_user_has_no_access` (unit).

### Requirement: Tenant Deletion — PARTIAL

Code: `TenantService.delete_tenant()` in `tenant_service.py:555-673`. All four cascade types are implemented.

**COVERED sub-conditions:**
- "all workspaces deleted (children before parents)": `test_deletes_workspaces_on_tenant_deletion` (unit) + **new** `test_deletes_child_workspaces_before_parent_on_cascade` (unit, depth-first order verified with 3-level hierarchy).
- "all API keys deleted": `test_deletes_api_keys_on_tenant_deletion`, `test_deletes_multiple_api_keys_on_tenant_deletion` (unit).
- "tenant itself is deleted": `test_deletes_tenant` (unit).
- "member snapshot captured": `test_tenant_aggregate.py::test_mark_for_deletion_captures_member_snapshot` (domain unit); service calls `_list_tenant_members_from_authorization` then `tenant.mark_for_deletion(members=members)`.
- **Unauthorized deletion**: `test_delete_tenant_raises_unauthorized_if_no_permission` (unit) + `TestDeleteTenantBlockedInSingleTenantMode` (unit).
- **Single-tenant mode**: `TestDeleteTenantBlockedInSingleTenantMode::{test_returns_403_in_single_tenant_mode, test_service_not_called_in_single_tenant_mode}` (unit).

**MISSING test coverage:**
- "AND all groups within the tenant are deleted" — **no unit or integration test exercises this condition with a non-empty group list**.

  The code is present (`tenant_service.py:603-655`):
  ```python
  groups = await self._group_repository.list_by_tenant(tenant_id)
  ...
  for group in groups:
      group.mark_for_deletion()
      await self._group_repository.delete(group)
  ```
  However every `TestDeleteTenant` test fixture mocks:
  ```python
  mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
  ```
  Neither the unit tests nor the integration tests (`test_tenant_api.py`) ever create actual groups and verify they are deleted as part of tenant cascade.

  **What is needed**: A unit test analogous to `test_deletes_api_keys_on_tenant_deletion` that mocks `mock_group_repo.list_by_tenant` to return one or more `Group` aggregates and asserts `mock_group_repo.delete` is called for each.

### Requirement: Add Tenant Member — COVERED
- **Add new member**: `TestAddMember::test_adds_member_to_tenant` + `TestAddTenantMemberRoute::test_returns_201_on_successful_add`.
- **Change member role**: `TestAddMember::test_replaces_role_when_user_has_different_role` (MemberRemoved + MemberAdded events).
- **Promote to admin syncs root workspace**: `TestAddMember::test_add_admin_grants_root_workspace_admin` (WorkspaceMemberAdded verified).
- **Demote from admin syncs root workspace**: `TestAddMember::test_downgrade_admin_to_member_revokes_root_workspace_admin` (WorkspaceMemberRemoved verified).
- **Demote last admin**: `TestAddMember::test_cannot_demote_last_tenant_admin` (CannotRemoveLastAdminError) + `TestAddTenantMemberRoute::test_returns_409_when_demoting_last_admin` (HTTP 409).

### Requirement: Remove Tenant Member — COVERED
- **Successful removal**: `TestRemoveMember::test_removes_member_from_tenant`.
- **Member's root workspace access revoked**: `TestRemoveMember::test_remove_member_revokes_root_workspace_access`.
- **Removing admin syncs root workspace**: `TestRemoveMember::test_remove_admin_revokes_root_workspace_admin`.
- **Remove last admin**: `TestRemoveMember::test_raises_error_if_last_admin` + `TestRemoveTenantMemberRoute::test_returns_409_when_removing_last_admin`.

### Requirement: List Tenant Members — COVERED
- **Authorized listing**: `TestListMembers::test_lists_members_from_spicedb` (returns user_ids and roles) + `TestListTenantMembersRoute::test_returns_200_with_member_list`.
- **Unauthorized listing**: `TestListMembers::test_raises_unauthorized_if_no_permission` + `TestListTenantMembersRoute::test_returns_403_when_not_admin`.

### Requirement: Tenant Name Validation — COVERED
All four new tests introduced by this branch:
- **Valid name (1 char)**: `TestTenantNameValidation::test_create_tenant_accepts_single_char_name` → HTTP 201.
- **Valid name (255 chars)**: `TestTenantNameValidation::test_create_tenant_accepts_name_at_max_length_boundary` → HTTP 201.
- **Empty name**: `TestTenantNameValidation::test_create_tenant_returns_422_for_empty_name` → HTTP 422, service not called.
- **Name too long (256 chars)**: `TestTenantNameValidation::test_create_tenant_returns_422_for_name_exceeding_255_chars` → HTTP 422, service not called.

### Requirement: Default Tenant Bootstrap — COVERED
- **First startup**: `TestEnsureDefaultTenantWithWorkspace::test_creates_tenant_and_workspace_when_neither_exist`.
- **Subsequent startup**: `test_does_nothing_when_tenant_and_workspace_exist`.
- **Concurrent startup**: `test_handles_race_condition_on_tenant_creation` (DuplicateTenantNameError race → re-query and reuse existing).

---

## Summary

**Verdict: FAIL**

One SHALL condition in the "Tenant Deletion / Successful deletion" scenario is missing test
coverage: "all groups within the tenant are deleted." The implementation is correct but no
test (unit or integration) exercises the group-deletion loop with a non-empty group list.

**Fix required**: Add a unit test to `tests/unit/iam/application/test_tenant_service.py`
inside `TestDeleteTenant` similar to `test_deletes_api_keys_on_tenant_deletion` but for
groups. The test should:
1. Create one or more real `Group` aggregates (not MagicMock).
2. Return them from `mock_group_repo.list_by_tenant`.
3. Assert `mock_group_repo.delete` is called once per group.