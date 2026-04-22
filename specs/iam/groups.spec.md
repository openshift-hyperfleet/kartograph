# Groups

## Purpose
Groups provide a way to manage workspace access for collections of users. Adding a group to a workspace grants all group members the assigned workspace role, and membership changes in the group automatically propagate to workspace permissions.

## Requirements

### Requirement: Group Creation
The system SHALL allow authenticated users to create groups within their tenant.

#### Scenario: Successful creation
- GIVEN an authenticated user within a tenant
- WHEN the user creates a group with name "Engineering"
- THEN a group is created with a generated ULID identifier
- AND the creating user is granted the `admin` role on the group

#### Scenario: Duplicate name within tenant
- GIVEN a group named "Engineering" already exists in the tenant
- WHEN a user attempts to create another group with the same name
- THEN the request is rejected with a conflict error

### Requirement: Group Name Validation
The system SHALL enforce constraints on group names.

#### Scenario: Valid name
- GIVEN a name between 1 and 255 characters (after trimming whitespace)
- WHEN used to create or rename a group
- THEN the name is accepted

#### Scenario: Empty or whitespace-only name
- GIVEN an empty or whitespace-only string as group name
- WHEN used to create or rename a group
- THEN the request is rejected with a validation error

### Requirement: Group Retrieval
The system SHALL return group details only to users with `view` permission.

#### Scenario: Authorized retrieval
- GIVEN a group the user has `view` permission on
- WHEN the user requests the group by ID
- THEN the group details are returned

#### Scenario: Unauthorized or non-existent
- GIVEN a group the user cannot view (or does not exist)
- WHEN the user requests the group by ID
- THEN a not-found response is returned

### Requirement: Group Listing
The system SHALL return only groups the requesting user has `view` permission on.

#### Scenario: Tenant member lists groups
- GIVEN a user who is a member of the tenant
- WHEN the user lists groups
- THEN all groups in the tenant are returned (tenant membership implies `view`)

### Requirement: Group Rename
The system SHALL allow users with `manage` permission to rename a group.

#### Scenario: Successful rename
- GIVEN a user with `manage` permission on a group
- WHEN the user renames the group to a unique name within the tenant
- THEN the group name is updated

#### Scenario: Duplicate name
- GIVEN another group with the desired name already exists in the tenant
- WHEN the user attempts the rename
- THEN the request is rejected with a conflict error

### Requirement: Group Deletion
The system SHALL allow users with `manage` permission to delete a group.

#### Scenario: Successful deletion
- GIVEN a user with `manage` permission on a group
- WHEN the user deletes the group
- THEN the group is removed
- AND a snapshot of all members is captured for authorization cleanup

### Requirement: Group Member Management
The system SHALL allow users with `manage` permission to add, remove, and update members.

#### Scenario: Add member
- GIVEN a user with `manage` permission on a group
- WHEN the user adds another user with role `member`
- THEN the new member is granted the `member` role on the group

#### Scenario: Change member role
- GIVEN a group member with role `member`
- WHEN an admin changes their role to `admin`
- THEN the previous `member` role is revoked
- AND the `admin` role is granted

#### Scenario: Remove member
- GIVEN a member of a group
- WHEN an admin removes the member
- THEN the member's role on the group is revoked

#### Scenario: Demote or remove last admin
- GIVEN a group with exactly one admin
- WHEN an attempt is made to demote or remove that admin
- THEN the request is rejected
- AND the admin's role is unchanged

### Requirement: Group Member Listing
The system SHALL allow users with `view` permission to list group members.

#### Scenario: List members
- GIVEN a user with `view` permission on a group
- WHEN the user requests the member list
- THEN all members are returned with their user IDs and roles

### Requirement: Workspace Access Inheritance
The system SHALL propagate group membership to workspace permissions when a group is assigned to a workspace.

#### Scenario: Group added to workspace
- GIVEN a group with members Alice and Bob
- WHEN the group is added to a workspace with role `editor`
- THEN Alice and Bob both receive `editor`-level permissions on the workspace

#### Scenario: Member added to group with workspace assignments
- GIVEN a group assigned to a workspace with role `editor`
- WHEN a new user is added to the group
- THEN that user immediately receives `editor`-level permissions on the workspace

#### Scenario: Member removed from group
- GIVEN a group assigned to a workspace with role `editor`
- WHEN a user is removed from the group
- THEN that user loses the inherited workspace permissions

### Requirement: Group Roles
The system SHALL support two roles for group membership.

#### Scenario: Admin role
- GIVEN a user with the `admin` role on a group
- THEN the user has `manage` and `view` permissions on the group
- AND the user is included in workspace permission inheritance

#### Scenario: Member role
- GIVEN a user with the `member` role on a group
- THEN the user has `view` permission on the group
- AND the user is included in workspace permission inheritance
