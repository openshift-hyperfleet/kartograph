# SpiceDB Authorization

## Purpose
The authorization provider is the shared interface for permission checks and relationship management across all bounded contexts. It abstracts SpiceDB operations behind a protocol, enabling permission checks, relationship writes, resource lookups, and relationship reads.

## Requirements

### Requirement: Permission Checking
The system SHALL evaluate whether a subject has a specific permission on a resource.

#### Scenario: Permission granted
- GIVEN a user with a relationship that grants `view` permission on a workspace
- WHEN a permission check is performed
- THEN the check returns true

#### Scenario: Permission denied
- GIVEN a user with no relationships granting `manage` permission on a workspace
- WHEN a permission check is performed
- THEN the check returns false

#### Scenario: Computed permission via inheritance
- GIVEN a user who is a member of a group assigned to a workspace
- WHEN a permission check for `edit` is performed on the workspace
- THEN the permission is computed through the group relationship chain

### Requirement: Bulk Permission Checking
The system SHALL support checking permissions across multiple resources in a single operation.

#### Scenario: Filter accessible resources
- GIVEN a list of resource IDs and a permission to check
- WHEN a bulk check is performed
- THEN only the resource IDs the user has permission on are returned

### Requirement: Relationship Writes
The system SHALL create explicit relationships between subjects and resources.

#### Scenario: Single relationship
- GIVEN a user and a workspace
- WHEN a relationship write creates `workspace#admin@user:alice`
- THEN future permission checks reflect the new relationship

#### Scenario: Bulk relationships
- GIVEN multiple relationships to write
- WHEN a bulk write is performed
- THEN all relationships are created atomically

### Requirement: Relationship Deletion
The system SHALL delete explicit relationships between subjects and resources.

#### Scenario: Single deletion
- GIVEN an existing relationship `workspace#admin@user:alice`
- WHEN the relationship is deleted
- THEN future permission checks no longer include it

#### Scenario: Filter-based deletion
- GIVEN a resource with multiple relationships
- WHEN relationships are deleted by filter (e.g., all relationships for a specific resource)
- THEN all matching relationships are removed
- AND at least one filter criterion beyond resource type is required

### Requirement: Resource Lookup
The system SHALL find all resources a subject has a specific permission on.

#### Scenario: Lookup accessible workspaces
- GIVEN a user with `view` permission on workspaces A and B
- WHEN a resource lookup is performed for `view` permission
- THEN workspace IDs A and B are returned

### Requirement: Relationship Reading
The system SHALL read explicit (non-computed) relationship tuples.

#### Scenario: Read explicit tuples
- GIVEN a workspace with explicit admin and editor relationships
- WHEN relationships are read for the workspace
- THEN only the directly-written tuples are returned
- AND computed permissions are NOT included

### Requirement: Subject Relations for Groups
The system SHALL use subject relations when writing group-based workspace grants.

#### Scenario: Group workspace assignment
- GIVEN a group being assigned the `editor` role on a workspace
- WHEN the relationship is written
- THEN it uses the form `workspace#editor@group:grp123#member`
- AND the `#member` subject relation ensures all group members inherit the permission
