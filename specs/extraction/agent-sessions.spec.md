# Agent Sessions

## Purpose
Agent sessions provide long-running conversational extraction workflows scoped to user, knowledge graph, and mode. Sessions remain active until explicitly cleared, while preserving auditable run history and metrics.

## Requirements

### Requirement: Session Scope
The system SHALL scope extraction agent sessions per user, knowledge graph, and mode.

#### Scenario: Scope isolation
- GIVEN two users working on the same knowledge graph
- WHEN they open extraction agent sessions
- THEN each user receives a separate session
- AND session state is not shared across users

#### Scenario: Mode isolation
- GIVEN a user session in bootstrap mode and a session in extraction mode
- WHEN both sessions exist for the same knowledge graph
- THEN each session keeps separate context and runtime state

### Requirement: Long-Running Session Lifecycle
The system SHALL keep sessions active until explicit reset.

#### Scenario: Persistent session context
- GIVEN an active extraction agent session
- WHEN the user sends follow-up messages over time
- THEN prior session context remains available for continued conversation

#### Scenario: Chat turn persistence
- GIVEN a completed graph-management chat turn
- WHEN the assistant reply is emitted
- THEN user and assistant messages are persisted on the session
- AND sticky runtime metadata is updated on the session runtime context

### Requirement: Sticky Runtime Association
The system SHALL associate active sessions with sticky container runtime leases.

#### Scenario: Runtime metadata on session
- GIVEN a chat turn starts a or reuses a sticky container
- WHEN the turn is accepted
- THEN session runtime context records sticky container identity and status

### Requirement: Clear Chat Reset
The system SHALL provide an explicit "Clear chat" action that resets runtime context.

#### Scenario: Full reset on clear
- GIVEN an active session with runtime context
- WHEN the user clicks "Clear chat"
- THEN message history and runtime context are reset
- AND a new clean session is started for that user/knowledge-graph/mode scope

### Requirement: Session Archival and Retention
The system SHALL retain completed session and run records indefinitely.

#### Scenario: Historical session visibility
- GIVEN prior sessions and mutation runs
- WHEN users or administrators query session history
- THEN archived sessions and associated run records remain available
- AND each record includes last-updated timestamps and run-level metrics

