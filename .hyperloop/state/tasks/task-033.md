---
id: task-033
title: Enforce last-admin and no-children-delete protection in workspace service
spec_ref: specs/iam/workspaces.spec.md@b46589a2
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Context

`specs/iam/workspaces.spec.md` requires two domain protections that are referenced in
the presentation layer but not enforced in the service layer:

1. **Last-admin protection**: `workspace_service.py` (918 lines) imports
   `CannotRemoveLastAdminError` from `iam.domain.exceptions` but never raises it.
   The routes for `remove_workspace_member` and `update_workspace_member_role` catch
   the error and return HTTP 409, but the service never triggers the path — so the
   guard is silently bypassed.

2. **No-children-deletion**: The spec prohibits deleting a workspace that has child
   workspaces. It is unclear whether this is enforced at the database level (FK
   RESTRICT) or needs a service-layer check. The service's `delete()` method must
   guarantee this invariant.

## What to implement

1. In `WorkspaceService.remove_member()`: count remaining admin relationships for the
   workspace before deleting. If the target is the last admin, raise
   `CannotRemoveLastAdminError`.

2. In `WorkspaceService.update_member_role()`: if downgrading the last admin to
   EDITOR or MEMBER, raise `CannotRemoveLastAdminError`.

3. In `WorkspaceService.delete()`: verify the workspace has no child workspaces
   before proceeding. If children exist, raise an appropriate domain exception (e.g.,
   `WorkspaceHasChildrenError`) that maps to HTTP 409.

4. Add unit tests for all three protection paths.

5. Add integration tests: last-admin removal → 409, deletion with children → 409.

## Acceptance criteria

- `remove_member()` raises `CannotRemoveLastAdminError` when removing the last admin.
- `update_member_role()` raises `CannotRemoveLastAdminError` when demoting the last admin.
- `delete()` rejects deletion of a workspace with existing child workspaces.
- HTTP 409 is returned for all three cases.
- Normal operations (two admins, no children) succeed without error.
