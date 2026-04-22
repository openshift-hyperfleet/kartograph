# Sync Lifecycle

## Purpose
A sync run progresses through a defined set of states, driven by domain events flowing through the outbox. Lightweight handlers update status and trigger downstream work. Heavy work (extraction, mutation application) runs asynchronously and reports outcomes as new events, forming an event-driven state machine.

## Requirements

### Requirement: Sync Orchestration
The system SHALL orchestrate the ingestion pipeline as: extract → package → publish event.

#### Scenario: Successful sync
- GIVEN a sync is triggered for a data source
- WHEN the ingestion service runs
- THEN the adapter extracts raw data from the source
- AND the packager assembles a JobPackage from the extracted data
- AND a `JobPackageProduced` event is published via the outbox

#### Scenario: Extraction failure
- GIVEN a sync is triggered but the adapter fails (e.g., credentials expired, source unreachable)
- WHEN the failure occurs
- THEN an `IngestionFailed` event is published
- AND the sync run status is set to `failed` with an error message

### Requirement: Lifecycle State Machine
The system SHALL track sync runs through a defined set of states, driven by domain events.

#### Scenario: State transitions
- GIVEN the following lifecycle events and their effects:
  - `SyncStarted` → status becomes `ingesting`
  - `JobPackageProduced` → status becomes `extracting` (AI extraction triggered)
  - `IngestionFailed` → status becomes `failed`
  - `MutationLogProduced` → status becomes `applying` (graph mutations triggered)
  - `ExtractionFailed` → status becomes `failed`
  - `MutationsApplied` → status becomes `completed`, `last_sync_at` updated
  - `MutationApplicationFailed` → status becomes `failed`
- THEN each event transitions the sync run to the corresponding status

#### Scenario: Terminal states
- GIVEN a sync run in `completed` or `failed` status
- THEN no further state transitions occur for that run

### Requirement: Event-Driven Side Effects
The system SHALL trigger downstream work via outbox event handlers.

#### Scenario: Extraction trigger
- GIVEN a `JobPackageProduced` event is processed
- THEN an extraction job record is created
- AND the Extraction context is signaled to process the JobPackage

#### Scenario: Mutation trigger
- GIVEN a `MutationLogProduced` event is processed
- THEN a mutation job record is created
- AND the Graph context is signaled to apply the mutation log

#### Scenario: Status updates
- GIVEN any lifecycle event is processed
- THEN the corresponding sync run record is updated with the new status

### Requirement: Sync Initiation
The system SHALL support both manual and scheduled sync triggers.

#### Scenario: Manual trigger
- GIVEN a user with `manage` permission on a data source
- WHEN the user triggers a sync via the API
- THEN a `SyncStarted` event is published
- AND a sync run record is created with status `pending`

#### Scenario: Scheduled trigger
- GIVEN a data source with a CRON or INTERVAL schedule
- WHEN the schedule fires
- THEN a sync is initiated as if manually triggered

### Requirement: Staleness-Based Node Lifecycle
The system SHALL use timestamp comparison to detect stale graph nodes instead of explicit delete events.

#### Scenario: Stale node detection
- GIVEN a node with `last_synced_at` older than its data source's `last_sync_at`
- THEN the node is considered stale
- AND downstream processes MAY remove or flag it

#### Scenario: Active node
- GIVEN a node whose `last_synced_at` matches or exceeds the data source's `last_sync_at`
- THEN the node is considered current
