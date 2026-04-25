---
id: task-032
title: Enforce last-admin protection in group member management
spec_ref: specs/iam/groups.spec.md@b46589a2
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Context

`specs/iam/groups.spec.md` requires demote-last-admin protection: a group must always
retain at least one admin. The group routes reference `CannotRemoveLastAdminError`, but
`group_service.py` (582 lines) never raises it — neither `remove_member()` nor
`update_member_role()` check whether the target member is the sole remaining admin.

Tenant management already implements this pattern correctly; groups must match.

## What to implement

1. In `GroupService.remove_member()`: before deleting the SpiceDB relationship, count
   admin relationships on the group. If the subject is the last admin, raise
   `CannotRemoveLastAdminError`.

2. In `GroupService.update_member_role()`: before writing the new role, check if the
   current role is ADMIN and no other admin exists. If so, raise
   `CannotRemoveLastAdminError`.

3. Add unit tests covering both protection paths (fake authorization provider, no
   infrastructure needed).

4. Add an integration test: demoting/removing the sole admin of a group returns HTTP
   409 Conflict.

## Acceptance criteria

- `remove_member()` raises `CannotRemoveLastAdminError` when removing the last admin.
- `update_member_role()` raises `CannotRemoveLastAdminError` when demoting the last admin.
- HTTP 409 is returned to callers in both cases.
- A group with two admins can have one admin removed without error.
