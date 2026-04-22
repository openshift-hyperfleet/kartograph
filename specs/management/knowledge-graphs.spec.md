# Knowledge Graphs

## Purpose
A knowledge graph is the central organizational unit in the Management context. It belongs to a workspace within a tenant and serves as the container for data sources that feed graph data.

## Requirements

### Requirement: Knowledge Graph Creation
The system SHALL allow users with `edit` permission on a workspace to create knowledge graphs within it.

#### Scenario: Successful creation
- GIVEN a user with `edit` permission on a workspace
- WHEN the user creates a knowledge graph with a name and description
- THEN the knowledge graph is created with a generated ULID identifier
- AND it is associated with the specified workspace and tenant
- AND authorization relationships are established (workspace and tenant links)

#### Scenario: Duplicate name within tenant
- GIVEN a knowledge graph named "Platform Graph" already exists in the tenant
- WHEN a user attempts to create another with the same name
- THEN the request is rejected with a duplicate name error

### Requirement: Knowledge Graph Name Validation
The system SHALL enforce constraints on knowledge graph names.

#### Scenario: Valid name
- GIVEN a name between 1 and 100 characters
- WHEN used to create or update a knowledge graph
- THEN the name is accepted

#### Scenario: Empty or oversized name
- GIVEN a name that is empty or exceeds 100 characters
- WHEN used to create or update a knowledge graph
- THEN the request is rejected with a validation error

### Requirement: Knowledge Graph Retrieval
The system SHALL return knowledge graph details only to users with `view` permission.

#### Scenario: Authorized retrieval
- GIVEN a knowledge graph the user has `view` permission on
- WHEN the user requests it by ID
- THEN the knowledge graph details are returned

#### Scenario: Unauthorized or non-existent
- GIVEN a knowledge graph the user cannot view (or does not exist)
- WHEN the user requests it by ID
- THEN no result is returned (no distinction between unauthorized and missing)

### Requirement: Knowledge Graph Listing
The system SHALL list knowledge graphs within a workspace, filtered by authorization.

#### Scenario: List for workspace
- GIVEN a user with `view` permission on a workspace containing knowledge graphs
- WHEN the user lists knowledge graphs for that workspace
- THEN only knowledge graphs the user can view are returned

### Requirement: Knowledge Graph Update
The system SHALL allow users with `edit` permission to update knowledge graph metadata.

#### Scenario: Update name and description
- GIVEN a user with `edit` permission on a knowledge graph
- WHEN the user updates the name and description
- THEN the metadata is updated

### Requirement: Knowledge Graph Deletion
The system SHALL allow users with `manage` permission to delete a knowledge graph, cascading to data sources.

#### Scenario: Successful deletion
- GIVEN a user with `manage` permission on a knowledge graph
- WHEN the user deletes the knowledge graph
- THEN all data sources within it are deleted first (including their credentials)
- AND the knowledge graph is deleted
- AND all authorization relationships are cleaned up (workspace, tenant, and all direct grants)

#### Scenario: Mutation after deletion
- GIVEN a knowledge graph that has been marked for deletion
- WHEN any mutation is attempted
- THEN the operation is rejected

### Requirement: Permission Inheritance
Knowledge graph permissions SHALL be inheritable from the parent workspace.

#### Scenario: Workspace-inherited access
- GIVEN a user with `edit` permission on a workspace
- THEN the user also has `edit` permission on all knowledge graphs in that workspace

#### Scenario: Direct grant
- GIVEN a user with a direct `admin` grant on a knowledge graph
- THEN the user has `manage`, `edit`, and `view` permissions regardless of workspace role
