# Workload Execution

NFR: This spec describes execution, isolation, and credential-injection constraints for agent workloads.

## Purpose
Kartograph executes extraction agent workloads in containers with a hybrid model: sticky conversational containers per session and ephemeral worker containers for extraction execution. Runtime credentials are injected securely and scoped with least privilege.

## Requirements

### Requirement: Container-Only Agent Runtime
The system SHALL run extraction agents in containers for both local development and deployed environments.

#### Scenario: Local development execution
- GIVEN local development workflows
- WHEN extraction agents are started
- THEN they run inside local containers rather than host-native processes

#### Scenario: Deployed execution
- GIVEN a deployed environment
- WHEN extraction workloads are started
- THEN they run in pod containers managed by the platform

### Requirement: Hybrid Container Model
The system SHALL use sticky containers for chat sessions and ephemeral containers for extraction execution workers.

#### Scenario: Sticky session container
- GIVEN a user starts an extraction chat session
- WHEN the session remains active
- THEN the session reuses the same container context until clear/reset or timeout

#### Scenario: Ephemeral execution workers
- GIVEN extraction jobs are launched
- WHEN worker tasks execute
- THEN they run in ephemeral worker containers
- AND worker containers are terminated after job completion or failure

### Requirement: Runtime Credential Injection
The system SHALL provide runtime credentials to agent containers through secure injection.

#### Scenario: Workload authentication material
- GIVEN a workload container requires access to platform services
- WHEN the workload starts
- THEN short-lived authentication credentials are injected at runtime
- AND credentials are not hardcoded in repository files, container images, or mutation logs

#### Scenario: Least-privilege scope
- GIVEN an extraction workload for a knowledge graph
- WHEN credentials are issued
- THEN permissions are limited to required tenant and knowledge-graph scope operations

### Requirement: Skill and Context Availability
The system SHALL provide required runtime context in workload containers.

#### Scenario: Built-in context
- GIVEN an extraction workload container
- WHEN the workload initializes
- THEN ingestion context resources and repository files needed for processing are available
- AND the skills directory is available to the agent runtime

#### Scenario: Sticky session Claude agent runtime
- GIVEN a sticky session container for graph-management chat
- WHEN the container starts
- THEN it hosts a Claude Agent SDK agent instance isolated from the API process
- AND JobPackage material may be mounted when ingestion context is required for the active graph-management mode

### Requirement: Graph Management UI Mode Skills
The system SHALL expose graph-management UI mode skill overlays in addition to workspace session mode skills.

#### Scenario: UI mode overlays
- GIVEN graph-management modes `Initial Schema Design`, `Extraction Jobs`, and `One-off Mutations`
- WHEN skill instructions are resolved for a chat turn
- THEN UI mode overlays adjust assistant framing while preserving workspace session mode guardrails

