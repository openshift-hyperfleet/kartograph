# Data Sources

## Purpose
A data source represents a connection to an external system (e.g., GitHub) from which graph data is extracted. Data sources belong to a knowledge graph and carry adapter-specific configuration, encrypted credentials, and a sync schedule.

## Requirements

### Requirement: Data Source Creation
The system SHALL allow users with `edit` permission on a knowledge graph to create data sources.

#### Scenario: Successful creation
- GIVEN a user with `edit` permission on a knowledge graph
- WHEN the user creates a data source with a name, adapter type, and connection config
- THEN the data source is created with a generated ULID identifier
- AND it is associated with the specified knowledge graph and tenant
- AND the schedule defaults to MANUAL

#### Scenario: Creation with credentials
- GIVEN a data source creation request that includes raw credentials
- WHEN the data source is created
- THEN the credentials are encrypted and stored at the path `datasource/{id}/credentials`
- AND the data source stores a reference to the credentials path (not the credentials themselves)

#### Scenario: Duplicate name within knowledge graph
- GIVEN a data source named "GitHub Repos" already exists in the knowledge graph
- WHEN a user attempts to create another with the same name
- THEN the request is rejected with a duplicate name error

### Requirement: Data Source Name Validation
The system SHALL enforce constraints on data source names.

#### Scenario: Valid name
- GIVEN a name between 1 and 100 characters
- WHEN used to create or update a data source
- THEN the name is accepted

#### Scenario: Empty or oversized name
- GIVEN a name that is empty or exceeds 100 characters
- WHEN used to create or update a data source
- THEN the request is rejected with a validation error

### Requirement: Schedule Configuration
The system SHALL support three schedule types for data source synchronization.

#### Scenario: Manual schedule
- GIVEN a schedule type of MANUAL
- WHEN the data source is configured
- THEN no automatic synchronization occurs
- AND no schedule value is required

#### Scenario: Cron schedule
- GIVEN a schedule type of CRON with a cron expression value
- WHEN the data source is configured
- THEN the schedule is stored with the cron expression

#### Scenario: Interval schedule
- GIVEN a schedule type of INTERVAL with an ISO 8601 duration value
- WHEN the data source is configured
- THEN the schedule is stored with the interval value

#### Scenario: Missing schedule value
- GIVEN a CRON or INTERVAL schedule without a value
- WHEN the data source is configured
- THEN the request is rejected with a validation error

### Requirement: Data Source Retrieval
The system SHALL return data source details only to users with `view` permission.

#### Scenario: Authorized retrieval
- GIVEN a data source the user has `view` permission on
- WHEN the user requests it by ID
- THEN the data source details are returned (without raw credentials)

#### Scenario: Unauthorized or non-existent
- GIVEN a data source the user cannot view (or does not exist)
- WHEN the user requests it by ID
- THEN no result is returned

### Requirement: Data Source Update
The system SHALL allow users with `edit` permission to update data source connection configuration.

#### Scenario: Update connection config
- GIVEN a user with `edit` permission on a data source
- WHEN the user updates the name, connection config, or credentials path
- THEN the data source is updated

### Requirement: Data Source Deletion
The system SHALL allow users with `manage` permission to delete a data source.

#### Scenario: Successful deletion
- GIVEN a user with `manage` permission on a data source
- WHEN the user deletes the data source
- THEN the encrypted credentials are deleted first
- AND the data source is deleted
- AND authorization relationships are cleaned up

### Requirement: Sync Triggering
The system SHALL allow users with `manage` permission to trigger a data source sync.

#### Scenario: Trigger sync
- GIVEN a user with `manage` permission on a data source
- WHEN the user triggers a sync
- THEN a sync run record is created with status "pending"
- AND a sync-requested event is emitted

### Requirement: Sync Run Tracking
The system SHALL track the execution status of each sync operation.

#### Scenario: Sync lifecycle
- GIVEN a triggered sync
- THEN the sync run tracks: status (pending/running/completed/failed), started_at, completed_at, and error message if failed

#### Scenario: Cascade deletion
- GIVEN a data source with sync run records
- WHEN the data source is deleted
- THEN all associated sync runs are cascade-deleted

### Requirement: Permission Inheritance
Data source permissions SHALL be fully inherited from the parent knowledge graph.

#### Scenario: Inherited access
- GIVEN a user with `edit` permission on a knowledge graph
- THEN the user also has `edit` permission on all data sources in that knowledge graph
