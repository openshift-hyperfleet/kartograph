# Tenants

## Purpose
Tenants are the top-level isolation boundary in Kartograph. A tenant represents an organization whose data, workspaces, and members are fully isolated from other tenants.

## Requirements

### Requirement: Tenant Creation
The system SHALL allow authenticated users to create a new tenant with a unique name.

#### Scenario: Successful creation
- GIVEN an authenticated user in multi-tenant mode
- WHEN the user creates a tenant with name "Acme Corp"
- THEN a tenant is created with a generated ULID identifier
- AND the creating user is granted the `admin` role on the tenant
- AND a root workspace is automatically created within the tenant
- AND the creating user is granted the `admin` role on the root workspace

#### Scenario: Duplicate name
- GIVEN a tenant named "Acme Corp" already exists
- WHEN a user attempts to create another tenant named "Acme Corp"
- THEN the request is rejected with a conflict error
- AND no tenant is created

#### Scenario: Single-tenant mode
- GIVEN the system is running in single-tenant mode
- WHEN a user attempts to create a tenant
- THEN the request is rejected

#### Scenario: Tenant graph provisioning
- GIVEN a tenant is successfully created
- WHEN the creation event is processed (via outbox)
- THEN a dedicated AGE graph named `tenant_{tenant_id}` is provisioned only if it does not already exist (create-if-not-exists)
- AND all knowledge graph data for this tenant will be stored in this graph
- AND if the graph already exists, the event is treated as a no-op (idempotent replay is safe)

### Requirement: Tenant Retrieval
The system SHALL return tenant details only to users with view permission.

#### Scenario: Authorized retrieval
- GIVEN a tenant exists and the requesting user has `view` permission
- WHEN the user requests the tenant by ID
- THEN the tenant's id and name are returned

#### Scenario: Unauthorized or non-existent
- GIVEN a tenant the user cannot view (or does not exist)
- WHEN the user requests the tenant by ID
- THEN a not-found response is returned
- AND no distinction is made between "unauthorized" and "missing"

### Requirement: Tenant Listing
The system SHALL return only tenants the requesting user has view permission on.

#### Scenario: User belongs to multiple tenants
- GIVEN a user has `view` permission on tenants A and B but not C
- WHEN the user lists tenants
- THEN tenants A and B are returned
- AND tenant C is excluded

#### Scenario: User belongs to no tenants
- GIVEN a user has no tenant memberships
- WHEN the user lists tenants
- THEN an empty list is returned

### Requirement: Tenant Deletion
The system SHALL allow tenant admins to delete a tenant, cascading to all owned resources.

#### Scenario: Successful deletion
- GIVEN an authenticated user with `administrate` permission on a tenant
- WHEN the user deletes the tenant
- THEN all workspaces within the tenant are deleted (children before parents)
- AND all groups within the tenant are deleted
- AND all API keys within the tenant are deleted
- AND the tenant itself is deleted
- AND a snapshot of all members is captured for authorization cleanup

#### Scenario: Unauthorized deletion
- GIVEN a user without `administrate` permission on a tenant
- WHEN the user attempts to delete the tenant
- THEN the request is rejected with a forbidden error

#### Scenario: Single-tenant mode
- GIVEN the system is running in single-tenant mode
- WHEN a user attempts to delete a tenant
- THEN the request is rejected

### Requirement: Add Tenant Member
The system SHALL allow tenant admins to add users as members with a specified role.

#### Scenario: Add new member
- GIVEN an admin of the tenant
- WHEN the admin adds a user with role `member`
- THEN the user is granted the `member` role on the tenant

#### Scenario: Change member role
- GIVEN a user with role `member` on the tenant
- WHEN an admin changes their role to `admin`
- THEN the previous `member` role is revoked
- AND the `admin` role is granted

#### Scenario: Promote to admin syncs root workspace
- GIVEN a user being granted the `admin` role on a tenant
- WHEN the role change is applied
- THEN the user is also granted the `admin` role on the tenant's root workspace

#### Scenario: Demote from admin syncs root workspace
- GIVEN a user being demoted from `admin` to `member` on a tenant
- WHEN the role change is applied
- THEN the user's admin access to the root workspace is revoked

#### Scenario: Demote last admin
- GIVEN a tenant with exactly one admin
- WHEN that admin's role is changed to `member`
- THEN the request is rejected with a conflict error
- AND the admin's role is unchanged

### Requirement: Remove Tenant Member
The system SHALL allow tenant admins to remove members from a tenant.

#### Scenario: Successful removal
- GIVEN an admin of the tenant and a member to remove
- WHEN the admin removes the member
- THEN the member's role on the tenant is revoked
- AND the member's access to the root workspace is revoked (if they were a member)

#### Scenario: Removing an admin syncs root workspace
- GIVEN a tenant admin being removed from the tenant
- WHEN the removal is applied
- THEN the user's admin access to the root workspace is also revoked

#### Scenario: Remove last admin
- GIVEN a tenant with exactly one admin
- WHEN an attempt is made to remove that admin
- THEN the request is rejected with a conflict error
- AND the admin remains on the tenant

### Requirement: List Tenant Members
The system SHALL allow tenant admins to list all members and their roles.

#### Scenario: Authorized listing
- GIVEN an admin of the tenant
- WHEN the admin requests the member list
- THEN all members are returned with their user IDs and roles

#### Scenario: Unauthorized listing
- GIVEN a non-admin member of the tenant
- WHEN the member requests the member list
- THEN the request is rejected with a forbidden error

### Requirement: Tenant Name Validation
The system SHALL enforce constraints on tenant names.

#### Scenario: Valid name
- GIVEN a name between 1 and 255 characters
- WHEN used to create a tenant
- THEN the name is accepted

#### Scenario: Empty name
- GIVEN an empty string as tenant name
- WHEN used to create a tenant
- THEN the request is rejected with a validation error

#### Scenario: Name too long
- GIVEN a name exceeding 255 characters
- WHEN used to create a tenant
- THEN the request is rejected with a validation error

### Requirement: Default Tenant Bootstrap
The system SHALL provision a default tenant on startup when running in single-tenant mode.

#### Scenario: First startup
- GIVEN no default tenant exists
- WHEN the system starts in single-tenant mode
- THEN a default tenant is created
- AND a root workspace is created within it

#### Scenario: Subsequent startup
- GIVEN the default tenant already exists
- WHEN the system starts in single-tenant mode
- THEN the existing tenant is reused
- AND no duplicate is created

#### Scenario: Concurrent startup
- GIVEN multiple instances starting simultaneously
- WHEN both attempt to create the default tenant
- THEN exactly one tenant is created
- AND the other instance discovers and uses the existing one
