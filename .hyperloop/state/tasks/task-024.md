---
id: task-024
title: Add integration test — member added to already-workspace-assigned group gets immediate workspace permissions
spec_ref: specs/iam/groups.spec.md@224a54b5ab2f7bca552b3845891a363215b7110b
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The Workspace Access Inheritance requirement in `specs/iam/groups.spec.md` has three scenarios. Two are covered by existing integration tests, but one is missing entirely:

> **Scenario: Member added to group with workspace assignments**
> - GIVEN a group assigned to a workspace with role `editor`
> - WHEN a new user is added to the group
> - THEN that user immediately receives `editor`-level permissions on the workspace

The existing integration tests in `test_group_workspace_inheritance.py` only test adding members first and then assigning the group to a workspace. No test verifies the reverse ordering — that a user added to a group that **already** has a workspace assignment receives the inherited workspace permissions immediately (via outbox → SpiceDB `MemberAdded` event handler).

## How

Add an integration test in `src/api/tests/integration/iam/test_group_workspace_inheritance.py` that:

1. Creates a group with at least one existing member
2. Assigns the group to a workspace with a specific role (e.g., `editor`)
3. Adds a **new** user to the group
4. Verifies that the new user now has `editor`-level permission on the workspace (via SpiceDB permission check)

The outbox worker must process the `MemberAdded` event and write the SpiceDB relationship `workspace#editor@user:{new_user_id}` (via the group subject relation `workspace#editor@group:{group_id}#member`).

## Acceptance

- The new test is marked `@pytest.mark.integration`
- The test passes against a running dev instance
- No production code changes are needed (only a test is added)
