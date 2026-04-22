# Workspaces

## Purpose
Workspaces organize knowledge graphs within a tenant. They form a hierarchy: each tenant has exactly one root workspace, and users create child workspaces beneath it. Access is controlled per-workspace via a three-tier role model (admin, editor, member) with both direct user grants and group-based grants.

## Requirements

### Requirement: Root Workspace
The system SHALL automatically create a root workspace when a tenant is created.

#### Scenario: Root workspace properties
- GIVEN a newly created tenant
- WHEN the root workspace is created
- THEN it has no parent workspace
- AND it is marked as a root workspace
- AND a `creator_tenant` relationship is established granting all tenant members the `create_child` permission

#### Scenario: Root workspace cannot be deleted
- GIVEN the root workspace of a tenant
- WHEN a user attempts to delete it
- THEN the request is rejected with a conflict error

### Requirement: Child Workspace Creation
The system SHALL allow users with `create_child` permission on a parent workspace to create child workspaces.

#### Scenario: Successful creation
- GIVEN a user with `create_child` permission on a parent workspace
- WHEN the user creates a workspace with a valid name
- THEN the workspace is created as a child of the specified parent
- AND the creating user is granted the `admin` role on the new workspace

#### Scenario: Duplicate name within tenant
- GIVEN a workspace named "Frontend" already exists in the tenant
- WHEN a user attempts to create another workspace named "Frontend" in the same tenant
- THEN the request is rejected with a conflict error

#### Scenario: Unauthorized creation
- GIVEN a user without `create_child` permission on the parent workspace
- WHEN the user attempts to create a child workspace
- THEN the request is rejected with a forbidden error

### Requirement: Workspace Name Validation
The system SHALL enforce constraints on workspace names.

#### Scenario: Valid name
- GIVEN a name between 1 and 512 characters
- WHEN used to create or rename a workspace
- THEN the name is accepted

#### Scenario: Empty or oversized name
- GIVEN a name that is empty or exceeds 512 characters
- WHEN used to create or rename a workspace
- THEN the request is rejected with a validation error

### Requirement: Workspace Retrieval
The system SHALL return workspace details only to users with `view` permission.

#### Scenario: Authorized retrieval
- GIVEN a workspace the requesting user has `view` permission on
- WHEN the user requests the workspace by ID
- THEN the workspace details are returned

#### Scenario: Unauthorized or non-existent
- GIVEN a workspace the user cannot view (or does not exist)
- WHEN the user requests the workspace by ID
- THEN a not-found response is returned
- AND no distinction is made between "unauthorized" and "missing"

### Requirement: Workspace Listing
The system SHALL return only workspaces the requesting user has `view` permission on within the current tenant.

#### Scenario: Filtered listing
- GIVEN a user with `view` permission on workspaces A and B but not C
- WHEN the user lists workspaces
- THEN workspaces A and B are returned with a count
- AND workspace C is excluded

### Requirement: Workspace Rename
The system SHALL allow users with `manage` permission to rename a workspace.

#### Scenario: Successful rename
- GIVEN a user with `manage` permission on a workspace
- WHEN the user renames the workspace to a unique name within the tenant
- THEN the workspace name is updated

#### Scenario: Duplicate name
- GIVEN another workspace with the desired name already exists in the tenant
- WHEN the user attempts the rename
- THEN the request is rejected with a conflict error

### Requirement: Workspace Deletion
The system SHALL allow users with `manage` permission to delete non-root workspaces that have no children.

#### Scenario: Successful deletion
- GIVEN a user with `manage` permission on a leaf workspace (no children)
- WHEN the user deletes the workspace
- THEN the workspace is removed
- AND a snapshot of all members is captured for authorization cleanup

#### Scenario: Workspace has children
- GIVEN a workspace with child workspaces
- WHEN a user attempts to delete it
- THEN the request is rejected with a conflict error

### Requirement: Workspace Member Management
The system SHALL allow users with `manage` permission to add, remove, and update members on a workspace.

#### Scenario: Add user member
- GIVEN a user with `manage` permission on a workspace
- WHEN the user adds another user with role `editor`
- THEN the new member is granted the `editor` role on the workspace

#### Scenario: Add group member
- GIVEN a user with `manage` permission on a workspace
- WHEN the user adds a group with role `editor`
- THEN all members of that group inherit `editor`-level permissions on the workspace

#### Scenario: Change member role
- GIVEN a member with role `member` on a workspace
- WHEN an admin changes their role to `editor`
- THEN the previous `member` role is revoked
- AND the `editor` role is granted

#### Scenario: Remove member
- GIVEN a member of a workspace
- WHEN an admin removes the member
- THEN the member's role on the workspace is revoked

#### Scenario: Demote or remove last admin
- GIVEN a workspace with exactly one admin
- WHEN an attempt is made to demote or remove that admin
- THEN the request is rejected with a conflict error

### Requirement: Workspace Member Listing
The system SHALL allow users with `view` permission to list workspace members.

#### Scenario: List members
- GIVEN a user with `view` permission on a workspace
- WHEN the user requests the member list
- THEN all direct members (users and groups) are returned with their roles
- AND group memberships are shown as group-type entries, not expanded to individual users

### Requirement: Three-Tier Role Hierarchy
The system SHALL enforce a permission hierarchy across workspace roles.

#### Scenario: Admin permissions
- GIVEN a user with the `admin` role on a workspace
- THEN the user has `manage`, `edit`, and `view` permissions

#### Scenario: Editor permissions
- GIVEN a user with the `editor` role on a workspace
- THEN the user has `edit` and `view` permissions
- AND the user does NOT have `manage` permission

#### Scenario: Member permissions
- GIVEN a user with the `member` role on a workspace
- THEN the user has `view` permission only
- AND the user does NOT have `edit` or `manage` permissions
