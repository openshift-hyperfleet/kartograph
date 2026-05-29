# Operations

## Purpose
Extraction operations define the mode-specific behaviors for schema bootstrap, extraction job setup, and minor direct edits. All write behavior is expressed as MutationLogs associated with a knowledge graph and session.

## Requirements

### Requirement: Mode-Specific Skill Sets
The system SHALL provide different default skill sets for bootstrap and extraction operations modes.

#### Scenario: Bootstrap skills
- GIVEN a knowledge graph in `schema_bootstrap`
- WHEN an extraction agent session starts
- THEN the default skill set is schema-bootstrap oriented
- AND it prioritizes complete entity/relationship modeling and prepopulated instance coverage

#### Scenario: Extraction skills
- GIVEN a knowledge graph in `extraction_operations`
- WHEN an extraction agent session starts
- THEN the default skill set is extraction-job-setup and minor-direct-edit oriented
- AND schema edit skills remain available but are not the primary framing

### Requirement: Graph Management UI Mode Overlays
The system SHALL apply graph-management UI mode overlays on top of workspace session mode skills.

#### Scenario: Initial schema design overlay
- GIVEN graph-management UI mode `Initial Schema Design`
- WHEN a chat turn resolves skills
- THEN schema bootstrap and validation guidance is primary

#### Scenario: Extraction jobs overlay
- GIVEN graph-management UI mode `Extraction Jobs`
- WHEN a chat turn resolves skills
- THEN extraction job setup and sync-run guidance is primary
- AND JobPackage readiness is required before agent execution

#### Scenario: One-off mutations overlay
- GIVEN graph-management UI mode `One-off Mutations`
- WHEN a chat turn resolves skills
- THEN scoped JSONL mutation authoring guidance is primary

### Requirement: Skill Resolution Model
The system SHALL resolve agent skills using global templates with knowledge-graph overrides.

#### Scenario: Global template with override
- GIVEN a knowledge graph with custom skill overrides
- WHEN an extraction session resolves skill instructions
- THEN global skill templates are loaded first
- AND knowledge-graph overrides are applied on top

### Requirement: Unified Extraction and Manual Edit Surface
The system SHALL provide one operational area for extraction jobs and minor direct graph edits.

#### Scenario: Unified write path
- GIVEN a user in extraction operations mode
- WHEN the user runs extraction jobs or performs minor direct edits
- THEN both behaviors emit MutationLogs
- AND both target the same knowledge graph

### Requirement: Validate-Then-Transition Workflow
The system SHALL gate transition from bootstrap mode through explicit validation and user action.

#### Scenario: Validation gate
- GIVEN a knowledge graph in `schema_bootstrap`
- WHEN the user clicks Validate
- THEN validation results are returned and persisted
- AND transition remains unavailable until checks pass

#### Scenario: Explicit transition action
- GIVEN validation has passed in `schema_bootstrap`
- WHEN the user clicks "Go to Extraction/Mutations"
- THEN the knowledge graph transitions to `extraction_operations`
- AND a new extraction-mode agent session is started

### Requirement: MutationLog Session Association
The system SHALL associate MutationLogs with both knowledge graph and session/run identity.

#### Scenario: Session-linked mutation runs
- GIVEN a session producing mutation operations
- WHEN MutationLogs are persisted
- THEN each log run stores session ID, knowledge graph ID, actor identity, and timestamps

#### Scenario: Per-run operation metrics
- GIVEN a persisted mutation log run
- WHEN metrics are recorded
- THEN operation counts are captured by operation class (for example create/update for entity and relationship instances)
- AND token usage and cost metrics are captured for the run

