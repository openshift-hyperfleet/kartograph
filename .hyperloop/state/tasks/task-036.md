---
id: task-036
title: Add integration test — group member removal revokes inherited workspace access
spec_ref: specs/iam/groups.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

`specs/iam/groups.spec.md` — **Workspace Access Inheritance**, scenario:
**"Member removed from group"**:

> - GIVEN a group assigned to a workspace with role `editor`
> - WHEN a user is removed from the group
> - THEN that user loses the inherited workspace permissions

`task-024` (complete) covers the inverse: user *added* to a group inherits workspace
access. The removal scenario is not tested. The code path is correct (the outbox
translator deletes the SpiceDB group membership relation, which automatically revokes
computed workspace permissions), but there is no integration test to verify it.

## What to build

Write an integration test in `tests/integration/iam/` that:

1. Creates a group (e.g., `engineering`) and assigns it to a workspace with role
   `editor`.
2. Adds user `bob` to the group as a `member`.
3. Waits for the outbox to propagate the SpiceDB relationships (pattern established
   by existing tests in `test_workspace_members_api.py`).
4. Asserts that `bob` has `edit` permission on the workspace.
5. Removes `bob` from the group via `GroupService.remove_member()`.
6. Waits for the outbox to propagate the removal.
7. Asserts that `bob` no longer has `edit` permission on the workspace.

## Implementation notes

- Follow the same integration test pattern as `task-024`
  (`tests/integration/iam/test_group_workspace_inheritance.py` or similar).
- No new application code is needed — this is a test-only task.
- The outbox propagation helper used in `test_workspace_members_api.py` (polling
  for SpiceDB relation to appear/disappear) should be reused.
- Use the `InMemoryAuthorizationProvider` or the real SpiceDB container, consistent
  with the test infrastructure pattern already in place.
