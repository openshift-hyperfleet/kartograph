# Knowledge Graph Workspace

## Purpose
A knowledge graph workspace provides a mode-aware control surface for progressing from initial schema bootstrap to ongoing extraction and mutation operations. It exposes lifecycle state, readiness checks, and navigation contracts consumed by the UI and extraction agents.

## Requirements

### Requirement: Workspace Mode Lifecycle
The system SHALL track each knowledge graph in one of two modes: `schema_bootstrap` and `extraction_operations`.

#### Scenario: Default mode on creation
- GIVEN a newly created knowledge graph
- WHEN the knowledge graph record is persisted
- THEN its workspace mode is `schema_bootstrap`

#### Scenario: Irreversible transition
- GIVEN a knowledge graph in `schema_bootstrap`
- WHEN the user completes validation and transitions to extraction operations
- THEN the mode changes to `extraction_operations`
- AND the mode cannot be changed back to `schema_bootstrap`

### Requirement: Workspace Status Projection
The system SHALL expose a knowledge-graph workspace status projection for UI rendering.

#### Scenario: Status includes mode and readiness
- GIVEN a knowledge graph workspace request
- WHEN the status projection is returned
- THEN it includes current mode, validation readiness flags, and a transition eligibility flag

#### Scenario: Status includes session pointers
- GIVEN one or more extraction agent sessions associated with the knowledge graph
- WHEN the status projection is returned
- THEN it includes pointers to the current active session per mode and the most recent completed session

### Requirement: Bootstrap Readiness Validation
The system SHALL define schema bootstrap readiness checks for transition eligibility.

#### Scenario: Minimum schema readiness
- GIVEN a knowledge graph in `schema_bootstrap`
- WHEN readiness is evaluated
- THEN validation fails unless there is at least one entity type and at least one relationship type

#### Scenario: Prepopulated instance readiness
- GIVEN one or more entity or relationship types marked `prepopulated=true`
- WHEN readiness is evaluated
- THEN validation fails if any such type has zero instances

#### Scenario: Prepopulated relationship endpoint constraint
- GIVEN a relationship type marked `prepopulated=true`
- WHEN the ontology is saved
- THEN every listed source and target entity type must also be marked `prepopulated=true`

### Requirement: Transition Authorization
The system SHALL require `edit` permission on the knowledge graph for bootstrap validation and mode transition.

#### Scenario: Authorized validate and transition
- GIVEN a user with `edit` permission on the knowledge graph
- WHEN the user invokes validate and transition actions
- THEN both actions are permitted

#### Scenario: Unauthorized validate and transition
- GIVEN a user without `edit` permission on the knowledge graph
- WHEN the user invokes validate or transition actions
- THEN the action is rejected with a forbidden error

