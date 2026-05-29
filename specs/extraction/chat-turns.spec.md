# Chat Turns

## Purpose
Graph Management chat turns orchestrate conversational extraction agent workloads inside sticky session containers. Each turn persists user and assistant messages, streams transparent activity to the UI, and gates execution until ingestion context (JobPackage) is available when required by the active graph-management mode.

## Requirements

### Requirement: Sticky Session Container Execution
The system SHALL execute graph-management chat turns in a sticky session container assigned to the active extraction agent session.

#### Scenario: Reuse sticky runtime across turns
- GIVEN an active extraction agent session with a running sticky container
- WHEN the user sends a follow-up chat message
- THEN the same sticky container lease is reused until clear-chat, timeout, or reset

#### Scenario: Start sticky runtime on first turn
- GIVEN an active session without a sticky container lease
- WHEN the user sends the first chat message
- THEN the system starts a sticky session container for that session scope
- AND records container identity in session runtime context

### Requirement: JobPackage Context in Sticky Runtime
The system SHALL load ingestion context from JobPackage archives into the sticky session container when JobPackage access is required.

#### Scenario: JobPackage required for extraction jobs mode
- GIVEN graph-management UI mode `Extraction Jobs`
- AND at least one data source exists for the knowledge graph
- WHEN JobPackage context is not yet prepared for all tracked sources
- THEN the chat turn enters a wait state instead of invoking the agent
- AND the UI receives wait-phase activity explaining that ingestion context is pending

#### Scenario: JobPackage ready
- GIVEN graph-management UI mode `Extraction Jobs`
- AND prepared ingestion context exists for the knowledge graph
- WHEN the user sends a chat message
- THEN JobPackage material is available to the sticky container agent runtime
- AND the agent turn proceeds normally

#### Scenario: Schema design without JobPackage gate
- GIVEN graph-management UI mode `Initial Schema Design`
- WHEN the user sends a chat message
- THEN JobPackage readiness is not required to start the agent turn
- AND schema-bootstrap skills remain primary framing

### Requirement: Mode-Aware Skill Framing
The system SHALL resolve agent skills using workspace session mode and graph-management UI mode.

#### Scenario: Three UI mode skill overlays
- GIVEN graph-management UI modes `Initial Schema Design`, `Extraction Jobs`, and `One-off Mutations`
- WHEN a chat turn starts
- THEN skill framing reflects the selected UI mode
- AND global templates plus knowledge-graph overrides still apply underneath

### Requirement: Streaming Chat Turn Contract
The system SHALL expose chat turns over an NDJSON streaming HTTP endpoint.

#### Scenario: Thinking transparency
- GIVEN an in-progress chat turn
- WHEN the agent performs preparatory work
- THEN the stream emits `thinking` events with recent activity lines for UI display

#### Scenario: Wait transparency
- GIVEN JobPackage context is required but unavailable
- WHEN the user sends a chat message
- THEN the stream emits a `wait` event with phase `awaiting_job_package`
- AND completes with an assistant explanation of the wait condition

#### Scenario: Successful completion
- GIVEN an agent turn completes successfully
- WHEN the stream finishes
- THEN a terminal `done` event includes the assistant reply
- AND user and assistant messages are persisted on the session

### Requirement: Clear Chat Resets Runtime
The system SHALL reset sticky session runtime when clear-chat is invoked.

#### Scenario: Clear chat terminates sticky container
- GIVEN an active session with sticky runtime state
- WHEN the user clicks Clear chat
- THEN the sticky container is reset
- AND a new clean session is started for the same scope
