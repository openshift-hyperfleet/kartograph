# Authorization

## Purpose
Kartograph uses a relationship-based access control (ReBAC) model via SpiceDB. Permissions are computed from explicit relationships between users, groups, and resources. This spec describes the permission model — not the SpiceDB implementation, but the authorization semantics the system enforces.

## Requirements

### Requirement: Tenant Permissions
The system SHALL enforce the following permission model for tenants.

#### Scenario: Admin permissions
- GIVEN a user with the `admin` relation on a tenant
- THEN the user has `view`, `create_api_key`, `manage`, and `administrate` permissions

#### Scenario: Member permissions
- GIVEN a user with the `member` relation on a tenant
- THEN the user has `view` and `create_api_key` permissions
- AND the user does NOT have `manage` or `administrate` permissions

### Requirement: Workspace Permissions
The system SHALL enforce the following permission model for workspaces.

#### Scenario: Admin permissions
- GIVEN a user with the `admin` role on a workspace
- THEN the user has `view`, `edit`, `manage`, and `create_child` permissions

#### Scenario: Editor permissions
- GIVEN a user with the `editor` role on a workspace
- THEN the user has `view`, `edit`, and `create_child` permissions
- AND the user does NOT have `manage` permission

#### Scenario: Member permissions
- GIVEN a user with the `member` role on a workspace
- THEN the user has `view` permission only

#### Scenario: Tenant member visibility
- GIVEN a user who is a member (or admin) of a tenant
- THEN the user has `view` permission on all workspaces in that tenant

### Requirement: Root Workspace Create-Child Access
The system SHALL grant all tenant members the ability to create child workspaces under the root workspace.

#### Scenario: Tenant member creates child of root
- GIVEN a user who is a member of a tenant
- WHEN the user attempts to create a child workspace under the root workspace
- THEN the request is permitted via the `creator_tenant` relationship

#### Scenario: Non-root workspace restricts creation
- GIVEN a child workspace (not root)
- WHEN a user who is only a tenant member (no workspace role) attempts to create a child
- THEN the request is denied

### Requirement: Group-to-Workspace Permission Inheritance
The system SHALL propagate group membership to workspace permissions when a group is assigned a role on a workspace.

#### Scenario: Group member inherits workspace access
- GIVEN a group assigned the `editor` role on a workspace
- AND a user who is a member of that group
- THEN the user has `edit` and `view` permissions on the workspace

#### Scenario: Group admin inherits workspace access
- GIVEN a group assigned a role on a workspace
- AND a user who is an `admin` of that group
- THEN the user also inherits the workspace permissions (group admins are included in the member expansion)

#### Scenario: Removing user from group revokes inherited access
- GIVEN a user whose only workspace access comes through a group
- WHEN the user is removed from the group
- THEN the user loses all inherited workspace permissions

### Requirement: Knowledge Graph Permissions
The system SHALL derive knowledge graph permissions from both direct grants and workspace inheritance.

#### Scenario: Workspace-inherited access
- GIVEN a knowledge graph associated with a workspace
- AND a user with `edit` permission on the workspace
- THEN the user has `edit` and `view` permissions on the knowledge graph

#### Scenario: Direct grant
- GIVEN a user with a direct `admin` role on a knowledge graph
- THEN the user has `manage`, `edit`, and `view` permissions on the knowledge graph

### Requirement: Data Source Permissions
The system SHALL derive all data source permissions from the parent knowledge graph.

#### Scenario: Inherited access
- GIVEN a data source belonging to a knowledge graph
- AND a user with `edit` permission on the knowledge graph
- THEN the user has `edit` and `view` permissions on the data source

### Requirement: API Key Permissions
The system SHALL allow API key owners and tenant admins to view and revoke keys.

#### Scenario: Owner access
- GIVEN a user who created an API key
- THEN the user has `view` and `revoke` permissions on that key

#### Scenario: Tenant admin access
- GIVEN a tenant admin
- THEN the admin has `view` and `revoke` permissions on all API keys in the tenant

### Requirement: Secure Enclave — Per-Entity Graph Authorization
The system SHALL enforce per-entity authorization on all graph query results, redacting content for entities the user is not authorized to view.

#### Scenario: Authorized entity — full properties
- GIVEN a node or edge the user has `view` permission on (via KnowledgeGraph or direct grant)
- WHEN the entity appears in query results
- THEN its full properties are returned

#### Scenario: Unauthorized entity — ID-only redaction
- GIVEN a node or edge the user does NOT have `view` permission on
- WHEN the entity appears in query results
- THEN only the entity ID is returned (e.g., `documentation_module:abf3ad8`)
- AND all other properties are stripped
- AND the entity is NOT removed from the result set (graph topology is preserved)

#### Scenario: Permission derivation for graph entities
- GIVEN a node or edge with a `knowledge_graph_id` property
- THEN `view` permission is derived from the user's access to that KnowledgeGraph
- AND KnowledgeGraph access is in turn derivable from workspace membership

#### Scenario: Missing or unresolvable knowledge_graph_id
- GIVEN a node or edge whose `knowledge_graph_id` property is missing, null, malformed, or cannot be resolved to a valid KnowledgeGraph
- THEN `view` permission MUST be denied (the entity is treated as redacted)
- AND this applies regardless of any other permissions the user may hold

### Requirement: Single-Role Enforcement
The system SHALL ensure each user or group holds exactly one role per resource.

#### Scenario: Role replacement
- GIVEN a user with the `member` role on a workspace
- WHEN the user is granted the `editor` role
- THEN the `member` role is removed
- AND the `editor` role is granted
- AND the user does NOT hold both roles simultaneously

### Requirement: Information Hiding on Authorization Failure
The system SHALL not reveal whether a resource exists when access is denied.

#### Scenario: Unauthorized access
- GIVEN a user without permission to view a resource
- WHEN the user requests the resource
- THEN a not-found response is returned (not forbidden)
- AND the response is indistinguishable from a genuinely missing resource

### Requirement: Group Permissions
The system SHALL enforce the following permission model for groups.

#### Scenario: Admin permissions
- GIVEN a user with the `admin` role on a group
- THEN the user has `view` and `manage` permissions

#### Scenario: Member permissions
- GIVEN a user with the `member` role on a group
- THEN the user has `view` permission only

#### Scenario: Tenant member visibility
- GIVEN a user who is a member of the tenant
- THEN the user has `view` permission on all groups in that tenant
