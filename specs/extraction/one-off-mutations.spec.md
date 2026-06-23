# One-off Mutations (Graph Management)

## Purpose
One-off Mutations is a Graph Management Assistant UI mode for direct schema and instance edits. The operator describes a change; the assistant validates and applies it via mutation tools. Sessions archive to Graph Writes History with token cost and applied JSONL.

## Requirements

### Requirement: One-off Mutations Skill Pack
The system SHALL resolve a dedicated skill pack when graph-management UI mode is `one-off-mutations`.

#### Scenario: Skills include edit workflows
- GIVEN UI mode `one-off-mutations`
- WHEN skills are resolved for a chat turn
- THEN instance and schema edit workflow skills are primary
- AND confirmation policy for destructive operations is included

### Requirement: Assistant Executes Edits In Session
The system SHALL implement requested schema and instance changes via Kartograph schema tools without deferring to extraction job workers.

#### Scenario: Instance property update
- GIVEN an operator asks to update a property on an existing instance
- WHEN the assistant completes the turn
- THEN it validates and applies UPDATE JSONL mutations
- AND reports write operation counts

#### Scenario: Bulk instance cleanup
- GIVEN an operator asks to delete many instances and keep or create a specific set
- WHEN the assistant completes the turn
- THEN it lists instances by type (not per-slug search loops)
- AND generates JSONL in batch to a workspace file or script
- AND validates once and applies once via file-based mutation tools

#### Scenario: Schema type change
- GIVEN an operator asks to add an optional property to an entity type
- WHEN the assistant completes the turn
- THEN it saves ontology via `kartograph_save_schema_ontology` after confirmation when required

### Requirement: JobPackage Not Required
The system SHALL NOT block one-off mutations chat on JobPackage ingestion readiness.

#### Scenario: Chat without prepared sources
- GIVEN no JobPackages are prepared
- WHEN the operator uses one-off mutations mode
- THEN the chat turn proceeds without awaiting ingestion

### Requirement: GMA Session Archive
The system SHALL archive each Graph Management Assistant session to Graph Writes History when chat is cleared.

#### Scenario: Archive with writes and cost
- GIVEN a GMA session applied mutations and consumed tokens
- WHEN the operator clears chat
- THEN one ARCHIVED entry is persisted
- AND job set name reflects the UI mode (Initial Schema Design, Extraction Jobs, or One-off Mutations)

#### Scenario: Token-only session
- GIVEN a GMA session consumed tokens but applied no graph writes
- WHEN chat is cleared
- THEN an ARCHIVED entry is still persisted with cost metrics

### Requirement: Graph Writes History Presentation
The system SHALL present archived GMA sessions and extraction worker jobs in a unified Graph Writes History view.

#### Scenario: Job list shows cost
- GIVEN an archived job or GMA session with cost metadata
- WHEN the operator views Graph Writes History
- THEN each entry shows write count and total cost in USD
- AND GMA sessions are distinguishable from extraction worker jobs
